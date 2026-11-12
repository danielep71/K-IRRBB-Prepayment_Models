"""Check the controls of the label workflows: only main reconciles, and pruning is guarded."""
import re
import unittest
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRANCH = "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"


def workflow(name: str) -> dict[Any, Any]:
    data: dict[Any, Any] = yaml.safe_load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'))
    return data


def reconcile_guard(data: dict[Any, Any]) -> str:
    return ' '.join(str(data['jobs']['reconcile']['if']).split())


class LabelWorkflowTests(unittest.TestCase):
    def test_only_the_default_branch_reconciles(self) -> None:
        data = workflow('labels-sync.yml')
        guard = reconcile_guard(data)
        self.assertIn("github.event_name != 'pull_request'", guard)
        self.assertIn(DEFAULT_BRANCH, guard)
        self.assertIn('workflow_dispatch', data[True])  # 'on' parses as True
        # pull-requests: read lets the in-use check before pruning see labels on pull requests.
        self.assertEqual(data['jobs']['reconcile']['permissions'],
                         {'contents': 'read', 'issues': 'write', 'pull-requests': 'read'})
        self.assertEqual(data['jobs']['validate']['permissions'], {'contents': 'read'})

    def test_a_missing_guard_is_detected(self) -> None:
        data = workflow('labels-sync.yml')
        data['jobs']['reconcile']['if'] = "github.event_name != 'pull_request'"
        self.assertNotIn(DEFAULT_BRANCH, reconcile_guard(data))

    def test_both_workflows_rerun_when_the_shared_helper_changes(self) -> None:
        for name in ('labels-sync.yml', 'labels-drift.yml'):
            with self.subTest(workflow=name):
                for event in ('pull_request', 'push'):
                    paths = workflow(name)[True].get(event, {}) or {}
                    if 'paths' in paths:
                        self.assertIn('.github/scripts/markdown.mjs', paths['paths'])

    def test_pruning_is_checked_before_any_change_is_applied(self) -> None:
        source = (ROOT / '.github/scripts/labels-sync.mjs').read_text(encoding='utf-8')
        main = source[source.index('async function main()'):]
        usage = re.search(r'await deletionsInUse\(', main)
        refusal = re.search(r'throw new Error\(deletionRefusal\(usage\)\)', main)
        apply = re.search(r'await applyChanges\(', main)
        assert usage is not None and refusal is not None and apply is not None
        dry_run = main.index('options.dryRun')
        # Label use is read before the dry run returns, so its summary can report it;
        # a real run refuses before the first change.
        self.assertLess(usage.start(), dry_run)
        self.assertLess(dry_run, refusal.start())
        self.assertLess(refusal.start(), apply.start())


if __name__ == '__main__':
    unittest.main()
