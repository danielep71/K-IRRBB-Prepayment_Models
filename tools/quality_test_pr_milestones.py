"""Exercise the inline reconciler of pr-milestones.yml offline against a fake API."""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def reconciler():
    workflow = yaml.safe_load((ROOT / '.github/workflows/pr-milestones.yml').read_text(encoding='utf-8'))
    steps = workflow['jobs']['reconcile']['steps']
    step = next(step for step in steps if step.get('name') == 'Reconcile PR metadata')
    code = step['run'].split("python - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    namespace = {'__name__': 'pr_milestones'}
    exec(compile(code, 'pr-milestones.yml', 'exec'), namespace)
    return namespace['reconcile']


class FakeApi:
    def __init__(self, items, keep_milestone=()):
        self.items = {item['number']: item for item in items}
        self.keep = set(keep_milestone)
        self.patched = []

    def __call__(self, method, path, data=None):
        if path.startswith('/repos/o/r/pulls?'):
            page = int(path.rsplit('page=', 1)[1])
            pulls = [item for item in self.items.values() if 'pull_request' in item]
            return pulls[(page - 1) * 100:page * 100]
        number = int(path.rsplit('/', 1)[1])
        if method == 'PATCH':
            self.patched.append((number, data))
            if number not in self.keep:
                self.items[number]['milestone'] = None
        return dict(self.items[number])


class PrMilestoneTests(unittest.TestCase):
    def test_event_clears_the_milestone_of_that_pull_request(self) -> None:
        api = FakeApi([{'number': 5, 'pull_request': {}, 'milestone': {'number': 2}}])
        reconciler()(api, 'o/r', {'pull_request': {}, 'number': 5})
        self.assertEqual(api.patched, [(5, {'milestone': None})])

    def test_an_issue_is_never_changed(self) -> None:
        api = FakeApi([{'number': 7, 'milestone': {'number': 2}}])
        with self.assertRaises(ValueError):
            reconciler()(api, 'o/r', {'pull_request': {}, 'number': 7})
        self.assertEqual(api.patched, [])

    def test_scan_clears_only_milestoned_pull_requests_across_pages(self) -> None:
        items = [{'number': n, 'pull_request': {}, 'milestone': {'number': 2} if n in (3, 150) else None}
                 for n in range(1, 201)]
        api = FakeApi(items)
        reconciler()(api, 'o/r', {})
        self.assertEqual([number for number, _ in api.patched], [3, 150])

    def test_a_milestone_that_stays_is_an_error(self) -> None:
        api = FakeApi([{'number': 5, 'pull_request': {}, 'milestone': {'number': 2}}], keep_milestone=[5])
        with self.assertRaises(ValueError):
            reconciler()(api, 'o/r', {'pull_request': {}, 'number': 5})

    def test_the_job_installs_python_and_never_checks_out_code(self) -> None:
        workflow = yaml.safe_load((ROOT / '.github/workflows/pr-milestones.yml').read_text(encoding='utf-8'))
        actions = [str(step.get('uses', '')).split('@')[0] for step in workflow['jobs']['reconcile']['steps']]
        self.assertEqual(actions, ['actions/setup-python', ''])


if __name__ == '__main__':
    unittest.main()
