"""Independent offline reference reader for docs/methodology/DATA_CONTRACT.md.

It reads the three input files of one import, applies the validation rules
in the contract's first-error order and returns the findings, warnings,
loan-month exposures, risk-set outcomes, reconciliation totals and the
comparison with optional control totals, and file fingerprints, and builds
the point-in-time view at a forecast origin. It is reference tooling only
(decision V4): standard library, exact decimal arithmetic, never a runtime
dependency, and written without reference to any toolkit source.

The validation conventions of decision D16, which settle what the rules
leave open, are listed in tests/reference/README.md.
"""
from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, Inexact, localcontext
from pathlib import Path

LOANS, PANEL, RATES = 'loans.csv', 'loan_panel.csv', 'market_rates.csv'
# Optional control totals: the workbook table Controls_Totals, given to the reader as a CSV file.
CONTROLS, CONTROLS_TABLE = 'controls.csv', 'Controls_Totals'
FILE_ORDER = (LOANS, PANEL, RATES, CONTROLS_TABLE)
HEADERS = {
    LOANS: ('loan_id', 'segment', 'currency', 'origination_date', 'maturity_date', 'original_balance',
            'rate_type', 'fixed_until', 'reset_months', 'amortisation', 'payment_months', 'penalty_type',
            'penalty_value', 'predecessor_id'),
    PANEL: ('as_of_date', 'loan_id', 'balance', 'client_rate', 'scheduled_principal', 'prepaid_principal',
            'other_change', 'event'),
    RATES: ('as_of_date', 'rate_id', 'currency', 'tenor_months', 'rate'),
}
SEGMENTS = {'MTG_FIX', 'MTG_RST', 'MTG_FLT', 'CON_FIX', 'SME_FIX'}
RATE_TYPES = {'FIXED', 'RESET', 'FLOAT'}
AMORTISATION = {'ANNUITY', 'LINEAR', 'BULLET'}
PAYMENT_MONTHS = {'1', '3', '6', '12'}
PENALTY_TYPES = {'NONE', 'PCT', 'MONTHS_INTEREST'}
EVENTS = {'NONE', 'PARTIAL', 'FULL', 'MATURITY', 'DEFAULT', 'RENEG', 'SALE'}
TERMINAL = {'FULL', 'MATURITY', 'DEFAULT', 'RENEG', 'SALE'}
TOLERANCE = Decimal('0.005')    # decision D9
DECIMAL_LIMIT = Decimal(10) ** 15    # decision D17: every decimal is below this in absolute value
KEY = ('as_of_date', 'segment', 'currency')
EXITS = ('full', 'maturity', 'default', 'reneg', 'sale')    # terminal events in the Controls_Totals order
RECON_MEASURES = ('loans', 'balance', 'scheduled_principal', 'prepaid_partial', 'prepaid_full', 'other_change',
                  *(f'{e}_{m}' for e in EXITS for m in ('count', 'balance')))
COUNT_MEASURES = {'loans', *(f'{e}_count' for e in EXITS)}
# Arithmetic runs in a wide context that traps rounding, so a result is exact or the reader stops.
PRECISION = 1000

ID_RE = re.compile(r'[A-Za-z0-9_-]{1,32}')
CCY_RE = re.compile(r'[A-Z]{3}')
DATE_RE = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
DECIMAL_RE = re.compile(r'-?\d+(?:\.(\d+))?')
POSITIVE_INT_RE = re.compile(r'[1-9]\d*')
COUNT_RE = re.compile(r'\d+')


# ---------------------------------------------------------------------------
# Field parsing (File format section)
# ---------------------------------------------------------------------------

def parse_date(text: str) -> date | None:
    """ISO YYYY-MM-DD, year 1900 to 9999, a real calendar date; otherwise None."""
    match = DATE_RE.fullmatch(text)
    if match is None:
        return None
    year, month, day = (int(g) for g in match.groups())
    if not 1900 <= year <= 9999:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def month_end(value: date) -> date:
    return date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])


