#!/usr/bin/env python3
"""Compile README examples and check their generated equation previews."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = re.compile(
    r"(?:^<!-- readme-example: ([a-z][a-z0-9-]*) -->\n)?"
    r"^```typst\n(.*?)^```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
IMPORTS = re.compile(r'"@(preview|local)/symbolica:([^"\s]+)"')
PREAMBLE = """#set page(width: auto, height: auto, margin: 10pt, fill: white)
#set text(font: "New Computer Modern", size: 11pt, fill: black)
"""


def check_examples(package_root: Path, update: bool, readme_path: Path | None = None):
    package = tomllib.loads((package_root / "typst.toml").read_text())["package"]
    readme_path = readme_path or package_root / "README.md"
    readme = readme_path.read_text()
    # Only the repository guide documents a local development installation.
    namespace = "local" if readme_path == ROOT / "README.md" else "preview"
    examples = list(EXAMPLES.finditer(readme))
    if not examples:
        raise ValueError("README has no Typst examples")
    marked = re.findall(r"^<!-- readme-example: (.*?) -->$", readme, re.MULTILINE)
    names = [match[1] for match in examples if match[1]]
    if marked != names or len(names) != len(set(names)):
        raise ValueError("Each preview marker must have a unique name and immediately precede a Typst code block")

    stale = []
    with tempfile.TemporaryDirectory(prefix="symbolica-readme-") as temporary:
        work = Path(temporary)
        packages = work / "packages"
        link = packages / namespace / package["name"] / package["version"]
        link.parent.mkdir(parents=True)
        link.symlink_to(package_root, target_is_directory=True)

        for index, match in enumerate(examples, 1):
            name, code = match[1], match[2]
            imports = IMPORTS.findall(code)
            if not imports or any(import_namespace != namespace or version != package["version"]
                                  for import_namespace, version in imports):
                raise ValueError(f"README example {index} must import @{namespace}/symbolica:{package['version']}")
            source = work / f"example-{index}.typ"
            output = source.with_suffix(".svg" if name else ".pdf")
            source.write_text(PREAMBLE + code)
            subprocess.run(
                ["typst", "compile", "--creation-timestamp", "0", "--package-path", str(packages),
                 "--root", str(work), str(source), str(output)], check=True,
            )
            if name:
                relative = Path("symbolica/readme") / f"{name}.svg"
                if f"]({relative.as_posix()})" not in readme:
                    raise ValueError(f"README example {name} has no link to its preview")
                expected = package_root / relative
                if update:
                    destination = ROOT / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(output.read_bytes())
                elif not expected.is_file() or output.read_bytes() != expected.read_bytes():
                    stale.append(str(relative))
            print(f"Compiled README example {index}" + (f" ({name})" if name else ""))
    if stale:
        raise ValueError("Stale README previews: " + ", ".join(stale)
                         + "; run python3 scripts/readme-examples.py --readme README-universe.md --update")
    print(f"Checked {len(examples)} README examples and {len(names)} previews")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=ROOT,
                        help="Package whose README, manifest, and Wasm to test")
    parser.add_argument("--readme", type=Path,
                        help="README to test instead of PACKAGE_ROOT/README.md")
    parser.add_argument("--update", action="store_true",
                        help="Regenerate previews in the repository's symbolica/readme directory")
    args = parser.parse_args()
    check_examples(args.package_root.resolve(), args.update,
                   args.readme.resolve() if args.readme else None)


if __name__ == "__main__":
    main()
