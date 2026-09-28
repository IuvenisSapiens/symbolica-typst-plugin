"""Exercise the two archives and the actual README selected for publication."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'prepare-distribution.py'
SPEC = importlib.util.spec_from_file_location('distribution', SCRIPT)
distribution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(distribution)


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in (*distribution.RUNTIME, *distribution.DOCUMENTATION,
                     'Cargo.lock', 'flake.lock', 'symbolica/readme/example.svg'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name + '\n')
        (self.root / 'typst.toml').write_text('''[package]
name = "symbolica"
version = "9.2.1"
repository = "https://github.com/symbolica-dev/symbolica-typst-plugin"
''')
        (self.root / 'README.md').write_text('Repository-only build instructions\n')
        (self.root / 'README-universe.md').write_text('''# Symbolica

## Example

![Computed output](symbolica/readme/example.svg)
[Manual](symbolica/manual.pdf), [example](#example).
''')

    def prepare(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return distribution.prepare(self.root, **kwargs)

    def test_submission_has_docs_but_download_contains_only_runtime(self):
        stage = self.prepare(release=True, source_revision='a' * 40)
        self.assertEqual((stage / 'README.md').read_bytes(),
                         (self.root / 'README-universe.md').read_bytes())
        runtime = self.root / 'dist/symbolica-9.2.1.tar.gz'
        with tarfile.open(runtime) as archive:
            self.assertEqual(set(archive.getnames()), set(distribution.RUNTIME) | {'SOURCE.json'})
            self.assertIn(b'Computed output', archive.extractfile('README.md').read())
            provenance = json.load(archive.extractfile('SOURCE.json'))
            self.assertEqual(provenance['revision'], 'a' * 40)
            self.assertEqual(provenance['sha256']['symbolica/symbolica.wasm'],
                             hashlib.sha256((self.root / 'symbolica/symbolica.wasm').read_bytes()).hexdigest())
        with tarfile.open(self.root / 'dist/symbolica-9.2.1-universe.tar.gz') as archive:
            names = archive.getnames()
            prefix = 'packages/preview/symbolica/9.2.1/'
            self.assertTrue(all(name.startswith(prefix) for name in names))
            self.assertIn(prefix + 'symbolica/manual.pdf', names)
            self.assertIn(prefix + 'symbolica/readme/example.svg', names)
            self.assertNotIn(prefix + 'README-universe.md', names)
        original = runtime.read_bytes()
        self.prepare(release=True, source_revision='a' * 40)
        self.assertEqual(runtime.read_bytes(), original)

    def test_missing_readme_resource_fails_before_replacing_stage(self):
        stage = self.prepare()
        expected = (stage / 'README.md').read_bytes()
        (self.root / 'README-universe.md').write_text('[Missing](not-staged.pdf)')
        with self.assertRaisesRegex(ValueError, 'absent from the submission'):
            self.prepare()
        self.assertEqual((stage / 'README.md').read_bytes(), expected)

    def test_raw_math_and_dangling_anchor_are_rejected(self):
        for source in ('$$ x^2 $$', '[Gone](#development)'):
            (self.root / 'README-universe.md').write_text(source)
            with self.assertRaises(ValueError):
                self.prepare()

    def test_release_requires_exact_source_revision(self):
        for revision in (None, 'main', 'abc123', '../unexpected'):
            with self.assertRaisesRegex(ValueError, 'full Git commit'):
                self.prepare(release=True, source_revision=revision)


if __name__ == '__main__':
    unittest.main()
