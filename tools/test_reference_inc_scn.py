"""Rate-incentive and overlay cases: run the references on each fixture and compare with its expected file."""
from __future__ import annotations

import json
import random
import sys
import unittest
from dataclasses import replace
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests' / 'reference'))
import derive_inc_scn  # noqa: E402
import incentive  # noqa: E402
import overlay  # noqa: E402

FIXTURES = ROOT / 'tests' / 'fixtures'


def expected(case: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / 'tests' / 'expected' / f'{case}.json').read_text(encoding='utf-8'))
    return data


def within(value: float, reference: str, tolerance: str) -> bool:
    """The register's tolerance rule: ``abs e`` or ``rel e`` against a decimal or a fraction."""
    kind, size = tolerance.split()
    ref, bound = Fraction(reference), Fraction(size)
    if kind == 'rel':
        bound *= max(Fraction(1), abs(ref))
    return abs(Fraction(value) - ref) <= bound


def margins(settings: dict[str, Any]) -> dict[str, float]:
    return {segment: float(value) for segment, value in settings['margins'].items()}


def optional_date(text: str) -> date | None:
    return date.fromisoformat(text) if text else None


class IncentiveCases(unittest.TestCase):
    def assert_near(self, value: float, reference: str, tolerance: str, label: str) -> None:
        self.assertTrue(within(value, reference, tolerance), f'{label}: {value!r} against {reference}')

    def test_inc_calc_01(self) -> None:
        spec = expected('INC-CALC-01')
        tol, settings = spec['tolerance'], spec['settings']
        self.assertEqual(incentive.LAG_MONTHS, settings['lag_months'], 'decision M4')
        rates = incentive.read_market_rates(FIXTURES / 'INC-CALC-01' / 'market_rates.csv')
        series = settings['refi_curve_series']
        months = incentive.read_incentive_months(FIXTURES / 'INC-CALC-01' / 'loan_months.csv')
        self.assertEqual(sorted(f'{m.loan_id}|{m.as_of_date}' for m in months), sorted(spec['incentives']))
        for month in months:
            key = f'{month.loan_id}|{month.as_of_date}'
            want = spec['incentives'][key]
            s = incentive.rate_date(month.as_of_date)
            self.assertEqual(s.isoformat(), want['rate_date'], key)
            rate = incentive.market_rate(rates, series, month.currency, s, month.term_years)
            self.assert_near(rate, want['refinancing_rate'], tol, f'{key} R')
            self.assert_near(margins(settings)[month.segment], want['margin'], tol, f'{key} m')
            charge = incentive.penalty(month.penalty_type, month.penalty_value, month.client_rate, month.term_years)
            self.assert_near(charge, want['penalty'], tol, f'{key} penalty')
            value = incentive.loan_month_incentive(month, rates, series, margins(settings))
            self.assert_near(value, want['incentive'], tol, f'{key} I')
            for lag in (0, 2):
                other = incentive.market_rate(rates, series, month.currency,
                                              incentive.rate_date(month.as_of_date, lag), month.term_years)
                self.assertFalse(within(other, '0', tol), f'{key}: the fixture separates lag {lag} from M4')

    def test_inc_calc_01_term_ends(self) -> None:
        want = expected('INC-CALC-01')['term_ends']
        path = FIXTURES / 'INC-CALC-01' / 'term_ends.csv'
        rows = incentive.read_rows(path, ('loan_id', 'rate_type', 'maturity_date', 'fixed_until', 'period_start'))
        self.assertEqual(sorted(row['loan_id'] for row in rows), sorted(want))
        for row in rows:
            end = incentive.term_end(row['rate_type'], date.fromisoformat(row['maturity_date']),
                                     optional_date(row['fixed_until']), date.fromisoformat(row['period_start']))
            self.assertEqual(end.isoformat() if end else None, want[row['loan_id']], row['loan_id'])
        with self.assertRaises(ValueError):
            incentive.term_end('RESET', date(2039, 6, 30), date(2024, 2, 29), date(2024, 2, 29))

    def test_penalty_inputs_are_checked(self) -> None:
        cases: list[tuple[str, float | None]] = [('NONE', 0.01), ('PCT', None), ('PCT', -0.01), ('MONTHS', 3.0)]
        for penalty_type, value in cases:
            with self.assertRaises(ValueError, msg=f'{penalty_type} {value}'):
                incentive.penalty(penalty_type, value, 0.04, 2.0)

    def test_inc_curve_01(self) -> None:
        spec = expected('INC-CURVE-01')
        rates = incentive.read_market_rates(FIXTURES / 'INC-CURVE-01' / 'market_rates.csv')
        series = spec['settings']['refi_curve_series']
        queries = incentive.read_rows(FIXTURES / 'INC-CURVE-01' / 'queries.csv',
                                      ('label', 'as_of_date', 'currency', 'term_years'))
        self.assertEqual(sorted(q['label'] for q in queries), sorted(spec['rates']))
        for query in queries:
            rate = incentive.market_rate(rates, series, query['currency'], date.fromisoformat(query['as_of_date']),
                                         float(query['term_years']))
            self.assert_near(rate, spec['rates'][query['label']], spec['tolerance'], query['label'])
        with self.assertRaises(ValueError):
            incentive.market_rate(rates, series, 'EUR', date(2024, 2, 29), -0.5)
        with self.assertRaises(ValueError):
            incentive.market_rate(rates, series, 'CHF', date(2024, 2, 29), 1.0)

    def perturbed(self, rates: list[incentive.MarketRate], after: date, rng: random.Random,
                  spec: dict[str, Any]) -> list[incentive.MarketRate]:
        """Every row dated after `after` dropped or redrawn, and rows added at later month ends."""
        low, high, drop = float(spec['rate_low']), float(spec['rate_high']), float(spec['drop_probability'])
        out: list[incentive.MarketRate] = []
        for row in rates:
            if row.as_of_date <= after:
                out.append(row)
            elif rng.random() >= drop:
                out.append(replace(row, rate=round(rng.uniform(low, high), 8)))
        series = sorted({(row.rate_id, row.currency, row.tenor_months) for row in rates})
        for day in spec['added_month_ends']:
            out += [incentive.MarketRate(date.fromisoformat(day), rate_id, currency, tenor,
                                         round(rng.uniform(low, high), 8)) for rate_id, currency, tenor in series]
        return out

    def test_inc_lag_01(self) -> None:
        spec = expected('INC-LAG-01')
        settings, trial = spec['settings'], spec['perturbation']
        self.assertEqual(incentive.LAG_MONTHS, settings['lag_months'], 'decision M4')
        rates = incentive.read_market_rates(FIXTURES / 'INC-LAG-01' / 'market_rates.csv')
        months = incentive.read_incentive_months(FIXTURES / 'INC-LAG-01' / 'loan_months.csv')
        series, margin = settings['refi_curve_series'], margins(settings)
        self.assertEqual(sorted(f'{m.loan_id}|{m.as_of_date}' for m in months), sorted(spec['rate_dates']))
        rng = random.Random(trial['seed'])
        for month in months:
            key = f'{month.loan_id}|{month.as_of_date}'
            s = incentive.rate_date(month.as_of_date)
            self.assertEqual(s.isoformat(), spec['rate_dates'][key], key)
            base = incentive.loan_month_incentive(month, rates, series, margin)
            lag_zero = incentive.loan_month_incentive(month, rates, series, margin, lag=0)
            lag_zero_changed = 0
            for _ in range(trial['trials']):
                altered = self.perturbed(rates, s, rng, trial)
                self.assertEqual(incentive.loan_month_incentive(month, altered, series, margin), base, key)
                try:
                    changed = incentive.loan_month_incentive(month, altered, series, margin, lag=0) != lag_zero
                except ValueError:    # a configured series dropped at t: the result depends on it
                    changed = True
                lag_zero_changed += changed
            self.assertGreater(lag_zero_changed, 0, f'{key}: negative control, lag 0 reads the altered rows')
            shift = float(trial['control_shift'])
            moved = [replace(row, rate=row.rate + shift) if row.as_of_date == s and row.rate_id in series else row
                     for row in rates]
            self.assertNotEqual(incentive.loan_month_incentive(month, moved, series, margin), base,
                                f'{key}: negative control, a rate at t - L moves the incentive')

    def test_expected_values_equal_their_derivation(self) -> None:
        derived = derive_inc_scn.derive()
        for case in ('INC-CALC-01', 'INC-CURVE-01', 'SCN-FLOOR-01', 'SCN-GAMMA-01'):
            spec = expected(case)
            self.assertEqual({key: spec[key] for key in derived[case]}, derived[case], case)