def is_month_end(value: date) -> bool:
    return value == month_end(value)


def parse_decimal(text: str, places: int) -> Decimal | None:
    """A '.' decimal with digits on both sides of the point, at most `places` decimals and below 10^15 (D17)."""
    match = DECIMAL_RE.fullmatch(text)
    if match is None:
        return None
    if match.group(1) is not None and len(match.group(1)) > places:
        return None
    value = Decimal(text)
    # Comparisons never round, unlike abs() in the reader's trapping context (review of #110).
    return value if -DECIMAL_LIMIT < value < DECIMAL_LIMIT else None


def previous_month_end(value: date) -> date:
    first = value.replace(day=1)
    prior = date(first.year - 1, 12, 1) if first.month == 1 else date(first.year, first.month - 1, 1)
    return month_end(prior)


def next_month_end(value: date) -> date:
    return month_end(date(value.year + (value.month == 12), value.month % 12 + 1, 1))


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class Result:
    errors: list[tuple[str, int, str]] = field(default_factory=list)
    warnings: list[tuple[str, int, str]] = field(default_factory=list)
    loan_months: dict[tuple[str, str], tuple[Decimal, Decimal]] = field(default_factory=dict)
    # Outcome of the loan-month that starts at month end t-1, keyed by (loan_id, t-1).
    outcomes: dict[tuple[str, str], str] = field(default_factory=dict)
    # Reconciliation totals per (as_of_date, segment, currency), set only when the three files have no error.
    totals: dict[tuple[str, ...], dict[str, Decimal]] = field(default_factory=dict)
    # One (line, key, measure) per E17 finding; the measure is empty for an invalid control row.
    control_differences: list[tuple[int, str, str]] = field(default_factory=list)
    fingerprints: dict[str, str] = field(default_factory=dict)
    # Keys of the line-0 findings: (loan_id, missing month end) per W01 and the month end of each E12 (D14, D16).
    gaps: list[tuple[str, str]] = field(default_factory=list)
    missing_extracts: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return not self.errors


@dataclass
class Row:
    file: str
    line: int
    values: dict[str, str]
    parsed: dict[str, object] = field(default_factory=dict)


def as_of_of(row: Row) -> date:
    value = row.parsed['as_of_date']
    assert isinstance(value, date)
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

