"""Built (Python) PM0 and PM1 cases: run the reference models on each fixture and compare with its expected file."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests' / 'reference'))
import derive_models  # noqa: E402
import models  # noqa: E402
import rates  # noqa: E402
import report_dgp  # noqa: E402

FIXTURES = ROOT / 'tests' / 'fixtures'
NAMES = ('c_min', 'c_max', 'k', 'x0')


def expected(case: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / 'tests' / 'expected' / f'{case}.json').read_text(encoding='utf-8'))
    return data


@lru_cache(maxsize=None)
def derived() -> dict[str, Any]:
    return derive_models.derive()


def within(value: float | Decimal | Fraction, reference: str, tolerance: str) -> bool:
    """The register's tolerance rule: ``abs e`` or ``rel e`` against a decimal."""
    kind, size = tolerance.split()
    ref, bound = Fraction(reference), Fraction(size)
    if kind == 'rel':
        bound *= max(Fraction(1), abs(ref))
    return math.isfinite(value) and abs(Fraction(value) - ref) <= bound


def curve(spec: dict[str, str]) -> models.Curve:
    return models.Curve(*(float(spec[name]) for name in NAMES))


def assumptions(spec: dict[str, Any]) -> models.Assumptions:
    return models.Assumptions(float(spec['a_ramp']), float(spec['b']), tuple(float(s) for s in spec['season']))


def settings(start: dict[str, str], spec: dict[str, Any]) -> models.Settings:
    return models.Settings(curve(start), tuple(float(s) for s in spec['steps']), float(spec['ftol']),
                           float(spec['xtol']), spec['max_iterations'], spec['restarts'])


def fit_case() -> tuple[list[rates.LoanMonth], list[models.FitRow], dict[str, Any]]:
    months, rows = models.read_fit_rows(FIXTURES / 'PM1-FIT-01' / 'loan_months.csv')
    spec: dict[str, Any] = json.loads((FIXTURES / 'PM1-FIT-01' / 'settings.json').read_text(encoding='utf-8'))
    return months, rows, spec


class Checks(unittest.TestCase):
    def assert_near(self, value: float | Decimal | Fraction, reference: str, tolerance: str, label: str) -> None:
        self.assertTrue(within(value, reference, tolerance), f'{label}: {value!r} against {reference}')


class PM0Cases(Checks):
    def test_pm0_calc_01(self) -> None:
        spec = expected('PM0-CALC-01')
        tol, window = spec['tolerance'], spec['window']
        months = rates.read_loan_months(FIXTURES / 'PM0-CALC-01' / 'loan_months.csv')
        got = {'|'.join(key): value for key, value in
               models.pm0(months, window['start'], window['end'], spec['include_reneg']).items()}
        self.assertEqual(sorted(got), sorted(spec['pools']))
        pools = rates.pool_rates(models.in_window(months, window['start'], window['end']), spec['include_reneg'])
        for key, want in spec['pools'].items():
            segment, currency = key.split('|')
            sums = {t: {'prepaid': str(p.prepaid), 'available': str(p.available)}
                    for (s, c, t), p in sorted(pools.items()) if (s, c) == (segment, currency)}
            self.assertEqual({t: {k: Decimal(v) for k, v in m.items()} for t, m in sums.items()},
                             {t: {k: Decimal(v) for k, v in m.items()} for t, m in want['months'].items()}, key)
            self.assert_near(got[key], want['pm0'], tol, f'{key} PM0')
            for wrong in ('average_of_monthly_cprs', 'cpr_of_window_pooled_smm', 'cpr_of_mean_monthly_smm'):
                self.assertFalse(within(got[key], want[wrong], tol), f'{key}: PM0 is not the {wrong}')

    def test_a_month_without_loan_months_is_refused(self) -> None:
        """Reference choice: the contract does not say whether such a month counts in n."""
        months = rates.read_loan_months(FIXTURES / 'PM0-CALC-01' / 'loan_months.csv')
        with self.assertRaises(ValueError):
            models.pm0(months, '2024-01-31', '2024-07-31')    # USD has no loan-month in January

    def test_expected_values_equal_their_derivation(self) -> None:
        for key, want in expected('PM0-CALC-01')['pools'].items():
            self.assertEqual({k: v for k, v in want.items() if k != 'months'}, derived()['PM0-CALC-01'][key])
        table = {'MTG_FIX|EUR': derive_models.PM0_WINDOW, 'MTG_FIX|USD': derive_models.PM0_USD}
        for key, want in expected('PM0-CALC-01')['pools'].items():
            self.assertEqual({t: (int(m['prepaid']), int(m['available'])) for t, m in want['months'].items()},
                             table[key])


