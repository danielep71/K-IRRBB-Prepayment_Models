"""Negative fixtures for the repository integrity boundary."""
from pathlib import Path
import tempfile
import unittest
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

    def test_valid_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in REQUIRED:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('# Fixture\n', encoding='utf-8')
            self.assertEqual(inspect(root, list(REQUIRED)), [])