def read_import(folder: Path, window_start: date, window_end: date, allowlist: set[str]) -> Result:
    """Read one import; raise decimal.Inexact rather than round an amount."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.traps[Inexact] = True
        return _read_import(folder, window_start, window_end, allowlist)


def _read_import(folder: Path, window_start: date, window_end: date, allowlist: set[str]) -> Result:
    result = Result()
    rows: dict[str, list[Row]] = {}
    for name in (LOANS, PANEL, RATES):
        path = folder / name
        result.fingerprints[name] = sha256_file(path)
        rows[name] = split_file(name, path.read_bytes(), result)
    failed: set[tuple[str, int]] = set()

    def fail(row: Row, code: str) -> None:
        if (row.file, row.line) not in failed:
            failed.add((row.file, row.line))
            result.errors.append((row.file, row.line, code))

    def ok(row: Row) -> bool:
        return (row.file, row.line) not in failed

    # Single-row rules E03, E02, E04, E06, E07, E09 in contract order.
    for name, checker in ((LOANS, check_loan), (PANEL, check_panel), (RATES, check_rate)):
        for row in rows[name]:
            if ok(row):
                code = checker(row, allowlist)
                if code:
                    fail(row, code)
    register = {r.values['loan_id']: r for r in rows[LOANS] if ok(r)}

    # E11 inconsistent dates.
    for row in rows[LOANS]:
        if ok(row):
            orig, mat = row.parsed['origination_date'], row.parsed['maturity_date']
            fixed = row.parsed.get('fixed_until')
            assert isinstance(orig, date) and isinstance(mat, date)
            if mat <= orig or (isinstance(fixed, date) and not orig < fixed < mat):
                fail(row, 'E11')
    for row in rows[PANEL]:
        loan = register.get(row.values['loan_id'])
        if ok(row) and loan is not None and ok(loan):
            origination = loan.parsed['origination_date']
            assert isinstance(origination, date)
            if row.parsed['as_of_date'] < month_end(origination):  # type: ignore[operator]
                fail(row, 'E11')

    # Rows outside the data window: excluded and counted (W04).
    inside: dict[str, list[Row]] = {LOANS: [r for r in rows[LOANS] if ok(r)]}
    for name in (PANEL, RATES):
        inside[name] = []
        for row in rows[name]:
            if not ok(row):
                continue
            as_of = row.parsed['as_of_date']
            assert isinstance(as_of, date)
            if window_start <= as_of <= window_end:
                inside[name].append(row)
            else:
                result.warnings.append((name, row.line, 'W04'))

    # E05 duplicate keys.
    keys = {LOANS: ('loan_id',), PANEL: ('as_of_date', 'loan_id'), RATES: ('as_of_date', 'rate_id')}
    for name, fields in keys.items():
        seen: set[tuple[str, ...]] = set()
        for row in inside[name]:
            key = tuple(row.values[f] for f in fields)
            if key in seen:
                fail(row, 'E05')
            seen.add(key)
    register = {r.values['loan_id']: r for r in inside[LOANS] if ok(r)}

    # E08 unknown references and inconsistent market series.
    for row in inside[LOANS]:
        pred = row.values['predecessor_id']
        if ok(row) and pred and pred not in register:
            fail(row, 'E08')
    for row in inside[PANEL]:
        if ok(row) and row.values['loan_id'] not in register:
            fail(row, 'E08')
    series: dict[str, tuple[str, str]] = {}
    for row in inside[RATES]:
        if ok(row):
            shape = (row.values['currency'], row.values['tenor_months'])
            if series.setdefault(row.values['rate_id'], shape) != shape:
                fail(row, 'E08')

    # Cross-row panel rules per loan, in date order: E14, E10, E13, E15.
    by_loan: dict[str, list[Row]] = {}
    for row in inside[PANEL]:
        if ok(row):
            by_loan.setdefault(row.values['loan_id'], []).append(row)
    for loan_id, loan_rows in by_loan.items():
        loan_rows.sort(key=lambda r: r.parsed['as_of_date'])  # type: ignore[arg-type, return-value]
        check_loan_history(register[loan_id], loan_rows, fail, ok, result, window_end)
        record_outcomes(register[loan_id], [r for r in loan_rows if ok(r)], result, window_end)

    # E16 RENEG successors (decision D11).
    check_successors(register, inside[PANEL], window_start, window_end, fail, ok, result)

    # E12 missing extract.
    present = {r.parsed['as_of_date'] for r in inside[PANEL]}
    month = month_end(window_start)
    while month <= window_end:
        if month not in present:
            result.errors.append((PANEL, 0, 'E12'))
            result.missing_extracts.append(month.isoformat())
        if month >= window_end:    # never build the month after 9999-12
            break
        month = next_month_end(month)

    # Reconciliation (D12) and control totals (E17, D13), only when the three files have no error.
    if not result.errors:
        result.totals = reconciliation_totals(register, inside[PANEL])
        if (folder / CONTROLS).exists():
            check_controls((folder / CONTROLS).read_bytes(), result)

    result.errors.sort(key=lambda e: (FILE_ORDER.index(e[0]), e[1]))
    result.warnings.sort(key=lambda w: (FILE_ORDER.index(w[0]), w[1], w[2]))
    result.control_differences.sort(key=lambda d: d[0])
    result.gaps.sort()
    return result


def split_file(name: str, data: bytes, result: Result) -> list[Row]:
    """E01: file-level header check, then each row's characters and field count."""
    header = ','.join(HEADERS[name])
    lines = data.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    texts = [line[:-1] if line.endswith(b'\r') else line for line in lines]
    if not texts or not texts[0].isascii() or texts[0].decode('ascii') != header:
        result.errors.append((name, 1, 'E01'))
        return []
    rows: list[Row] = []
    for number, raw in enumerate(texts[1:], start=2):
        fields = raw.decode('ascii').split(',') if raw.isascii() else []
        if len(fields) != len(HEADERS[name]):
            result.errors.append((name, number, 'E01'))
            continue
        rows.append(Row(name, number, dict(zip(HEADERS[name], fields))))
    return rows


