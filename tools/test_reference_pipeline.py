"""Pipeline cases of the case register, run against the independent reference pipeline.

OOS-WINDOW-01, OOS-FREEZE-01, OOS-LEAK-01, OOS-SCORE-01, SEG-ISO-01, REPEAT-01, PARAM-01 and SCN-LAYER-01
use tests/reference/pipeline.py, written from the contracts. The property cases follow DATA-PIT-02: hand-checked
instances, a seeded property check and a negative control that shows the check can fail. They pin the
reference pipeline and the design of each check; the toolkit must later pass the same checks on the same
fixtures.
"""
from __future__ import annotations

import dataclasses
import json
import operator
import os
import random
import subprocess
import sys
import tempfile
import types
import unittest
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'tests' / 'reference'
sys.path.insert(0, str(REFERENCE))
import data_reader as reader  # noqa: E402
import pipeline  # noqa: E402

FIXTURES = ROOT / 'tests' / 'fixtures'
LOANS, PANEL, RATES = reader.LOANS, reader.PANEL, reader.RATES
Book = pipeline.Book
Group = pipeline.Group
Outcome = tuple[dict[Group, tuple[object, ...]], dict[tuple[Group, str], tuple[object, ...]], dict[Group, str]]
ROW_KINDS = ('partial', 'full', 'censor', 'client_rate')
LOAN_KINDS = ('add_loan', 'delete_loan')
RATE_KINDS = ('remark_rate', 'truncate_rate', 'extend_rate')


def expected(case: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / 'tests' / 'expected' / f'{case}.json').read_text(encoding='utf-8'))
    return data


def key(group: Group) -> str:
    return '|'.join(group)


def group_of_key(text: str) -> Group:
    segment, currency = text.split('|')
    return segment, currency


def within(value: float | Fraction, reference: str, tolerance: str = 'abs 1e-12') -> bool:
    kind, size = tolerance.split()
    ref, bound = Fraction(reference), Fraction(size)
    if kind == 'rel':
        bound *= max(Fraction(1), abs(ref))
    return abs(Fraction(value) - ref) <= bound


_BOOKS: dict[str, Book] = {}
_RUNS: dict[str, pipeline.Run] = {}


def base_book(fixture: str) -> Book:
    """The generated book of a fixture, built once. Tests never change its rows: changes copy the lists
    and replace the rows they alter (copy_book)."""
    if fixture not in _BOOKS:
        _BOOKS[fixture] = pipeline.generate_book(json.loads((FIXTURES / fixture).read_text(encoding='utf-8')))
    return _BOOKS[fixture]


def base_run(spec: Mapping[str, Any], group_of: pipeline.GroupOf = pipeline.segment_and_currency,
             name: str = 'separate') -> pipeline.Run:
    """A complete run on the unchanged book, built once per grouping."""
    if name not in _RUNS:
        _RUNS[name] = pipeline.run_pipeline(base_book(spec['fixture']), pipeline.settings_from(spec['settings']),
                                            group_of=group_of)
    return _RUNS[name]


def outcome(run: pipeline.Run) -> Outcome:
    """Parameter estimates and forecasts of a run without lineage, and the groups not estimated."""
    return ({g: p.estimate() for g, p in run.parameter_sets.items()},
            {k: f.outcome() for k, f in run.forecasts.items()}, dict(run.not_estimated))


def everything(book: Book, origin: date) -> Book:
    """Negative control: no point-in-time filter."""
    return book


def pool_currencies(loan: Mapping[str, str]) -> Group:
    return loan['segment'], 'ALL'


def pool_segments(loan: Mapping[str, str]) -> Group:
    return 'ALL', loan['currency']


# ---------------------------------------------------------------------------
# Valid changes to a book (the import stays accepted; see Perturbations)
# ---------------------------------------------------------------------------

def copy_book(book: Book) -> Book:
    return {name: list(rows) for name, rows in book.items()}


def history(book: Book, loan_id: str) -> list[int]:
    rows = book[PANEL]
    return sorted((i for i, r in enumerate(rows) if r['loan_id'] == loan_id), key=lambda i: rows[i]['as_of_date'])


def prepay(book: Book, loan_id: str, at: str, amount: Decimal | None) -> bool:
    """A partial prepayment of `amount`, or a full one when it is None, in a NONE month with a row in the
    month before; later balances, and a later FULL amount, follow the balance identity."""
    rows, indices = book[PANEL], history(book, loan_id)
    dates = [rows[i]['as_of_date'] for i in indices]
    k = dates.index(at) if at in dates else 0
    current = rows[indices[k]]
    if k == 0 or current['event'] != 'NONE' or pipeline.next_month_end(dates[k - 1]) != at:
        return False
    if amount is None:
        opening = Decimal(rows[indices[k - 1]]['balance'])
        paid = opening - Decimal(current['scheduled_principal']) + Decimal(current['other_change'])
        rows[indices[k]] = {**current, 'balance': '0', 'prepaid_principal': str(paid), 'event': 'FULL'}
        drop = set(indices[k + 1:])
        book[PANEL] = [r for i, r in enumerate(rows) if i not in drop]
        return True
    if any(rows[i]['event'] != 'FULL' and Decimal(rows[i]['balance']) <= amount for i in indices[k:]):
        return False
    for i in indices[k:]:
        r = rows[i]
        field = 'prepaid_principal' if r['event'] == 'FULL' else 'balance'
        rows[i] = {**r, field: str(Decimal(r[field]) - amount)}
    rows[indices[k]] = {**rows[indices[k]], 'prepaid_principal': str(amount), 'event': 'PARTIAL'}
    return True


