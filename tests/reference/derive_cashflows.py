"""Derive the expected values of the CF-* and SCN-* cases exactly, without cashflows.py or scenarios.py.

Run offline: ``python tests/reference/derive_cashflows.py`` prints the values that the expected
files CF-SCHED-01, CF-PREPAY-01, CF-RESET-01, SCN-BASE-01 and SCN-MONO-01 hold;
test_reference_cashflows.py checks that the committed files still equal this derivation.

The schedules of the CF cases are computed month by month in rationals (fractions.Fraction),
exact before the final rounding. Every CPR in their fixtures is 1 - (1 - s)^12 for a rational
SMM s, which is recovered by an exact integer twelfth root, so no rounded root enters. The
annuity instalment is B j (1 + j)^n / ((1 + j)^n - 1) with j = client_rate / 12 and n the
remaining monthly payments, B / n at j = 0. The scenario views use decimal arithmetic at 60
significant digits for exp and the twelfth root. Every value is rounded half-even to 30
significant digits.
"""
from __future__ import annotations

import calendar
import csv
import json
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests' / 'fixtures'
DIGITS = 30
MEASURES = ('opening', 'interest', 'scheduled', 'prepaid', 'repricing', 'closing')
SCENARIO_BOOK = 'SCN-BASE-01'
VIEW_LOANS = ('B1', 'B7')
VIEW_SHOCK = Decimal('0.02')


def text(value: Fraction | Decimal) -> str:
    """value rounded to DIGITS significant digits, in plain notation."""
    if isinstance(value, Fraction):
        with localcontext(Context(prec=DIGITS + 40)):
            value = Decimal(value.numerator) / Decimal(value.denominator)
    rounded = Context(prec=DIGITS).normalize(value)
    return format(rounded, 'f') if rounded else '0'


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='ascii', newline='') as handle:
        return list(csv.DictReader(handle))


def month(iso: str) -> int:
    """Months since year 0 of the month holding an ISO date."""
    return int(iso[:4]) * 12 + int(iso[5:7]) - 1


def month_end(index: int) -> str:
    year, month0 = divmod(index, 12)
    return f'{year:04d}-{month0 + 1:02d}-{calendar.monthrange(year, month0 + 1)[1]:02d}'


def integer_root(value: int, degree: int) -> int:
    root = int(float(value) ** (1.0 / degree) + 0.5)
    for candidate in (root - 1, root, root + 1):
        if candidate >= 0 and candidate ** degree == value:
            return candidate
    raise ValueError(f'{value} is not an exact power {degree}')


def smm_of(cpr: str) -> Fraction:
    """SMM = 1 - (1 - CPR)^(1/12), exactly, for a fixture CPR that is 1 - (1 - s)^12."""
    survival = 1 - Fraction(cpr)
    return 1 - Fraction(integer_root(survival.numerator, 12), integer_root(survival.denominator, 12))