def check_loan(row: Row, allowlist: set[str]) -> str | None:
    v, p = row.values, row.parsed
    required = ['loan_id', 'segment', 'currency', 'origination_date', 'maturity_date', 'original_balance',
                'rate_type', 'amortisation', 'payment_months', 'penalty_type']
    if any(not v[f] for f in required):
        return 'E03'
    if v['rate_type'] == 'RESET' and not v['fixed_until']:
        return 'E03'
    if v['rate_type'] in {'FIXED', 'FLOAT'} and v['fixed_until']:
        return 'E03'
    if v['rate_type'] in {'RESET', 'FLOAT'} and not v['reset_months']:
        return 'E03'
    if v['rate_type'] == 'FIXED' and v['reset_months']:
        return 'E03'
    if v['penalty_type'] == 'NONE' and v['penalty_value']:
        return 'E03'
    if v['penalty_type'] in {'PCT', 'MONTHS_INTEREST'} and not v['penalty_value']:
        return 'E03'
    for name in ('origination_date', 'maturity_date', 'fixed_until'):
        if v[name]:
            p[name] = parse_date(v[name])
            if p[name] is None:
                return 'E02'
    balance = parse_decimal(v['original_balance'], 4)
    if not ID_RE.fullmatch(v['loan_id']) or not CCY_RE.fullmatch(v['currency']):
        return 'E04'
    if balance is None or balance <= 0:
        return 'E04'
    if v['predecessor_id'] and not ID_RE.fullmatch(v['predecessor_id']):
        return 'E04'
    if v['reset_months'] and not POSITIVE_INT_RE.fullmatch(v['reset_months']):
        return 'E04'
    if v['penalty_value']:
        penalty = parse_decimal(v['penalty_value'], 8)
        if penalty is None or penalty < 0:
            return 'E04'
    p['original_balance'] = balance
    if (v['segment'] not in SEGMENTS or v['rate_type'] not in RATE_TYPES or v['amortisation'] not in AMORTISATION
            or v['payment_months'] not in PAYMENT_MONTHS or v['penalty_type'] not in PENALTY_TYPES):
        return 'E06'
    if v['currency'] not in allowlist:
        return 'E07'
    return None


def check_panel(row: Row, allowlist: set[str]) -> str | None:
    v, p = row.values, row.parsed
    if any(not v[f] for f in HEADERS[PANEL]):
        return 'E03'
    as_of = parse_date(v['as_of_date'])
    if as_of is None or not is_month_end(as_of):
        return 'E02'
    p['as_of_date'] = as_of
    if not ID_RE.fullmatch(v['loan_id']):
        return 'E04'
    for name, places in (('balance', 4), ('client_rate', 8), ('scheduled_principal', 4),
                         ('prepaid_principal', 4), ('other_change', 4)):
        p[name] = parse_decimal(v[name], places)
        if p[name] is None:
            return 'E04'
    rate = p['client_rate']
    assert isinstance(rate, Decimal)
    if not Decimal('-0.05') <= rate <= Decimal('0.50'):
        return 'E04'
    if v['event'] not in EVENTS:
        return 'E06'
    if any(p[n] < 0 for n in ('balance', 'scheduled_principal', 'prepaid_principal')):  # type: ignore[operator]
        return 'E09'
    return None


