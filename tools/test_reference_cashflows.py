"""Built (Python) cash-flow and scenario cases: run the references on each fixture and compare with its expected file.

CF-SCHED-01, CF-PREPAY-01 and CF-RESET-01 compare projected months with values derived exactly
by derive_cashflows.py; CF-CONS-01 checks conservation on every projected month; SCN-BASE-01 and
SCN-MONO-01 are property tests with hand-derived views and negative controls, as DATA-PIT-02.
"""
from __future__ import annotations

import json
import random
import sys
import unittest
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests' / 'reference'))
import cashflows  # noqa: E402
import derive_cashflows  # noqa: E402
import scenarios  # noqa: E402
from cashflows import ContractQuestion, Loan, Month, Position  # noqa: E402

FIXTURES = ROOT / 'tests' / 'fixtures'
Results = dict[str, list[Month]]


def expected(case: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / 'tests' / 'expected' / f'{case}.json').read_text(encoding='utf-8'))
    return data


def within(value: float, reference: str, tolerance: str) -> bool:
    """The register's tolerance rule: ``abs e`` or ``rel e`` against a decimal reference."""
    kind, size = tolerance.split()
    ref, bound = Fraction(reference), Fraction(size)
    if kind == 'rel':
        bound *= max(Fraction(1), abs(ref))
    return abs(Fraction(value) - ref) <= bound


def book(folder: Path) -> tuple[dict[str, Loan], list[Position]]:
    loans = cashflows.read_loans(folder / 'loans.csv')
    return loans, cashflows.read_positions(folder / 'positions.csv', loans)


def loan(amortisation: str = 'LINEAR', payment_months: int = 1, rate_type: str = 'FIXED',
         origination: date = date(2024, 1, 15), maturity: date = date(2025, 1, 15),
         fixed_until: date | None = None, reset_months: int | None = None) -> Loan:
    return Loan('X1', 'MTG_FIX', 'EUR', origination, maturity, rate_type, fixed_until, reset_months, amortisation,
                payment_months, 'NONE')


