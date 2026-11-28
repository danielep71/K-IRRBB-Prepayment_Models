"""Independent reference for the out-of-time pipeline of the model contracts.

Written from MODEL_CONTRACTS.md (Common rules, Candidate models, Regulatory overlay, Parameter and
scenario outputs, decisions M9 and M10), VALIDATION_PLAN.md (out-of-time validation, leakage,
segmentation, V1 to V3) and DATA_CONTRACT.md (point-in-time availability), not from toolkit source.
The model is PM0, the realised CPR of the estimation window per segment and currency; the PM1 fit is
another workstream. The pipeline declares windows, estimates once on the estimation window, freezes
an immutable parameter set, forecasts from each origin of the test window with the point-in-time
view at that origin, applies the standardised-multiplier overlay after the fit and exports CSV with
the parameter-set ID in every row. Scoring of (origin, horizon) pairs is a separate function on a
table of pairs. Run ``python tests/reference/pipeline.py SPEC SETTINGS`` to print the fingerprints of
one run, as REPEAT-01 does in two separate processes.

Reference choices where the contracts leave a detail open. No expected file depends on them: each
fixture is built so that every reading gives the same result, or the check compares the reference
with itself (a property) rather than with a contract value.

1. The estimation window holds the loan-months (i, t) with t in [estimation_start, estimation_end].
   The fixtures start it at the data start, where no loan-month ends.
2. M9 counts the month ends with a pool, the risk-set loan-months of the group and its FULL events.
3. A forecast from origin t records the frozen parameters, the PM0 SMM path, the loans in the view,
   the latest known row of each loan outstanding in the extract at t, and the latest row in the view
   of each configured curve series of the currency. The fixtures have a rate row at every month end.
4. The parameter-set ID is a digest of the set's content without its timestamp.
5. Layer labels are spelt 'internal_model' and 'standardised_multiplier'; gamma is recorded on the
   scenario rows, not in the parameter set; CONTRACT and user-defined shocks are not produced.
6. Scores are plain means over the scored pairs; the bias is reported as a magnitude.
7. Window boundaries must be month ends with start <= end; anything else raises ValueError.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache
from operator import itemgetter
from pathlib import Path

import data_reader as reader
import rates

LOANS, PANEL, RATES = reader.LOANS, reader.PANEL, reader.RATES
Book = dict[str, list[dict[str, str]]]
Group = tuple[str, str]    # (segment, currency)

HORIZONS = 12    # V2: horizons 1 to 12 months
MIN_COMPLETE_ORIGINS = 12    # V1
MIN_MONTH_ENDS, MIN_LOAN_MONTHS, MIN_FULL = 36, 5_000, 100    # M9
MODEL_ID, MODEL_VERSION = 'PM0', '1'
INTERNAL, STANDARDISED = 'internal_model', 'standardised_multiplier'    # CPR layers (M15)
LAYERS = (INTERNAL, STANDARDISED)
VALUE_LAYERS = ('estimate', 'assumption', 'overlay')
SUPERVISORY = ('PAR_UP', 'PAR_DOWN', 'STEEPENER', 'FLATTENER', 'SHORT_UP', 'SHORT_DOWN')
# REG-1 SRP31.119, Table 5: 0.8 for parallel up, steepener and short up; 1.2 for the others.
GAMMA = {'PAR_UP': '0.8', 'STEEPENER': '0.8', 'SHORT_UP': '0.8',
         'PAR_DOWN': '1.2', 'FLATTENER': '1.2', 'SHORT_DOWN': '1.2'}


# ---------------------------------------------------------------------------
# Month ends and windows (Common rules; V1)
# ---------------------------------------------------------------------------

def add_months(end: date, months: int) -> date:
    """The month end `months` calendar months after (or before) a month end."""
    index = end.year * 12 + end.month - 1 + months
    return reader.month_end(date(index // 12, index % 12 + 1, 1))


@lru_cache(maxsize=None)
def next_month_end(text: str) -> str:
    """The ISO month end one month after an ISO month end."""
    return add_months(date.fromisoformat(text), 1).isoformat()


def month_ends(first: date, last: date) -> list[date]:
    ends, month = [], first
    while month <= last:
        ends.append(month)
        month = add_months(month, 1)
    return ends


@dataclass(frozen=True)
class Windows:
    data_start: date
    data_end: date
    estimation_start: date
    estimation_end: date
    test_start: date | None = None
    test_end: date | None = None

    def __post_init__(self) -> None:
        """Preconditions of a declaration, not contract rules: month ends, and start <= end in each window."""
        bounds = [(self.data_start, self.data_end), (self.estimation_start, self.estimation_end)]
        if (self.test_start is None) != (self.test_end is None):
            raise ValueError('a test window needs both boundaries')
        if self.test_start is not None and self.test_end is not None:
            bounds.append((self.test_start, self.test_end))
        for start, end in bounds:
            if not (reader.is_month_end(start) and reader.is_month_end(end) and start <= end):
                raise ValueError(f'not a window of month ends: {start} to {end}')

    def origins(self) -> list[date]:
        """Each month end of the test window is a forecast origin."""
        if self.test_start is None or self.test_end is None:
            return []
        return month_ends(self.test_start, self.test_end)

    def complete_origins(self) -> list[date]:
        """Origins whose month end HORIZONS months later lies inside the data window."""
        return [o for o in self.origins() if add_months(o, HORIZONS) <= self.data_end]


def window_breaches(windows: Windows) -> list[str]:
    """The rules a declaration breaks; empty when it is accepted.

    Both windows lie inside the data window; the test window is disjoint from and strictly after the
    estimation window, test_start > estimation_end, so an overlapping, equal or earlier window is
    rejected; V1 needs at least 12 origins with a complete 12-month horizon. The names are this
    reference's; the contract prescribes the rejection, not its wording.
    """
    breaches = []
    if not windows.data_start <= windows.estimation_start or not windows.estimation_end <= windows.data_end:
        breaches.append('estimation_outside_data_window')
    if windows.test_start is None or windows.test_end is None:
        return breaches
    if not windows.data_start <= windows.test_start or not windows.test_end <= windows.data_end:
        breaches.append('test_outside_data_window')
    if not windows.test_start > windows.estimation_end:
        breaches.append('test_not_after_estimation')
    if len(windows.complete_origins()) < MIN_COMPLETE_ORIGINS:
        breaches.append('fewer_than_12_complete_origins')
    return breaches


class WindowRejected(ValueError):
    def __init__(self, breaches: list[str]) -> None:
        super().__init__(', '.join(breaches))
        self.breaches = breaches


# ---------------------------------------------------------------------------
# Synthetic book (generated fixture)
# ---------------------------------------------------------------------------

def generate_book(spec: Mapping[str, object]) -> Book:
    """A valid import built from a book specification (tests/fixtures/OOS-FREEZE-01/book.json).

    Every group keeps `loans` active bullet loans of one balance. At each month end after the first,
    the oldest active loans prepay in full (`full_per_month[0]` per month up to `split`, then
    `full_per_month[1]`), the others report NONE, and as many new loans originate in that month, so
    every month's pool has the same exposure and an exact SMM of full_per_month / loans.
    """
    first, last = (date.fromisoformat(d) for d in spec['data_window'])  # type: ignore[attr-defined]
    split = date.fromisoformat(str(spec['split']))
    book: Book = {LOANS: [], PANEL: [], RATES: []}
    ends = month_ends(first, last)
    for group in spec['groups']:  # type: ignore[attr-defined]
        serial = 0

        def register(origination: str) -> str:
            nonlocal serial
            serial += 1
            loan_id = f'{group["prefix"]}{serial:04d}'
            book[LOANS].append(dict(zip(reader.HEADERS[LOANS], (
                loan_id, group['segment'], group['currency'], origination, str(spec['maturity']), group['balance'],
                'FIXED', '', '', 'BULLET', '12', 'NONE', '', ''))))
            return loan_id

        active = [register(str(spec['initial_origination'])) for _ in range(group['loans'])]
        for index, end in enumerate(ends):
            full = 0 if index == 0 else group['full_per_month'][0 if end <= split else 1]
            for position, loan_id in enumerate(active):
                prepaid = group['balance'] if position < full else '0'
                book[PANEL].append(row(end, loan_id, '0' if position < full else group['balance'],
                                       str(spec['client_rate']), prepaid, 'FULL' if position < full else 'NONE'))
            active = active[full:]
            for _ in range(full):
                loan_id = register(end.replace(day=15).isoformat())
                active.append(loan_id)
                book[PANEL].append(row(end, loan_id, group['balance'], str(spec['client_rate']), '0', 'NONE'))
    for index, end in enumerate(ends):
        for series in spec['rates']:  # type: ignore[attr-defined]
            value = Decimal(series['first']) + index * Decimal(series['step'])
            book[RATES].append(dict(zip(reader.HEADERS[RATES], (
                end.isoformat(), series['rate_id'], series['currency'], str(series['tenor_months']),
                f'{value:.8f}'))))
    return book


def row(end: date, loan_id: str, balance: str, client_rate: str, prepaid: str, event: str) -> dict[str, str]:
    return dict(zip(reader.HEADERS[PANEL], (end.isoformat(), loan_id, balance, client_rate, '0', prepaid, '0', event)))


def book_files(book: Book) -> dict[str, bytes]:
    """The three input files of a book, header first, LF line ends, rows in book order."""
    files = {}
    for name in (LOANS, PANEL, RATES):
        fields = itemgetter(*reader.HEADERS[name])
        lines = [','.join(reader.HEADERS[name])] + [','.join(fields(r)) for r in book[name]]
        files[name] = ('\n'.join(lines) + '\n').encode('ascii')
    return files


def fingerprints(book: Book) -> tuple[tuple[str, str], ...]:
    return tuple((name, hashlib.sha256(data).hexdigest()) for name, data in book_files(book).items())


# ---------------------------------------------------------------------------
# Point-in-time view and loan-months
# ---------------------------------------------------------------------------

View = Callable[[Book, date], Book]
GroupOf = Callable[[Mapping[str, str]], Group]


def point_in_time(book: Book, origin: date) -> Book:
    """Register rows of loans originated on or before the origin; panel and market-rate rows dated on
    or before it. ISO dates of one width compare as text; tools/test_reference_pipeline.py checks this
    view against data_reader.point_in_time_view."""
    t = origin.isoformat()
    return {LOANS: [r for r in book[LOANS] if r['origination_date'] <= t],
            PANEL: [r for r in book[PANEL] if r['as_of_date'] <= t],
            RATES: [r for r in book[RATES] if r['as_of_date'] <= t]}


def segment_and_currency(loan: Mapping[str, str]) -> Group:
    """Every model runs per segment x currency; loans in different currencies are never pooled."""
    return loan['segment'], loan['currency']


def loan_months(view: Book, group_of: GroupOf, start: date, end: date) -> dict[Group, list[rates.LoanMonth]]:
    """Risk-set loan-months (i, t) with t in [start, end], per group.

    A loan-month is in the risk set when the loan has a row at t-1 with balance > 0 that is not a
    terminal event, t-1 is before the month end of maturity_date, and the next row is at t.
    """
    register = {r['loan_id']: r for r in view[LOANS]}
    histories: dict[str, list[dict[str, str]]] = {}
    for r in view[PANEL]:
        histories.setdefault(r['loan_id'], []).append(r)
    first, last = start.isoformat(), end.isoformat()
    months: dict[Group, list[rates.LoanMonth]] = {}
    for loan_id, history in histories.items():
        loan = register.get(loan_id)
        if loan is None:
            continue
        group = group_of(loan)
        maturity_end = reader.month_end(date.fromisoformat(loan['maturity_date'])).isoformat()
        history.sort(key=lambda r: r['as_of_date'])
        for prev, current in zip(history, history[1:]):
            t = current['as_of_date']
            if not first <= t <= last or prev['event'] in reader.TERMINAL or prev['as_of_date'] >= maturity_end:
                continue
            opening = Decimal(prev['balance'])
            if opening <= 0 or next_month_end(prev['as_of_date']) != t:
                continue
            months.setdefault(group, []).append(rates.LoanMonth(
                loan_id, group[0], group[1], t, opening, Decimal(current['scheduled_principal']),
                Decimal(current['other_change']), Decimal(current['prepaid_principal']), current['event']))
    return months


# ---------------------------------------------------------------------------
# Parameter sets (Parameter and scenario outputs)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Value:
    name: str
    value: float
    unit: str
    layer: str    # estimate, assumption or overlay


@dataclass(frozen=True)
class ParameterSet:
    """Immutable once created: a frozen record whose every container is a tuple."""
    id: str
    model_id: str
    model_version: str
    segment: str
    currency: str
    data_window: tuple[str, str]
    fingerprints: tuple[tuple[str, str], ...]
    estimation_window: tuple[str, str]
    test_window: tuple[str, str] | None
    settings: tuple[tuple[str, str], ...]
    values: tuple[Value, ...]
    diagnostics: tuple[tuple[str, str], ...]
    timestamp: str
    commit: str

    def estimate(self) -> tuple[object, ...]:
        """What the fit produced, without lineage (ID, input fingerprints, timestamp, commit)."""
        return (self.model_id, self.model_version, self.segment, self.currency, self.estimation_window,
                self.settings, self.values, self.diagnostics)

    def value(self, name: str) -> float:
        return next(v.value for v in self.values if v.name == name)


def canonical(content: Mapping[str, object]) -> str:
    def plain(item: object) -> object:
        if isinstance(item, Value):
            return [item.name, item.value, item.unit, item.layer]
        if isinstance(item, tuple):
            return [plain(i) for i in item]
        return item
    return json.dumps({k: plain(v) for k, v in content.items()}, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True)
class Settings:
    windows: Windows
    commit: str
    timestamp: str
    curve_series: tuple[str, ...]
    include_reneg: bool = False    # data decision D4

    def recorded(self) -> tuple[tuple[str, str], ...]:
        return (('curve_series', ' '.join(self.curve_series)), ('include_reneg', str(self.include_reneg).lower()),
                ('default_and_sale', 'excluded'))    # data decision D5


def longest_run(ends: Sequence[str]) -> int:
    best = run = 0
    previous: date | None = None
    for text in sorted(ends):
        current = date.fromisoformat(text)
        run = run + 1 if previous is not None and add_months(previous, 1) == current else 1
        best, previous = max(best, run), current
    return best


def estimate_group(group: Group, months: list[rates.LoanMonth], settings: Settings,
                   lineage: tuple[tuple[str, str], ...], start: date, end: date) -> ParameterSet | str:
    """PM0: the realised CPR of the estimation window, 1 - (prod (1 - SMM(t)))^(12/n) over the month
    ends with a pool. Below the minimum sample (M9) the group is not estimated: the reason is returned."""
    pools = rates.pool_rates(months, settings.include_reneg)
    by_month = sorted((key[2], pool) for key, pool in pools.items())
    consecutive = longest_run([m for m, _ in by_month])
    full = sum(1 for m in months if m.event == 'FULL')
    if consecutive < MIN_MONTH_ENDS or len(months) < MIN_LOAN_MONTHS or full < MIN_FULL:
        return f'below the minimum sample: {consecutive} month ends, {len(months)} loan-months, {full} FULL'
    cpr = rates.realised_cpr([float(pool.smm) for _, pool in by_month])
    windows = settings.windows
    test = (None if windows.test_start is None or windows.test_end is None
            else (windows.test_start.isoformat(), windows.test_end.isoformat()))
    content: dict[str, object] = {
        'model_id': MODEL_ID, 'model_version': MODEL_VERSION, 'segment': group[0], 'currency': group[1],
        'data_window': (windows.data_start.isoformat(), windows.data_end.isoformat()), 'fingerprints': lineage,
        'estimation_window': (start.isoformat(), end.isoformat()), 'test_window': test,
        'settings': settings.recorded(), 'values': (Value('cpr', cpr, 'decimal per annum', 'estimate'),),
        'diagnostics': (('month_ends', str(len(by_month))), ('loan_months', str(len(months))),
                        ('full_events', str(full))),
        'commit': settings.commit}
    identifier = 'PS-' + hashlib.sha256(canonical(content).encode('ascii')).hexdigest()[:16]
    return ParameterSet(id=identifier, timestamp=settings.timestamp, **content)  # type: ignore[arg-type]


def estimate(book: Book, settings: Settings, start: date, end: date, view: View = point_in_time,
             group_of: GroupOf = segment_and_currency) -> tuple[dict[Group, ParameterSet], dict[Group, str]]:
    """Estimate once, from the point-in-time view at the end of the estimation window."""
    lineage = fingerprints(book)
    estimated: dict[Group, ParameterSet] = {}
    not_estimated: dict[Group, str] = {}
    for group, months in sorted(loan_months(view(book, end), group_of, start, end).items()):
        result = estimate_group(group, months, settings, lineage, start, end)
        if isinstance(result, str):
            not_estimated[group] = result
        else:
            estimated[group] = result
    return estimated, not_estimated


# ---------------------------------------------------------------------------
# Forecasts from each origin
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Forecast:
    """What a forecast from an origin consumes and produces: the frozen parameters, the latest known
    row of each loan outstanding in the extract at the origin, the loans known at the origin, the curve
    observed at the origin, and the PM0 SMM path over horizons 1 to 12."""
    parameter_set_id: str
    segment: str
    currency: str
    origin: str
    layer: str
    cpr: float
    smm: tuple[float, ...]
    known_loans: tuple[str, ...]    # loans in the point-in-time view, by loan_id
    cohort: tuple[tuple[str, ...], ...]
    curve: tuple[tuple[str, ...], ...]

    def outcome(self) -> tuple[object, ...]:
        """The forecast without its lineage (the parameter-set ID records the input fingerprints)."""
        return (self.segment, self.currency, self.origin, self.layer, self.cpr, self.smm, self.known_loans,
                self.cohort, self.curve)


def forecast(book: Book, settings: Settings, parameter_sets: Mapping[Group, ParameterSet], origin: date,
             view: View = point_in_time, group_of: GroupOf = segment_and_currency) -> dict[Group, Forecast]:
    seen = view(book, origin)
    t = origin.isoformat()
    groups = {r['loan_id']: group_of(r) for r in seen[LOANS]}
    latest: dict[str, dict[str, str]] = {}
    outstanding: set[str] = set()
    for r in seen[PANEL]:
        loan_id = r['loan_id']
        if loan_id not in latest or r['as_of_date'] >= latest[loan_id]['as_of_date']:
            latest[loan_id] = r
        if r['as_of_date'] == t and r['event'] not in reader.TERMINAL and Decimal(r['balance']) > 0:
            outstanding.add(loan_id)
    curves: dict[str, dict[str, dict[str, str]]] = {}
    for r in seen[RATES]:
        if r['rate_id'] in settings.curve_series:
            series = curves.setdefault(r['currency'], {})
            if r['rate_id'] not in series or r['as_of_date'] >= series[r['rate_id']]['as_of_date']:
                series[r['rate_id']] = r
    result = {}
    for group, parameters in sorted(parameter_sets.items()):
        cpr = parameters.value('cpr')
        cohort = tuple(sorted(tuple(latest[i][f] for f in reader.HEADERS[PANEL])
                              for i in outstanding if groups.get(i) == group))
        curve = tuple(sorted((r['rate_id'], r['tenor_months'], r['as_of_date'], r['rate'])
                             for r in curves.get(group[1], {}).values()))
        result[group] = Forecast(parameters.id, group[0], group[1], t, INTERNAL, cpr,
                                 (rates.smm_from_cpr(cpr),) * HORIZONS,
                                 tuple(sorted(i for i, g in groups.items() if g == group)), cohort, curve)
    return result


@dataclass
class Run:
    settings: Settings
    book: Book    # the accepted dataset the run was estimated from
    parameter_sets: dict[Group, ParameterSet]
    not_estimated: dict[Group, str]
    forecasts: dict[tuple[Group, str], Forecast]


def run_pipeline(book: Book, settings: Settings, origins: Iterable[date] | None = None,
                 view: View = point_in_time, group_of: GroupOf = segment_and_currency) -> Run:
    """Reject a bad window declaration before estimation, estimate once, then forecast from each origin
    of the test window (or the given subset) with the frozen parameter sets."""
    windows = settings.windows
    breaches = window_breaches(windows)
    if breaches:
        raise WindowRejected(breaches)
    estimated, not_estimated = estimate(book, settings, windows.estimation_start, windows.estimation_end,
                                        view, group_of)
    run = Run(settings, book, estimated, not_estimated, {})
    chosen = windows.origins() if origins is None else list(origins)
    for origin in chosen:
        if origin not in windows.origins():
            raise ValueError(f'{origin} is not a forecast origin of the test window')
        for group, made in forecast(book, settings, estimated, origin, view, group_of).items():
            run.forecasts[(group, origin.isoformat())] = made
    return run


# ---------------------------------------------------------------------------
# Regulatory overlay (applied after the fit)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScenarioRow:
    parameter_set_id: str
    segment: str
    currency: str
    scenario: str
    layer: str
    gamma: str
    cpr: float
    smm: float


def scenario_rows(run: Run, scenarios: Sequence[str], standardised: bool) -> list[ScenarioRow]:
    """CPR per scenario and layer. PM0 has no incentive, so its internal-model CPR is the same in every
    scenario. The standardised-multiplier layer gives min(1, gamma x CPR_BASE) for the six supervisory
    scenarios, and CPR_BASE for BASE (M15). The overlay reads the parameter set and writes only rows."""
    rows = []
    for group, parameters in sorted(run.parameter_sets.items()):
        base = parameters.value('cpr')
        for scenario in ('BASE', *scenarios):
            if scenario != 'BASE' and scenario not in SUPERVISORY:
                raise ValueError(f'unknown scenario {scenario}')
            rows.append(ScenarioRow(parameters.id, group[0], group[1], scenario, INTERNAL, '', base,
                                    rates.smm_from_cpr(base)))
            if standardised:
                gamma = GAMMA.get(scenario, '')
                cpr = min(1.0, float(gamma) * base) if gamma else base
                rows.append(ScenarioRow(parameters.id, group[0], group[1], scenario, STANDARDISED, gamma, cpr,
                                        rates.smm_from_cpr(cpr)))
    return rows


# ---------------------------------------------------------------------------
# Export (decision M10: CSV with the parameter-set ID in every row)
# ---------------------------------------------------------------------------

def csv_bytes(header: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    def cell(value: object) -> str:
        text = repr(value) if isinstance(value, float) else str(value)
        if ',' in text or '\n' in text:
            raise ValueError(f'cell not representable in the CSV subset: {text!r}')
        return text
    lines = [','.join(header)] + [','.join(cell(v) for v in r) for r in rows]
    return ('\n'.join(lines) + '\n').encode('ascii')


def export_parameters(run: Run) -> bytes:
    """Each parameter set as metadata, value and diagnostic rows; exporting never re-estimates."""
    out: list[tuple[object, ...]] = []
    for _, p in sorted(run.parameter_sets.items()):
        metadata: list[tuple[str, object]] = [
            ('model_id', p.model_id), ('model_version', p.model_version), ('segment', p.segment),
            ('currency', p.currency), ('data_window', ' '.join(p.data_window)),
            *((f'fingerprint {name}', digest) for name, digest in p.fingerprints),
            ('estimation_window', ' '.join(p.estimation_window)),
            ('test_window', ' '.join(p.test_window) if p.test_window else ''),
            *((f'setting {name}', value) for name, value in p.settings),
            ('timestamp', p.timestamp), ('commit', p.commit)]
        out += [(p.id, 'metadata', name, value, '', '') for name, value in metadata]
        out += [(p.id, 'value', v.name, v.value, v.unit, v.layer) for v in p.values]
        out += [(p.id, 'diagnostic', name, value, '', '') for name, value in p.diagnostics]
    return csv_bytes(('parameter_set_id', 'section', 'name', 'value', 'unit', 'layer'), out)


def export_forecasts(run: Run) -> bytes:
    out = []
    for (_, origin), f in sorted(run.forecasts.items()):
        balance = sum((Decimal(r[2]) for r in f.cohort), Decimal(0))
        for horizon, smm in enumerate(f.smm, start=1):
            out.append((f.parameter_set_id, f.segment, f.currency, origin, horizon, f.layer, smm, f.cpr,
                        len(f.cohort), balance))
    return csv_bytes(('parameter_set_id', 'segment', 'currency', 'origin', 'horizon', 'layer', 'smm', 'cpr',
                      'cohort_loans', 'cohort_balance'), out)


def export_scenarios(rows: Iterable[ScenarioRow]) -> bytes:
    return csv_bytes(('parameter_set_id', 'segment', 'currency', 'scenario', 'layer', 'gamma', 'cpr', 'smm'),
                     [(r.parameter_set_id, r.segment, r.currency, r.scenario, r.layer, r.gamma, r.cpr, r.smm)
                      for r in rows])


# ---------------------------------------------------------------------------
# Out-of-time scoring (VALIDATION_PLAN.md, steps 3 and 4; V3)
# ---------------------------------------------------------------------------

INCOMPLETE, ZERO_REALISED, SCORED = 'INCOMPLETE', 'ZERO_REALISED', 'SCORED'


@dataclass(frozen=True)
class Pair:
    origin: date
    horizon: int
    forecast_smm: Fraction
    realised_smm: Fraction
    forecast_prepaid: Fraction    # cumulative over months 1..horizon
    realised_prepaid: Fraction
    realised_available: Fraction


@dataclass
class HorizonScore:
    scored: int = 0
    incomplete: int = 0
    zero_realised: int = 0
    mae: Fraction | None = None
    abs_bias: Fraction | None = None
    # Cumulative prepaid error per origin: ('relative', |F - R| / R) or ('zero_realised', |F - R|).
    cumulative: dict[str, tuple[str, Fraction]] | None = None


def classify(pair_origin: date, horizon: int, data_end: date, realised_prepaid: Fraction | None) -> str:
    """INCOMPLETE when the month end `horizon` months after the origin lies outside the data window,
    whatever values are supplied for it; ZERO_REALISED when the realised cumulative prepaid amount is 0."""
    if add_months(pair_origin, horizon) > data_end:
        return INCOMPLETE
    if realised_prepaid is None:
        raise ValueError(f'complete pair without realised values: {pair_origin} h={horizon}')
    return ZERO_REALISED if realised_prepaid == 0 else SCORED


def score(pairs: Iterable[Pair], origins: Sequence[date], data_end: date,
          horizons: int = HORIZONS) -> dict[int, HorizonScore]:
    """Scores per horizon over the origins. Every (origin, horizon) pair is classified; INCOMPLETE pairs
    are counted and never scored. The SMM scores are plain means over the scored pairs: the weighting
    of 'balance-weighted' is open, so the registered case has equal exposure in every pair. The bias is
    reported as a magnitude because the contract does not fix its sign."""
    table = {(p.origin, p.horizon): p for p in pairs}
    result: dict[int, HorizonScore] = {}
    for horizon in range(1, horizons + 1):
        score_h = HorizonScore(cumulative={})
        errors: list[Fraction] = []
        for origin in origins:
            pair = table.get((origin, horizon))
            kind = classify(origin, horizon, data_end, None if pair is None else pair.realised_prepaid)
            if kind == INCOMPLETE:
                score_h.incomplete += 1
                continue
            assert pair is not None and score_h.cumulative is not None
            score_h.scored += 1
            errors.append(pair.forecast_smm - pair.realised_smm)
            gap = abs(pair.forecast_prepaid - pair.realised_prepaid)
            if kind == ZERO_REALISED:
                score_h.zero_realised += 1
                score_h.cumulative[origin.isoformat()] = ('zero_realised', gap)
            else:
                score_h.cumulative[origin.isoformat()] = ('relative', gap / pair.realised_prepaid)
        if errors:
            score_h.mae = sum((abs(e) for e in errors), Fraction(0)) / len(errors)
            score_h.abs_bias = abs(sum(errors, Fraction(0)) / len(errors))
        result[horizon] = score_h
    return result


def read_pairs(path: Path) -> list[Pair]:
    lines = path.read_text(encoding='ascii').splitlines()
    header = ('origin', 'horizon', 'forecast_smm', 'realised_smm', 'forecast_prepaid', 'realised_prepaid',
              'realised_available')
    if tuple(lines[0].split(',')) != header:
        raise ValueError(f'{path}: header must be {",".join(header)}')
    pairs = []
    for line in lines[1:]:
        values = dict(zip(header, line.split(',')))
        pairs.append(Pair(date.fromisoformat(values['origin']), int(values['horizon']),
                          *(Fraction(values[k]) for k in header[2:])))
    return pairs


# ---------------------------------------------------------------------------
# One run's fingerprints (REPEAT-01)
# ---------------------------------------------------------------------------

def settings_from(data: Mapping[str, object]) -> Settings:
    w = data['windows']
    assert isinstance(w, dict)
    parse = date.fromisoformat
    windows = Windows(parse(w['data_start']), parse(w['data_end']), parse(w['estimation_start']),
                      parse(w['estimation_end']), parse(w['test_start']), parse(w['test_end']))
    return Settings(windows, str(data['commit']), str(data['timestamp']),
                    tuple(data['curve_series']))  # type: ignore[arg-type]


def run_fingerprints(spec_path: Path, settings: Settings) -> dict[str, str]:
    """SHA-256 of the input files, of every export of one complete run and of its records in memory
    (parameter sets and forecasts, including the parts no export shows)."""
    book = generate_book(json.loads(spec_path.read_text(encoding='utf-8')))
    run = run_pipeline(book, settings)
    records = repr((sorted(run.parameter_sets.items()), sorted(run.not_estimated.items()),
                    sorted(run.forecasts.items())))
    outputs = {'parameters.csv': export_parameters(run), 'forecasts.csv': export_forecasts(run),
               'scenarios.csv': export_scenarios(scenario_rows(run, SUPERVISORY, True)),
               'records': records.encode('ascii')}
    digests = dict(fingerprints(book))
    digests.update({name: hashlib.sha256(data).hexdigest() for name, data in outputs.items()})
    return digests


if __name__ == '__main__':
    print(json.dumps(run_fingerprints(Path(sys.argv[1]), settings_from(json.loads(sys.argv[2]))), sort_keys=True))