def check_rate(row: Row, allowlist: set[str]) -> str | None:
    v, p = row.values, row.parsed
    if any(not v[f] for f in HEADERS[RATES]):
        return 'E03'
    as_of = parse_date(v['as_of_date'])
    if as_of is None or not is_month_end(as_of):
        return 'E02'
    p['as_of_date'] = as_of
    rate = parse_decimal(v['rate'], 8)
    if (not ID_RE.fullmatch(v['rate_id']) or not CCY_RE.fullmatch(v['currency'])
            or not POSITIVE_INT_RE.fullmatch(v['tenor_months'])
            or rate is None or not Decimal('-0.05') <= rate <= Decimal('0.25')):
        return 'E04'
    if v['currency'] not in allowlist:
        return 'E07'
    return None


def check_loan_history(loan: Row, rows: list[Row], fail, ok, result: Result, window_end: date) -> None:
    origination = loan.parsed['origination_date']
    maturity = loan.parsed['maturity_date']
    assert isinstance(origination, date) and isinstance(maturity, date)
    maturity_end = month_end(maturity)
    terminal_seen = False
    previous: Row | None = None
    for row in rows:
        p = row.parsed
        as_of, bal = p['as_of_date'], p['balance']
        sched, prepaid, other = p['scheduled_principal'], p['prepaid_principal'], p['other_change']
        assert isinstance(as_of, date)
        assert isinstance(bal, Decimal) and isinstance(sched, Decimal)
        assert isinstance(prepaid, Decimal) and isinstance(other, Decimal)
        opening: Decimal | None = None
        if previous is not None and previous.parsed['as_of_date'] == previous_month_end(as_of):
            opening = previous.parsed['balance']  # type: ignore[assignment]
        elif previous is None and as_of == month_end(origination):
            opening = loan.parsed['original_balance']  # type: ignore[assignment]
        event = row.values['event']
        if not event_consistent(event, bal, sched, prepaid, other, opening, as_of, maturity_end):
            fail(row, 'E14')
        elif terminal_seen:
            fail(row, 'E10')
        elif opening is not None and abs(bal - (opening - sched - prepaid + other)) > TOLERANCE:
            fail(row, 'E13')
        elif opening is not None and prepaid > opening - sched + max(other, Decimal(0)):
            fail(row, 'E15')    # also on a first row in the origination month, against original_balance (D16)
        if previous is not None and opening is not None and opening > 0 and as_of_of(previous) < maturity_end:
            available = opening - sched + max(other, Decimal(0))
            if available > 0 and event in {'NONE', 'PARTIAL', 'FULL'}:
                result.loan_months[(row.values['loan_id'], row.values['as_of_date'])] = (available, prepaid)
        if other != 0:
            result.warnings.append((PANEL, row.line, 'W03'))
        if bal > 0 and as_of > maturity_end:
            result.warnings.append((PANEL, row.line, 'W05'))
        if previous is not None and ok(row):
            month = previous_month_end(as_of)
            while month > previous.parsed['as_of_date']:  # type: ignore[operator]
                result.warnings.append((PANEL, 0, 'W01'))    # at the missing month: line 0 (D16)
                result.gaps.append((row.values['loan_id'], month.isoformat()))
                month = previous_month_end(month)
        terminal_seen = terminal_seen or event in TERMINAL
        previous = row
    if previous is not None and not terminal_seen and previous.parsed['as_of_date'] < window_end:  # type: ignore[operator]
        result.warnings.append((PANEL, previous.line, 'W02'))


