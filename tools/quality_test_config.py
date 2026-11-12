"""Negative fixtures for GitHub configuration validation."""
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml
from check_config import (
    REQUIRED_FORM_FIELDS,
    dependabot_targets,
    inspect_config,
    logical_lines,
    runtime_errors,
    unrequired_fields,
)

SETUP_PYTHON: dict[str, Any] = {'uses': 'actions/setup-python@' + '0' * 40, 'with': {'python-version': '3.13.18'}}
SETUP_NODE: dict[str, Any] = {'uses': 'actions/setup-node@' + '0' * 40, 'with': {'node-version': '22.23.5'}}


class ConfigTests(unittest.TestCase):
    def test_invalid_defaults_duplicate_keys_and_yaml(self):
        cases = [
            ('name: one\nname: two\n', 'duplicate YAML key'),
            ('name: [\n', ''),
            ('labels: [unknown]\n', 'unknown or missing issue labels'),
            ('labels: [P2, P3]\n', 'one priority required'),
            ('labels: [P2]\nassignees: []\n', 'owner assignee required'),
            ('labels: [P2]\nassignees: [danielep71]\nbody: []\n', 'issue form must require: commit'),
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

    def test_issue_forms_must_require_their_fields(self):
        forms = Path(__file__).resolve().parents[1] / '.github/ISSUE_TEMPLATE'
        body: list[dict[str, Any]] = [{'type': 'input', 'id': 'commit', 'validations': {'required': True}},
                {'type': 'textarea', 'id': 'environment', 'validations': {'required': False}},
                {'type': 'textarea', 'id': 'acceptance'}]
        missing = unrequired_fields('bug.yml', body)
        self.assertIn('environment', missing)
        self.assertIn('acceptance', missing)
        self.assertNotIn('commit', missing)
        self.assertEqual(unrequired_fields('config.yml', body), [])
        for form in REQUIRED_FORM_FIELDS:
            with self.subTest(form=form):
                data = yaml.safe_load((forms / form).read_text(encoding='utf-8'))
                self.assertEqual(unrequired_fields(form, data['body']), [])

    def test_runtimes_must_be_installed_at_an_exact_version_first(self) -> None:
        self.assertEqual(runtime_errors([SETUP_PYTHON, SETUP_NODE,
                                         {'run': 'python tools/check.py && node x.mjs'}]), [])
        self.assertEqual(runtime_errors([{'run': 'echo "python 3"'}]), [])
        cases: list[tuple[list[dict[str, Any]], str]] = [
            ([{'run': 'python3 script.py'}], 'python3 runs before actions/setup-python'),
            ([{'run': "python - <<'PY'\nPY"}], 'python runs before actions/setup-python'),
            ([{'run': 'set -e\nnode a.mjs'}, SETUP_NODE], 'node runs before actions/setup-node'),
            ([SETUP_PYTHON, {'run': 'cd x && node a.mjs'}], 'node runs before actions/setup-node'),
            ([{'uses': SETUP_NODE['uses'], 'with': {'node-version': '22.x'}}],
             "needs an exact node-version, not '22.x'"),
            ([{'uses': SETUP_PYTHON['uses']}], "needs an exact python-version, not ''")]
        for steps, expected in cases:
            with self.subTest(steps=steps):
                errors = runtime_errors(steps)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_quoted_action_tag_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / '.github/workflows'
            workflows.mkdir(parents=True)
            (root / '.github/labels.json').write_text('{"core": []}')
            (workflows / 'bad.yml').write_text('jobs:\n  job:\n    steps:\n      - uses: "actions/checkout@main"\n')
            self.assertTrue(any('unpinned action' in error for error in inspect_config(root)))

    def test_dependabot_must_target_release_branch(self):
        for target in ('main', 'release/next', 'release/0.2', None):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / '.github').mkdir()
                (root / '.github/labels.json').write_text('{"core": []}')
                update = {'package-ecosystem': 'github-actions', 'directory': '/'}
                if target:
                    update['target-branch'] = target
                (root / '.github/dependabot.yml').write_text(json.dumps({'version': 2, 'updates': [update]}))
                self.assertTrue(any('active release branch' in error for error in inspect_config(root)))

    def test_requirements_need_pins_and_hashes(self):
        digest = '0' * 64
        cases = [
            ('mypy==1.0\n', 'mypy'),
            ('mypy>=1.0 --hash=sha256:' + digest + '\n', 'mypy>=1.0'),
            ('mypy==1.0 \\\n    --hash=sha256:short\n', 'mypy==1.0'),
        ]
        for content, name in cases:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / '.github').mkdir()
                (root / '.github/labels.json').write_text('{"core": []}')
                (root / 'tools').mkdir()
                (root / 'tools/requirements-x.txt').write_text('# comment\n' + content)
                errors = inspect_config(root)
                self.assertTrue(any('without an exact pin and hash' in e and name in e for e in errors), errors)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.github').mkdir()
            (root / '.github/labels.json').write_text('{"core": []}')
            (root / 'tools').mkdir()
            (root / 'tools/requirements-x.txt').write_text('mypy==1.0 \\\n    --hash=sha256:' + digest + '\n')
            self.assertEqual(inspect_config(root), [])

    def test_pip_install_needs_hash_and_binary_flags(self):
        for command in ('python -m pip install -r tools/r.txt',
                        'python -m pip install --require-hashes -r tools/r.txt',
                        'python -m pip install --only-binary=:all: \\\n  -r tools/r.txt'):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                workflows = root / '.github/workflows'
                workflows.mkdir(parents=True)
                (root / '.github/labels.json').write_text('{"core": []}')
                step = json.dumps({'jobs': {'job': {'steps': [{'run': command}]}}})
                (workflows / 'w.yml').write_text(step)
                self.assertTrue(any('pip install without' in e for e in inspect_config(root)))
        self.assertEqual(logical_lines('a \\\n  b # note\n\n# c\n'), ['a b'])

    def test_dependabot_must_update_pip_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.github').mkdir()
            (root / '.github/labels.json').write_text('{"core": []}')
            update = {'package-ecosystem': 'github-actions', 'directory': '/', 'target-branch': 'release/0.2.0'}
            (root / '.github/dependabot.yml').write_text(json.dumps({'version': 2, 'updates': [update]}))
            self.assertTrue(any('pip requirements in /tools' in e for e in inspect_config(root)))

    def test_dependabot_entries_share_one_release_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.github').mkdir()
            (root / '.github/labels.json').write_text('{"core": []}')
            updates = [{'package-ecosystem': 'github-actions', 'directory': '/', 'target-branch': 'release/0.2.0'},
                       {'package-ecosystem': 'pip', 'directory': '/tools', 'target-branch': 'release/0.3.0'}]
            (root / '.github/dependabot.yml').write_text(json.dumps({'version': 2, 'updates': updates}))
            self.assertTrue(any('same active release branch' in e for e in inspect_config(root)))

    def test_dependabot_targets_are_parsed_as_yaml(self):
        # Quoting and trailing comments are YAML, not part of the branch name (review of #127).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.github').mkdir()
            (root / '.github/dependabot.yml').write_text(
                "version: 2\nupdates:\n"
                "  - package-ecosystem: pip\n    target-branch: 'release/0.2.0'\n"
                "  - package-ecosystem: npm\n    target-branch: release/9.9.9 # next milestone\n"
                "  - package-ecosystem: docker\n    target-branch: \"release/0.2.0\"\n")
            self.assertEqual(dependabot_targets(root), ['release/0.2.0', 'release/9.9.9'])
