#!/usr/bin/env python3
"""Validate release metadata and collect the already-built release artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")


def package_metadata(root):
    package = tomllib.loads((root / "typst.toml").read_text())["package"]
    name, version = package["name"], package["version"]
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or not VERSION.fullmatch(version):
        raise ValueError("Expected a package name and a numeric major.minor.patch version")
    return name, version


def check_imports(root, name, version):
    """Check runnable documentation, excluding historical changelog entries."""
    pattern = re.compile(
        r"(?:@(?:preview|local)/" + re.escape(name) + r":"
        r"|(?:packages/)?(?:preview|local)/" + re.escape(name) + r"/)"
        r"(?P<version>[0-9][0-9A-Za-z.+-]*)")
    paths = [root / "README.md", root / "README-universe.md",
             *sorted((root / "symbolica").rglob("*.typ"))]
    errors = []
    for path in paths:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            for match in pattern.finditer(line):
                if match["version"] != version:
                    errors.append(f"{path.relative_to(root)}:{number}: {match[0]} (expected {version})")
    if errors:
        raise ValueError("Outdated package imports or installation paths:\n" + "\n".join(errors))


def check_unpublished(name, version):
    url = f"https://raw.githubusercontent.com/typst/packages/main/packages/preview/{name}/{version}/typst.toml"
    request = Request(url, headers={"User-Agent": "symbolica-release-check"})
    try:
        with urlopen(request, timeout=30):
            pass
    except HTTPError as error:
        error.close()
        if error.code == 404:
            return
        raise ValueError(f"Cannot check the package registry: HTTP {error.code}") from error
    except (URLError, TimeoutError) as error:
        raise ValueError(f"Cannot check the package registry: {error}") from error
    raise ValueError(f"{name}:{version} is already published; choose a new version")


def preflight(root, tag=None):
    name, version = package_metadata(root)
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"Release tag {tag!r} does not match typst.toml version {version}")
    check_imports(root, name, version)
    if tag is not None:
        check_unpublished(name, version)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected a complete Git source revision")
    return {"name": name, "version": version, "package-id": f"{name}-{version}",
            "source-revision": revision}


def checksums(root):
    name, version = package_metadata(root)
    package_id = f"{name}-{version}"
    dist = root / "dist"
    archives = [dist / f"{package_id}{suffix}.tar.gz" for suffix in ("", "-universe", "-source")]
    for path in archives:
        if not path.is_file():
            raise ValueError(f"Missing release artifact: {path}")
    manual = dist / f"{package_id}-manual.pdf"
    shutil.copyfile(root / "symbolica/manual.pdf", manual)
    lines = []
    for path in [*archives, manual]:
        with path.open("rb") as file:
            digest = hashlib.file_digest(file, "sha256").hexdigest()
        lines.append(f"{digest}  {path.name}\n")
    (dist / "SHA256SUMS").write_text("".join(lines))
    print("".join(lines), end="")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("preflight")
    check.add_argument("--tag", help="A publishing tag; omitted for an artifact-only dry run")
    check.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"), type=Path)
    commands.add_parser("checksums")
    args = parser.parse_args()
    try:
        if args.command == "checksums":
            checksums(args.root)
        else:
            metadata = preflight(args.root, args.tag)
            if args.github_output:
                with args.github_output.open("a") as file:
                    file.writelines(f"{key}={value}\n" for key, value in metadata.items())
            print(json.dumps(metadata, indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Release check failed: {error}\n")


if __name__ == "__main__":
    main()
