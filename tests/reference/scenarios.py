"""Independent reference for scenario CPR paths (MODEL_CONTRACTS.md, Scenarios, Rate incentive, PM1).

Written from the contract, not from toolkit source. A scenario is a shocked refinancing curve
applied at the as-of date and held; it reaches the model only through the incentive
I = client_rate - (R + m) - penalty, which drives the PM1 S-curve at fixed parameters:

    CPR = min(1, max(0, [c_min + (c_max - c_min) x B x logistic(k x (I - x0))] x Ramp(age) x Season(month)))

The CPR path then drives the projection of cashflows.py. With the lag of decision M4 (one month)
every projected month reads the curve at or after the as-of date, which is the held scenario
curve. Inputs the contract leaves open are refused with ContractQuestion: a curve of more than
one series in a currency (the remaining term T in years is not defined to the day), a penalty
other than NONE (it also needs T), a burnout strength b other than 0 (the pool factor of a
projected month is not defined) and a shocked rate below zero, where the post-shock floor of
SCN-FLOOR-01 could bind.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import cashflows
from cashflows import ContractQuestion, Month, Position

RATE_FIELDS = ('as_of_date', 'rate_id', 'currency', 'tenor_months', 'rate')
SETTING_FIELDS = ('name', 'value')
SEASON_NAMES = tuple(f'season_{m:02d}' for m in range(1, 13))


@dataclass(frozen=True)
class PM1:
    c_min: float
    c_max: float
    k: float
    x0: float
    a_ramp: float    # seasoning months to full speed
    season: tuple[float, ...]    # factors for January to December
    b: float    # burnout strength

    def __post_init__(self) -> None:
        if not 0.0 <= self.c_min <= self.c_max <= 1.0:
            raise ValueError('PM1 needs 0 <= c_min <= c_max <= 1')
        if not self.k > 0.0:
            raise ValueError('PM1 needs k > 0')
        if not self.a_ramp >= 0.0:
            raise ValueError('PM1 needs a_ramp >= 0')
        if len(self.season) != 12 or min(self.season) < 0.0 or abs(math.fsum(self.season) / 12.0 - 1.0) > 1e-12:
            raise ValueError('PM1 needs 12 nonnegative seasonal factors with mean 1')
        if self.b != 0.0:
            raise ContractQuestion('burnout in a projected month: the pool factor is not defined there')


@dataclass(frozen=True)
class Settings:
    params: PM1
    margin: float    # new-business margin m (M5)
    lag: int    # incentive lag L in months (M4)


def logistic(z: float) -> float:
    """1 / (1 + exp(-z)), without overflow for large |z|."""
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def pm1_cpr(params: PM1, incentive: float, age: int, month: int) -> float:
    """PM1 CPR at fixed parameters; burnout B = 1 because b = 0."""
    ramp = 1.0 if params.a_ramp == 0.0 else min(1.0, age / params.a_ramp)
    curve = params.c_min + (params.c_max - params.c_min) * logistic(params.k * (incentive - params.x0))
    return min(1.0, max(0.0, curve * ramp * params.season[month - 1]))


def incentive(client_rate: float, refinancing_rate: float, margin: float) -> float:
    """I = client_rate - (R + m) - penalty, with penalty type NONE."""
    return client_rate - (refinancing_rate + margin)


def shocked_curve(curve: dict[str, float], shock: float) -> dict[str, float]:
    """A parallel shock applied at the as-of date and held, per currency."""
    result = {currency: rate + shock for currency, rate in curve.items()}
    if shock != 0.0 and any(rate < 0.0 for rate in result.values()):
        raise ContractQuestion('a shocked rate below zero: the post-shock floor may bind')
    return result


def cpr_path(position: Position, curve: dict[str, float], settings: Settings) -> list[float]:
    """PM1 CPR of each projected month of a FIXED loan under one curve."""
    loan, as_of = position.loan, position.as_of_date
    if loan.rate_type != 'FIXED':
        raise ValueError(f'{loan.loan_id}: the scenario reference projects FIXED loans only')
    if loan.penalty_type != 'NONE':
        raise ContractQuestion(f'{loan.loan_id}: a penalty needs the remaining term T in years')
    if settings.lag != 1:
        raise ValueError('incentive lag L is 1 month (decision M4)')
    rate = curve[loan.currency]
    origin = cashflows.month_end(loan.origination_date)
    path = []
    for k, when in enumerate(cashflows.projection_months(loan, as_of), start=1):
        # Age at t: whole months from the origination month end to t - 1.
        age = cashflows.months_between(origin, as_of) + k - 1
        path.append(pm1_cpr(settings.params, incentive(position.client_rate, rate, settings.margin), age,
                            when.month))
    return path


def run(positions: list[Position], curve: dict[str, float], settings: Settings) -> dict[str, list[Month]]:
    """Projected months of every loan under one scenario curve."""
    return {p.loan.loan_id: cashflows.project(p, cpr_path(p, curve, settings)) for p in positions}


def read_curve(path: Path, as_of: date) -> dict[str, float]:
    """The refinancing rate per currency at the as-of date, from a market_rates.csv file."""
    with path.open(encoding='ascii', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != RATE_FIELDS:
            raise ValueError(f'{path}: header must be {",".join(RATE_FIELDS)}')
        return curve_at(list(reader), as_of)


def curve_at(rows: list[dict[str, str]], as_of: date) -> dict[str, float]:
    """One series per currency at the as-of date; rows of other month ends are not used."""
    curve: dict[str, float] = {}
    for row in rows:
        if date.fromisoformat(row['as_of_date']) != as_of:
            continue
        if row['currency'] in curve:
            raise ContractQuestion(f'{row["currency"]}: several tenors need T in years')
        curve[row['currency']] = float(row['rate'])
    return curve


def read_settings(path: Path) -> Settings:
    with path.open(encoding='ascii', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != SETTING_FIELDS:
            raise ValueError(f'{path}: header must be {",".join(SETTING_FIELDS)}')
        values = {row['name']: row['value'] for row in reader}
    params = PM1(float(values['c_min']), float(values['c_max']), float(values['k']), float(values['x0']),
                 float(values['a_ramp']), tuple(float(values[name]) for name in SEASON_NAMES), float(values['b']))
    return Settings(params, float(values['margin']), int(values['lag']))
