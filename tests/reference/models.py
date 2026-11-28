"""Independent reference for the PM0 and PM1 models (MODEL_CONTRACTS.md, Candidate models).

Written from the contract, not from toolkit source. PM0 is the realised CPR of the estimation
window, compounded from the pool SMM of each month (rates.py). PM1 is the rate-incentive
S-curve with ramp, seasonality, burnout and clamp; its four curve parameters are fitted by
weighted least squares on monthly bucket SMM, the predicted bucket value being the
exposure-weighted mean of loan-level model SMM (decision M11), with Nelder-Mead in the
constraint-enforcing parametrisation. Ramp, seasonality and burnout enter the fit as fixed
behavioural assumptions (decision M7). Arithmetic is binary floating point; the expected
values come from derive_models.py, which shares no code with this module.

Drivers (incentive, age, burnout pool factor) are inputs here: their derivation from the data
is covered by the INC-* cases and is not reproduced. Where the contract leaves a point open
this module refuses the input rather than guess: a pool without loan-months in some month of
the window has no PM0, and a "parameter at a numerical boundary" is not tested, because the
contract does not define it.
"""
from __future__ import annotations

import csv
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import rates

BUCKET_WIDTH = 0.0025    # incentive bucket of 25 basis points (decision M8)
MIN_MONTH_ENDS = 36    # minimum sample (decision M9)
MIN_LOAN_MONTHS = 5_000
MIN_FULL_EVENTS = 100
DRIVER_FIELDS = ('incentive', 'age', 'pool_factor')

NON_CONVERGENCE = 'non-convergence'
NON_FINITE = 'non-finite objective'
BELOW_MINIMUM = 'below the minimum sample'


# ---------------------------------------------------------------------------------------------------------
# Estimation window
# ---------------------------------------------------------------------------------------------------------

