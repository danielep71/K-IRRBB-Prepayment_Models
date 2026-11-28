"""Independent reference for the rate incentive (MODEL_CONTRACTS.md, Rate incentive).

Written from the contract, not from toolkit source. For a fixed-rate loan-month ending at t:

    I(i,t) = client_rate(i,t-1) - [ R(t-L, T(i,t)) + m ] - penalty(i,t)

with the lag L = 1 month of decision M4, the margin m of the loan's segment (M5), and R(s, T)
the market rate for term T at month end s, interpolated linearly in rate between the configured
refinancing series of the loan's currency and held flat outside them. Rates use binary floating
point. Inputs are risk-set loan-months with the remaining fixed term T already in years.

Two points are left open by the contract and are deliberately not pinned here:

- the year fraction that turns maturity_date or fixed_until into T; term_end() returns the end
  date the contract names, and the cases take T as an input;
- the compounding of R (decision M3 names a par swap rate, the incentive section says the
  prototype uses a zero rate, and neither states a conversion). R enters the formula as the
  interpolated series value; the cases pin I only where R = 0, where every convention agrees,
  and INC-LAG-01 is a property that holds for any function of R.
"""
from __future__ import annotations

import calendar
import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

LAG_MONTHS = 1    # decision M4
MARKET_FIELDS = ('as_of_date', 'rate_id', 'currency', 'tenor_months', 'rate')
INCENTIVE_FIELDS = ('loan_id', 'segment', 'currency', 'as_of_date', 'client_rate', 'term_years',
                    'penalty_type', 'penalty_value')
PENALTY_TYPES = frozenset({'NONE', 'PCT', 'MONTHS_INTEREST'})


@dataclass(frozen=True)
class MarketRate:
    as_of_date: date
    rate_id: str
    currency: str
    tenor_months: int
    rate: float


@dataclass(frozen=True)
class IncentiveMonth:
    loan_id: str
    segment: str
    currency: str
    as_of_date: date    # month end t; the loan-month runs from t-1 to t
    client_rate: float    # client_rate(i, t-1)
    term_years: float    # T(i, t), remaining fixed term at t-1
    penalty_type: str
    penalty_value: float | None


def read_rows(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f'{path}: header must be {",".join(fields)}')
        return list(reader)


def read_market_rates(path: Path) -> list[MarketRate]:
    return [MarketRate(date.fromisoformat(row['as_of_date']), row['rate_id'], row['currency'],
                       int(row['tenor_months']), float(row['rate']))
            for row in read_rows(path, MARKET_FIELDS)]


def read_incentive_months(path: Path) -> list[IncentiveMonth]:
    return [IncentiveMonth(row['loan_id'], row['segment'], row['currency'], date.fromisoformat(row['as_of_date']),
                           float(row['client_rate']), float(row['term_years']), row['penalty_type'],
                           float(row['penalty_value']) if row['penalty_value'] else None)
            for row in read_rows(path, INCENTIVE_FIELDS)]


def is_month_end(day: date) -> bool:
    return day.day == calendar.monthrange(day.year, day.month)[1]


def month_end_before(t: date, months: int) -> date:
    """The month end `months` months before month end t."""
    if not is_month_end(t) or months < 0:
        raise ValueError(f'{t} is not a month end, or {months} is negative')
    year, index = divmod(t.year * 12 + t.month - 1 - months, 12)
    return date(year, index + 1, calendar.monthrange(year, index + 1)[1])


def rate_date(t: date, lag: int = LAG_MONTHS) -> date:
    """s = t - L: the month end whose market rates enter the incentive of the loan-month ending at t."""
    return month_end_before(t, lag)


