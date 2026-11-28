"""Derive the expected values of the PM0 and PM1 cases, and generate their fixtures, without models.py.

Run offline: ``python tests/reference/derive_models.py`` prints the derived values;
test_reference_models.py checks that the committed fixtures and expected files still equal
this derivation. Everything here is written from the model contracts in decimal arithmetic at
PRECISION significant digits and shares no code with models.py or rates.py:

* PM0-CALC-01: the hand-tabulated monthly sums of the fixture give the realised CPR exactly
  in rationals (a 6-month window, exponent 12 / 6 = 2).
* PM1-FORM-01: the formula at the fixture's parameters and points, in decimal.
* PM1-FIT-01: the fixture is built so that its optimum is known in closed form: observed
  bucket SMM = predicted SMM at the design parameters plus residuals made orthogonal, in the
  weighted inner product, to the derivatives of the predictions, so the first-order conditions
  hold exactly at the design parameters. Prepaid amounts are then rounded to 4 decimal places,
  which moves the optimum slightly; Newton's method in decimal, a derivative-based method unlike
  the Nelder-Mead under test, finds the optimum of the rounded data from the design point, and
  the gradient and a finite-difference Hessian (positive definite) confirm it is a minimum.
* PM1-DGP-01: the generated sample: binomial counts of FULL prepayments drawn from the model
  SMM at known parameters, with random.Random(seed).random() as the only source of randomness.
"""
from __future__ import annotations

import json
import random
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

PRECISION = 50
DIGITS = 20    # significant digits written for the PM1 values
D = Decimal
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests' / 'fixtures'

# PM0-CALC-01: sum P and sum A of the MTG_FIX EUR pool for each month end of the window, by hand.
PM0_WINDOW = {'2024-02-29': (3_000, 150_000), '2024-03-31': (1_500, 100_000), '2024-04-30': (4_400, 110_000),
              '2024-05-31': (0, 90_000), '2024-06-30': (2_500, 125_000), '2024-07-31': (8_000, 80_000)}
PM0_USD = {'2024-02-29': (500, 50_000), '2024-03-31': (1_000, 50_000), '2024-04-30': (0, 50_000),
           '2024-05-31': (2_000, 40_000), '2024-06-30': (0, 40_000), '2024-07-31': (400, 40_000)}


def text(value: Fraction | Decimal, digits: int = 40) -> str:
    """value rounded half-even to digits significant digits, in plain notation."""
    if isinstance(value, Fraction):
        with localcontext(Context(prec=digits + 40)):
            value = Decimal(value.numerator) / Decimal(value.denominator)
    rounded = Context(prec=digits).plus(value)
    return format(rounded, 'f') if rounded else '0'