def censor(book: Book, loan_id: str, at: str) -> bool:
    """Remove the loan's rows from `at` on, keeping at least one."""
    dates = [book[PANEL][i]['as_of_date'] for i in history(book, loan_id)]
    if not dates or dates[0] >= at or dates[-1] < at:
        return False
    book[PANEL] = [r for r in book[PANEL] if not (r['loan_id'] == loan_id and r['as_of_date'] >= at)]
    return True


def set_client_rate(book: Book, loan_id: str, at: str, rate: str) -> bool:
    rows, changed = book[PANEL], False
    for i, r in enumerate(rows):
        if r['loan_id'] == loan_id and r['as_of_date'] >= at and r['client_rate'] != rate:
            rows[i], changed = {**r, 'client_rate': rate}, True
    return changed


def add_loan(book: Book, template: Mapping[str, str], loan_id: str, start: date, months: int, end: date) -> None:
    """A new loan like `template`, originated in the month of `start`, reporting NONE for `months` months."""
    book[LOANS].append({**template, 'loan_id': loan_id, 'origination_date': start.replace(day=15).isoformat(),
                        'original_balance': '777', 'predecessor_id': ''})
    for month in pipeline.month_ends(start, min(end, pipeline.add_months(start, months - 1))):
        book[PANEL].append(pipeline.row(month, loan_id, '777', '0.03', '0', 'NONE'))


def delete_loan(book: Book, loan_id: str) -> None:
    book[LOANS] = [r for r in book[LOANS] if r['loan_id'] != loan_id]
    book[PANEL] = [r for r in book[PANEL] if r['loan_id'] != loan_id]


def remark_rate(book: Book, rate_id: str, at: str, delta: Decimal) -> None:
    rows = book[RATES]
    for i, r in enumerate(rows):
        if r['rate_id'] == rate_id and r['as_of_date'] >= at:
            rows[i] = {**r, 'rate': f'{Decimal(r["rate"]) + delta:.8f}'}


def truncate_rate(book: Book, rate_id: str, at: str) -> None:
    book[RATES] = [r for r in book[RATES] if not (r['rate_id'] == rate_id and r['as_of_date'] >= at)]


def extend_rate(book: Book, rate_id: str, months: int) -> None:
    """Rows after the series' last month end, as a later extract would bring."""
    last = max((r for r in book[RATES] if r['rate_id'] == rate_id), key=lambda r: r['as_of_date'])
    month = date.fromisoformat(last['as_of_date'])
    for step in range(1, months + 1):
        value = Decimal(last['rate']) + step * Decimal('0.001')
        book[RATES].append({**last, 'as_of_date': pipeline.add_months(month, step).isoformat(),
                            'rate': f'{value:.8f}'})


def changed_dates(base: Book, book: Book, names: Sequence[str] = (LOANS, PANEL, RATES)) -> set[str]:
    """The date of every row added, removed or replaced: as_of_date of panel and rate rows, origination_date
    of register rows. Unchanged rows are the same objects in both books."""
    dates = set()
    fields = {LOANS: 'origination_date', PANEL: 'as_of_date', RATES: 'as_of_date'}
    for name, field in ((n, fields[n]) for n in names):
        before, after = {id(r) for r in base[name]}, {id(r) for r in book[name]}
        dates |= {r[field] for r in base[name] if id(r) not in after}
        dates |= {r[field] for r in book[name] if id(r) not in before}
    return dates