class Schedules(unittest.TestCase):
    def assert_book(self, case: str) -> Results:
        spec = expected(case)
        tol = spec['tolerance']
        results = cashflows.project_book(FIXTURES / spec['fixture'])
        self.assertEqual(sorted(results), sorted(spec['loans']))
        for loan_id, want in spec['loans'].items():
            months = results[loan_id]
            self.assertEqual([m.as_of_date.isoformat() for m in months], want['months'], f'{case} {loan_id}')
            measures = [*cashflows.MEASURES, *(('instalment',) if 'instalment' in want else ())]
            for measure in measures:
                for month, ref in zip(months, want[measure], strict=True):
                    value = month.interest + month.scheduled if measure == 'instalment' else getattr(month, measure)
                    self.assertTrue(within(value, ref, tol),
                                    f'{case} {loan_id} {month.as_of_date} {measure}: {value!r} against {ref}')
        return results

    def test_cf_sched_01(self) -> None:
        results = self.assert_book('CF-SCHED-01')
        # Without prepayment an annuity's instalment is level and a linear loan's principal is constant.
        for loan_id in ('S-ANN-STD', 'S-ANN-ZERO', 'S-ANN-TINY', 'S-ANN-NEG', 'S-ANN-MID'):
            instalments = [m.interest + m.scheduled for m in results[loan_id]]
            self.assertLess(max(instalments) - min(instalments), 1e-8, loan_id)
        for loan_id in ('S-LIN-1', 'S-LIN-3', 'S-LIN-6', 'S-LIN-12'):
            self.assertEqual(len({round(m.scheduled, 6) for m in results[loan_id] if m.scheduled}), 1, loan_id)

    def test_cf_prepay_01(self) -> None:
        results = self.assert_book('CF-PREPAY-01')
        loans, _ = book(FIXTURES / 'CF-PREPAY-01')
        for loan_id in ('P1', 'P3'):
            months = results[loan_id]
            # M6: the maturity is kept; the balance is repaid in the maturity month and not before.
            self.assertEqual(months[-1].as_of_date, cashflows.month_end(loans[loan_id].maturity_date))
            self.assertTrue(all(m.closing > 1.0 for m in months[:-1]), loan_id)
            self.assertLess(abs(months[-1].closing), 1e-8, loan_id)
            # ... and the instalment falls by the factor 1 - SMM of the month that prepaid.
            for before, after in zip(months, months[1:]):
                ratio = (after.interest + after.scheduled) / (before.interest + before.scheduled)
                self.assertAlmostEqual(ratio, 1.0 - before.smm, places=12, msg=f'{loan_id} {after.as_of_date}')
                if before.prepaid > 0:
                    self.assertLess(after.interest + after.scheduled, before.interest + before.scheduled)
        full = results['P2']
        self.assertEqual(full[1].smm, 1.0)
        self.assertEqual([m.closing for m in full[1:]], [0.0] * 3)

    def test_cf_reset_01(self) -> None:
        results = self.assert_book('CF-RESET-01')
        loans, positions = book(FIXTURES / 'CF-RESET-01')
        for position in positions:
            loan_id, as_of = position.loan.loan_id, position.as_of_date
            months = results[loan_id]
            reset = cashflows.next_reset(loans[loan_id], as_of)
            maturity = cashflows.month_end(loans[loan_id].maturity_date)
            self.assertIsNotNone(reset, loan_id)
            if reset is not None and reset < maturity:
                # The balance leaves as repricing principal at the next reset; nothing is projected after it.
                self.assertEqual(months[-1].as_of_date, reset, loan_id)
                self.assertEqual(months[-1].repricing, months[-1].opening, loan_id)
                self.assertGreater(months[-1].repricing, 0.0, loan_id)
                self.assertEqual(months[-1].closing, 0.0, loan_id)
            else:
                self.assertEqual(months[-1].as_of_date, maturity, loan_id)
                self.assertEqual(months[-1].scheduled, months[-1].opening, loan_id)
            self.assertEqual([m.repricing for m in months[:-1]], [0.0] * (len(months) - 1), loan_id)

    def test_expected_values_equal_their_derivation(self) -> None:
        derived = derive_cashflows.derive()
        for case in ('CF-SCHED-01', 'CF-PREPAY-01', 'CF-RESET-01'):
            self.assertEqual(expected(case)['loans'], derived[case]['loans'], case)
        for case in ('SCN-BASE-01', 'SCN-MONO-01'):
            self.assertEqual(expected(case)['views'], derived[case]['views'], case)