class PM1FormCases(Checks):
    def test_pm1_form_01(self) -> None:
        spec = expected('PM1-FORM-01')
        tol = spec['tolerance']
        folder = FIXTURES / 'PM1-FORM-01'
        sets = {}
        with (folder / 'parameters.csv').open(encoding='utf-8', newline='') as handle:
            for row in csv.DictReader(handle):
                sets[row['set']] = (curve(row), assumptions({**row, 'season': [row[f'season_{m}']
                                                                               for m in range(1, 13)]}))
        with (folder / 'points.csv').open(encoding='utf-8', newline='') as handle:
            points = list(csv.DictReader(handle))
        self.assertEqual([p['point'] for p in points], list(spec['points']))
        for point in points:
            want = spec['points'][point['point']]
            args = (*sets[point['set']], float(point['incentive']), int(point['age']),
                    models.calendar_month(point['as_of_date']), float(point['pool_factor']))
            self.assert_near(models.pm1_raw(*args), want['raw'], tol, f'{point["point"]} raw')
            self.assert_near(models.pm1_cpr(*args), want['cpr'], tol, f'{point["point"]} CPR')
            self.assert_near(models.pm1_smm(*args), want['smm'], tol, f'{point["point"]} SMM')

    def test_inputs_outside_the_contract_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            models.Assumptions(12.0, 1.0, (1.1,) * 12)    # Season factors with mean 1.1
        with self.assertRaises(ValueError):
            models.Assumptions(12.0, 1.0, (1.0,) * 11)
        for bad in ((0.3, 0.2, 100.0, 0.0), (-0.01, 0.2, 100.0, 0.0), (0.1, 1.01, 100.0, 0.0), (0.1, 0.2, 0.0, 0.0)):
            with self.assertRaises(ValueError):
                models.Curve(*bad)

    def test_expected_values_equal_their_derivation(self) -> None:
        self.assertEqual(expected('PM1-FORM-01')['points'], derived()['PM1-FORM-01']['points'])


class PM1FitCases(Checks):
    def test_pm1_fit_01(self) -> None:
        spec = expected('PM1-FIT-01')
        tol = spec['tolerance']
        _, rows, fixture = fit_case()
        for start in fixture['starts']:
            with self.subTest(start=start):
                result = models.fit(rows, assumptions(fixture['assumptions']), settings(start, fixture['optimiser']))
                self.assertTrue(result.estimated, result.reason)
                assert result.curve is not None and result.objective is not None
                for name in NAMES:
                    self.assert_near(getattr(result.curve, name), spec['parameters'][name], tol['parameters'], name)
                self.assert_near(result.objective, spec['objective'], tol['objective'], 'objective')

    def test_objective_at_the_expected_parameters(self) -> None:
        spec = expected('PM1-FIT-01')
        months, rows, fixture = fit_case()
        groups = models.groups(rows)
        self.assertEqual(len(groups), spec['bucket_months'])
        self.assertEqual(sum((m.available for m in months), Decimal(0)), Decimal(spec['total_weight']))
        value = models.objective(curve(spec['parameters']), assumptions(fixture['assumptions']), groups)
        self.assert_near(value, spec['objective'], spec['tolerance']['objective'], 'objective')

    def test_parametrisation_enforces_the_constraints(self) -> None:
        """c_min = logistic(p1), c_max = c_min + (1 - c_min) logistic(p2), k = exp(p3), x0 = p4."""
        got = models.curve_from_p([0.0, 0.0, 0.0, 0.001])
        self.assertEqual((got.c_min, got.c_max, got.k, got.x0), (0.5, 0.75, 1.0, 0.001))
        got = models.curve_from_p([math.log(3), math.log(3), math.log(300), -0.002])
        for value, want in zip((got.c_min, got.c_max, got.k, got.x0), ('0.75', '0.9375', '300', '-0.002')):
            self.assert_near(value, want, 'rel 1e-12', 'curve from p')
        for p1 in (-30.0, -2.0, 0.0, 2.0, 30.0):
            for p2 in (-30.0, -2.0, 0.0, 2.0, 30.0):
                got = models.curve_from_p([p1, p2, -5.0, 0.0])    # Curve refuses values outside the constraints
                self.assertTrue(0.0 <= got.c_min <= got.c_max <= 1.0 and got.k > 0.0)

    def test_grouping_does_not_depend_on_the_bucket_anchor(self) -> None:
        """Bucket edges at multiples of 25 bp, or shifted by 12.5 bp, group the fixture's loan-months alike."""
        _, rows, _ = fit_case()
        partitions = [sorted(sorted(map(id, g.rows)) for g in models.groups(rows, offset).values())
                      for offset in (0.0, models.BUCKET_WIDTH / 2)]
        self.assertEqual(partitions[0], partitions[1])
        self.assertTrue(all(len(g.rows) == 3 for g in models.groups(rows).values()))

    def test_fixture_and_expected_values_equal_their_derivation(self) -> None:
        want = derived()['PM1-FIT-01']
        self.assertEqual((FIXTURES / 'PM1-FIT-01' / 'loan_months.csv').read_text(encoding='utf-8'), want['fixture'])
        spec = expected('PM1-FIT-01')
        self.assertEqual({k: v for k, v in spec.items() if k not in ('case', 'provenance', 'tolerance')},
                         {k: v for k, v in want.items() if k != 'fixture'})
        _, _, fixture = fit_case()
        self.assertEqual(fixture['assumptions'], derive_models.FIT_ASSUMPTIONS)