class Perturber:
    """Random valid changes, each at a month end in [lo, hi] (a rate extension lies after the data)."""

    def __init__(self, rng: random.Random, data_end: date) -> None:
        self.rng, self.data_end, self.serial = rng, data_end, 0

    def apply(self, book: Book, lo: date, hi: date, loans: Sequence[str],
              scope: Callable[[Mapping[str, str]], bool], kinds: Sequence[str]) -> tuple[str, str]:
        """Apply one change of a random kind; return the kind and its month end."""
        for _ in range(200):
            kind = self.rng.choice(kinds)
            self.serial += 1
            if kind in ROW_KINDS:
                at = self.row_change(book, kind, lo.isoformat(), hi.isoformat(), loans)
            elif kind in LOAN_KINDS:
                at = self.loan_change(book, kind, lo, hi, scope)
            else:
                at = self.rate_change(book, kind, lo.isoformat(), hi.isoformat())
            if at:
                return kind, at
        raise AssertionError(f'no applicable change among {kinds}')

    def row_change(self, book: Book, kind: str, lo: str, hi: str, loans: Sequence[str]) -> str:
        loan_id = self.rng.choice(loans)
        dates = [d for d in (book[PANEL][i]['as_of_date'] for i in history(book, loan_id)) if lo <= d <= hi]
        if not dates:
            return ''
        at = self.rng.choice(dates)
        if kind == 'partial':
            done = prepay(book, loan_id, at, Decimal(self.rng.choice(('0.0001', '1', '99.5'))))
        elif kind == 'full':
            done = prepay(book, loan_id, at, None)
        elif kind == 'censor':
            done = censor(book, loan_id, at)
        else:
            done = set_client_rate(book, loan_id, at, f'0.{400 + self.serial % 500:04d}')
        return at if done else ''

    def loan_change(self, book: Book, kind: str, lo: date, hi: date,
                    scope: Callable[[Mapping[str, str]], bool]) -> str:
        if kind == 'add_loan':
            start = self.rng.choice(pipeline.month_ends(lo, min(hi, self.data_end)))
            template = self.rng.choice([r for r in book[LOANS] if scope(r)])
            add_loan(book, template, f'NEW{self.serial}', start, self.rng.randint(2, 6), self.data_end)
            return start.isoformat()
        candidates = [r for r in book[LOANS] if scope(r)
                      and lo <= reader.month_end(date.fromisoformat(r['origination_date'])) <= hi]
        if not candidates:
            return ''
        loan = self.rng.choice(candidates)
        delete_loan(book, loan['loan_id'])
        return reader.month_end(date.fromisoformat(loan['origination_date'])).isoformat()

    def rate_change(self, book: Book, kind: str, lo: str, hi: str) -> str:
        rate_id = self.rng.choice(sorted({r['rate_id'] for r in book[RATES]}))
        if kind == 'extend_rate':
            extend_rate(book, rate_id, self.rng.randint(1, 2))
            return max(r['as_of_date'] for r in book[RATES] if r['rate_id'] == rate_id)
        dates = sorted(r['as_of_date'] for r in book[RATES] if r['rate_id'] == rate_id and lo <= r['as_of_date'] <= hi)
        if not dates:
            return ''
        at = self.rng.choice(dates)
        if kind == 'remark_rate':
            remark_rate(book, rate_id, at, Decimal(self.rng.choice(('0.0001', '0.001', '0.01'))))
        else:
            truncate_rate(book, rate_id, at)
        return at


@contextmanager
def counting(*names: str) -> Iterator[list[int]]:
    """Count calls of reference functions (looked up at call time) while the block runs."""
    calls, originals = [0], {name: getattr(pipeline, name) for name in names}

    def wrap(function: Callable[..., Any]) -> Callable[..., Any]:
        def counted(*args: Any, **kwargs: Any) -> Any:
            calls[0] += 1
            return function(*args, **kwargs)
        return counted

    for name, function in originals.items():
        setattr(pipeline, name, wrap(function))
    try:
        yield calls
    finally:
        for name, function in originals.items():
            setattr(pipeline, name, function)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

class Fixture(unittest.TestCase):
    """The generated book and the changes of the property tests are accepted imports."""

    def test_generated_book_is_an_accepted_import(self) -> None:
        spec = expected('OOS-FREEZE-01')
        book = base_book(spec['fixture'])
        result = read(book, spec['settings']['windows'])
        self.assertEqual((result.errors, result.warnings), ([], []))
        # The data reader's own risk-set outcomes count the loan-months of the estimation window (M9).
        end = spec['settings']['windows']['estimation_end']
        counts: dict[str, list[int]] = {}
        for (loan_id, start), event in result.outcomes.items():
            segment, currency, _ = result.outcome_starts[(loan_id, start)]
            if start < end and event in {'NONE', 'PARTIAL', 'FULL'}:
                tally = counts.setdefault(f'{segment}|{currency}', [0, 0])
                tally[0] += 1
                tally[1] += event == 'FULL'
        self.assertEqual(counts, {g: [p['loan_months'], p['full_events']] for g, p in spec['parameters'].items()})

    def test_changes_keep_the_import_accepted(self) -> None:
        spec = json.loads((FIXTURES / 'OOS-FREEZE-01' / 'book.json').read_text(encoding='utf-8'))
        spec.update(data_window=['2019-12-31', '2020-12-31'], split='2020-06-30')
        spec['groups'] = [{**g, 'loans': 6, 'full_per_month': [1, 2]} for g in spec['groups']]
        base = pipeline.generate_book(spec)
        perturber = Perturber(random.Random(1), date(2020, 12, 31))
        loans = sorted({r['loan_id'] for r in base[LOANS]})
        for kind in (*ROW_KINDS, *LOAN_KINDS, *RATE_KINDS):
            for trial in range(3):
                book = copy_book(base)
                perturber.apply(book, date(2020, 1, 31), date(2020, 12, 31), loans, lambda r: True, [kind])
                with self.subTest(kind=kind, trial=trial):
                    result = read(book, {'data_start': '2019-12-31', 'data_end': '2020-12-31'})
                    self.assertEqual(result.errors, [])
                    self.assertTrue({w[2] for w in result.warnings} <= {'W02', 'W04'}, result.warnings)

    def test_view_matches_the_data_reader(self) -> None:
        rows = reader.read_rows(FIXTURES / 'DATA-PIT-01' / 'events')
        book: Book = {**rows, RATES: []}
        origins = [*expected('DATA-PIT-02')['views'], '2023-06-30']
        generated = base_book(expected('OOS-LEAK-01')['fixture'])
        for source, origin in [(book, o) for o in origins] + [(generated, '2023-06-30')]:
            mine = pipeline.point_in_time(source, date.fromisoformat(origin))
            theirs = reader.point_in_time_view({LOANS: source[LOANS], PANEL: source[PANEL]}, date.fromisoformat(origin))
            for name in (LOANS, PANEL):
                self.assertEqual(sorted(tuple(r[f] for f in reader.HEADERS[name]) for r in mine[name]),
                                 theirs[name], origin)


