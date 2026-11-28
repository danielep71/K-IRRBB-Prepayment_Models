"""Derive the expected values of EVE-PV-01 and MEAS-01 exactly, without eve.py.

Run offline: ``python tests/reference/derive_eve.py`` prints the values that the expected
files EVE-PV-01 and MEAS-01 hold; test_reference_eve.py checks that the committed files
still equal this derivation. The fixtures are read with the csv module and every amount and
rate becomes a fractions.Fraction. Interpolated zero rates, weighted average repricing
times, monthly SMMs and their products are exact; exp() and the non-integral powers of the
projected CPR use decimal arithmetic at 60 significant digits. Every value is rounded
half-even to 40 significant digits. The values of EVE-DELTA-01, EVE-RATIO-01, GAP-BUCKET-01,
GAP-CONS-01 and the effective-duration cases of MEAS-01 with PV_BASE <= 0 are hand
computations written into their expected files directly.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

DIGITS = 40
WORK = 60
FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
# Nominal parallel shock of EUR in REG-3 Annex, Part A (200 bp), as a decimal per annum.
PARALLEL_SHOCK = {'EUR': '0.02'}

Flows = dict[str, list[dict[str, Fraction]]]


def text(value: Fraction | Decimal) -> str:
    """value rounded to DIGITS significant digits, in plain notation."""
    if isinstance(value, Fraction):
        with localcontext(Context(prec=DIGITS + 40)):
            exact = Decimal(value.numerator) / Decimal(value.denominator)
    else:
        exact = value
    rounded = Context(prec=DIGITS).plus(exact)
    return format(rounded, 'f') if rounded else '0'


def decimal(value: Fraction) -> Decimal:
    with localcontext(Context(prec=WORK)):
        return Decimal(value.numerator) / Decimal(value.denominator)


def read_flows(case: str) -> Flows:
    """{'scenario|segment|currency': [row, ...]} with every number as a Fraction, in file order."""
    flows: Flows = defaultdict(list)
    with (FIXTURES / case / 'cash_flows.csv').open(encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            key = '|'.join((row['scenario'], row['segment'], row['currency']))
            flows[key].append({name: Fraction(value) for name, value in row.items()
                               if name not in ('scenario', 'segment', 'currency')})
    return dict(flows)


def read_curves(case: str) -> dict[str, list[tuple[Fraction, Fraction]]]:
    """{'scenario|currency': [(tenor in years, zero rate), ...]} sorted by tenor."""
    curves: dict[str, list[tuple[Fraction, Fraction]]] = defaultdict(list)
    with (FIXTURES / case / 'curves.csv').open(encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            curves[f'{row["scenario"]}|{row["currency"]}'].append(
                (Fraction(int(row['tenor_months']), 12), Fraction(row['zero_rate'])))
    return {key: sorted(points) for key, points in curves.items()}


def zero(points: list[tuple[Fraction, Fraction]], years: Fraction) -> Fraction:
    """Linear in rate between neighbouring tenors; the end rates held flat outside them."""
    if years <= points[0][0]:
        return points[0][1]
    if years >= points[-1][0]:
        return points[-1][1]
    i = max(j for j, (tenor, _) in enumerate(points) if tenor <= years)
    (t0, z0), (t1, z1) = points[i], points[i + 1]
    return z0 + (z1 - z0) * (years - t0) / (t1 - t0)


def discount(points: list[tuple[Fraction, Fraction]], k: Fraction) -> Decimal:
    years = k / 12
    with localcontext(Context(prec=WORK)):
        return (-decimal(zero(points, years) * years)).exp()


def present_value(rows: list[dict[str, Fraction]], points: list[tuple[Fraction, Fraction]]) -> Decimal:
    with localcontext(Context(prec=WORK)):
        total = Decimal(0)
        for row in rows:
            flow = row['interest'] + row['scheduled'] + row['prepaid'] + row['repricing']
            total += decimal(flow) * discount(points, row['k'])
        return total


def curve_of(key: str) -> str:
    scenario, _, currency = key.split('|')
    return f'{scenario}|{currency}'


def eve_pv() -> dict[str, object]:
    flows, curves = read_flows('EVE-PV-01'), read_curves('EVE-PV-01')
    points: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    values: dict[str, Decimal] = {}
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for key, rows in flows.items():
        curve = curves[curve_of(key)]
        for row in rows:
            k = row['k']
            points[curve_of(key)][str(k)] = {'zero_rate': text(zero(curve, k / 12)),
                                             'discount_factor': text(discount(curve, k))}
        values[key] = present_value(rows, curve)
        with localcontext(Context(prec=WORK)):
            totals[curve_of(key)] += values[key]
    return {'curves': {c: dict(sorted(p.items(), key=lambda item: int(item[0]))) for c, p in sorted(points.items())},
            'present_values': {key: text(value) for key, value in sorted(values.items())},
            'currency_totals': {key: text(value) for key, value in sorted(totals.items())}}


def compounded(smms: list[Fraction]) -> Fraction | Decimal:
    """1 - (prod (1 - SMM))^(12/n), exactly when 12/n is an integer."""
    survival = Fraction(1)
    for smm in smms:
        survival *= 1 - smm
    exponent = Fraction(12, len(smms))
    if exponent.denominator == 1:
        return 1 - survival ** exponent.numerator
    with localcontext(Context(prec=WORK)):
        return 1 - decimal(survival) ** decimal(exponent)


def projected(rows: list[dict[str, Fraction]], last: int | None) -> dict[str, object]:
    smms = [row['prepaid'] / (row['opening'] - row['scheduled']) for row in rows
            if row['opening'] - row['scheduled'] > 0 and (last is None or row['k'] <= last)]
    return {'months': len(smms), 'cpr': text(compounded(smms)) if smms else None}


def meas() -> dict[str, object]:
    flows, curves = read_flows('MEAS-01'), read_curves('MEAS-01')
    timing, cpr = {}, {}
    for key, rows in sorted(flows.items()):
        principal = [(row['k'], row['scheduled'] + row['prepaid'] + row['repricing']) for row in rows]
        weighted = sum((k / 12 * p for k, p in principal), Fraction(0))
        timing[key] = text(weighted / sum((p for _, p in principal), Fraction(0)))
        cpr[key] = {'first_12_months': projected(rows, 12), 'projection': projected(rows, None)}
    duration = {}
    for currency, shock in PARALLEL_SHOCK.items():
        pools = {key.split('|', 1)[1] for key in flows if key.endswith(f'|{currency}')}
        for pool in sorted(pools):
            names = [f'{s}|{pool}' for s in ('BASE', 'PAR_DOWN', 'PAR_UP')]
            if not all(name in flows for name in names):
                continue
            base, down, up = (present_value(flows[name], curves[curve_of(name)]) for name in names)
            with localcontext(Context(prec=WORK)):
                duration[pool] = {'pv_base': text(base), 'pv_par_down': text(down), 'pv_par_up': text(up),
                                  'effective_duration': text((down - up) / (2 * base * Decimal(shock)))}
    return {'parallel_shock': PARALLEL_SHOCK, 'repricing_time': timing, 'projected_cpr': cpr,
            'effective_duration': duration}


def derive() -> dict[str, dict[str, object]]:
    return {'EVE-PV-01': eve_pv(), 'MEAS-01': meas()}


if __name__ == '__main__':
    print(json.dumps(derive(), indent=2))
