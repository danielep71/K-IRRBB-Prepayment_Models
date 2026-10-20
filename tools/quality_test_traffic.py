"""Exercise the actual embedded exporter offline with synthetic API responses."""
import csv
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]


class TrafficTests(unittest.TestCase):
    def test_rerun_replaces_snapshot_and_preserves_history(self) -> None:
        workflow = yaml.safe_load((ROOT / '.github/workflows/daily-traffic.yml').read_text())
        job = workflow['jobs']['traffic']
        step = next(s for s in job['steps'] if s['name'] == 'Build CSV history')
        code = step['run'].split("python3 << 'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        today = datetime.now(timezone.utc).date().isoformat()
        older = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, data in {
                'views': {'count': 20, 'uniques': 3, 'views': [
                    {'timestamp': today + 'T00:00:00Z', 'count': 20, 'uniques': 3}]},
                'clones': {'count': 5, 'uniques': 2, 'clones': [
                    {'timestamp': today + 'T00:00:00Z', 'count': 5, 'uniques': 2}]},
                'referrers': [{'referrer': 'example.test', 'count': 6, 'uniques': 2}],
                'paths': [{'path': '/example', 'title': 'Synthetic', 'count': 9, 'uniques': 2}],
                'repo': {'stargazers_count': 0, 'open_issues_count': 6},
            }.items():
                (root / (name + '.json')).write_text(json.dumps(data))
                code = code.replace('/tmp/' + name + '.json', str(root / (name + '.json')))
            (root / 'data').mkdir()
            (root / 'data/traffic_daily.csv').write_text(
                'date,views,unique_views,clones,unique_clones\n' + older + ',10,2,7,3\n')
            previous = Path.cwd()
            try:
                os.chdir(root)
                exec(compile(code, 'traffic-export', 'exec'), {})
                (root / 'referrers.json').write_text('[]')
                (root / 'paths.json').write_text('[]')
                exec(compile(code, 'traffic-export', 'exec'), {})
                def rows(name: str) -> list[dict[str, str]]:
                    with (root / ('data/' + name + '.csv')).open(newline='') as stream:
                        return list(csv.DictReader(stream))
                self.assertEqual(len(rows('traffic')), 1)
                self.assertEqual(len(rows('traffic_daily')), 2)
                self.assertEqual(rows('referrers'), [])
                self.assertEqual(rows('popular_paths'), [])
                for name, expected in [('clones', '12'), ('visits', '5'), ('visitors', '3')]:
                    self.assertEqual(json.loads((root / f'data/badges/{name}.json').read_text())['message'], expected)
            finally:
                os.chdir(previous)

    def test_milestone_checked_before_first_snapshot_exit(self) -> None:
        workflow = yaml.safe_load((ROOT / '.github/workflows/daily-traffic.yml').read_text())
        step = next(s for s in workflow['jobs']['traffic']['steps'] if s['name'].startswith('Create alert'))
        code = step['run'].split("python3 << 'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        with patch.dict(os.environ, {'ISSUE_MILESTONE_NUMBER': '1', 'GITHUB_REPOSITORY': 'synthetic/test'}):
            with patch('subprocess.run') as run:
                run.return_value.stdout = '{"state":"closed","title":"Closed milestone"}'
                with self.assertRaisesRegex(RuntimeError, 'must be open'):
                    exec(compile(code, 'traffic-alert', 'exec'), {})
                self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