def read(book: Book, windows: Mapping[str, str]) -> reader.Result:
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in pipeline.book_files(book).items():
            (Path(tmp) / name).write_bytes(data)
        return reader.read_import(Path(tmp), date.fromisoformat(windows['data_start']),
                                  date.fromisoformat(windows['data_end']), {'EUR', 'USD'})


class WindowCases(unittest.TestCase):
    """OOS-WINDOW-01."""

    def setUp(self) -> None:
        self.spec = expected('OOS-WINDOW-01')

    def test_month_end_arithmetic(self) -> None:
        for start, months, end in self.spec['month_end_arithmetic']:
            self.assertEqual(pipeline.add_months(date.fromisoformat(start), months), date.fromisoformat(end))

    def test_declarations(self) -> None:
        parse = date.fromisoformat
        for name, want in self.spec['variants'].items():
            test = want['test'] or [None, None]
            windows = pipeline.Windows(parse(want['data'][0]), parse(want['data'][1]), parse(want['estimation'][0]),
                                       parse(want['estimation'][1]), test[0] and parse(test[0]),
                                       test[1] and parse(test[1]))
            with self.subTest(variant=name):
                breaches = pipeline.window_breaches(windows)
                self.assertEqual(not breaches, want['accepted'])
                self.assertEqual(breaches, want['breaches'])
                self.assertEqual(len(windows.origins()), want['origins'])
                self.assertEqual(len(windows.complete_origins()), want['complete_origins'])

    def test_rejected_before_estimation(self) -> None:
        settings = pipeline.settings_from(expected('OOS-FREEZE-01')['settings'])
        book = base_book(self.spec['pipeline']['fixture'])
        for start, end in self.spec['pipeline']['rejected_tests']:
            windows = dataclasses.replace(settings.windows, test_start=date.fromisoformat(start),
                                          test_end=date.fromisoformat(end))
            with self.subTest(test=(start, end)), counting('estimate', 'estimate_group', 'loan_months') as calls:
                with self.assertRaises(pipeline.WindowRejected) as caught:
                    pipeline.run_pipeline(book, dataclasses.replace(settings, windows=windows))
                self.assertEqual(caught.exception.breaches, self.spec['pipeline']['breaches'])
                self.assertEqual(calls[0], 0)


class FreezeCases(unittest.TestCase):
    """OOS-FREEZE-01: one parameter set per segment and currency, the same at every origin."""

    def setUp(self) -> None:
        self.spec = expected('OOS-FREEZE-01')
        self.settings = pipeline.settings_from(self.spec['settings'])
        self.book = base_book(self.spec['fixture'])

    def assert_frozen(self, run: pipeline.Run, book: Book) -> None:
        windows = self.settings.windows
        cut = windows.estimation_end.isoformat()
        truncated = {LOANS: [r for r in book[LOANS] if r['origination_date'] <= cut],
                     PANEL: [r for r in book[PANEL] if r['as_of_date'] <= cut],
                     RATES: [r for r in book[RATES] if r['as_of_date'] <= cut]}
        alone, _ = pipeline.estimate(truncated, self.settings, windows.estimation_start, windows.estimation_end)
        self.assertEqual({g: p.estimate() for g, p in run.parameter_sets.items()},
                         {g: p.estimate() for g, p in alone.items()})
        for group, parameters in run.parameter_sets.items():
            used = {(f.parameter_set_id, f.cpr) for (g, _), f in run.forecasts.items() if g == group}
            self.assertEqual(used, {(parameters.id, parameters.value('cpr'))}, group)
            self.assertEqual(sum(1 for g, _ in run.forecasts if g == group), len(windows.origins()))

    def test_hand_instance(self) -> None:
        run = base_run(self.spec)
        self.assert_frozen(run, self.book)
        self.assertEqual(sorted(key(g) for g in run.parameter_sets), sorted(self.spec['parameters']))
        for group, parameters in run.parameter_sets.items():
            want = self.spec['parameters'][key(group)]
            self.assertEqual(Fraction(want['pm0_cpr']), 1 - (1 - Fraction(want['pool_smm'])) ** 12)
            self.assertTrue(within(parameters.value('cpr'), want['pm0_cpr']), group)
            self.assertEqual(dict(parameters.diagnostics), {n: str(want[n]) for n in
                                                            ('month_ends', 'loan_months', 'full_events')})

    def test_changes_anywhere_never_unfreeze(self) -> None:
        rng = random.Random(self.spec['seed'])
        windows = self.settings.windows
        perturber = Perturber(rng, windows.data_end)
        loans = sorted({r['loan_id'] for r in self.book[LOANS]})
        for trial in range(self.spec['trials']):
            book = copy_book(self.book)
            changes = [perturber.apply(book, pipeline.add_months(windows.data_start, 1), windows.data_end, loans,
                                       lambda r: True, (*ROW_KINDS, *LOAN_KINDS, *RATE_KINDS))
                       for _ in range(rng.randint(1, 3))]
            with self.subTest(trial=trial, changes=changes):
                self.assert_frozen(pipeline.run_pipeline(book, self.settings), book)

    def test_negative_control_re_estimation(self) -> None:
        frozen = base_run(self.spec).parameter_sets
        start = self.settings.windows.estimation_start
        for origin in self.spec['rolling_origins']:
            rolling, _ = pipeline.estimate(self.book, self.settings, start, date.fromisoformat(origin))
            for group, parameters in rolling.items():
                with self.subTest(origin=origin, group=group):
                    self.assertNotEqual(parameters.value('cpr'), frozen[group].value('cpr'))