class ContractQuestions(unittest.TestCase):
    """Treatments the contract leaves open are refused, never chosen (see tests/reference/README.md)."""

    def project(self, subject: Loan, cpr: float = 0.0, as_of: date = date(2024, 1, 31)) -> None:
        months = cashflows.projection_months(subject, as_of)
        cashflows.project(Position(subject, as_of, 1000.0, 0.03), [cpr] * len(months))

    def test_open_schedule_questions_are_refused(self) -> None:
        for payment_months in (3, 6, 12):
            with self.assertRaises(ContractQuestion):
                self.project(loan('ANNUITY', payment_months))
        with self.assertRaises(ContractQuestion):    # 14-month term: origination and maturity anchors differ
            self.project(loan('LINEAR', 3, origination=date(2023, 11, 15)))
        self.project(loan('BULLET', 3, origination=date(2023, 11, 15)))    # a bullet has no such question

    def test_open_reset_questions_are_refused(self) -> None:
        floating = loan('LINEAR', 1, 'FLOAT', origination=date(2023, 1, 15), reset_months=3)
        with self.assertRaises(ContractQuestion):    # the reset month is a monthly payment month
            self.project(floating)
        bullet = loan('BULLET', 1, 'FLOAT', origination=date(2023, 1, 15), reset_months=3)
        self.project(bullet)
        with self.assertRaises(ContractQuestion):    # a positive SMM in the reset month
            self.project(bullet, cpr=0.1)
        with self.assertRaises(ContractQuestion):    # a reset in the maturity month
            self.project(loan('BULLET', 1, 'FLOAT', origination=date(2024, 1, 15), maturity=date(2024, 4, 20),
                              reset_months=3))

    def test_open_scenario_questions_are_refused(self) -> None:
        season = (1.0,) * 12
        with self.assertRaises(ContractQuestion):
            scenarios.PM1(0.02, 0.3, 100.0, 0.0, 0.0, season, 0.5)
        settings = scenarios.Settings(scenarios.PM1(0.02, 0.3, 100.0, 0.0, 0.0, season, 0.0), 0.005, 1)
        penalised = Loan('X1', 'MTG_FIX', 'EUR', date(2024, 1, 15), date(2025, 1, 15), 'FIXED', None, None,
                         'BULLET', 1, 'PCT')
        with self.assertRaises(ContractQuestion):
            scenarios.cpr_path(Position(penalised, date(2024, 1, 31), 1000.0, 0.03), {'EUR': 0.03}, settings)
        with self.assertRaises(ContractQuestion):
            scenarios.shocked_curve({'EUR': 0.01}, -0.02)
        rates_file = FIXTURES / 'SCN-BASE-01' / 'market_rates.csv'
        self.assertEqual(scenarios.read_curve(rates_file, date(2023, 12, 31)), {'EUR': 0.032, 'USD': 0.042})
        with self.assertRaises(ContractQuestion):    # two tenors in one currency need T in years
            scenarios.curve_at([dict(zip(scenarios.RATE_FIELDS, ('2024-01-31', f'EUR_SWAP_{n}M', 'EUR', str(n), r)))
                                for n, r in ((24, '0.02'), (60, '0.03'))], date(2024, 1, 31))


def gap(total: float | Fraction, parts: list[float]) -> Fraction:
    return abs(Fraction(total) - sum((Fraction(p) for p in parts), Fraction(0)))