class OverlayCases(unittest.TestCase):
    def assert_near(self, value: float, reference: str, tolerance: str, label: str) -> None:
        self.assertTrue(within(value, reference, tolerance), f'{label}: {value!r} against {reference}')

    def test_scn_floor_01(self) -> None:
        spec = expected('SCN-FLOOR-01')
        tol = spec['tolerance']
        points = overlay.read_table(FIXTURES / 'SCN-FLOOR-01' / 'points.csv',
                                    ('label', 'maturity_years', 'observed', 'shocked'))
        self.assertEqual(sorted(p['label'] for p in points), sorted(spec['points']))
        for point in points:
            label, want = point['label'], spec['points'][point['label']]
            maturity, observed, shocked = (float(point[k]) for k in ('maturity_years', 'observed', 'shocked'))
            floor = overlay.post_shock_floor(maturity, observed)
            floored = overlay.floored_rate(maturity, observed, shocked)
            self.assert_near(floor, want['floor'], tol, f'{label} floor')
            self.assert_near(floored, want['floored'], tol, f'{label} floored')
            self.assertGreaterEqual(floored, shocked, f'{label}: a lower bound only')
            if shocked >= floor:
                self.assertEqual(floored, shocked, f'{label}: a shocked rate above the floor is unchanged')
        with self.assertRaises(ValueError):
            overlay.post_shock_floor(-1.0, 0.01)

    def test_scn_gamma_01(self) -> None:
        spec = expected('SCN-GAMMA-01')
        tol = spec['tolerance']
        self.assertEqual(overlay.GAMMA, {k: float(v) for k, v in spec['gamma'].items()})
        base = overlay.read_table(FIXTURES / 'SCN-GAMMA-01' / 'cpr_base.csv', ('label', 'cpr_base'))
        self.assertEqual(sorted(spec['cpr']), sorted([*overlay.GAMMA, 'BASE']))
        for scenario, want in spec['cpr'].items():
            self.assertEqual(sorted(row['label'] for row in base), sorted(want), scenario)
            for row in base:
                cpr = overlay.standardised_cpr(scenario, float(row['cpr_base']))
                self.assert_near(cpr, want[row['label']], tol, f'{scenario} {row["label"]}')
                self.assertLessEqual(cpr, 1.0)
        for scenario in ('CONTRACT', 'USER_PARALLEL'):
            with self.assertRaises(ValueError):
                overlay.standardised_cpr(scenario, 0.1)
        for value in (-1e-12, 1.0 + 1e-12, float('nan')):
            with self.assertRaises(ValueError):
                overlay.standardised_cpr('PAR_UP', value)


if __name__ == '__main__':
    unittest.main()