def next_reset(loan: dict[str, str], as_of: int) -> int | None:
    if loan['rate_type'] == 'FIXED':
        return None
    step = int(loan['reset_months'])
    first = month(loan['fixed_until']) if loan['rate_type'] == 'RESET' else month(loan['origination_date'])
    if loan['rate_type'] == 'RESET' and first > as_of:
        return first
    return first + step * ((as_of - first) // step + 1)


def schedule(loan: dict[str, str], position: dict[str, str], smms: dict[tuple[str, int], Fraction]
             ) -> dict[str, list[str]]:
    as_of, maturity = month(position['as_of_date']), month(loan['maturity_date'])
    step, kind = int(loan['payment_months']), loan['amortisation']
    reset = next_reset(loan, as_of)
    assert reset != maturity
    end = reset if reset is not None and reset < maturity else maturity
    if kind == 'BULLET':
        payments = {maturity}
    else:
        assert (maturity - month(loan['origination_date'])) % step == 0, 'payment anchors differ'
        assert kind == 'LINEAR' or step == 1, 'annuity periodic rate not fixed by the contract'
        payments = {m for m in range(as_of + 1, maturity + 1) if (maturity - m) % step == 0}
    j = Fraction(position['client_rate']) / 12
    balance = Fraction(position['balance'])
    out: dict[str, list[str]] = {name: [] for name in ('months', *MEASURES, 'instalment')}
    for m in range(as_of + 1, end + 1):
        opening, smm = balance, smms.get((loan['loan_id'], m), Fraction(0))
        scheduled = prepaid = repricing = Fraction(0)
        if m == reset:
            assert smm == 0 and (m not in payments or kind == 'BULLET'), 'reset-month treatment not fixed'
            repricing = opening
        else:
            if m in payments:
                n = sum(1 for p in payments if p >= m)
                if kind == 'BULLET':
                    scheduled = opening
                elif kind == 'LINEAR':
                    scheduled = opening / n
                elif j == 0:
                    scheduled = opening / n
                else:
                    growth = (1 + j) ** n
                    scheduled = opening * j * growth / (growth - 1) - j * opening
            prepaid = smm * (opening - scheduled)
        balance = opening - scheduled - prepaid - repricing
        values = (opening, j * opening, scheduled, prepaid, repricing, balance, j * opening + scheduled)
        out['months'].append(month_end(m))
        for name, value in zip((*MEASURES, 'instalment'), values):
            out[name].append(text(value))
    return out


def derive_book(case: str, instalments: bool) -> dict[str, dict[str, list[str]]]:
    folder = FIXTURES / case
    loans = {row['loan_id']: row for row in rows(folder / 'loans.csv')}
    smms = {(row['loan_id'], month(row['as_of_date'])): smm_of(row['cpr'])
            for row in (rows(folder / 'cpr.csv') if (folder / 'cpr.csv').exists() else [])}
    result = {}
    for position in rows(folder / 'positions.csv'):
        flows = schedule(loans[position['loan_id']], position, smms)
        if not instalments:
            del flows['instalment']
        result[position['loan_id']] = flows
    return result


def scenario_view(loan_id: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """PM1 CPR of one loan under a parallel shock of -200bp, 0 and +200bp, and its BASE cash flows."""
    folder = FIXTURES / SCENARIO_BOOK
    settings = {row['name']: Decimal(row['value']) for row in rows(folder / 'settings.csv')}
    loan = next(row for row in rows(folder / 'loans.csv') if row['loan_id'] == loan_id)
    position = next(row for row in rows(folder / 'positions.csv') if row['loan_id'] == loan_id)
    as_of = month(position['as_of_date'])
    curve = next(Decimal(row['rate']) for row in rows(folder / 'market_rates.csv')
                 if row['currency'] == loan['currency'] and month(row['as_of_date']) == as_of)
    assert settings['b'] == 0 and settings['lag'] == 1 and loan['rate_type'] == 'FIXED'
    assert loan['amortisation'] == 'ANNUITY' and loan['payment_months'] == '1' and loan['penalty_type'] == 'NONE'
    months = list(range(as_of + 1, month(loan['maturity_date']) + 1))
    mono: dict[str, list[str]] = {'months': [month_end(m) for m in months]}
    base: dict[str, list[str]] = {'months': mono['months']}
    with localcontext(Context(prec=60)):
        client = Decimal(position['client_rate'])
        paths: dict[str, list[Decimal]] = {}
        for name, shock in (('PAR_DOWN', -VIEW_SHOCK), ('BASE', Decimal(0)), ('PAR_UP', VIEW_SHOCK)):
            incentive = client - (curve + shock + settings['margin'])
            s_curve = 1 / (1 + (-settings['k'] * (incentive - settings['x0'])).exp())
            paths[name] = []
            for m in months:
                age = m - 1 - month(loan['origination_date'])    # origination month end to t - 1
                ramp = Decimal(1) if settings['a_ramp'] == 0 else min(Decimal(1), age / settings['a_ramp'])
                season = settings[f'season_{m % 12 + 1:02d}']
                level = (settings['c_min'] + (settings['c_max'] - settings['c_min']) * s_curve) * ramp * season
                paths[name].append(min(Decimal(1), max(Decimal(0), level)))
            mono[name] = [text(cpr) for cpr in paths[name]]
        j = client / 12
        balance = Decimal(position['balance'])
        flows: dict[str, list[str]] = {name: [] for name in ('cpr', 'smm', *MEASURES)}
        for i, cpr in enumerate(paths['BASE']):
            n = len(months) - i
            growth = (1 + j) ** n
            scheduled = balance if n == 1 else balance * j * growth / (growth - 1) - j * balance
            smm = 1 - (1 - cpr) ** (Decimal(1) / 12)
            prepaid = smm * (balance - scheduled)
            closing = balance - scheduled - prepaid
            for name, value in zip(flows, (cpr, smm, balance, j * balance, scheduled, prepaid, Decimal(0), closing)):
                flows[name].append(text(value))
            balance = closing
        base.update(flows)
    return base, mono


def scenario_views() -> tuple[dict[str, dict[str, list[str]]], dict[str, dict[str, list[str]]]]:
    views = {loan_id: scenario_view(loan_id) for loan_id in VIEW_LOANS}
    return {k: v[0] for k, v in views.items()}, {k: v[1] for k, v in views.items()}


def derive() -> dict[str, dict[str, object]]:
    base_view, mono_view = scenario_views()
    return {
        'CF-SCHED-01': {'loans': derive_book('CF-SCHED-01', False)},
        'CF-PREPAY-01': {'loans': derive_book('CF-PREPAY-01', True)},
        'CF-RESET-01': {'loans': derive_book('CF-RESET-01', False)},
        'SCN-BASE-01': {'views': base_view},
        'SCN-MONO-01': {'views': mono_view},
    }


if __name__ == '__main__':
    print(json.dumps(derive(), indent=2))