def record_outcomes(loan: Row, rows: list[Row], result: Result, window_end: date) -> None:
    """Risk set, missing observations and censoring: one outcome per loan-month starting at a non-terminal row."""
    maturity = loan.parsed['maturity_date']
    assert isinstance(maturity, date)
    maturity_end = month_end(maturity)
    for index, row in enumerate(rows):
        if row.values['event'] in TERMINAL:
            continue
        start = as_of_of(row)
        later = rows[index + 1:]
        if start >= maturity_end:
            outcome = 'PAST_MATURITY'
        elif start == window_end:
            outcome = 'END_OF_WINDOW'
        elif later and as_of_of(later[0]) == next_month_end(start):
            outcome = later[0].values['event']
        elif later:
            outcome = 'GAP'
        else:
            outcome = 'CENSORED'
        result.outcomes[(row.values['loan_id'], start.isoformat())] = outcome


def event_consistent(event: str, bal: Decimal, sched: Decimal, prepaid: Decimal, other: Decimal,
                     opening: Decimal | None, as_of: date, maturity_end: date) -> bool:
    if event == 'NONE':
        return prepaid == 0 and bal > 0
    if event == 'PARTIAL':
        return prepaid > 0 and bal > 0
    if event == 'FULL':
        return prepaid > 0 and bal == 0 and as_of < maturity_end
    if event == 'MATURITY':
        return bal == 0 and as_of == maturity_end
    if event in {'DEFAULT', 'SALE'}:
        return prepaid == 0
    # RENEG
    if prepaid != 0 or bal != 0 or opening is None:
        return False
    return sched <= opening and other == -(opening - sched)


def check_successors(register: dict[str, Row], panel: list[Row], window_start: date, window_end: date,
                     fail, ok, result: Result) -> None:
    successors: dict[str, list[Row]] = {}
    for loan in register.values():
        pred = loan.values['predecessor_id']
        if pred == loan.values['loan_id']:
            fail(loan, 'E16')    # D6: a modification continues under a new loan_id
        elif pred:
            successors.setdefault(pred, []).append(loan)
    reneg = {r.values['loan_id']: r for r in panel if ok(r) and r.values['event'] == 'RENEG'}
    for loan_id, row in reneg.items():
        found = successors.get(loan_id, [])
        transferred = -row.parsed['other_change']  # type: ignore[operator]
        if transferred <= TOLERANCE:    # D15: a zero-residual RENEG needs no successor and may have none
            for successor in found:
                fail(successor, 'E16')
            continue
        if len(found) != 1:
            fail(row, 'E16')
            continue
        successor, predecessor = found[0], register[loan_id]
        if (month_end(successor.parsed['origination_date']) != row.parsed['as_of_date']  # type: ignore[arg-type]
                or successor.values['currency'] != predecessor.values['currency']
                or abs(successor.parsed['original_balance'] - transferred) > TOLERANCE):
            fail(row, 'E16')
        elif successor.values['segment'] != predecessor.values['segment']:
            result.warnings.append((LOANS, successor.line, 'W06'))
    for pred_id, found in successors.items():
        for successor in found:
            start = month_end(successor.parsed['origination_date'])  # type: ignore[arg-type]
            if window_start <= start <= window_end and ok(successor):
                ending = reneg.get(pred_id)
                if ending is None or ending.parsed['as_of_date'] != start:
                    fail(successor, 'E16')


# ---------------------------------------------------------------------------
# Point-in-time availability
# ---------------------------------------------------------------------------

def read_rows(folder: Path) -> dict[str, list[dict[str, str]]]:
    """The register and panel rows of an import as field values, without validation."""
    rows: dict[str, list[dict[str, str]]] = {}
    for name in (LOANS, PANEL):
        lines = (folder / name).read_text(encoding='ascii').splitlines()
        rows[name] = [dict(zip(HEADERS[name], line.split(','))) for line in lines[1:]]
    return rows