class LeakCases(unittest.TestCase):
    """OOS-LEAK-01: nothing dated after an origin reaches a forecast from it."""

    def setUp(self) -> None:
        self.spec = expected('OOS-LEAK-01')
        self.settings = pipeline.settings_from(self.spec['settings'])
        self.book = base_book(self.spec['fixture'])

    def forecast(self, book: Book, origin: date, view: pipeline.View = pipeline.point_in_time) -> Outcome:
        return outcome(pipeline.run_pipeline(book, self.settings, [origin], view=view))

    def test_hand_instance(self) -> None:
        instance = self.spec['instance']
        origin = date.fromisoformat(instance['origin'])
        run = pipeline.run_pipeline(self.book, self.settings, [origin])
        for name, want in instance['groups'].items():
            made = run.forecasts[(group_of_key(name), instance['origin'])]
            self.assertEqual(len(made.known_loans), want['known_loans'], name)
            self.assertEqual(len(made.cohort), want['cohort_loans'], name)
            self.assertEqual(sum(Decimal(r[2]) for r in made.cohort), Decimal(want['cohort_balance']), name)
            self.assertEqual([list(c) for c in made.curve], want['curve'], name)
        # The rate at the origin is read, so the property below must never alter it.
        change = instance['rate_at_origin']
        book = copy_book(self.book)
        rows = book[RATES]
        for i, r in enumerate(rows):
            if r['rate_id'] == change['rate_id'] and r['as_of_date'] == instance['origin']:
                rows[i] = {**r, 'rate': change['rate']}
        moved = pipeline.run_pipeline(book, self.settings, [origin])
        differ = sorted(key(g) for (g, _), f in moved.forecasts.items()
                        if f.outcome() != run.forecasts[(g, instance['origin'])].outcome())
        self.assertEqual(differ, change['changes'])

    def test_rate_changes_are_dated_after_the_origin(self) -> None:
        """The property never alters a market rate at the origin; checked on many cheap draws."""
        rng = random.Random(self.spec['seed'])
        perturber = Perturber(rng, self.settings.windows.data_end)
        for origin_text in self.spec['origins']:
            origin = date.fromisoformat(origin_text)
            for kind in RATE_KINDS:
                for draw in range(20):
                    book = copy_book(self.book)
                    perturber.apply(book, pipeline.add_months(origin, 1), self.settings.windows.data_end, [],
                                    lambda r: True, [kind])
                    dates = changed_dates(self.book, book, (RATES,))
                    self.assertTrue(dates and min(dates) > origin_text, (origin_text, kind, draw, dates))

    def test_changes_after_the_origin_do_not_leak(self) -> None:
        rng = random.Random(self.spec['seed'])
        data_end = self.settings.windows.data_end
        perturber = Perturber(rng, data_end)
        for origin_text in self.spec['origins']:
            origin = date.fromisoformat(origin_text)
            before, before_open = self.forecast(self.book, origin), self.forecast(self.book, origin, everything)
            outstanding = sorted(r['loan_id'] for r in self.book[PANEL] if r['as_of_date'] == origin_text
                                 and r['event'] not in reader.TERMINAL)
            for trial in range(self.spec['trials_per_origin']):
                book = copy_book(self.book)
                changes = [perturber.apply(book, pipeline.add_months(origin, 1), data_end, outstanding,
                                           lambda r: True, (*ROW_KINDS, *LOAN_KINDS, *RATE_KINDS))
                           for _ in range(rng.randint(1, 3))]
                with self.subTest(origin=origin_text, trial=trial, changes=changes):
                    self.assertTrue(all(d > origin_text for d in changed_dates(self.book, book)))
                    self.assertEqual(self.forecast(book, origin), before)
                    self.assertNotEqual(self.forecast(book, origin, everything), before_open)


