"""Offline tests of tools/traffic_history.py with synthetic API responses."""
import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import traffic_history as traffic  # noqa: E402

NOW = datetime(2026, 11, 2, 6, 23, 5, tzinfo=timezone.utc)


def responses(raw: Path, views=(('2026-11-01', 20, 3), ('2026-11-02', 4, 2)),
              clones=(('2026-11-02', 5, 2),), referrers=(('example.test', 6, 2),),
              repository=None) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    series = {'views': views, 'clones': clones}
    for key, days in series.items():
        items = [{'timestamp': day + 'T00:00:00Z', 'count': c, 'uniques': u} for day, c, u in days]
        (raw / f'{key}.json').write_text(json.dumps({
            'count': sum(c for _, c, _ in days), 'uniques': max([u for _, _, u in days], default=0), key: items}))
    (raw / 'referrers.json').write_text(json.dumps(
        [{'referrer': r, 'count': c, 'uniques': u} for r, c, u in referrers]))
    (raw / 'paths.json').write_text(json.dumps([{'path': '/x', 'title': 'X', 'count': 9, 'uniques': 2}]))
    (raw / 'repo.json').write_text(json.dumps(repository or {
        'stargazers_count': 0, 'forks_count': 0, 'subscribers_count': 1, 'open_issues_count': 6}))


def rows(data: Path, name: str) -> list[dict[str, str]]:
    with (data / name).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def badge(data: Path, name: str) -> str:
    message: str = json.loads((data / f'badges/{name}.json').read_text())['message']
    return message


class MergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw, self.data = self.root / 'raw', self.root / 'data'

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_first_merge_writes_history_and_badges(self) -> None:
        responses(self.raw)
        changed = traffic.merge(self.raw, self.data, NOW)
        self.assertIn('traffic.csv', changed)
        self.assertEqual([r['date'] for r in rows(self.data, 'traffic_daily.csv')], ['2026-11-01', '2026-11-02'])
        snapshot = rows(self.data, 'traffic.csv')[0]
        self.assertEqual((snapshot['snapshot_date'], snapshot['snapshot_datetime_utc'], snapshot['views_14d']),
                         ('2026-11-02', '2026-11-02T06:23:05+00:00', '24'))
        self.assertEqual((badge(self.data, 'clones'), badge(self.data, 'visits'), badge(self.data, 'visitors')),
                         ('5', '5', '3'))
        self.assertTrue((self.data / 'traffic.csv').read_bytes().endswith(b'\r\n'))

    def test_same_day_replay_replaces_that_day_only(self) -> None:
        responses(self.raw)
        traffic.merge(self.raw, self.data, NOW)
        self.assertEqual(traffic.merge(self.raw, self.data, NOW), [])  # identical replay changes nothing
        responses(self.raw, views=(('2026-11-02', 7, 3),), referrers=())
        traffic.merge(self.raw, self.data, NOW.replace(hour=18))
        snapshots = rows(self.data, 'traffic.csv')
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]['snapshot_datetime_utc'], '2026-11-02T18:23:05+00:00')
        self.assertEqual(rows(self.data, 'referrers.csv'), [])
        daily = {r['date']: r for r in rows(self.data, 'traffic_daily.csv')}
        self.assertEqual((daily['2026-11-02']['views'], daily['2026-11-01']['views']), ('7', '20'))

    def test_dates_no_longer_reported_keep_their_values(self) -> None:
        self.data.mkdir()
        (self.data / 'traffic_daily.csv').write_text(
            'date,views,unique_views,clones,unique_clones\r\n2026-10-01,10,2,7,3\r\n', newline='')
        (self.data / 'traffic.csv').write_text(  # an older layout, converted on read
            'date,views,unique_views,clones,unique_clones,stars,forks,watchers,open_issues\r\n'
            '2026-10-01T06:00:00+00:00,1,1,0,0,0,0,0,4\r\n', newline='')
        responses(self.raw)
        traffic.merge(self.raw, self.data, NOW)
        daily = {r['date']: r for r in rows(self.data, 'traffic_daily.csv')}
        self.assertEqual(daily['2026-10-01'], {'date': '2026-10-01', 'views': '10', 'unique_views': '2',
                                               'clones': '7', 'unique_clones': '3'})
        self.assertEqual([r['snapshot_date'] for r in rows(self.data, 'traffic.csv')], ['2026-10-01', '2026-11-02'])
        self.assertEqual(rows(self.data, 'traffic.csv')[0]['open_issues_and_prs'], '4')
        self.assertEqual(badge(self.data, 'clones'), '12')

    def test_invalid_input_leaves_the_history_unchanged(self) -> None:
        responses(self.raw)
        traffic.merge(self.raw, self.data, NOW)
        before = {p.name: p.read_bytes() for p in self.data.rglob('*') if p.is_file()}
        for name, content in (('views.json', '{"count": -1, "uniques": 0, "views": []}'),
                              ('clones.json', 'not json'),
                              ('referrers.json', '{"referrer": "x"}'),
                              ('repo.json', '{"stargazers_count": "1"}')):
            with self.subTest(name=name):
                responses(self.raw)
                (self.raw / name).write_text(content)
                with self.assertRaises(traffic.TrafficError):
                    traffic.merge(self.raw, self.data, NOW.replace(day=3))
                self.assertEqual({p.name: p.read_bytes() for p in self.data.rglob('*') if p.is_file()}, before)
        (self.raw / 'paths.json').unlink()
        with self.assertRaisesRegex(traffic.TrafficError, 'response missing'):
            traffic.merge(self.raw, self.data, NOW)

    def test_a_malformed_history_file_is_refused(self) -> None:
        self.data.mkdir()
        (self.data / 'referrers.csv').write_text('snapshot_date,rank,referrer,count,uniques\r\nnot-a-date,1,x,1,1\r\n')
        responses(self.raw)
        with self.assertRaisesRegex(traffic.TrafficError, 'invalid snapshot_date'):
            traffic.merge(self.raw, self.data, NOW)
        self.assertFalse((self.data / 'traffic.csv').exists())

    def test_badge_numbers(self) -> None:
        self.assertEqual([traffic.compact(n) for n in (950, 1000, 1234, 11000, 3_400_000)],
                         ['950', '1k', '1.2k', '11k', '3.4M'])


