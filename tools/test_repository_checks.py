"""Negative fixtures for the repository integrity boundary."""
import tempfile
import unittest
from pathlib import Path

from check import REQUIRED, inspect


class IntegrityTests(unittest.TestCase):
    def test_missing_required_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(inspect(Path(tmp), []))

    def test_broken_link_unpinned_action_and_binary_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {name: '# Fixture\n' for name in REQUIRED}
            files.update({'README.md': '[Missing](absent.md)\n',
                          '.github/workflows/bad.yml': 'steps:\n  - uses: actions/checkout@main\n',
                          'private.xlsm': ''})
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
            errors = inspect(root, list(files))
            for expected in ('missing/unsafe link', 'unpinned action', 'Unapproved binary'):
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_branding_exception_rejects_changed_or_unlisted_binary(self):
        from check import APPROVED_IMAGES
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = next(iter(APPROVED_IMAGES))
            path = root / name
            path.parent.mkdir(parents=True)
            path.write_bytes(b'\x89PNG\r\n\x1a\nchanged')
            (root / 'unapproved.png').write_bytes(path.read_bytes())
            errors = inspect(root, [name, 'unapproved.png'])
            self.assertTrue(any('Unreviewed image content' in e for e in errors))
            self.assertTrue(any('Non-UTF-8 source: unapproved.png' in e for e in errors))

    def test_valid_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in REQUIRED:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}\n' if path.suffix == '.json' else '# Fixture\n', encoding='utf-8')
            self.assertEqual(inspect(root, list(REQUIRED)), [])


class SourceTests(unittest.TestCase):
    def test_bad_names_and_missing_provenance(self):
        from check_source import inspect_source
        with tempfile.TemporaryDirectory() as tmp:
            errors = inspect_source(Path(tmp), ['A.md', 'a.md', 'bad name.md', 'CON.txt'])
            for expected in ('collision', 'Non-portable', 'Invalid provenance'):
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_untracked_link_target_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('[Local only](not-committed.md)\n')
            (root / 'not-committed.md').write_text('Exists locally\n')
            self.assertTrue(any('missing/unsafe link' in e for e in inspect(root, ['README.md'])))

    def test_invalid_reference_revision(self):
        import json

        from check_source import inspect_source
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'docs').mkdir()
            register = {'schema_version': 1, 'sources': [{'repository': 'https://github.com/owner/repo',
                        'reference_revision': 'main', 'treatment': 'adapted', 'files': ['README.md']}]}
            (root / 'docs/provenance.json').write_text(json.dumps(register))
            self.assertTrue(any('full commit SHA' in e for e in inspect_source(root, ['README.md'])))