def curve(rates: Iterable[MarketRate], series: Iterable[str], currency: str, s: date) -> list[tuple[float, float]]:
    """(tenor in years, rate) of each configured series of the currency at month end s, by tenor.

    Only rows dated at or before s are looked at. A configured series of the currency seen by s
    without a row at s, two rows of one series at s, or two series with one tenor are refused:
    the contract does not say how the curve is formed then.
    """
    configured = set(series)
    known: set[str] = set()
    nodes: dict[str, tuple[float, float]] = {}
    for row in rates:
        if row.rate_id not in configured or row.currency != currency or row.as_of_date > s:
            continue
        known.add(row.rate_id)
        if row.as_of_date == s:
            if row.rate_id in nodes:
                raise ValueError(f'two rows of {row.rate_id} at {s}')
            nodes[row.rate_id] = (row.tenor_months / 12, row.rate)
    if not nodes or known - nodes.keys():
        raise ValueError(f'configured {currency} series without a rate at {s}: {sorted(known - nodes.keys())}')
    points = sorted(nodes.values())
    if len({tenor for tenor, _ in points}) != len(points):
        raise ValueError(f'two configured {currency} series share a tenor at {s}')
    return points


def interpolate(points: list[tuple[float, float]], term_years: float) -> float:
    """Linear in rate between the nodes, flat below the shortest and above the longest tenor."""
    if term_years <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if term_years <= x1:
            return y0 + (y1 - y0) * (term_years - x0) / (x1 - x0)
    return points[-1][1]


def market_rate(rates: Iterable[MarketRate], series: Iterable[str], currency: str, s: date,
                term_years: float) -> float:
    """R(s, T)."""
    if term_years < 0:
        raise ValueError(f'negative term {term_years}')
    return interpolate(curve(rates, series, currency, s), term_years)


def penalty(penalty_type: str, penalty_value: float | None, client_rate: float, term_years: float) -> float:
    """PCT: value / max(T, 1); MONTHS_INTEREST: value x client_rate / 12 / max(T, 1); NONE: 0."""
    if penalty_type not in PENALTY_TYPES:
        raise ValueError(f'unknown penalty type {penalty_type!r}')
    if penalty_type == 'NONE':
        if penalty_value is not None:
            raise ValueError('penalty_value must be empty for NONE')
        return 0.0
    if penalty_value is None or penalty_value < 0:
        raise ValueError(f'{penalty_type} needs a nonnegative penalty_value')
    years = max(term_years, 1.0)
    if penalty_type == 'PCT':
        return penalty_value / years
    return penalty_value * client_rate / 12 / years


def incentive(client_rate: float, refinancing_rate: float, margin: float, penalty_rate: float) -> float:
    """I = client_rate - (R + m) - penalty."""
    return client_rate - (refinancing_rate + margin) - penalty_rate


def loan_month_incentive(month: IncentiveMonth, rates: Iterable[MarketRate], series: Iterable[str],
                         margins: Mapping[str, float], lag: int = LAG_MONTHS) -> float:
    """I(i,t) of one loan-month, reading the curve at t - lag."""
    refinancing = market_rate(rates, series, month.currency, rate_date(month.as_of_date, lag), month.term_years)
    charge = penalty(month.penalty_type, month.penalty_value, month.client_rate, month.term_years)
    return incentive(month.client_rate, refinancing, margins[month.segment], charge)


def term_end(rate_type: str, maturity_date: date, fixed_until: date | None, period_start: date) -> date | None:
    """End of the remaining fixed term at t-1 (period_start), or None when there is no incentive.

    FIXED: maturity_date. RESET: fixed_until while t-1 is before it; past it, no incentive.
    FLOAT: no incentive. A RESET loan with t-1 exactly at fixed_until is refused: the contract
    does not say whether its remaining fixed term is zero or over.
    """
    if rate_type == 'FIXED':
        return maturity_date
    if rate_type == 'FLOAT':
        return None
    if rate_type != 'RESET' or fixed_until is None:
        raise ValueError(f'unknown rate type {rate_type!r}, or RESET without fixed_until')
    if period_start == fixed_until:
        raise ValueError('t-1 at fixed_until is not decided by the contract')
    return fixed_until if period_start < fixed_until else None
