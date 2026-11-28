"""Derive the decimal expected values of the RATE-* cases exactly, without rates.py.

Run offline: ``python tests/reference/derive_rates.py`` prints the values that the expected
files RATE-CONV-01, RATE-CONV-02 and RATE-PERIOD-01 hold; test_reference_cases.py checks
that the committed files still equal this derivation. Rational values are computed with
fractions.Fraction and are exact before the final rounding; the twelfth root of the
CPR -> SMM direction uses decimal arithmetic at 60 significant digits. Every value is
rounded half-even to 40 significant digits. The amounts and SMM fractions of the RATE-POOL
cases are hand computations written into their expected files directly.
"""
from __future__ import annotations

import json
from decimal import Context, Decimal, localcontext
from fractions import Fraction

DIGITS = 40
GRID = ('0', '1e-8', '0.02', '0.5', '0.999999', '1')
PERIOD_SMMS = ('0.01', '0.02', '0.03', '0.015', '0', '0.025', '0.05', '0.01', '0.02', '0.005', '0.03', '0.04')


def text(value: Fraction | Decimal) -> str:
    """value rounded to DIGITS significant digits, in plain notation."""
    if isinstance(value, Fraction):
        with localcontext(Context(prec=DIGITS + 40)):
            exact = Decimal(value.numerator) / Decimal(value.denominator)
    else:
        exact = value
    rounded = Context(prec=DIGITS).plus(exact)
    return format(rounded, 'f') if rounded else '0'


def cpr_exact(smm: Fraction) -> Fraction:
    return 1 - (1 - smm) ** 12


def smm_from_cpr(cpr: Fraction) -> Decimal:
    if cpr == 1:
        return Decimal(1)
    with localcontext(Context(prec=DIGITS + 20)):
        base = Decimal(cpr.numerator) / Decimal(cpr.denominator)
        return 1 - (1 - base) ** (Decimal(1) / Decimal(12))


def realised_cpr(smms: list[Fraction]) -> Fraction:
    survival = Fraction(1)
    for smm in smms:
        survival *= 1 - smm
    exponent = Fraction(12, len(smms))
    if exponent.denominator != 1:
        raise ValueError('the registered windows have 12 / n integral')
    return 1 - survival ** exponent.numerator


def derive() -> dict[str, dict[str, object]]:
    grid = [Fraction(value) for value in GRID]
    period = [Fraction(value) for value in PERIOD_SMMS]
    worked_smm = Fraction(2_000, 99_000)
    worked_cpr = cpr_exact(worked_smm)
    windows: dict[str, dict[str, str]] = {}
    for n in (3, 12):
        cprs = [cpr_exact(smm) for smm in period[:n]]
        windows[str(n)] = {'realised_cpr': text(realised_cpr(period[:n])),
                           'average_of_monthly_cprs': text(sum(cprs, Fraction(0)) / n)}
    return {
        'RATE-CONV-01': {'smm_to_cpr': {g: text(cpr_exact(s)) for g, s in zip(GRID, grid)},
                         'cpr_to_smm': {g: text(smm_from_cpr(c)) for g, c in zip(GRID, grid)}},
        'RATE-CONV-02': {'cpr': text(worked_cpr), 'cpr_over_12': text(worked_cpr / 12)},
        'RATE-PERIOD-01': {'windows': windows},
    }


if __name__ == '__main__':
    print(json.dumps(derive(), indent=2))
