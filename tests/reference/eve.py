"""Independent reference for EVE sensitivity and the repricing gap (MODEL_CONTRACTS.md, #72).

Written from the contract, not from toolkit source. Present values use binary floating point
(math.exp, math.fsum); principal sums, the repricing gap and the ΔEVE of hand-built present
values use exact decimals; the ratio, the weighted average repricing time and the effective
duration use exact rationals. Cash flows are hand-built projection rows, one per scenario,
segment, currency and month k after the as-of date; the projection that produces them is
covered by the CF-* cases.
"""
from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import rates

BASE = 'BASE'
CONTRACT = 'CONTRACT'
# The six EVE scenarios of REG-3 Article 1(1); only these enter the worst case (M15).
SUPERVISORY = ('PAR_UP', 'PAR_DOWN', 'STEEPENER', 'FLATTENER', 'SHORT_UP', 'SHORT_DOWN')
# CPR layers of the regulatory overlay: internal-model CPR and standardised multipliers (M15).
LAYERS = ('INTERNAL', 'STANDARDISED')
THRESHOLD = Fraction(15, 100)
INDICATOR_LABEL = 'loan-book indicator; not the supervisory outlier test'
GAP_TOLERANCE = Decimal('0.005')
# Upper bounds in years of buckets 2 to 18 of REG-1 Table 3 (SRP31.96), each inclusive (M17).
# Bucket 1 is overnight, empty on a monthly grid; bucket 19 is t > 20 years.
BUCKET_UPPER = tuple(Fraction(b) for b in ('1/12', '3/12', '6/12', '9/12', '1', '3/2', '2', '3', '4', '5', '6',
                                           '7', '8', '9', '10', '15', '20'))
BUCKETS = 19

CASH_FLOW_FIELDS = ('scenario', 'segment', 'currency', 'k', 'opening', 'interest', 'scheduled', 'prepaid',
                    'repricing', 'closing')
CURVE_FIELDS = ('scenario', 'currency', 'tenor_months', 'zero_rate')
PV_FIELDS = ('currency', 'layer', 'scenario', 'pv')
AMOUNT_RE = re.compile(r'-?[0-9]+(?:\.([0-9]+))?')
CURRENCY_RE = re.compile(r'[A-Z]{3}')

Key = tuple[str, str, str]    # (scenario, segment, currency)
Curve = list[tuple[int, float]]    # (tenor in months, continuously compounded zero rate)


def read_rows(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f'{path}: header must be {",".join(fields)}')
        return list(reader)


# ---------------------------------------------------------------------------
# Cash flows
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CashFlow:
    """Projected flows of one scenario, segment and currency in month k after the as-of date."""
    scenario: str
    segment: str
    currency: str
    k: int    # paid at the month end k/12 years after the as-of date
    opening: Decimal
    interest: Decimal
    scheduled: Decimal
    prepaid: Decimal
    repricing: Decimal
    closing: Decimal

    @property
    def key(self) -> Key:
        return (self.scenario, self.segment, self.currency)

    @property
    def principal(self) -> Decimal:
        """Scheduled, prepaid and repricing principal: what the gap and the repricing time use."""
        return self.scheduled + self.prepaid + self.repricing

    @property
    def total(self) -> Decimal:
        """CF_s(k) = interest + scheduled + prepaid + repricing."""
        return self.interest + self.principal


def read_cash_flows(path: Path) -> list[CashFlow]:
    flows = []
    for row in read_rows(path, CASH_FLOW_FIELDS):
        k = int(row['k'])
        if k < 1:
            raise ValueError(f'{path}: cash flows are paid from month 1 after the as-of date, not {k}')
        flows.append(CashFlow(row['scenario'], row['segment'], row['currency'], k,
                              *(Decimal(row[name]) for name in CASH_FLOW_FIELDS[4:])))
    return flows


def by_key(flows: list[CashFlow]) -> dict[Key, list[CashFlow]]:
    groups: dict[Key, list[CashFlow]] = defaultdict(list)
    for flow in flows:
        groups[flow.key].append(flow)
    return {key: sorted(group, key=lambda f: f.k) for key, group in groups.items()}


# ---------------------------------------------------------------------------
# Present value
# ---------------------------------------------------------------------------

def read_curves(path: Path) -> dict[tuple[str, str], Curve]:
    """Zero curves per (scenario, currency), already shocked and floored, sorted by tenor."""
    curves: dict[tuple[str, str], Curve] = defaultdict(list)
    for row in read_rows(path, CURVE_FIELDS):
        tenor = int(row['tenor_months'])
        if tenor < 1:
            raise ValueError(f'{path}: tenor must be a positive number of months, not {tenor}')
        curves[(row['scenario'], row['currency'])].append((tenor, float(row['zero_rate'])))
    for key, curve in curves.items():
        curve.sort()
        if len({tenor for tenor, _ in curve}) != len(curve):
            raise ValueError(f'{path}: duplicate tenor in curve {key}')
    return dict(curves)