class AlertTests(unittest.TestCase):
    def history(self, root: Path, previous: dict[str, str], current: dict[str, str], referrers=()) -> Path:
        data = root / 'data'
        data.mkdir()
        base = {'views_14d': '10', 'unique_views_14d': '2', 'clones_14d': '10', 'unique_clones_14d': '2',
                'stars': '0', 'forks': '0', 'watchers': '0', 'open_issues_and_prs': '1'}
        lines = [','.join(traffic.HEADERS['traffic.csv'])]
        for day, values in (('2026-11-01', previous), ('2026-11-02', current)):
            row = {**base, **values, 'snapshot_date': day, 'snapshot_datetime_utc': day + 'T06:00:00+00:00'}
            lines.append(','.join(row[key] for key in traffic.HEADERS['traffic.csv']))
        (data / 'traffic.csv').write_text('\r\n'.join(lines) + '\r\n', newline='')
        ref = ['snapshot_date,rank,referrer,count,uniques'] + [','.join(r) for r in referrers]
        (data / 'referrers.csv').write_text('\r\n'.join(ref) + '\r\n', newline='')
        return data

    def alert(self, *args, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            return traffic.alert(self.history(Path(tmp), *args, **kwargs))

    def test_quiet_traffic_raises_nothing(self) -> None:
        self.assertIsNone(self.alert({}, {}))
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            self.assertIsNone(traffic.alert(data))

    def test_views_spike_raises_an_alert(self) -> None:
        issue = self.alert({'views_14d': '10'}, {'views_14d': '110'})
        self.assertEqual(issue['title'], 'Traffic alert: 2026-11-02')
        self.assertIn('Views spike', issue['body'])
        self.assertIsNone(self.alert({'views_14d': '10'}, {'views_14d': '109'}))  # +100 needed

    def test_clones_are_never_a_spike_reason_but_stay_in_the_table(self) -> None:
        self.assertIsNone(self.alert({'clones_14d': '10'}, {'clones_14d': '5000'}))
        issue = self.alert({'stars': '0', 'clones_14d': '10'}, {'stars': '1', 'clones_14d': '5000'})
        self.assertIn('Stars increased', issue['body'])
        self.assertNotIn('Clones spike', issue['body'])
        self.assertIn('- Clones: 5000 vs 10 on 2026-11-01', issue['body'])

    def test_forks_and_new_referrers(self) -> None:
        self.assertIn('Forks increased', self.alert({'forks': '1'}, {'forks': '2'})['body'])
        seen = [('2026-11-01', '1', 'known.example', '9', '2'), ('2026-11-02', '1', 'known.example', '9', '2')]
        self.assertIsNone(self.alert({}, {}, seen))
        issue = self.alert({}, {}, [*seen, ('2026-11-02', '2', 'new.example', '5', '1')])
        self.assertIn('New referrer detected', issue['body'])
        self.assertIn('- new.example: 5 views, 1 unique', issue['body'])
        self.assertIsNone(self.alert({}, {}, [('2026-11-02', '1', 'small.example', '4', '1')]))


class CommandLineTests(unittest.TestCase):
    def test_merge_and_alert_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            root = Path(tmp)
            responses(root / 'raw')
            self.assertEqual(traffic.main(['merge', '--raw', str(root / 'raw'), '--data', str(root / 'data'),
                                           '--collected-at', '2026-11-02T06:23:05Z']), 0)
            self.assertEqual(traffic.main(['alert', '--data', str(root / 'data'), '--output', str(root / 'a.json')]), 0)
            self.assertFalse((root / 'a.json').exists())  # one snapshot: no alert
            (root / 'raw/views.json').write_text('[]')
            self.assertEqual(traffic.main(['merge', '--raw', str(root / 'raw'), '--data', str(root / 'data')]), 2)


if __name__ == '__main__':
    unittest.main()