def realised(sums: dict[str, tuple[int, int]]) -> dict[str, str]:
    smms = [Fraction(p, a) for p, a in sums.values()]
    survival = Fraction(1)
    for smm in smms:
        survival *= 1 - smm
    if 12 % len(smms):
        raise ValueError('the window has 12 / n integral')
    cprs = [1 - (1 - s) ** 12 for s in smms]
    pooled = Fraction(sum(p for p, _ in sums.values()), sum(a for _, a in sums.values()))
    mean_smm = sum(smms, Fraction(0)) / len(smms)
    return {'pm0': text(1 - survival ** (12 // len(smms))),
            'average_of_monthly_cprs': text(sum(cprs, Fraction(0)) / len(cprs)),
            'cpr_of_window_pooled_smm': text(1 - (1 - pooled) ** 12),
            'cpr_of_mean_monthly_smm': text(1 - (1 - mean_smm) ** 12)}


# ---------------------------------------------------------------------------------------------------------
# PM1 formula in decimal
# ---------------------------------------------------------------------------------------------------------

class Model:
    """PM1 at fixed ramp, burnout and season, in decimal; theta = (c_min, c_max, k, x0)."""

    def __init__(self, a_ramp: str, b: str, season: list[str]) -> None:
        self.a_ramp, self.b, self.season = D(a_ramp), D(b), [D(s) for s in season]
        if len(self.season) != 12 or sum(self.season) != 12:
            raise ValueError('12 season factors with mean 1')

    def raw(self, theta: tuple[Decimal, ...], incentive: Decimal, age: int, as_of: str, pool: Decimal) -> Decimal:
        c_min, c_max, k, x0 = theta
        s_shape = 1 / (1 + (-(k * (incentive - x0))).exp())
        burn = (-self.b * (1 - pool)).exp()
        rmp = D(1) if self.a_ramp == 0 else min(D(1), D(age) / self.a_ramp)
        return (c_min + (c_max - c_min) * burn * s_shape) * rmp * self.season[int(as_of[5:7]) - 1]

    def cpr(self, theta: tuple[Decimal, ...], incentive: Decimal, age: int, as_of: str, pool: Decimal) -> Decimal:
        return min(D(1), max(D(0), self.raw(theta, incentive, age, as_of, pool)))

    def smm(self, theta: tuple[Decimal, ...], incentive: Decimal, age: int, as_of: str, pool: Decimal) -> Decimal:
        cpr = self.cpr(theta, incentive, age, as_of, pool)
        return D(1) if cpr == 1 else 1 - ((1 - cpr).ln() / 12).exp()


def csv_rows(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding='utf-8').splitlines()
    header = lines[0].split(',')
    return [dict(zip(header, line.split(','))) for line in lines[1:]]


def derive_form() -> dict[str, object]:
    folder = FIXTURES / 'PM1-FORM-01'
    sets = {}
    for row in csv_rows(folder / 'parameters.csv'):
        sets[row['set']] = (Model(row['a_ramp'], row['b'], [row[f'season_{m}'] for m in range(1, 13)]),
                            tuple(D(row[name]) for name in ('c_min', 'c_max', 'k', 'x0')))
    points = {}
    with localcontext(Context(prec=PRECISION)):
        for row in csv_rows(folder / 'points.csv'):
            model, theta = sets[row['set']]
            args = (theta, D(row['incentive']), int(row['age']), row['as_of_date'], D(row['pool_factor']))
            points[row['point']] = {'raw': text(model.raw(*args), DIGITS), 'cpr': text(model.cpr(*args), DIGITS),
                                    'smm': text(model.smm(*args), DIGITS)}
    return {'points': points}


# ---------------------------------------------------------------------------------------------------------
# PM1-FIT-01
# ---------------------------------------------------------------------------------------------------------

FIT_SEED = 4111
FIT_DESIGN = ('0.015', '0.32', '300', '0.003')
FIT_ASSUMPTIONS: dict[str, Any] = {'a_ramp': '12', 'b': '1.2',
                   'season': ['0.82', '0.86', '0.98', '1.04', '1.10', '1.14', '1.16', '1.08', '1.00', '0.98', '0.94',
                              '0.90']}
FIT_MONTHS = ('2024-01-31', '2024-02-29', '2024-03-31', '2024-04-30', '2024-05-31', '2024-06-30')
FIT_BUCKETS = range(-4, 4)
# Offsets of the three loans of a bucket-month within its bucket, in basis points: always inside
# (25 j, 25 j + 12.5), so buckets anchored at 0 and buckets centred on 0 group the loans alike.
FIT_OFFSETS = (('2', '7', '11'), ('3.5', '5', '10'), ('1.25', '8.5', '12'))
FIT_AGES = (3, 9, 15, 30, 60, 120)
FIT_POOL = ('1', '0.92', '0.85', '0.7', '0.55')
FIT_NOISE = D('0.2')    # raw residual up to 20 % of the predicted bucket SMM, before projection
HEADER = 'loan_id,segment,currency,as_of_date,opening_balance,scheduled_principal,other_change,' \
         'prepaid_principal,event,incentive,age,pool_factor'
Loan = tuple[str, Decimal, int, Decimal, Decimal]    # as_of, incentive, age, pool factor, A


def solve(matrix: list[list[Decimal]], vector: list[Decimal]) -> list[Decimal]:
    """Gaussian elimination with partial pivoting."""
    n = len(vector)
    rows = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(rows[r][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(col + 1, n):
            factor = rows[r][col] / rows[col][col]
            rows[r] = [x - factor * y for x, y in zip(rows[r], rows[col])]
    out = [D(0)] * n
    for i in reversed(range(n)):
        out[i] = (rows[i][n] - sum((rows[i][j] * out[j] for j in range(i + 1, n)), D(0))) / rows[i][i]
    return out


class Problem:
    """The weighted least-squares objective of decision M11 over bucket-month groups, in decimal.

    Predictions and their derivatives in theta are analytic, valid where no loan-month's CPR is
    clamped (checked); the Hessian of the objective is a central difference of its gradient.
    """

    def __init__(self, model: Model, groups: list[list[Loan]], prepaid: list[Decimal]) -> None:
        self.model, self.groups = model, groups
        self.weights = [sum((loan[4] for loan in g), D(0)) for g in groups]
        self.observed = [p / w for p, w in zip(prepaid, self.weights)]

    def evaluate(self, theta: tuple[Decimal, ...]) -> tuple[list[Decimal], list[list[Decimal]]]:
        """Predicted bucket values and their derivatives in (c_min, c_max, k, x0)."""
        c_min, c_max, k, x0 = theta
        model = self.model
        values, jac = [], []
        for group, weight in zip(self.groups, self.weights):
            value, grad = D(0), [D(0)] * 4
            for t, incentive, age, pool, available in group:
                shape = 1 / (1 + (-(k * (incentive - x0))).exp())
                burn = (-model.b * (1 - pool)).exp()
                scale = (D(1) if model.a_ramp == 0 else min(D(1), D(age) / model.a_ramp)) \
                    * model.season[int(t[5:7]) - 1]
                cpr = (c_min + (c_max - c_min) * burn * shape) * scale
                if not 0 < cpr < 1:
                    raise ValueError('a clamped CPR has no derivative')
                survival = ((1 - cpr).ln() / 12).exp()    # (1 - CPR)^(1/12)
                d_smm = survival / (12 * (1 - cpr)) * scale    # dSMM/dCPR x dCPR/ds
                slope = (c_max - c_min) * burn * shape * (1 - shape)
                partial = [1 - burn * shape, burn * shape, slope * (incentive - x0), -slope * k]
                value += available * (1 - survival)
                grad = [g + available * d_smm * p for g, p in zip(grad, partial)]
            values.append(value / weight)
            jac.append([g / weight for g in grad])
        return values, jac

    def objective(self, theta: tuple[Decimal, ...]) -> Decimal:
        predicted, _ = self.evaluate(theta)
        return sum((w * (o - p) ** 2 for w, o, p in zip(self.weights, self.observed, predicted)), D(0))

    def normal(self, jac: list[list[Decimal]], residual: list[Decimal]) -> tuple[list[list[Decimal]], list[Decimal]]:
        """J'WJ and J'Wr."""
        jtwj = [[sum((w * row[a] * row[b] for w, row in zip(self.weights, jac)), D(0)) for b in range(4)]
                for a in range(4)]
        jtwr = [sum((w * row[a] * r for w, row, r in zip(self.weights, jac, residual)), D(0)) for a in range(4)]
        return jtwj, jtwr

    def gradient(self, theta: tuple[Decimal, ...]) -> list[Decimal]:
        """-2 J'W (observed - predicted)."""
        predicted, jac = self.evaluate(theta)
        _, jtwr = self.normal(jac, [o - p for o, p in zip(self.observed, predicted)])
        return [-2 * g for g in jtwr]

    def hessian(self, theta: tuple[Decimal, ...]) -> list[list[Decimal]]:
        """Central differences of the gradient, step 1e-15 relative, symmetrised."""
        columns = []
        for j in range(4):
            h = D('1e-15') * max(D(1), abs(theta[j]))
            up = self.gradient(tuple(x + h if i == j else x for i, x in enumerate(theta)))
            down = self.gradient(tuple(x - h if i == j else x for i, x in enumerate(theta)))
            columns.append([(u - d) / (2 * h) for u, d in zip(up, down)])
        return [[(columns[a][b] + columns[b][a]) / 2 for b in range(4)] for a in range(4)]

    def newton(self, theta: tuple[Decimal, ...]) -> tuple[tuple[Decimal, ...], int, list[list[Decimal]]]:
        """Newton's method on the gradient; returns the optimum, iterations and the last Hessian."""
        for iteration in range(1, 10):
            hess = self.hessian(theta)
            step = solve(hess, [-g for g in self.gradient(theta)])
            theta = tuple(x + s for x, s in zip(theta, step))
            if max(abs(s) / max(D(1), abs(x)) for s, x in zip(step, theta)) < D('1e-30'):
                return theta, iteration, hess
        raise ValueError('Newton did not converge')


def cholesky_pivots(matrix: list[list[Decimal]]) -> list[Decimal]:
    """Pivots of the LDL' factorisation: all positive exactly when the matrix is positive definite."""
    n = len(matrix)
    work = [list(row) for row in matrix]
    pivots = []
    for k in range(n):
        pivots.append(work[k][k])
        for i in range(k + 1, n):
            factor = work[i][k] / work[k][k]
            for j in range(k, n):
                work[i][j] -= factor * work[k][j]
    return pivots


def fit_design() -> tuple[str, Problem, Decimal]:
    """The PM1-FIT-01 fixture text and its decimal problem."""
    rng = random.Random(FIT_SEED)
    model = Model(FIT_ASSUMPTIONS['a_ramp'], FIT_ASSUMPTIONS['b'], list(FIT_ASSUMPTIONS['season']))
    design = tuple(D(x) for x in FIT_DESIGN)
    groups: list[list[Loan]] = []
    balances: list[list[tuple[Decimal, Decimal]]] = []
    serial = 0
    for t in FIT_MONTHS:
        for j in FIT_BUCKETS:
            scale = 1 + 9 * D(rng.random())    # group sizes differ by up to a factor of 10
            group, amounts = [], []
            for offset in FIT_OFFSETS[(len(groups)) % 3]:
                opening = (scale * D(200_000 + 800_000 * rng.random())).quantize(D('0.0001'))
                scheduled = (opening * D('0.003')).quantize(D('0.0001'))
                group.append((t, (25 * j + D(offset)) / 10_000, FIT_AGES[serial % 6],
                              D(FIT_POOL[(serial * 2) % 5]), opening - scheduled))
                amounts.append((opening, scheduled))
                serial += 1
            groups.append(group)
            balances.append(amounts)
    with localcontext(Context(prec=PRECISION)):
        exact = Problem(model, groups, [D(0)] * len(groups))
        target, jac = exact.evaluate(design)
        raw = [p * FIT_NOISE * (2 * D(rng.random()) - 1) for p in target]
        jtwj, jtwu = exact.normal(jac, raw)
        coef = solve(jtwj, jtwu)
        residual = [u - sum((row[a] * coef[a] for a in range(4)), D(0)) for u, row in zip(raw, jac)]
        design_objective = sum((w * r * r for w, r in zip(exact.weights, residual)), D(0))
        lines, prepaid = [HEADER], []
        serial = 0
        for g, (group, amounts, smm) in enumerate(zip(groups, balances, (p + r for p, r in zip(target, residual)))):
            total = exact.weights[g] * smm
            rest = sum((loan[4] for loan in group[1:]), D(0))
            group_prepaid = D(0)
            for n, ((t, incentive, age, pool, available), (opening, scheduled)) in enumerate(zip(group, amounts)):
                amount = D(0) if n == 0 else (total * available / rest).quantize(D('0.0001'))
                if not 0 <= amount < available:
                    raise ValueError('prepayment outside (0, A)')
                group_prepaid += amount
                serial += 1
                lines.append(f'F{serial:03d},MTG_FIX,EUR,{t},{opening},{scheduled},0,{amount},'
                             f'{"PARTIAL" if amount else "NONE"},{incentive},{age},{pool}')
            prepaid.append(group_prepaid)
    return '\n'.join(lines) + '\n', Problem(model, groups, prepaid), design_objective


def derive_fit() -> dict[str, object]:
    fixture, problem, design_objective = fit_design()
    design = tuple(D(x) for x in FIT_DESIGN)
    with localcontext(Context(prec=PRECISION)):
        theta, iterations, hessian = problem.newton(design)
        gradient = problem.gradient(theta)
        pivots = cholesky_pivots(hessian)
        if min(pivots) <= 0:
            raise ValueError('the stationary point is not a minimum')
        names = ('c_min', 'c_max', 'k', 'x0')
        return {
            'fixture': fixture,
            'parameters': {n: text(x, DIGITS) for n, x in zip(names, theta)},
            'objective': text(problem.objective(theta), DIGITS),
            'total_weight': text(sum(problem.weights, D(0)), DIGITS),
            'bucket_months': len(problem.groups),
            'check': {
                'design_parameters': dict(zip(names, FIT_DESIGN)),
                'design_objective_before_rounding': text(design_objective, DIGITS),
                'max_relative_shift_from_design': text(max(abs(x - d) / max(D(1), abs(d))
                                                           for x, d in zip(theta, design)), 3),
                'newton_iterations': iterations,
                'max_abs_gradient': text(max(abs(g) for g in gradient), 3),
                'hessian_ldl_pivots': [text(p, 6) for p in pivots],
            },
        }


# ---------------------------------------------------------------------------------------------------------
# PM1-DGP-01
# ---------------------------------------------------------------------------------------------------------

DGP_SEED = 20261128
DGP_TRUE = ('0.01', '0.30', '250', '0.0025')
DGP_ASSUMPTIONS: dict[str, Any] = {'a_ramp': '18', 'b': '0.9',
                   'season': ['0.85', '0.88', '0.97', '1.02', '1.08', '1.12', '1.15', '1.06', '1.00', '0.97', '0.96',
                              '0.94']}
DGP_MONTHS = 24
DGP_BUCKETS = range(-6, 6)
DGP_OFFSETS = ('4', '10')    # basis points inside each bucket, away from either anchoring of its edges
DGP_AGES = (4, 12, 30, 90)
DGP_POOL = ('1', '0.85', '0.7', '0.55')
CELL_HEADER = 'as_of_date,incentive,age,pool_factor,loans,balance,full_events'


def month_end_text(index: int) -> str:
    """The index-th month end from January 2023."""
    year, month = 2023 + index // 12, index % 12 + 1
    days = [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return f'{year:04d}-{month:02d}-{days:02d}'


def binomial(n: int, p: float, u: float) -> int:
    """Inverse CDF of Binomial(n, p) at u, from probability ratios around the mode: basic IEEE arithmetic only."""
    if p <= 0.0:
        return 0
    mode = min(n, int((n + 1) * p))
    ratio = p / (1.0 - p)
    weights = {mode: 1.0}
    k, w = mode, 1.0
    while k < n and w > 1e-40:
        w *= (n - k) / (k + 1) * ratio
        k += 1
        weights[k] = w
    k, w = mode, 1.0
    while k > 0 and w > 1e-40:
        w *= k / ((n - k + 1) * ratio)
        k -= 1
        weights[k] = w
    total = sum(weights[i] for i in sorted(weights))
    acc = 0.0
    for i in sorted(weights):
        acc += weights[i]
        if acc >= u * total:
            return i
    return max(weights)


def dgp_sample() -> str:
    rng = random.Random(DGP_SEED)
    model = Model(DGP_ASSUMPTIONS['a_ramp'], DGP_ASSUMPTIONS['b'], list(DGP_ASSUMPTIONS['season']))
    theta = tuple(D(x) for x in DGP_TRUE)
    lines = [CELL_HEADER]
    with localcontext(Context(prec=PRECISION)):
        for m in range(DGP_MONTHS):
            t = month_end_text(m)
            for c, (j, offset) in enumerate((j, o) for j in DGP_BUCKETS for o in DGP_OFFSETS):
                incentive = (25 * j + D(offset)) / 10_000
                age, pool = DGP_AGES[(m + c) % 4], D(DGP_POOL[(3 * m + c) % 4])
                loans = 10_000 + int(20_000 * rng.random())
                balance = D(20_000 + 200_000 * rng.random()).quantize(D('0.01'))
                smm = float(model.smm(theta, incentive, age, t, pool))
                lines.append(f'{t},{incentive},{age},{pool},{loans},{balance},{binomial(loans, smm, rng.random())}')
    return '\n'.join(lines) + '\n'


def derive() -> dict[str, Any]:
    return {
        'PM0-CALC-01': {'MTG_FIX|EUR': realised(PM0_WINDOW), 'MTG_FIX|USD': realised(PM0_USD)},
        'PM1-FORM-01': derive_form(),
        'PM1-FIT-01': derive_fit(),
    }


if __name__ == '__main__':
    derived = derive()
    derived['PM1-FIT-01'].pop('fixture')
    print(json.dumps(derived, indent=2))