def point_in_time_view(rows: dict[str, list[dict[str, str]]], origin: date) -> dict[str, list[tuple[str, ...]]]:
    """Register rows of loans originated on or before the origin and panel rows dated on or before it."""
    def known(text: str) -> bool:
        value = parse_date(text)
        return value is not None and value <= origin

    view = {LOANS: [r for r in rows[LOANS] if known(r['origination_date'])],
            PANEL: [r for r in rows[PANEL] if known(r['as_of_date'])]}
    return {name: sorted(tuple(r[f] for f in HEADERS[name]) for r in kept) for name, kept in view.items()}


# ---------------------------------------------------------------------------
# Reconciliation (D12) and control totals (D13)
# ---------------------------------------------------------------------------

def reconciliation_totals(register: dict[str, Row], panel: list[Row]) -> dict[tuple[str, ...], dict[str, Decimal]]:
    totals: dict[tuple[str, ...], dict[str, Decimal]] = {}
    for row in panel:
        loan = register[row.values['loan_id']]
        key = (row.values['as_of_date'], loan.values['segment'], loan.values['currency'])
        total = totals.setdefault(key, {m: Decimal(0) for m in RECON_MEASURES})
        p, event = row.parsed, row.values['event']
        total['loans'] += 1
        for name in ('balance', 'scheduled_principal', 'other_change'):
            total[name] += p[name]  # type: ignore[operator]
        if event in {'PARTIAL', 'FULL'}:
            total[f'prepaid_{event.lower()}'] += p['prepaid_principal']  # type: ignore[operator]
        if event in TERMINAL:
            total[f'{event.lower()}_count'] += 1
            total[f'{event.lower()}_balance'] += p['balance']  # type: ignore[operator]
    return totals


def parse_control(values: dict[str, str]) -> dict[str, Decimal] | None:
    """A control row's measures, or None when a cell is empty or does not parse."""
    as_of = parse_date(values['as_of_date'])
    if (as_of is None or not is_month_end(as_of) or values['segment'] not in SEGMENTS
            or not CCY_RE.fullmatch(values['currency'])):
        return None
    measures: dict[str, Decimal] = {}
    for name in RECON_MEASURES:
        text = values[name]
        value = (Decimal(text) if COUNT_RE.fullmatch(text) else None) if name in COUNT_MEASURES \
            else parse_decimal(text, 4)
        if value is None:
            return None
        measures[name] = value
    return measures


def check_controls(data: bytes, result: Result) -> None:
    def differ(line: int, key: tuple[str, ...], measure: str) -> None:
        result.errors.append((CONTROLS_TABLE, line, 'E17'))
        result.control_differences.append((line, '|'.join(key), measure))

    header = ','.join(KEY + RECON_MEASURES)
    texts = [t[:-1] if t.endswith(b'\r') else t for t in data.split(b'\n')]
    if texts and texts[-1] == b'':
        texts.pop()
    if not texts or texts[0] != header.encode('ascii'):
        differ(1, (), '')
        return
    if len(texts) == 1:    # an empty Controls_Totals table: no control totals were supplied
        return
    controls: dict[tuple[str, ...], tuple[int, dict[str, Decimal] | None]] = {}
    for line, raw in enumerate(texts[1:], start=2):
        fields = raw.decode('ascii').split(',') if raw.isascii() else []
        values = dict(zip(KEY + RECON_MEASURES, fields)) if len(fields) == len(KEY + RECON_MEASURES) else None
        key = tuple(values[k] for k in KEY) if values else ()
        measures = parse_control(values) if values and all(values.values()) else None
        if measures is None or key in controls:
            differ(line, key, '')
        if key and key not in controls:
            controls[key] = (line, measures)    # an invalid row still stands for its key
    for key in sorted(set(result.totals) | set(controls)):
        line, measures = controls.get(key, (0, None))
        if key in controls and measures is None:
            continue
        computed = result.totals.get(key)
        for name in RECON_MEASURES:
            # Counts parse as integers only, so the amount tolerance compares them exactly.
            if measures is None or computed is None or abs(measures[name] - computed[name]) > TOLERANCE:
                differ(line, key, name)
