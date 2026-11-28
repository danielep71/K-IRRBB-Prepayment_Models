"""PM1-DGP-01: fit the reference estimator to the generated sample and report the recovery.

Run offline: ``python tests/reference/report_dgp.py`` prints the report held in
tests/expected/PM1-DGP-01.json. The sample comes from derive_models.dgp_sample (seed and
parameters recorded there); the estimator is models.fit. The report is statistical, not a
tolerance test: it states the estimates, their difference from the generating values and an
approximate standard error of each, from the sandwich formula of weighted least squares with
the binomial variance of each cell's FULL count evaluated at the estimates.
"""
from __future__ import annotations

import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any

import derive_models
import models

FIXTURE = derive_models.FIXTURES / 'PM1-DGP-01' / 'cells.csv'
NAMES = ('c_min', 'c_max', 'k', 'x0')
SETTINGS = models.Settings(models.Curve(0.05, 0.5, 100.0, 0.0), (0.5, 0.5, 0.5, 0.0025), 1e-6, 1e-10, 5000, 3)


def assumptions() -> models.Assumptions:
    spec = derive_models.DGP_ASSUMPTIONS
    return models.Assumptions(float(spec['a_ramp']), float(spec['b']), tuple(float(s) for s in spec['season']))


def invert(matrix: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan inverse with partial pivoting."""
    n = len(matrix)
    work = [list(row) + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(work[r][col]))
        work[col], work[pivot] = work[pivot], work[col]
        lead = work[col][col]
        work[col] = [x / lead for x in work[col]]
        for r in range(n):
            if r != col:
                factor = work[r][col]
                work[r] = [x - factor * y for x, y in zip(work[r], work[col])]
    return [row[n:] for row in work]


def standard_errors(curve: models.Curve, assume: models.Assumptions, path: Path) -> list[float]:
    """Sandwich standard errors (J'WJ)^-1 J'W V W J (J'WJ)^-1 at the estimates."""
    lines = path.read_text(encoding='utf-8').splitlines()
    cells = [dict(zip(lines[0].split(','), line.split(','))) for line in lines[1:]]
    rows = models.read_cells(path)
    variance: dict[tuple[int, str], float] = {}
    for cell, row in zip(cells, rows):
        smm = models.pm1_smm(curve, assume, row.incentive, row.age, models.calendar_month(row.as_of_date),
                             row.pool_factor)
        key = (models.bucket(row.incentive), row.as_of_date)
        variance[key] = variance.get(key, 0.0) + float(Decimal(cell['balance'])) ** 2 * int(cell['loans']) \
            * smm * (1.0 - smm)
    fitted = models.groups(rows)
    theta = [curve.c_min, curve.c_max, curve.k, curve.x0]
    columns = []
    for j in range(4):
        h = 1e-6 * abs(theta[j])

        def at(shift: float) -> dict[tuple[int, str], float]:
            moved = models.Curve(*[x + shift if i == j else x for i, x in enumerate(theta)])
            return {key: models.predicted(moved, assume, g) for key, g in fitted.items()}
        up, down = at(h), at(-h)
        columns.append({key: (up[key] - down[key]) / (2 * h) for key in fitted})
    bread = [[math.fsum(g.weight * columns[a][key] * columns[b][key] for key, g in fitted.items())
              for b in range(4)] for a in range(4)]
    meat = [[math.fsum(variance[key] * columns[a][key] * columns[b][key] for key in fitted)
             for b in range(4)] for a in range(4)]
    inverse = invert(bread)
    cov = [[math.fsum(inverse[a][i] * meat[i][j] * inverse[j][b] for i in range(4) for j in range(4))
            for b in range(4)] for a in range(4)]
    return [math.sqrt(cov[j][j]) for j in range(4)]


def report() -> dict[str, Any]:
    assume = assumptions()
    rows = models.read_cells(FIXTURE)
    result = models.fit(rows, assume, SETTINGS)
    if result.curve is None or result.objective is None:
        raise ValueError(f'the reference fit failed: {result.reason}')
    truth = [float(x) for x in derive_models.DGP_TRUE]
    estimate = [result.curve.c_min, result.curve.c_max, result.curve.k, result.curve.x0]
    errors = standard_errors(result.curve, assume, FIXTURE)
    objective_at_truth = models.objective(models.Curve(*truth), assume, models.groups(rows))
    return {
        'estimated': result.estimated,
        'iterations': result.iterations,
        'objective_at_estimate': f'{result.objective:.15g}',
        'objective_at_generating_parameters': f'{objective_at_truth:.15g}',
        'parameters': {name: {'generating': derive_models.DGP_TRUE[i], 'estimate': f'{estimate[i]:.15g}',
                              'difference': f'{estimate[i] - truth[i]:.6g}',
                              'approx_standard_error': f'{errors[i]:.6g}',
                              'difference_in_standard_errors': f'{(estimate[i] - truth[i]) / errors[i]:.3f}'}
                       for i, name in enumerate(NAMES)},
    }


if __name__ == '__main__':
    print(json.dumps(report(), indent=2))