class PM1FailCases(Checks):
    def test_pm1_fail_01(self) -> None:
        spec = expected('PM1-FAIL-01')
        fixture = json.loads((FIXTURES / 'PM1-FAIL-01' / 'settings.json').read_text(encoding='utf-8'))
        _, rows = models.read_fit_rows(FIXTURES / fixture['data'])
        assume = json.loads((FIXTURES / fixture['assumptions']).read_text(encoding='utf-8'))['assumptions']
        injected = {'nan': math.nan, 'inf': math.inf}
        for name, want in spec['variants'].items():
            variant = fixture['variants'][name]
            with self.subTest(variant=name):
                value = injected.get(variant.get('injected_objective', ''))
                target = None if value is None else (lambda p, v=value: v)
                result = models.fit(rows, assumptions(assume), settings(variant['start'], variant), target)
                self.assertEqual(result.estimated, want['estimated'])
                if not want['estimated']:
                    self.assertEqual(result.reason, want['reason'])
                    self.assertIsNone(result.curve)
                    self.assertIsNone(result.objective)
                    self.assertEqual(want['parameters'], None)


    def test_a_non_finite_value_at_the_start_stops_the_fit(self) -> None:
        """Reference choice: any non-finite value met by the search fails the fit. The contract does not say
        whether it means the objective anywhere in the search or only at the optimum, so this is not in the
        expected file."""
        _, rows, fixture = fit_case()
        start = fixture['starts'][0]
        p_start = models.p_from_curve(curve(start))

        def target(p: list[float]) -> float:
            return math.nan if p == p_start else math.fsum((x - 1.0) ** 2 for x in p)
        result = models.fit(rows, assumptions(fixture['assumptions']), settings(start, fixture['optimiser']), target)
        self.assertEqual((result.estimated, result.reason, result.curve), (False, models.NON_FINITE, None))


    def test_a_non_finite_trial_point_stops_the_search(self) -> None:
        """A NaN or infinity at any evaluation (start simplex, reflection, expansion, contraction or shrink)
        stops the search as non-finite (reference choice, as above); it is never discarded as merely worse."""
        def bowl(x: list[float]) -> float:
            return math.fsum((v - 2.0) ** 2 for v in x)

        calls: list[int] = []

        def counted(x: list[float]) -> float:
            calls.append(1)
            return bowl(x)
        clean = models.nelder_mead(counted, [0.0, 0.0], [1.0, 1.0], 1e-12, 1e-8, 1000)
        self.assertEqual((clean.converged, clean.non_finite), (True, False))
        for bad in (math.nan, math.inf):
            for n in range(1, len(calls) + 1):
                seen: list[int] = []

                def target(x: list[float], bad: float = bad, n: int = n, seen: list[int] = seen) -> float:
                    seen.append(1)
                    return bad if len(seen) == n else bowl(x)
                with self.subTest(bad=bad, evaluation=n):
                    result = models.nelder_mead(target, [0.0, 0.0], [1.0, 1.0], 1e-12, 1e-8, 1000)
                    self.assertEqual((result.converged, result.non_finite), (False, True))

