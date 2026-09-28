import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

SPEC = importlib.util.spec_from_file_location("release", Path(__file__).parents[1] / "release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "typst.toml").write_text('[package]\nname = "symbolica"\nversion = "0.2.0"\n')
        (self.root / "README.md").write_text('#import "@preview/symbolica:0.2.0": *\n')
        (self.root / "README-universe.md").write_text('#import "@preview/symbolica:0.2.0": *\n')
        (self.root / "symbolica/examples").mkdir(parents=True)
        (self.root / "symbolica/examples/basic.typ").write_text('#import "@preview/symbolica:0.2.0": *\n')
        self.revision = patch.object(release.subprocess, "check_output", return_value="a" * 40 + "\n")
        self.revision.start()
        self.addCleanup(self.revision.stop)

    def test_dry_run_does_not_require_unpublished_version(self):
        with patch.object(release, "check_unpublished") as registry:
            metadata = release.preflight(self.root)
        registry.assert_not_called()
        self.assertEqual(metadata["package-id"], "symbolica-0.2.0")

    def test_tag_must_match_manifest_before_registry_access(self):
        with patch.object(release, "check_unpublished") as registry:
            with self.assertRaisesRegex(ValueError, "does not match"):
                release.preflight(self.root, "v0.1.0")
        registry.assert_not_called()

    def test_tagged_release_checks_registry(self):
        with patch.object(release, "check_unpublished") as registry:
            release.preflight(self.root, "v0.2.0")
        registry.assert_called_once_with("symbolica", "0.2.0")

    def test_old_readme_and_example_imports_are_reported(self):
        (self.root / "README.md").write_text('#import "@preview/symbolica:0.1.0": *\n')
        (self.root / "README-universe.md").write_text('#import "@preview/symbolica:0.1.0": *\n')
        (self.root / "symbolica/examples/basic.typ").write_text('#import "@local/symbolica:0.1.0": *\n')
        with self.assertRaises(ValueError) as error:
            release.preflight(self.root)
        self.assertIn("README.md:1", str(error.exception))
        self.assertIn("README-universe.md:1", str(error.exception))
        self.assertIn("symbolica/examples/basic.typ:1", str(error.exception))

    def test_existing_registry_package_is_rejected(self):
        with patch.object(release, "urlopen"):
            with self.assertRaisesRegex(ValueError, "already published"):
                release.check_unpublished("symbolica", "0.1.0")

    def test_old_local_installation_path_is_rejected(self):
        readme = self.root / "README.md"
        readme.write_text(readme.read_text() + 'ln -s "$PWD" "packages/local/symbolica/0.1.0"\n')
        with self.assertRaisesRegex(ValueError, "packages/local/symbolica/0.1.0"):
            release.preflight(self.root)
        readme.write_text(readme.read_text().replace("packages/local/symbolica/0.1.0",
                                                   "packages/local/symbolica/0.2.0"))
        release.preflight(self.root)

    def test_absent_registry_package_is_allowed(self):
        with patch.object(release, "urlopen", side_effect=HTTPError("url", 404, "missing", {}, None)):
            release.check_unpublished("symbolica", "0.2.0")

    def test_registry_failures_do_not_authorize_publication(self):
        for error in (HTTPError("url", 403, "denied", {}, None), URLError("offline"), TimeoutError()):
            with self.subTest(error=error):
                with patch.object(release, "urlopen", side_effect=error):
                    with self.assertRaisesRegex(ValueError, "Cannot check"):
                        release.check_unpublished("symbolica", "0.2.0")

    def test_checksums_require_all_archives(self):
        (self.root / "dist").mkdir()
        with self.assertRaisesRegex(ValueError, "Missing release artifact"):
            release.checksums(self.root)


if __name__ == "__main__":
    unittest.main()