class ScoreCases(unittest.TestCase):
    """OOS-SCORE-01."""

    def setUp(self) -> None:
        self.spec = expected('OOS-SCORE-01')
        self.pairs = pipeline.read_pairs(FIXTURES / self.spec['fixture'])
        self.origins = [date.fromisoformat(o) for o in self.spec['origins']]
        self.data_end = date.fromisoformat(self.spec['data_end'])

    def test_hand_case(self) -> None:
        scores = pipeline.score(self.pairs, self.origins, self.data_end, self.spec['horizons'])
        self.assertEqual(sorted(scores), list(range(1, self.spec['horizons'] + 1)))
        self.assertEqual(sum(s.incomplete for s in scores.values()), self.spec['incomplete_total'])
        self.assertEqual(sum(s.scored + s.incomplete for s in scores.values()),
                         len(self.origins) * self.spec['horizons'])
        tol = self.spec['tolerance']
        for horizon, want in self.spec['by_horizon'].items():
            got = scores[int(horizon)]
            with self.subTest(horizon=horizon):
                self.assertEqual((got.scored, got.incomplete, got.zero_realised),
                                 (want['scored'], want['incomplete'], want['zero_realised']))
                for name in ('mae', 'abs_bias'):
                    value = getattr(got, name)
                    if want[name] is None:
                        self.assertIsNone(value)
                    else:
                        self.assertTrue(within(value, want[name], tol), f'{name}: {value}')
                assert got.cumulative is not None
                self.assertEqual(sorted(got.cumulative), sorted(want['cumulative']))
                for origin, (kind, value) in want['cumulative'].items():
                    self.assertEqual(got.cumulative[origin][0], kind)
                    self.assertTrue(within(got.cumulative[origin][1], value, tol), origin)

    def test_case_design(self) -> None:
        """Values supplied for INCOMPLETE pairs, and one exposure per horizon, so no weighting choice matters."""
        beyond = [p for p in self.pairs if pipeline.add_months(p.origin, p.horizon) > self.data_end]
        self.assertGreaterEqual(len(beyond), 2)
        for horizon in {p.horizon for p in self.pairs}:
            self.assertEqual(len({p.realised_available for p in self.pairs if p.horizon == horizon}), 1)

    def test_a_complete_pair_is_never_dropped(self) -> None:
        kept = [p for p in self.pairs if (p.origin, p.horizon) != (self.origins[0], 1)]
        with self.assertRaises(ValueError):
            pipeline.score(kept, self.origins, self.data_end, self.spec['horizons'])


class SegmentCases(unittest.TestCase):
    """SEG-ISO-01: segments and currencies are estimated and forecast in isolation."""

    def setUp(self) -> None:
        self.spec = expected('SEG-ISO-01')
        self.settings = pipeline.settings_from(self.spec['settings'])
        self.book = base_book(self.spec['fixture'])

    def test_hand_instance(self) -> None:
        run = base_run(self.spec)
        for group, parameters in run.parameter_sets.items():
            self.assertTrue(within(parameters.value('cpr'), self.spec['parameters'][key(group)]['pm0_cpr']))
            self.assertIn(parameters.currency, {'EUR', 'USD'})
        for (group, _), made in run.forecasts.items():
            self.assertEqual(made.currency, run.parameter_sets[group].currency)
        pooled = self.spec['pooled']
        for name, group_of, group in (('currencies', pool_currencies, ('MTG_FIX', 'ALL')),
                                      ('segments', pool_segments, ('ALL', 'EUR'))):
            want = pooled[name][group[0] if name == 'currencies' else group[1]]
            self.assertEqual(Fraction(want['pm0_cpr']), 1 - (1 - Fraction(want['pool_smm'])) ** 12)
            value = base_run(self.spec, group_of, name).parameter_sets[group].value('cpr')
            self.assertTrue(within(value, want['pm0_cpr']), name)
            for separate in self.spec['parameters'].values():
                self.assertFalse(within(value, separate['pm0_cpr']), name)

    def outputs(self, run: pipeline.Run, group: Group, origins: set[str]) -> tuple[object, ...]:
        forecasts = tuple(f.outcome() for (g, o), f in sorted(run.forecasts.items()) if g == group and o in origins)
        return run.parameter_sets[group].estimate(), forecasts

    def change_one_group(self, rng: random.Random, perturber: Perturber, target: Group) -> tuple[Book, list[str]]:
        """One to three random valid changes to the loans of one group, up to the end of the test window."""
        def in_target(loan: Mapping[str, str]) -> bool:
            return pipeline.segment_and_currency(loan) == target

        windows = self.settings.windows
        loans = sorted(r['loan_id'] for r in self.book[LOANS] if in_target(r))
        book = copy_book(self.book)
        changes = [perturber.apply(book, pipeline.add_months(windows.data_start, 1), windows.origins()[-1], loans,
                                   in_target, (*ROW_KINDS[:3], *LOAN_KINDS)) for _ in range(rng.randint(1, 3))]
        return book, [f'{kind} {at}' for kind, at in changes]

    def test_changing_one_segment_leaves_the_others(self) -> None:
        rng = random.Random(self.spec['seed'])
        perturber = Perturber(rng, self.settings.windows.data_end)
        origins = self.settings.windows.origins()
        groups = sorted(base_run(self.spec).parameter_sets)
        for trial in range(self.spec['trials']):
            target = groups[trial % len(groups)]
            book, changes = self.change_one_group(rng, perturber, target)
            # The first and last origins, and every origin at which a change happens.
            months = {c.split()[1] for c in changes}
            chosen = sorted({origins[0], origins[-1], *(o for o in origins if o.isoformat() in months)})
            texts = {o.isoformat() for o in chosen}
            run = pipeline.run_pipeline(book, self.settings, chosen)
            with self.subTest(trial=trial, target=target, changes=changes):
                for group in groups:
                    same = self.outputs(run, group, texts) == self.outputs(base_run(self.spec), group, texts)
                    self.assertEqual(same, group != target, group)
                # Negative control: pooled with another group, the change reaches that group's outputs.
                name, group_of = pooling(target, trial)
                pooled = pipeline.run_pipeline(book, self.settings, chosen, group_of=group_of)
                shared = group_of({'segment': target[0], 'currency': target[1]})
                self.assertNotEqual(self.outputs(pooled, shared, texts),
                                    self.outputs(base_run(self.spec, group_of, name), shared, texts))