class Conservation(unittest.TestCase):
    """CF-CONS-01: opening = scheduled + prepaid + repricing + closing every month; lifetime principal = opening."""

    def assert_conserved(self, loans: dict[str, Loan], results: Results, tolerance: Fraction, label: str) -> None:
        for loan_id, months in results.items():
            for month in months:
                parts = [month.scheduled, month.prepaid, month.repricing, month.closing]
                self.assertLessEqual(gap(month.opening, parts), tolerance, f'{label} {loan_id} {month.as_of_date}')
            for before, after in zip(months, months[1:]):
                self.assertEqual(after.opening, before.closing, f'{label} {loan_id} {after.as_of_date}')
            principal = [x for m in months for x in (m.scheduled, m.prepaid, m.repricing)]
            self.assertLessEqual(gap(months[0].opening, principal), tolerance, f'{label} {loan_id} lifetime')
            self.assertLessEqual(abs(Fraction(months[-1].closing)), tolerance, f'{label} {loan_id} final closing')
        for key, sums in cashflows.aggregate(loans, results).items():
            opening, _, scheduled, prepaid, repricing, closing = sums
            self.assertLessEqual(gap(opening, [scheduled, prepaid, repricing, closing]), tolerance, f'{label} {key}')

    def test_cf_cons_01(self) -> None:
        spec = expected('CF-CONS-01')
        tolerance = Fraction(spec['tolerance'].split()[1])
        loans, positions = book(FIXTURES / spec['fixture'])
        generator = spec['generator']
        rng = random.Random(spec['seed'])
        self.assertEqual({p.loan.loan_id: len(cashflows.projection_months(p.loan, p.as_of_date)) for p in positions},
                         spec['horizons'])
        for trial in range(spec['trials']):
            results: Results = {}
            for position in positions:
                reset = cashflows.next_reset(position.loan, position.as_of_date)
                path = []
                for when in cashflows.projection_months(position.loan, position.as_of_date):
                    draw = rng.random()
                    cpr = 0.0 if draw < generator['zero_share'] else 1.0 if draw < generator['zero_share'] + \
                        generator['full_share'] else round(rng.uniform(0.0, generator['max_cpr']), 6)
                    path.append(0.0 if when == reset else cpr)
                results[position.loan.loan_id] = cashflows.project(position, path)
            with self.subTest(trial=trial):
                self.assert_conserved(loans, results, tolerance, f'trial {trial}')
                # Totals per segment and currency, never across currencies: the first month opens at the hand sum.
                first = positions[0].as_of_date
                opened = {f'{s}|{c}': sums[0] for (s, c, when), sums in cashflows.aggregate(loans, results).items()
                          if cashflows.months_between(first, when) == 1}
                self.assertEqual(sorted(opened), sorted(spec['opening_balances']))
                for key, opening in opened.items():
                    self.assertLessEqual(gap(Fraction(spec['opening_balances'][key]), [opening]), tolerance, key)
                for loan_id, month_end in spec['repricing_months'].items():
                    last = results[loan_id][-1]
                    self.assertEqual((last.as_of_date.isoformat(), last.repricing), (month_end, last.opening))
                lifetime: dict[str, list[float]] = {}
                for loan_id, months in results.items():
                    key = f'{loans[loan_id].segment}|{loans[loan_id].currency}'
                    lifetime.setdefault(key, []).extend(x for m in months for x in (m.scheduled, m.prepaid, m.repricing))
                self.assertEqual(sorted(lifetime), sorted(spec['opening_balances']))
                for key, flows in lifetime.items():
                    self.assertLessEqual(gap(Fraction(spec['opening_balances'][key]), flows), tolerance, key)

    def test_identity_on_every_other_case(self) -> None:
        tolerance = Fraction(expected('CF-CONS-01')['tolerance'].split()[1])
        for case in ('CF-SCHED-01', 'CF-PREPAY-01', 'CF-RESET-01'):
            loans, _ = book(FIXTURES / case)
            self.assert_conserved(loans, cashflows.project_book(FIXTURES / case), tolerance, case)
        folder = FIXTURES / 'SCN-BASE-01'
        loans, positions = book(folder)
        settings = scenarios.read_settings(folder / 'settings.csv')
        curve = scenarios.read_curve(folder / 'market_rates.csv', positions[0].as_of_date)
        for shock in (0.0, 0.02, -0.02):
            results = scenarios.run(positions, scenarios.shocked_curve(curve, shock), settings)
            self.assert_conserved(loans, results, tolerance, f'SCN-BASE-01 shock {shock}')


def random_settings(rng: random.Random) -> scenarios.Settings:
    """PM1 parameters inside the contract's constraints, seasonal factors in pairs 1 +/- s (mean 1), b = 0."""
    c_min = rng.uniform(0.0, 0.1)
    c_max = c_min + (1.0 - c_min) * rng.uniform(0.05, 0.9)
    swings = [round(rng.uniform(0.0, 0.5), 2) for _ in range(6)]
    season = [1.0 + s for s in swings] + [1.0 - s for s in swings]
    rng.shuffle(season)
    params = scenarios.PM1(c_min, c_max, rng.uniform(5.0, 200.0), rng.uniform(-0.03, 0.03),
                           rng.choice((0.0, 6.0, 12.0, 30.0)), tuple(season), 0.0)
    return scenarios.Settings(params, rng.uniform(0.0, 0.01), 1)


