"""Controls of the traffic workflow: credentials, job permissions and schedule."""
import unittest
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow() -> dict[Any, Any]:
    text = (ROOT / '.github/workflows/daily-traffic.yml').read_text(encoding='utf-8')
    document: dict[Any, Any] = yaml.safe_load(text)
    document['text'] = text
    return document


class TrafficWorkflowTests(unittest.TestCase):
    def test_collection_and_alerting_are_separate_jobs(self) -> None:
        jobs = workflow()['jobs']
        self.assertEqual(jobs['collect']['permissions'], {'contents': 'write'})
        self.assertEqual(jobs['collect']['environment']['name'], 'analytics')
        self.assertEqual(jobs['alert']['permissions'], {'contents': 'read', 'issues': 'write'})
        self.assertNotIn('environment', jobs['alert'])
        self.assertEqual(jobs['alert']['needs'], 'collect')
        self.assertNotIn('secrets.', yaml.safe_dump(jobs['alert']))

    def test_the_token_comes_from_the_traffic_app(self) -> None:
        document = workflow()
        self.assertNotIn('TRAFFIC_TOKEN', document['text'])
        steps = document['jobs']['collect']['steps']
        token = next(step for step in steps if step.get('id') == 'app-token')
        self.assertTrue(token['uses'].startswith('actions/create-github-app-token@'))
        self.assertEqual(token['with']['permission-administration'], 'read')
        # Only the token step reads the key, and only the fetch step the token.
        self.assertEqual([step.get('name') for step in steps if 'TRAFFIC_APP_PRIVATE_KEY' in yaml.safe_dump(step)],
                         ['Check the traffic App configuration', 'Create the traffic App token'])
        self.assertEqual([step.get('name') for step in steps if 'steps.app-token' in yaml.safe_dump(step)],
                         ['Fetch GitHub traffic API data'])

    def test_schedule_is_off_the_hour(self) -> None:
        document = workflow()
        # PyYAML reads the key `on` as True.
        triggers = document['on'] if 'on' in document else document[True]
        for entry in triggers['schedule']:
            self.assertNotEqual(entry['cron'].split()[0], '0', entry['cron'])

    def test_the_python_lives_in_the_tested_module(self) -> None:
        self.assertNotIn("<< 'PY'", workflow()['text'])
        self.assertIn('tools/traffic_history.py merge', workflow()['text'])
        self.assertIn('tools/traffic_history.py alert', workflow()['text'])


if __name__ == '__main__':
    unittest.main()