def pooling(target: Group, trial: int) -> tuple[str, pipeline.GroupOf]:
    """A grouping that pools the target with another group of the book: its currency's other segment, or
    its segment's other currency (MTG_FIX EUR takes each in turn)."""
    if target == ('MTG_FIX', 'USD') or (target == ('MTG_FIX', 'EUR') and trial % 2):
        return 'currencies', pool_currencies
    return 'segments', pool_segments


class RepeatCases(unittest.TestCase):
    """REPEAT-01: two runs in separate processes give identical outputs and fingerprints."""

    def setUp(self) -> None:
        self.spec = expected('REPEAT-01')

    def test_two_runs_agree(self) -> None:
        command = [sys.executable, str(REFERENCE / 'pipeline.py'), str(FIXTURES / self.spec['fixture']),
                   json.dumps(self.spec['settings'])]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, text=True,
                                      env={**os.environ, 'PYTHONHASHSEED': seed})
                     for seed in self.spec['hash_seeds']]
        runs = []
        for process in processes:
            out, _ = process.communicate(timeout=120)
            self.assertEqual(process.returncode, 0)
            runs.append(json.loads(out))
        self.assertEqual(runs[0], runs[1])
        self.assertEqual({n: runs[0][n] for n in self.spec['input_fingerprints']}, self.spec['input_fingerprints'])
        self.assertEqual(set(runs[0]) - set(self.spec['input_fingerprints']),
                         {'parameters.csv', 'forecasts.csv', 'scenarios.csv', 'records'})

    def test_negative_control(self) -> None:
        settings = pipeline.settings_from(self.spec['settings'])
        book = base_book(self.spec['fixture'])
        run = base_run(self.spec)
        other = pipeline.run_pipeline(book, dataclasses.replace(settings, commit='f' * 40), [])
        self.assertNotEqual(pipeline.export_parameters(other), pipeline.export_parameters(run))
        changed = copy_book(book)
        changed[RATES][-1] = {**changed[RATES][-1], 'rate': '0.25000000'}
        self.assertNotEqual(pipeline.fingerprints(changed), pipeline.fingerprints(book))


def snapshot(item: object) -> object:
    """Plain content of a parameter set or of its mutable copy."""
    if isinstance(item, (pipeline.ParameterSet, pipeline.Value, types.SimpleNamespace)):
        return {k: snapshot(v) for k, v in sorted(vars(item).items())}
    if isinstance(item, (tuple, list)):
        return [snapshot(i) for i in item]
    return item


def mutable_copy(item: object) -> object:
    if isinstance(item, (pipeline.ParameterSet, pipeline.Value)):
        return types.SimpleNamespace(**{k: mutable_copy(v) for k, v in vars(item).items()})
    if isinstance(item, tuple):
        return [mutable_copy(i) for i in item]
    return item


def attempt(target: object, kind: str, field: str) -> None:
    """One in-place change: assign a field, assign, append or delete an item, or assign a field of a value."""
    if kind == 'assign':
        setattr(target, field, 'changed')
    elif kind == 'set_item':
        operator.setitem(getattr(target, field), 0, 'changed')
    elif kind == 'append':
        getattr(getattr(target, field), 'append')('changed')
    elif kind == 'delete_item':
        operator.delitem(getattr(target, field), 0)
    else:
        setattr(getattr(target, 'values')[0], 'value', 0.5)


class ParameterCases(unittest.TestCase):
    """PARAM-01: a parameter set is immutable; exporting never re-estimates."""

    def setUp(self) -> None:
        self.spec = expected('PARAM-01')
        self.settings = pipeline.settings_from(self.spec['settings'])

    def test_contents(self) -> None:
        self.assertEqual([f.name for f in dataclasses.fields(pipeline.ParameterSet)], self.spec['fields'])
        for parameters in base_run(self.spec).parameter_sets.values():
            self.assertEqual([{'name': v.name, 'unit': v.unit, 'layer': v.layer} for v in parameters.values],
                             self.spec['values'])
            self.assertIsNotNone(parameters.test_window)

    def attempts(self, rng: random.Random) -> list[tuple[str, str]]:
        """Every in-place change on every field it applies to, in a random order."""
        fields = self.spec['fields']
        sequences = [f for f in fields if f in {'data_window', 'fingerprints', 'estimation_window', 'test_window',
                                                'settings', 'values', 'diagnostics'}]
        chosen = [('assign', f) for f in fields] + [('value', 'values')]
        chosen += [(kind, f) for kind in ('set_item', 'append', 'delete_item') for f in sequences]
        rng.shuffle(chosen)
        return chosen

    def test_parameter_sets_are_immutable(self) -> None:
        rng = random.Random(self.spec['seed'])
        run = base_run(self.spec)
        export = pipeline.export_parameters(run)
        for trial in range(self.spec['trials']):
            group = rng.choice(sorted(run.parameter_sets))
            parameters = run.parameter_sets[group]
            content = snapshot(parameters)
            for kind, field in self.attempts(rng):
                with self.subTest(trial=trial, kind=kind, field=field):
                    with self.assertRaises((AttributeError, TypeError)):
                        attempt(parameters, kind, field)
                    # Negative control: the same change to a mutable copy succeeds.
                    twin = mutable_copy(parameters)
                    attempt(twin, kind, field)
                    self.assertNotEqual(snapshot(twin), content)
            self.assertEqual(snapshot(parameters), content)
            self.assertEqual(pipeline.export_parameters(run), export)

    def test_export_never_re_estimates(self) -> None:
        rng = random.Random(self.spec['seed'])
        windows = self.settings.windows
        book = copy_book(base_book(self.spec['fixture']))
        run = pipeline.run_pipeline(book, self.settings, windows.origins()[:1])
        first = pipeline.export_parameters(run)
        perturber = Perturber(rng, windows.data_end)
        loans = sorted({r['loan_id'] for r in book[LOANS]})
        for trial in range(self.spec['trials']):
            changes = [perturber.apply(run.book, pipeline.add_months(windows.data_start, 1), windows.estimation_end,
                                       loans, lambda r: True, (*ROW_KINDS[:3], *LOAN_KINDS))
                       for _ in range(rng.randint(1, 3))]
            with self.subTest(trial=trial, changes=changes):
                with counting('estimate', 'estimate_group', 'loan_months') as calls:
                    again = pipeline.export_parameters(run)
                self.assertEqual((again, calls[0]), (first, 0))
                # Negative control: an exporter that re-estimates from the dataset sees the change.
                fresh, _ = pipeline.estimate(run.book, run.settings, windows.estimation_start, windows.estimation_end)
                self.assertNotEqual(pipeline.export_parameters(dataclasses.replace(run, parameter_sets=fresh)), first)