def zero_rate(curve: Curve, years: float) -> float:
    """z(t): linear in rate between the tenors, held flat before the first and after the last (M13)."""
    if not curve:
        raise ValueError('a curve needs at least one tenor')
    points = [(tenor / 12.0, rate) for tenor, rate in curve]
    if years <= points[0][0]:
        return points[0][1]
    for (t0, z0), (t1, z1) in zip(points, points[1:]):
        if years <= t1:
            return z0 + (z1 - z0) * (years - t0) / (t1 - t0)
    return points[-1][1]


def discount_factor(curve: Curve, k: int) -> float:
    """DF(k) = exp(-z(k/12) x k/12), continuously compounded on the k/12 grid."""
    years = k / 12.0
    return math.exp(-zero_rate(curve, years) * years)


def present_values(flows: list[CashFlow], curves: dict[tuple[str, str], Curve]) -> dict[Key, float]:
    """PV_s per scenario, segment and currency: sum_k CF_s(k) x DF_s(k), each scenario on its own curve.

    CONTRACT is the observed curve with no prepayment, so it is discounted on the BASE curve.
    """
    result = {}
    for key, group in by_key(flows).items():
        scenario, _, currency = key
        curve_key = (BASE if scenario == CONTRACT else scenario, currency)
        if curve_key not in curves:
            raise ValueError(f'no discount curve for {scenario} {currency}')
        curve = curves[curve_key]
        result[key] = math.fsum(float(f.total) * discount_factor(curve, f.k) for f in group)
    return result


def currency_totals(values: dict[Key, float]) -> dict[tuple[str, str], float]:
    """PV per scenario in total per currency: segments are added, currencies never."""
    parts: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (scenario, _, currency), value in values.items():
        parts[(scenario, currency)].append(value)
    return {key: math.fsum(group) for key, group in parts.items()}


# ---------------------------------------------------------------------------
# ΔEVE, worst case, ratio and indicator
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PresentValue:
    """PV of one currency, CPR layer and scenario, in total per currency.

    BASE and CONTRACT carry no layer: BASE uses CPR_BASE in both layers and CONTRACT has
    SMM = 0, so each has one PV per currency (M15).
    """
    currency: str
    layer: str
    scenario: str
    pv: Decimal


def read_present_values(path: Path) -> list[PresentValue]:
    return [PresentValue(row['currency'], row['layer'], row['scenario'], Decimal(row['pv']))
            for row in read_rows(path, PV_FIELDS)]


@dataclass
class LayerResult:
    """ΔEVE of one CPR layer and currency; never added across currencies or mixed across layers."""
    layer: str
    currency: str
    pv_base: Decimal
    pv_contract: Decimal | None    # reported for comparison; never in the worst case
    delta: dict[str, Decimal]    # dEVE_s = PV_s - PV_BASE of every scenario of the layer, user shocks included
    worst: Decimal    # min over the six supervisory scenarios
    worst_scenario: str
    ratio: Fraction | None = None    # only for the currency of the Tier 1 amount
    indicator: bool | None = None
    label: str = field(default=INDICATOR_LABEL)


def delta_eve(values: list[PresentValue]) -> dict[tuple[str, str], LayerResult]:
    """dEVE_s = PV_s - PV_BASE per layer and currency; worst over the six supervisory scenarios only."""
    bases: dict[str, Decimal] = {}
    contracts: dict[str, Decimal] = {}
    scenarios: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(dict)
    for item in values:
        if item.scenario in (BASE, CONTRACT):
            if item.layer:
                raise ValueError(f'{item.scenario} {item.currency} is the same in every layer; it takes no layer')
            target = bases if item.scenario == BASE else contracts
            if item.currency in target:
                raise ValueError(f'two {item.scenario} PVs for {item.currency}')
            target[item.currency] = item.pv
            continue
        if item.layer not in LAYERS:
            raise ValueError(f'unknown CPR layer {item.layer!r} for {item.scenario} {item.currency}')
        group = scenarios[(item.layer, item.currency)]
        if item.scenario in group:
            raise ValueError(f'two PVs for {item.layer} {item.currency} {item.scenario}')
        group[item.scenario] = item.pv
    results = {}
    for (layer, currency), group in sorted(scenarios.items()):
        if currency not in bases:
            raise ValueError(f'no BASE PV for {currency}')
        missing = [name for name in SUPERVISORY if name not in group]
        if missing:
            raise ValueError(f'{layer} {currency}: the worst case needs all six scenarios; missing {missing}')
        base = bases[currency]
        delta = {name: pv - base for name, pv in group.items()}
        worst_scenario = min(SUPERVISORY, key=lambda name: delta[name])
        results[(layer, currency)] = LayerResult(layer, currency, base, contracts.get(currency), delta,
                                                 delta[worst_scenario], worst_scenario)
    return results


class Tier1Error(ValueError):
    """A missing or invalid Tier 1 setting: the run stops before any calculation (D10)."""


@dataclass(frozen=True)
class Tier1:
    amount: Decimal
    currency: str


