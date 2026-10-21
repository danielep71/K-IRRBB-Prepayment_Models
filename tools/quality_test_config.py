"""Negative fixtures for GitHub configuration validation."""
import json
import tempfile
import unittest
from pathlib import Path

from check_config import inspect_config


class ConfigTests(unittest.TestCase):
    def test_invalid_defaults_duplicate_keys_and_yaml(self):
        cases = [
            ('name: one\nname: two\n', 'duplicate YAML key'),
            ('name: [\n', ''),
            ('labels: [unknown]\n', 'unknown or missing issue labels'),
            ('labels: [P2, P3]\n', 'one priority required'),
            ('labels: [P2]\nassignees: []\n', 'owner assignee required'),
        ]
        for content, expected in cases:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                forms = root / '.github/ISSUE_TEMPLATE'
                forms.mkdir(parents=True)
                (root / '.github/labels.json').write_text(json.dumps({'core': [{'name': 'P2'}, {'name': 'P3'}]}))
                (forms / 'bug.yml').write_text(content)
                errors = inspect_config(root)
                self.assertTrue(errors)
                self.assertIn(expected, errors[0])

    def test_quoted_action_tag_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / '.github/workflows'
            workflows.mkdir(parents=True)
            (root / '.github/labels.json').write_text('{"core": []}')
            (workflows / 'bad.yml').write_text('jobs:\n  job:\n    steps:\n      - uses: "actions/checkout@main"\n')
            self.assertTrue(any('unpinned action' in error for error in inspect_config(root)))

    def test_dependabot_must_target_release_branch(self):
        for target in ('main', 'release/next', None):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / '.github').mkdir()
                (root / '.github/labels.json').write_text('{"core": []}')
                update = {'package-ecosystem': 'github-actions', 'directory': '/'}
                if target:
                    update['target-branch'] = target
                (root / '.github/dependabot.yml').write_text(json.dumps({'version': 2, 'updates': [update]}))
                self.assertTrue(any('active release branch' in error for error in inspect_config(root)))