class LayerCases(unittest.TestCase):
    """SCN-LAYER-01: overlays change no fitted parameter, and every output is labelled with its layer."""

    def setUp(self) -> None:
        self.spec = expected('SCN-LAYER-01')

    def fresh_run(self) -> pipeline.Run:
        run = base_run(self.spec)
        return dataclasses.replace(run, parameter_sets=dict(run.parameter_sets), forecasts=dict(run.forecasts))

    def test_hand_instance(self) -> None:
        run = self.fresh_run()
        rows = pipeline.scenario_rows(run, pipeline.SUPERVISORY, True)
        self.assertEqual(len(rows), len(run.parameter_sets) * 7 * 2)
        for r in rows:
            group = (r.segment, r.currency)
            pm0 = Fraction(self.spec['parameters'][key(group)]['pm0_cpr'])
            self.assertEqual(r.parameter_set_id, run.parameter_sets[group].id)
            if r.layer == pipeline.INTERNAL or r.scenario == 'BASE':
                self.assertEqual((r.gamma, r.cpr), ('', run.parameter_sets[group].value('cpr')), r)
                continue
            gamma = Fraction(self.spec['gamma'][r.scenario])
            self.assertEqual(Fraction(r.gamma), gamma)
            self.assertTrue(within(r.cpr, str(min(Fraction(1), gamma * pm0))), r)
        self.assertEqual(self.problems(run, dict(run.parameter_sets), pipeline.export_parameters(run), rows), [])

    def problems(self, run: pipeline.Run, before: dict[Group, pipeline.ParameterSet], export: bytes,
                 rows: Sequence[pipeline.ScenarioRow]) -> list[str]:
        found = []
        if run.parameter_sets != before or pipeline.export_parameters(run) != export:
            found.append('a parameter set changed')
        layers = set(self.spec['layers'])
        for r in rows:
            if r.layer not in layers or r.parameter_set_id != run.parameter_sets[(r.segment, r.currency)].id:
                found.append(f'scenario row {r}')
        for name, data in (('scenarios', pipeline.export_scenarios(rows)),
                           ('forecasts', pipeline.export_forecasts(run))):
            lines = [line.split(',') for line in data.decode('ascii').splitlines()]
            column = lines[0].index('layer')
            found += [f'{name} row {line}' for line in lines[1:] if line[column] not in layers]
        found += [f'value {v}' for p in run.parameter_sets.values() for v in p.values
                  if v.layer not in pipeline.VALUE_LAYERS]
        return found

    def test_overlays_change_no_parameter(self) -> None:
        rng = random.Random(self.spec['seed'])
        for trial in range(self.spec['trials']):
            run = self.fresh_run()
            before, export = dict(run.parameter_sets), pipeline.export_parameters(run)
            scenarios = rng.sample(pipeline.SUPERVISORY, rng.randint(1, len(pipeline.SUPERVISORY)))
            standardised = trial % 2 == 0
            with self.subTest(trial=trial, scenarios=scenarios, standardised=standardised):
                rows = pipeline.scenario_rows(run, scenarios, standardised)
                self.assertEqual(self.problems(run, before, export, rows), [])
                # Negative controls: a row without its layer, and an overlay stored in the parameter set.
                unlabelled = [dataclasses.replace(rows[0], layer=''), *rows[1:]]
                self.assertNotEqual(self.problems(run, before, export, unlabelled), [])
                group = rng.choice(sorted(run.parameter_sets))
                fitted = run.parameter_sets[group]
                gamma = float(pipeline.GAMMA[scenarios[0]])
                run.parameter_sets[group] = dataclasses.replace(fitted, values=(
                    pipeline.Value('cpr', min(1.0, gamma * fitted.value('cpr')), 'decimal per annum', 'overlay'),))
                self.assertNotEqual(self.problems(run, before, export, rows), [])


if __name__ == '__main__':
    unittest.main()
