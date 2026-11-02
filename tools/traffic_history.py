"""Merge GitHub traffic API responses into the traffic-history branch, and build traffic alerts.

Used by .github/workflows/daily-traffic.yml (docs/TRAFFIC.md); it reads and
writes local files only and needs no token.

merge  validates the five API responses of one collection and every existing
       history file, then rewrites data/traffic.csv (one 14-day snapshot per
       collection date), data/traffic_daily.csv (one row per traffic date),
       data/referrers.csv, data/popular_paths.csv and the README badge files
       under data/badges/. A rerun on the same date replaces that date's
       snapshot, referrers and paths; dates the API no longer reports keep
       their stored values. Nothing is written unless every input is valid.
alert  compares the two latest snapshots and writes the title and body of one
       alert issue when views spike, stars or forks increase, or a new
       referrer brings enough views. Clones are never a spike reason: every
       workflow checkout of this repository counts as a clone.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRAFFIC = 'traffic.csv'
DAILY = 'traffic_daily.csv'
REFERRERS = 'referrers.csv'
PATHS = 'popular_paths.csv'
HEADERS: dict[str, tuple[str, ...]] = {
    TRAFFIC: ('snapshot_date', 'snapshot_datetime_utc', 'views_14d', 'unique_views_14d', 'clones_14d',
              'unique_clones_14d', 'stars', 'forks', 'watchers', 'open_issues_and_prs'),
    DAILY: ('date', 'views', 'unique_views', 'clones', 'unique_clones'),
    REFERRERS: ('snapshot_date', 'rank', 'referrer', 'count', 'uniques'),
    PATHS: ('snapshot_date', 'rank', 'path', 'title', 'count', 'uniques'),
}
RESPONSES = ('views.json', 'clones.json', 'referrers.json', 'paths.json', 'repo.json')
REPOSITORY_COUNTS = {'stars': 'stargazers_count', 'forks': 'forks_count',
                     'watchers': 'subscribers_count', 'open_issues_and_prs': 'open_issues_count'}
BADGE_COLOR = '217346'
ISO_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
# A 14-day total that at least doubles and grows by this much is a spike.
SPIKE_GROWTH = {'views_14d': 100}
NEW_REFERRER_VIEWS = 5
Row = dict[str, str]


class TrafficError(Exception):
    """An invalid API response or history file; nothing has been written."""


# --- API responses ---------------------------------------------------------------

def count(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TrafficError(f'{where}: expected a non-negative integer, got {value!r}')
    return value


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as error:
        raise TrafficError(f'{path.name}: response missing') from error
    except (OSError, ValueError) as error:
        raise TrafficError(f'{path.name}: unreadable response ({error})') from error


def parse_series(data: Any, key: str) -> tuple[int, int, dict[str, tuple[int, int]]]:
    """14-day count and uniques, and (count, uniques) per UTC day."""
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise TrafficError(f'{key}: expected an object with a {key!r} list')
    days: dict[str, tuple[int, int]] = {}
    for index, item in enumerate(data[key]):
        where = f'{key}[{index}]'
        if not isinstance(item, dict) or not isinstance(item.get('timestamp'), str):
            raise TrafficError(f'{where}: expected an object with a timestamp')
        day = item['timestamp'][:10]
        if not ISO_DATE.fullmatch(day) or day in days:
            raise TrafficError(f'{where}: invalid or duplicate date {item["timestamp"]!r}')
        days[day] = (count(item.get('count'), f'{where}.count'), count(item.get('uniques'), f'{where}.uniques'))
    return count(data.get('count'), f'{key}.count'), count(data.get('uniques'), f'{key}.uniques'), days


def parse_ranked(data: Any, name: str, fields: Sequence[str]) -> list[Row]:
    if not isinstance(data, list):
        raise TrafficError(f'{name}: expected a list')
    rows = []
    for rank, item in enumerate(data, start=1):
        where = f'{name}[{rank - 1}]'
        if not isinstance(item, dict):
            raise TrafficError(f'{where}: expected an object')
        row = {'rank': str(rank)}
        for key in fields:
            if not isinstance(item.get(key, ''), str):
                raise TrafficError(f'{where}.{key}: expected a string')
            row[key] = item.get(key, '')
        row['count'] = str(count(item.get('count'), f'{where}.count'))
        row['uniques'] = str(count(item.get('uniques'), f'{where}.uniques'))
        rows.append(row)
    return rows


# --- History files ---------------------------------------------------------------

def read_history(path: Path) -> list[Row]:
    """One history file; an older traffic.csv layout (date, views, ...) is converted."""
    if not path.exists():
        return []
    try:
        reader = csv.DictReader(io.StringIO(path.read_text(encoding='utf-8')))
        rows = list(reader)
    except (OSError, ValueError, csv.Error) as error:
        raise TrafficError(f'{path.name}: unreadable ({error})') from error
    header = HEADERS[path.name]
    result = []
    for number, row in enumerate(rows, start=2):
        if None in row or any(value is None for value in row.values()):
            raise TrafficError(f'{path.name}:{number}: wrong number of fields')
        if path.name == TRAFFIC and not row.get('snapshot_date') and row.get('date'):
            row = {'snapshot_date': row['date'][:10], 'snapshot_datetime_utc': row['date'],
                   'views_14d': row.get('views', '0'), 'unique_views_14d': row.get('unique_views', '0'),
                   'clones_14d': row.get('clones', '0'), 'unique_clones_14d': row.get('unique_clones', '0'),
                   **{key: row.get(key, '0') for key in ('stars', 'forks', 'watchers')},
                   'open_issues_and_prs': row.get('open_issues_and_prs', row.get('open_issues', '0'))}
        elif path.name == TRAFFIC and 'open_issues_and_prs' not in row:
            row = {**row, 'open_issues_and_prs': row.get('open_issues', '0')}
        if not ISO_DATE.fullmatch(row.get(header[0], '')):
            raise TrafficError(f'{path.name}:{number}: invalid {header[0]} {row.get(header[0])!r}')
        result.append({key: row.get(key, '') for key in header})
    return result


def render(name: str, rows: Sequence[Mapping[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADERS[name], lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def write_all(data: Path, contents: Mapping[str, str]) -> None:
    """Write each file to a temporary sibling first, then move them all into place."""
    staged = []
    for name, content in contents.items():
        target = data / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f'.{target.name}.tmp')
        temporary.write_text(content, encoding='utf-8', newline='')
        staged.append((temporary, target))
    for temporary, target in staged:
        os.replace(temporary, target)


# --- Merge -----------------------------------------------------------------------

def compact(value: int) -> str:
    """A badge number: 950, 1.2k, 11k, 3.4M."""
    for limit, suffix in ((1_000_000, 'M'), (1_000, 'k')):
        if value >= limit:
            text = f'{value / limit:.1f}'
            return (text[:-2] if text.endswith('.0') else text) + suffix
    return str(value)


def to_int(value: str) -> int:
    return int(value) if value.isdigit() else 0


def badges(daily: Sequence[Mapping[str, str]], snapshot: Mapping[str, str]) -> dict[str, str]:
    """shields.io endpoint files for the README.

    clones: clones of every stored day. visitors (14d): unique visitors over
    the API's 14-day window, from today's snapshot; daily uniques cannot be
    summed into a unique count. visits: daily unique visitors summed over every
    stored day, so a visitor counts once per day of visit.
    """
    values = {'clones': ('clones', sum(to_int(row['clones']) for row in daily)),
              'visits': ('visits', sum(to_int(row['unique_views']) for row in daily)),
              'visitors': ('visitors (14d)', to_int(snapshot['unique_views_14d']))}
    return {f'badges/{name}.json': json.dumps({'schemaVersion': 1, 'label': label, 'message': compact(value),
                                                'color': BADGE_COLOR}) + '\n'
            for name, (label, value) in values.items()}


def merge(raw: Path, data: Path, collected_at: datetime) -> list[str]:
    """Merge one collection; return the names of the files whose content changed."""
    views = parse_series(load_json(raw / 'views.json'), 'views')
    clones = parse_series(load_json(raw / 'clones.json'), 'clones')
    referrers = parse_ranked(load_json(raw / 'referrers.json'), 'referrers', ('referrer',))
    paths = parse_ranked(load_json(raw / 'paths.json'), 'paths', ('path', 'title'))
    repository = load_json(raw / 'repo.json')
    if not isinstance(repository, dict):
        raise TrafficError('repo: expected an object')
    current = {name: read_history(data / name) for name in HEADERS}

    day = collected_at.astimezone(timezone.utc).date().isoformat()
    snapshot = {'snapshot_date': day,
                'snapshot_datetime_utc': collected_at.astimezone(timezone.utc).isoformat(timespec='seconds'),
                'views_14d': str(views[0]), 'unique_views_14d': str(views[1]),
                'clones_14d': str(clones[0]), 'unique_clones_14d': str(clones[1]),
                **{column: str(count(repository.get(field), f'repo.{field}'))
                   for column, field in REPOSITORY_COUNTS.items()}}
    traffic = sorted([row for row in current[TRAFFIC] if row['snapshot_date'] != day] + [snapshot],
                     key=lambda row: row['snapshot_date'])
    # Dates the API reports take its values; dates it no longer reports keep theirs.
    by_date = {row['date']: row for row in current[DAILY]}
    for prefix, (_, _, days) in (('views', views), ('clones', clones)):
        for date, (total, unique) in days.items():
            row = by_date.setdefault(date, {'date': date, 'views': '0', 'unique_views': '0',
                                            'clones': '0', 'unique_clones': '0'})
            row[prefix], row[f'unique_{prefix}'] = str(total), str(unique)
    daily = [by_date[date] for date in sorted(by_date)]

    def replace_day(rows: Sequence[Row], new: Sequence[Row]) -> list[Row]:
        kept = [row for row in rows if row['snapshot_date'] != day]
        return sorted([*kept, *({'snapshot_date': day, **row} for row in new)],
                      key=lambda row: (row['snapshot_date'], int(row['rank'] or 0)))

    merged = {TRAFFIC: traffic, DAILY: daily,
              REFERRERS: replace_day(current[REFERRERS], referrers),
              PATHS: replace_day(current[PATHS], paths)}
    contents = {name: render(name, rows) for name, rows in merged.items()}
    contents.update(badges(daily, snapshot))
    # Compare bytes: the CSV files end their lines with CRLF, which read_text would translate.
    changed = {name: content for name, content in contents.items()
               if not (data / name).exists() or (data / name).read_bytes() != content.encode('utf-8')}
    write_all(data, changed)
    return sorted(changed)


# --- Alert -----------------------------------------------------------------------

def alert(data: Path) -> dict[str, str] | None:
    """The alert issue for the latest snapshot, or None when nothing stands out."""
    snapshots = read_history(data / TRAFFIC)
    if len(snapshots) < 2:
        return None
    previous, current = snapshots[-2], snapshots[-1]
    day, before = current['snapshot_date'], previous['snapshot_date']
    reasons = []
    for key, growth in SPIKE_GROWTH.items():
        old, new = to_int(previous[key]), to_int(current[key])
        if new >= max(old * 2, old + growth):
            reasons.append(f"{key.split('_')[0].capitalize()} spike")
    for key in ('stars', 'forks'):
        if to_int(current[key]) > to_int(previous[key]):
            reasons.append(f'{key.capitalize()} increased')
    referrers = read_history(data / REFERRERS)
    known = {row['referrer'] for row in referrers if row['snapshot_date'] < day}
    today = [row for row in referrers if row['snapshot_date'] == day]
    new_referrers = [row for row in today if row['referrer'] and row['referrer'] not in known
                     and to_int(row['count']) >= NEW_REFERRER_VIEWS]
    if new_referrers:
        reasons.append('New referrer detected')
    if not reasons:
        return None

    def ranked(rows: Sequence[Row], label: str, empty: str) -> list[str]:
        top = sorted(rows, key=lambda row: to_int(row['count']), reverse=True)[:10]
        return [f"- {row[label]}: {row['count']} views, {row['uniques']} unique" for row in top] or [empty]

    def compared(key: str, name: str) -> str:
        return f'- {name}: {current[key]} vs {previous[key]} on {before}'

    paths = [row for row in read_history(data / PATHS) if row['snapshot_date'] == day]
    body = [
        'Automated traffic alert for **K-IRRBB Prepayment Models**.', '',
        'Trigger reason:', ', '.join(reasons), '',
        'Current 14-day snapshot:',
        compared('views_14d', 'Views'), compared('unique_views_14d', 'Unique views'),
        compared('clones_14d', 'Clones'), compared('unique_clones_14d', 'Unique clones'),
        compared('stars', 'Stars'), compared('forks', 'Forks'), '',
        'New referrers:', *ranked(new_referrers, 'referrer', '- No new referrer above threshold'), '',
        'Current top referrers:', *ranked(today, 'referrer', '- No referrers available'), '',
        'Current popular paths:', *ranked(paths, 'path', '- No popular paths available'), '',
        'Suggested checks:',
        '1. Go to **Insights → Traffic**',
        '2. Check whether one of the referrers is a blog, forum, Reddit, StackOverflow, GitHub project, or newsletter',
        '3. Check which page, release, screenshot, source file, or README section is attracting traffic',
        '4. Consider adding a short README CTA asking users to star the repository if they are using the project',
    ]
    return {'title': f'Traffic alert: {day}', 'body': '\n'.join(body)}


# --- Command line ----------------------------------------------------------------

def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise argparse.ArgumentTypeError(f'invalid timestamp {value!r}') from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError('the timestamp needs a UTC offset')
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    merge_command = commands.add_parser('merge', help='merge one collection into the history')
    merge_command.add_argument('--raw', type=Path, required=True, help=f"directory holding {', '.join(RESPONSES)}")
    merge_command.add_argument('--data', type=Path, required=True, help='data/ on the traffic-history branch')
    merge_command.add_argument('--collected-at', type=parse_time,
                               default=datetime.now(timezone.utc).replace(microsecond=0))
    alert_command = commands.add_parser('alert', help='write the alert issue, if one is due')
    alert_command.add_argument('--data', type=Path, required=True)
    alert_command.add_argument('--output', type=Path, required=True,
                               help='JSON file for the title and body; not written when no alert is due')
    args = parser.parse_args(argv)
    try:
        if args.command == 'alert':
            issue = alert(args.data)
            if issue is None:
                print('No alert: nothing stands out in the latest snapshot.')
            else:
                args.output.write_text(json.dumps(issue), encoding='utf-8')
                print(issue['title'])
            return 0
        changed = merge(args.raw, args.data, args.collected_at)
    except TrafficError as error:
        print(f'ERROR: {error}; the history was not changed', file=sys.stderr)
        return 2
    print('Changed: ' + (', '.join(changed) or 'nothing'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