class PM1MinCases(Checks):
    def loan_months(self) -> list[rates.LoanMonth]:
        out = []
        with (FIXTURES / 'PM1-MIN-01' / 'monthly_counts.csv').open(encoding='utf-8', newline='') as handle:
            for row in csv.DictReader(handle):
                full = int(row['full_events'])
                for n in range(int(row['loan_months'])):
                    event = 'FULL' if n < full else 'NONE'
                    out.append(rates.LoanMonth(f'{row["segment"]}{row["currency"]}{n}', row['segment'],
                                               row['currency'], row['as_of_date'], Decimal(1000), Decimal(10),
                                               Decimal(0), Decimal(990 if event == 'FULL' else 0), event))
        return out

    def test_pm1_min_01(self) -> None:
        spec = expected('PM1-MIN-01')
        self.assertEqual(spec['minimum'], {'month_ends': models.MIN_MONTH_ENDS, 'loan_months': models.MIN_LOAN_MONTHS,
                                           'full_events': models.MIN_FULL_EVENTS})
        months = self.loan_months()
        _, rows, fixture = fit_case()
        start = fixture['starts'][0]
        for name, variant in spec['variants'].items():
            got = {'|'.join(key): sample for key, sample in
                   models.samples(months, variant['start'], variant['end']).items()}
            self.assertEqual(sorted(got), sorted(variant['pools']), name)
            for key, want in variant['pools'].items():
                with self.subTest(variant=name, pool=key):
                    sample = got[key]
                    self.assertEqual((sample.month_ends, sample.loan_months, sample.full_events),
                                     (want['month_ends'], want['loan_months'], want['full_events']))
                    self.assertEqual(sample.shortfalls(), want['shortfalls'])
                    self.assertEqual(not sample.shortfalls(), want['meets_minimum_sample'])
                    if not want['meets_minimum_sample']:
                        # Rows that would fit, so only the minimum sample stops the estimate.
                        result = models.estimate(sample, rows, assumptions(fixture['assumptions']),
                                                 settings(start, fixture['optimiser']))
                        self.assertFalse(result.estimated)
                        self.assertIsNone(result.curve)
                        self.assertEqual(result.reason, f'{models.BELOW_MINIMUM}: {", ".join(want["shortfalls"])}')


class PM1DgpCases(Checks):
    """Statistical and reported: these tests check reproduction of the committed report, not recovery."""

    def test_fixture_equals_its_generation(self) -> None:
        spec = expected('PM1-DGP-01')
        text = (FIXTURES / 'PM1-DGP-01' / 'cells.csv').read_text(encoding='utf-8')
        self.assertEqual(text, derive_models.dgp_sample())
        self.assertEqual(hashlib.sha256(text.encode('utf-8')).hexdigest(), spec['sample']['sha256'])
        generator = spec['generator']
        self.assertEqual(generator['seed'], derive_models.DGP_SEED)
        self.assertEqual(tuple(generator['generating_parameters'][n] for n in NAMES), derive_models.DGP_TRUE)
        self.assertEqual(generator['assumptions'], derive_models.DGP_ASSUMPTIONS)
        lines = [line.split(',') for line in text.splitlines()[1:]]
        self.assertEqual((len(lines), sum(int(r[4]) for r in lines), sum(int(r[6]) for r in lines)),
                         (spec['sample']['cells'], spec['sample']['loan_months'], spec['sample']['full_events']))

    def test_report_reproduces(self) -> None:
        spec = expected('PM1-DGP-01')
        self.assertEqual(settings(spec['settings']['start'], spec['settings']), report_dgp.SETTINGS)
        got, want = report_dgp.report(), spec['report']
        self.assertTrue(got['estimated'])
        for name in NAMES:
            self.assert_near(float(got['parameters'][name]['estimate']), want['parameters'][name]['estimate'],
                             'rel 1e-6', name)
        for name in ('objective_at_estimate', 'objective_at_generating_parameters'):
            self.assert_near(float(got[name]), want[name], 'rel 1e-9', name)
        self.assertLessEqual(float(got['objective_at_estimate']), float(got['objective_at_generating_parameters']))


if __name__ == '__main__':
    unittest.main()