def validate_tier1(amount: str | None, currency: str | None, allowlist: set[str]) -> Tier1:
    """tier1_amount a decimal of up to 4 places, > 0; tier1_currency ISO 4217 in the allowlist (D10)."""
    if not amount or not currency:
        raise Tier1Error('Tier 1 amount and currency are required when the ratio is requested')
    match = AMOUNT_RE.fullmatch(amount)
    if match is None or (match.group(1) is not None and len(match.group(1)) > 4):
        raise Tier1Error(f'Tier 1 amount is not a decimal of up to 4 places: {amount!r}')
    value = Decimal(amount)
    if value <= 0:
        raise Tier1Error(f'Tier 1 amount must be positive: {amount!r}')
    if CURRENCY_RE.fullmatch(currency) is None or currency not in allowlist:
        raise Tier1Error(f'Tier 1 currency is not an allowed ISO 4217 code: {currency!r}')
    return Tier1(value, currency)


def run_eve(values: list[PresentValue], ratio_requested: bool, tier1_amount: str | None,
            tier1_currency: str | None, allowlist: set[str]) -> dict[tuple[str, str], LayerResult]:
    """ΔEVE per layer and currency, with ratio = -worst / Tier1 and the indicator (ratio > 0.15)
    for the Tier 1 currency only; Tier 1 is validated before anything is calculated."""
    tier1 = validate_tier1(tier1_amount, tier1_currency, allowlist) if ratio_requested else None
    results = delta_eve(values)
    if tier1 is not None:
        for result in results.values():
            if result.currency == tier1.currency:    # no implicit FX conversion
                result.ratio = -Fraction(result.worst) / Fraction(tier1.amount)
                result.indicator = result.ratio > THRESHOLD
    return results


# ---------------------------------------------------------------------------
# Repricing gap
# ---------------------------------------------------------------------------

def bucket_of(k: int) -> int:
    """The REG-1 Table 3 bucket (1 to 19) of a flow paid k/12 years after the as-of date."""
    if k < 1:
        raise ValueError(f'month {k} is not after the as-of date')
    years = Fraction(k, 12)
    for number, upper in enumerate(BUCKET_UPPER, start=2):
        if years <= upper:
            return number
    return BUCKETS


def repricing_gap(flows: list[CashFlow]) -> dict[Key, list[Decimal]]:
    """Principal per bucket (index 0 is bucket 1) for each scenario, segment and currency."""
    gaps: dict[Key, list[Decimal]] = {}
    for key, group in by_key(flows).items():
        gap = [Decimal(0)] * BUCKETS
        for flow in group:
            gap[bucket_of(flow.k) - 1] += flow.principal
        gaps[key] = gap
    return gaps


def gap_conserves(gap: list[Decimal], outstanding: Decimal) -> bool:
    """The sum over buckets equals the outstanding balance at the as-of date within 0.005."""
    return abs(sum(gap, Decimal(0)) - outstanding) <= GAP_TOLERANCE


# ---------------------------------------------------------------------------
# Other measures (M18)
# ---------------------------------------------------------------------------

def repricing_time(flows: list[CashFlow]) -> dict[Key, Fraction | None]:
    """sum_k (k/12) x principal(k) / sum_k principal(k) in years, repricing principal included."""
    result: dict[Key, Fraction | None] = {}
    for key, group in by_key(flows).items():
        total = sum((Fraction(f.principal) for f in group), Fraction(0))
        weighted = sum((Fraction(f.k, 12) * Fraction(f.principal) for f in group), Fraction(0))
        result[key] = weighted / total if total else None
    return result


def effective_duration(pv_base: Fraction, pv_par_down: Fraction, pv_par_up: Fraction,
                       shock: Fraction) -> Fraction | None:
    """(PV_PAR_DOWN - PV_PAR_UP) / (2 x PV_BASE x dr), dr the nominal parallel shock of the currency;
    not reported when PV_BASE <= 0."""
    if pv_base <= 0:
        return None
    return (pv_par_down - pv_par_up) / (2 * pv_base * shock)


def projected_smms(group: list[CashFlow]) -> list[tuple[int, float | None]]:
    """Pool SMM of each projected month, sum prepaid / sum (opening - scheduled); None when that is <= 0."""
    months: dict[int, list[Decimal]] = {}
    for flow in group:
        sums = months.setdefault(flow.k, [Decimal(0), Decimal(0)])
        sums[0] += flow.prepaid
        sums[1] += flow.opening - flow.scheduled
    if sorted(months) != list(range(1, len(months) + 1)):
        raise ValueError('a projected CPR needs every month from 1 to the end of the projection')
    return [(k, float(Fraction(prepaid) / Fraction(exposure)) if exposure > 0 else None)
            for k, (prepaid, exposure) in sorted(months.items())]


def projected_cpr(flows: list[CashFlow], months: int | None = None) -> dict[Key, float | None]:
    """1 - (prod (1 - SMM))^(12/n) over the first `months` months, or over the whole projection;
    a month without SMM is left out of the product and of n; None when no month remains."""
    result: dict[Key, float | None] = {}
    for key, group in by_key(flows).items():
        smms = [smm for k, smm in projected_smms(group) if smm is not None and (months is None or k <= months)]
        result[key] = rates.realised_cpr(smms) if smms else None
    return result