class ScenarioCase(unittest.TestCase):
    case = ''

    def setUp(self) -> None:
        self.spec = expected(self.case)
        folder = FIXTURES / self.spec['fixture']
        self.loans, self.positions = book(folder)
        self.settings = scenarios.read_settings(folder / 'settings.csv')
        self.curve = scenarios.read_curve(folder / 'market_rates.csv', self.positions[0].as_of_date)
        self.rng = random.Random(self.spec['seed'])

    def run_shock(self, shock: float | None, settings: scenarios.Settings | None = None,
                  curve: dict[str, float] | None = None) -> Results:
        """BASE (shock None) uses the observed curve itself; a scenario applies its parallel shock."""
        observed = self.curve if curve is None else curve
        scenario = observed if shock is None else scenarios.shocked_curve(observed, shock)
        return scenarios.run(self.positions, scenario, self.settings if settings is None else settings)

    def assert_view(self, months: list[Month], want: dict[str, list[str]], measure: str, tolerance: str) -> None:
        self.assertEqual([m.as_of_date.isoformat() for m in months], want['months'])
        for month, ref in zip(months, want[measure], strict=True):
            value = getattr(month, measure)
            self.assertTrue(within(value, ref, tolerance), f'{self.case} {month.as_of_date} {measure}: {value!r} {ref}')


class ScenarioBase(ScenarioCase):
    """SCN-BASE-01: a zero shock reproduces the BASE cash flows exactly."""
    case = 'SCN-BASE-01'

    def test_views(self) -> None:
        tolerances = self.spec['view_tolerance']
        base = self.run_shock(None)
        for loan_id, want in self.spec['views'].items():
            for measure in ('cpr', 'smm', *cashflows.MEASURES):
                self.assert_view(base[loan_id], want, measure, tolerances.get(measure, tolerances['amounts']))

    def test_zero_shock_reproduces_base(self) -> None:
        zeros = [float(z) for z in self.spec['zero_shocks']]
        control = float(self.spec['control_shock'])
        for trial in range(self.spec['trials']):
            settings = random_settings(self.rng)
            curve = {currency: round(self.rng.uniform(0.005, 0.06), 6) for currency in self.curve}
            base = self.run_shock(None, settings, curve)
            with self.subTest(trial=trial):
                for zero in zeros:
                    self.assertEqual(self.run_shock(zero, settings, curve), base)
                # Negative control: the same comparison detects a 1bp shock.
                self.assertNotEqual(self.run_shock(control, settings, curve), base)


def monotone(lower: Results, higher: Results) -> bool:
    """CPR of ``lower`` no higher than CPR of ``higher`` in every loan and projected month."""
    if sorted(lower) != sorted(higher):
        raise ValueError('different books')
    return all(low.cpr <= high.cpr for loan_id in lower for low, high in zip(lower[loan_id], higher[loan_id],
                                                                              strict=True))


class ScenarioMonotone(ScenarioCase):
    """SCN-MONO-01: parallel up gives CPR no higher than BASE in every month; parallel down no lower."""
    case = 'SCN-MONO-01'

    def test_views(self) -> None:
        shock = float(self.spec['view_shock'])
        runs = {'PAR_DOWN': self.run_shock(-shock), 'BASE': self.run_shock(None), 'PAR_UP': self.run_shock(shock)}
        for loan_id, want in self.spec['views'].items():
            for name, results in runs.items():
                self.assert_view(results[loan_id], {'months': want['months'], 'cpr': want[name]}, 'cpr',
                                 self.spec['view_tolerance'])

    def test_parallel_shocks_order_cpr(self) -> None:
        for trial in range(self.spec['trials']):
            settings = random_settings(self.rng)
            shock = self.rng.randint(1, self.spec['max_shock_bp']) / 10_000
            base = self.run_shock(None, settings)
            up, down = self.run_shock(shock, settings), self.run_shock(-shock, settings)
            with self.subTest(trial=trial, shock=shock):
                self.assertTrue(monotone(up, base))
                self.assertTrue(monotone(base, down))
                # Negative control: with up and down exchanged the same comparison fails.
                self.assertFalse(monotone(base, up))
                self.assertFalse(monotone(down, base))


if __name__ == '__main__':
    unittest.main()