def month_end(day: date) -> date:
    following = date(day.year + day.month // 12, day.month % 12 + 1, 1)
    return following - timedelta(days=1)


def month_ends(start: str, end: str) -> list[str]:
    """The month ends from start to end, both included; both must be month ends."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if month_end(first) != first or month_end(last) != last or last < first:
        raise ValueError(f'window must run from one month end to a later one: {start} to {end}')
    out = []
    day = first
    while day <= last:
        out.append(day.isoformat())
        day = month_end(day + timedelta(days=1))
    return out


def in_window(months: list[rates.LoanMonth], start: str, end: str) -> list[rates.LoanMonth]:
    """Loan-months whose month end t lies in the window; loan-month (i, t) runs from t-1 to t."""
    window = set(month_ends(start, end))
    return [m for m in months if m.as_of_date in window]


# ---------------------------------------------------------------------------------------------------------
# PM0
# ---------------------------------------------------------------------------------------------------------

def pm0(months: list[rates.LoanMonth], start: str, end: str,
        include_reneg: bool = False) -> dict[tuple[str, str], float]:
    """PM0 per (segment, currency): the realised CPR of the estimation window.

    1 - (prod_t (1 - SMM(t)))^(12/n) over the n month ends of the window, SMM(t) the pool SMM
    sum P / sum A of the month; never an average of monthly CPRs. A pool without loan-months
    in some month of the window is refused: the contract does not say whether that month
    counts in n.
    """
    window = month_ends(start, end)
    by_pool: dict[tuple[str, str], dict[str, Decimal]] = {}
    for (segment, currency, as_of), pool in rates.pool_rates(in_window(months, start, end), include_reneg).items():
        by_pool.setdefault((segment, currency), {})[as_of] = pool.smm
    out = {}
    for key, smms in sorted(by_pool.items()):
        if sorted(smms) != window:
            raise ValueError(f'{key}: no loan-months in {sorted(set(window) - set(smms))}')
        out[key] = rates.realised_cpr([float(smms[t]) for t in window])
    return out


# ---------------------------------------------------------------------------------------------------------
# PM1 formula
# ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Curve:
    """The estimated S-curve parameters: 0 <= c_min <= c_max <= 1, k > 0."""
    c_min: float
    c_max: float
    k: float
    x0: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.c_min <= self.c_max <= 1.0 and self.k > 0.0 and math.isfinite(self.x0)):
            raise ValueError(f'curve parameters outside their constraints: {self}')


@dataclass(frozen=True)
class Assumptions:
    """Ramp months, burnout strength and the 12 calendar-month factors (January first), mean 1."""
    a_ramp: float
    b: float
    season: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.season) != 12:
            raise ValueError('Season needs 12 factors')
        if abs(math.fsum(self.season) - 12.0) > 12.0 * 1e-12:
            raise ValueError(f'Season factors must have mean 1: {self.season}')
        if not self.a_ramp >= 0.0:
            raise ValueError(f'a_ramp must be at least 0: {self.a_ramp}')


def logistic(z: float) -> float:
    """1 / (1 + exp(-z)), without overflow for large |z|."""
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def ramp(age: int, a_ramp: float) -> float:
    """Ramp(age) = min(1, age / a_ramp); 1 when a_ramp = 0."""
    if age < 0:
        raise ValueError(f'age must be at least 0: {age}')
    return 1.0 if a_ramp == 0.0 else min(1.0, age / a_ramp)


def burnout(b: float, pool_factor: float) -> float:
    """B = exp(-b x (1 - pool factor))."""
    if not 0.0 <= pool_factor <= 1.0:
        raise ValueError(f'pool factor outside [0, 1]: {pool_factor}')
    return math.exp(-b * (1.0 - pool_factor))


def calendar_month(as_of_date: str) -> int:
    """Month of t, the month end that closes the loan-month."""
    return date.fromisoformat(as_of_date).month


def pm1_raw(curve: Curve, assume: Assumptions, incentive: float, age: int, month: int,
            pool_factor: float) -> float:
    """[c_min + (c_max - c_min) x B x logistic(k x (I - x0))] x Ramp(age) x Season(month), unclamped."""
    s_curve = curve.c_min + (curve.c_max - curve.c_min) * burnout(assume.b, pool_factor) \
        * logistic(curve.k * (incentive - curve.x0))
    return s_curve * ramp(age, assume.a_ramp) * assume.season[month - 1]


def pm1_cpr(curve: Curve, assume: Assumptions, incentive: float, age: int, month: int,
            pool_factor: float) -> float:
    """CPR(i, t) = min(1, max(0, raw)); a NaN stays NaN so that the objective reports it."""
    raw = pm1_raw(curve, assume, incentive, age, month, pool_factor)
    if math.isnan(raw):
        return raw
    return min(1.0, max(0.0, raw))


def pm1_smm(curve: Curve, assume: Assumptions, incentive: float, age: int, month: int,
            pool_factor: float) -> float:
    """The model's CPR converted to SMM, 1 - (1 - CPR)^(1/12); never CPR / 12."""
    cpr = pm1_cpr(curve, assume, incentive, age, month, pool_factor)
    return cpr if math.isnan(cpr) else rates.smm_from_cpr(cpr)


# ---------------------------------------------------------------------------------------------------------
# PM1 fit
# ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class FitRow:
    """Loan-months sharing their drivers: A and P summed over them (one loan-month in PM1-FIT-01)."""
    as_of_date: str
    incentive: float
    age: int
    pool_factor: float
    available: float
    prepaid: float


@dataclass
class Group:
    """One incentive bucket and month end: weight sum A, observed SMM sum P / sum A."""
    weight: float
    prepaid: float
    rows: list[FitRow]

    @property
    def observed(self) -> float:
        return self.prepaid / self.weight


def bucket(incentive: float) -> int:
    """Index of the 25 bp bucket [j x 25 bp, (j + 1) x 25 bp); see bucket_offsets_agree."""
    return math.floor(incentive / BUCKET_WIDTH)


def groups(rows: Sequence[FitRow], offset: float = 0.0) -> dict[tuple[int, str], Group]:
    """Bucket-month groups; offset shifts the bucket edges, for checking that a fixture's grouping
    does not depend on where the edges are anchored, which the contract leaves open."""
    out: dict[tuple[int, str], Group] = {}
    sums: dict[tuple[int, str], tuple[list[float], list[float], list[FitRow]]] = {}
    for row in rows:
        if not row.available > 0.0:
            raise ValueError(f'a fitted loan-month needs A > 0: {row}')
        a, p, members = sums.setdefault((bucket(row.incentive + offset), row.as_of_date), ([], [], []))
        a.append(row.available)
        p.append(row.prepaid)
        members.append(row)
    for key, (a, p, members) in sums.items():
        out[key] = Group(math.fsum(a), math.fsum(p), members)
    return out


def predicted(curve: Curve, assume: Assumptions, group: Group) -> float:
    """Decision M11: sum_i A x SMM_model(i) / sum_i A, each loan-month at its own drivers."""
    return math.fsum(r.available * pm1_smm(curve, assume, r.incentive, r.age, calendar_month(r.as_of_date),
                                           r.pool_factor) for r in group.rows) / group.weight


def objective(curve: Curve, assume: Assumptions, fitted: dict[tuple[int, str], Group]) -> float:
    """Weighted least squares on monthly SMM: sum over bucket-months of sum A x (observed - predicted)^2."""
    return math.fsum(g.weight * (g.observed - predicted(curve, assume, g)) ** 2 for g in fitted.values())


def curve_from_p(p: Sequence[float]) -> Curve:
    """c_min = logistic(p1), c_max = c_min + (1 - c_min) x logistic(p2), k = exp(p3), x0 = p4."""
    c_min = logistic(p[0])
    k = math.inf if p[2] > 709.0 else math.exp(p[2])    # IEEE overflow, as math.exp would raise
    return Curve(c_min, c_min + (1.0 - c_min) * logistic(p[1]), k, p[3])


def p_from_curve(curve: Curve) -> list[float]:
    """Inverse of curve_from_p, for start values strictly inside the constraints."""
    def logit(u: float) -> float:
        return math.log(u / (1.0 - u))
    return [logit(curve.c_min), logit((curve.c_max - curve.c_min) / (1.0 - curve.c_min)), math.log(curve.k),
            curve.x0]


@dataclass(frozen=True)
class Settings:
    """Recorded optimiser settings: start values, initial step per parameter in p, tolerances,
    iteration limit per search and number of restarts."""
    start: Curve
    steps: tuple[float, ...]
    ftol: float
    xtol: float
    max_iterations: int
    restarts: int


@dataclass(frozen=True)
class Search:
    x: list[float]
    f: float
    iterations: int
    converged: bool
    non_finite: bool


def nelder_mead(f: Callable[[list[float]], float], start: Sequence[float], steps: Sequence[float],
                ftol: float, xtol: float, max_iterations: int) -> Search:
    """Nelder-Mead with reflection 1, expansion 2, contraction 1/2 and shrink 1/2.

    The initial simplex is start and start + steps[j] e_j. It has converged when every vertex is
    within ftol of the best value and within xtol of the best point in every coordinate. Any
    non-finite value stops the search.
    """
    simplex = [list(start)] + [[x + (steps[j] if i == j else 0.0) for i, x in enumerate(start)]
                               for j in range(len(start))]
    values = [f(x) for x in simplex]
    iterations = 0
    while True:
        if not all(math.isfinite(v) for v in values):
            return Search(simplex[0], math.nan, iterations, False, True)
        order = sorted(range(len(simplex)), key=lambda i: values[i])
        simplex, values = [simplex[i] for i in order], [values[i] for i in order]
        best, worst = simplex[0], simplex[-1]
        if values[-1] - values[0] <= ftol and \
                max(abs(x[j] - best[j]) for x in simplex[1:] for j in range(len(best))) <= xtol:
            return Search(best, values[0], iterations, True, False)
        if iterations >= max_iterations:
            return Search(best, values[0], iterations, False, False)
        iterations += 1
        n = len(best)
        centroid = [math.fsum(x[j] for x in simplex[:-1]) / n for j in range(n)]

        def toward(scale: float) -> list[float]:
            return [c + scale * (w - c) for c, w in zip(centroid, worst)]
        reflected = toward(-1.0)
        fr = f(reflected)
        if not math.isfinite(fr):
            return Search(best, math.nan, iterations, False, True)
        if fr < values[0]:
            expanded = toward(-2.0)
            fe = f(expanded)
            simplex[-1], values[-1] = (expanded, fe) if fe < fr else (reflected, fr)
            continue
        if fr < values[-2]:
            simplex[-1], values[-1] = reflected, fr
            continue
        contracted = toward(-0.5) if fr < values[-1] else toward(0.5)
        fc = f(contracted)
        if fc < min(fr, values[-1]):
            simplex[-1], values[-1] = contracted, fc
            continue
        simplex = [best] + [[b + 0.5 * (x - b) for b, x in zip(best, vertex)] for vertex in simplex[1:]]
        values = [values[0]] + [f(x) for x in simplex[1:]]


@dataclass(frozen=True)
class Fit:
    """Outcome for one segment and currency; a fit that is not estimated stores no parameters."""
    estimated: bool
    reason: str | None
    curve: Curve | None
    objective: float | None
    iterations: int


def fit(rows: Sequence[FitRow], assume: Assumptions, settings: Settings,
        target: Callable[[list[float]], float] | None = None) -> Fit:
    """Fit c_min, c_max, k and x0 by Nelder-Mead in p, restarting from the best point.

    Restarts stop early once a restart improves the objective by no more than ftol. A search
    that hits its iteration limit is non-convergence and a non-finite value is a non-finite
    objective; either gives "not estimated" with no parameters. target replaces the objective
    of p, for injecting failures.
    """
    fitted = groups(rows)

    def f(p: list[float]) -> float:
        return objective(curve_from_p(p), assume, fitted)
    function = f if target is None else target
    x = p_from_curve(settings.start)
    iterations = 0
    best: Search | None = None
    for _ in range(settings.restarts + 1):
        search = nelder_mead(function, x, settings.steps, settings.ftol, settings.xtol, settings.max_iterations)
        iterations += search.iterations
        if search.non_finite:
            return Fit(False, NON_FINITE, None, None, iterations)
        if not search.converged:
            return Fit(False, NON_CONVERGENCE, None, None, iterations)
        improved = best is None or best.f - search.f > settings.ftol
        if best is None or search.f < best.f:
            best = search
        if not improved:
            break
        x = best.x
    assert best is not None
    return Fit(True, None, curve_from_p(best.x), best.f, iterations)


# ---------------------------------------------------------------------------------------------------------
# Minimum sample (decision M9)
# ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Sample:
    month_ends: int
    loan_months: int
    full_events: int

    def shortfalls(self) -> list[str]:
        out = []
        if self.month_ends < MIN_MONTH_ENDS:
            out.append('month_ends')
        if self.loan_months < MIN_LOAN_MONTHS:
            out.append('loan_months')
        if self.full_events < MIN_FULL_EVENTS:
            out.append('full_events')
        return out


def samples(months: list[rates.LoanMonth], start: str, end: str) -> dict[tuple[str, str], Sample]:
    """Per (segment, currency): the longest run of consecutive month ends of the window with
    loan-months, the loan-months and the FULL events. Loan-months are those entering the SMM
    (NONE, PARTIAL, FULL with A > 0); PM1-MIN-01 holds no other kind, so it does not decide
    whether other risk-set loan-months count."""
    window = month_ends(start, end)
    seen: dict[tuple[str, str], tuple[set[str], list[int]]] = {}
    for m in in_window(months, start, end):
        if m.event not in rates.PREPAYMENT_EVENTS or m.available <= 0:
            continue
        dates, counts = seen.setdefault((m.segment, m.currency), (set(), [0, 0]))
        dates.add(m.as_of_date)
        counts[0] += 1
        counts[1] += m.event == 'FULL'
    out = {}
    for key, (dates, (loan_months, full)) in sorted(seen.items()):
        run = longest = 0
        for t in window:
            run = run + 1 if t in dates else 0
            longest = max(longest, run)
        out[key] = Sample(longest, loan_months, full)
    return out


def estimate(sample: Sample, rows: Sequence[FitRow], assume: Assumptions, settings: Settings) -> Fit:
    """PM1 for one segment and currency: not estimated below the minimum sample, otherwise fit."""
    short = sample.shortfalls()
    if short:
        return Fit(False, f'{BELOW_MINIMUM}: {", ".join(short)}', None, None, 0)
    return fit(rows, assume, settings)


# ---------------------------------------------------------------------------------------------------------
# Fixture readers
# ---------------------------------------------------------------------------------------------------------

def read_fit_rows(path: Path) -> tuple[list[rates.LoanMonth], list[FitRow]]:
    """Loan-months with their drivers; each row of an SMM outcome with A > 0 becomes one FitRow."""
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != rates.LOAN_MONTH_FIELDS + DRIVER_FIELDS:
            raise ValueError(f'{path}: header must be {",".join(rates.LOAN_MONTH_FIELDS + DRIVER_FIELDS)}')
        months, rows = [], []
        for row in reader:
            month = rates.LoanMonth(row['loan_id'], row['segment'], row['currency'], row['as_of_date'],
                                    Decimal(row['opening_balance']), Decimal(row['scheduled_principal']),
                                    Decimal(row['other_change']), Decimal(row['prepaid_principal']), row['event'])
            months.append(month)
            if month.event in rates.PREPAYMENT_EVENTS and month.available > 0:
                rows.append(FitRow(month.as_of_date, float(row['incentive']), int(row['age']),
                                   float(row['pool_factor']), float(month.available),
                                   float(month.prepaid_principal)))
        return months, rows


CELL_FIELDS = ('as_of_date', 'incentive', 'age', 'pool_factor', 'loans', 'balance', 'full_events')


def read_cells(path: Path) -> list[FitRow]:
    """PM1-DGP-01 cells: loans identical loan-months of balance A each, full_events of them FULL."""
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CELL_FIELDS:
            raise ValueError(f'{path}: header must be {",".join(CELL_FIELDS)}')
        return [FitRow(r['as_of_date'], float(r['incentive']), int(r['age']), float(r['pool_factor']),
                       float(Decimal(r['loans']) * Decimal(r['balance'])),
                       float(Decimal(r['full_events']) * Decimal(r['balance']))) for r in reader]
