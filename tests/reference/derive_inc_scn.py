"""Derive the expected values of INC-CALC-01, INC-CURVE-01, SCN-FLOOR-01 and SCN-GAMMA-01 exactly.

Run offline: ``python tests/reference/derive_inc_scn.py`` prints the values that those expected
files hold; tools/test_reference_inc_scn.py checks that the committed files still equal this
derivation. It reads the fixtures with the csv module and computes in fractions.Fraction, so
every value is exact; it does not import incentive.py or overlay.py and finds curve nodes by
bracketing in months rather than by walking sorted segments. A value whose denominator has
only the factors 2 and 5 is written as a plain decimal, any other as ``numerator/denominator``.
The term ends of INC-CALC-01 and the rate dates of INC-LAG-01 are hand assignments written
into their expected files directly.
"""
from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
INC_CALC_SERIES = ['EUR_SWAP_120M', 'EUR_SWAP_12M', 'EUR_SWAP_60M', 'USD_SWAP_36M', 'USD_SWAP_84M']
INC_CALC_MARGINS = {'MTG_FIX': '0.005', 'MTG_RST': '0.0075', 'CON_FIX': '0.012'}
INC_CURVE_SERIES = ['EUR_SWAP_120M', 'EUR_SWAP_12M', 'EUR_SWAP_60M', 'EUR_SWAP_24M', 'USD_SWAP_120M',
                    'USD_SWAP_12M']
GAMMA = {'PAR_UP': '0.8', 'STEEPENER': '0.8', 'SHORT_UP': '0.8', 'PAR_DOWN': '1.2', 'FLATTENER': '1.2',
         'SHORT_DOWN': '1.2'}


def text(value: Fraction) -> str:
    """Plain decimal when the value terminates, otherwise ``numerator/denominator``."""
    rest = value.denominator
    for factor in (2, 5):
        while rest % factor == 0:
            rest //= factor
    if rest != 1:
        return str(value)
    exact = Decimal(value.numerator) / Decimal(value.denominator)
    return format(exact.normalize(), 'f') if value else '0'


def rows(case: str, name: str) -> list[dict[str, str]]:
    with (FIXTURES / case / name).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def previous_month_end(t: date) -> date:
    """t - 1 month for a month end t: the day before the first of t's month."""
    return t.replace(day=1) - timedelta(days=1)


def inc_calc() -> dict[str, object]:
    market = rows('INC-CALC-01', 'market_rates.csv')
    result: dict[str, dict[str, str]] = {}
    for month in rows('INC-CALC-01', 'loan_months.csv'):
        s = previous_month_end(date.fromisoformat(month['as_of_date']))
        nodes = [Fraction(r['rate']) for r in market if r['rate_id'] in INC_CALC_SERIES
                 and r['currency'] == month['currency'] and r['as_of_date'] == s.isoformat()]
        if not nodes or any(nodes):
            raise ValueError(f'{month["loan_id"]}: the derivation needs a configured curve of zeros at {s}')
        client, term = Fraction(month['client_rate']), Fraction(month['term_years'])
        margin = Fraction(INC_CALC_MARGINS[month['segment']])
        value = Fraction(month['penalty_value'] or 0)
        charge = {'NONE': Fraction(0), 'PCT': value / max(term, Fraction(1)),
                  'MONTHS_INTEREST': value * client / 12 / max(term, Fraction(1))}[month['penalty_type']]
        result[f'{month["loan_id"]}|{month["as_of_date"]}'] = {
            'rate_date': s.isoformat(), 'refinancing_rate': '0', 'margin': text(margin), 'penalty': text(charge),
            'incentive': text(client - margin - charge)}
    return {'settings': {'lag_months': 1, 'refi_curve_series': INC_CALC_SERIES, 'margins': INC_CALC_MARGINS},
            'incentives': result}


def curve_rate(market: list[dict[str, str]], s: str, currency: str, term_years: Fraction) -> Fraction:
    """Bracket T x 12 months between the configured tenors; flat beyond the outermost."""
    nodes = {int(r['tenor_months']): Fraction(r['rate']) for r in market
             if r['rate_id'] in INC_CURVE_SERIES and r['currency'] == currency and r['as_of_date'] == s}
    months = term_years * 12
    below = [tenor for tenor in nodes if tenor <= months]
    above = [tenor for tenor in nodes if tenor >= months]
    if not below:
        return nodes[min(nodes)]
    if not above:
        return nodes[max(nodes)]
    low, high = max(below), min(above)
    if low == high:
        return nodes[low]
    return nodes[low] + (nodes[high] - nodes[low]) * (months - low) / (high - low)


def inc_curve() -> dict[str, object]:
    market = rows('INC-CURVE-01', 'market_rates.csv')
    return {'settings': {'refi_curve_series': INC_CURVE_SERIES},
            'rates': {q['label']: text(curve_rate(market, q['as_of_date'], q['currency'], Fraction(q['term_years'])))
                      for q in rows('INC-CURVE-01', 'queries.csv')}}


def scn_floor() -> dict[str, object]:
    points: dict[str, dict[str, str]] = {}
    for point in rows('SCN-FLOOR-01', 'points.csv'):
        maturity, observed = Fraction(point['maturity_years']), Fraction(point['observed'])
        shocked = Fraction(point['shocked'])
        floor = min(observed, min(Fraction(0), Fraction(-150, 10_000) + Fraction(3, 10_000) * maturity))
        points[point['label']] = {'floor': text(floor), 'floored': text(max(shocked, floor))}
    return {'points': points}


def scn_gamma() -> dict[str, object]:
    base = {row['label']: Fraction(row['cpr_base']) for row in rows('SCN-GAMMA-01', 'cpr_base.csv')}
    cpr = {scenario: {label: text(min(Fraction(1), Fraction(gamma) * value)) for label, value in base.items()}
           for scenario, gamma in GAMMA.items()}
    cpr['BASE'] = {label: text(value) for label, value in base.items()}
    return {'gamma': GAMMA, 'cpr': cpr}


def derive() -> dict[str, dict[str, object]]:
    return {'INC-CALC-01': inc_calc(), 'INC-CURVE-01': inc_curve(), 'SCN-FLOOR-01': scn_floor(),
            'SCN-GAMMA-01': scn_gamma()}


if __name__ == '__main__':
    print(json.dumps(derive(), indent=2))
