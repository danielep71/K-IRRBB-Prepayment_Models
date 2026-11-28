"""Built (Python) EVE and repricing-gap cases: run the reference on each fixture and compare with its expected file."""
from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests' / 'reference'))
import derive_eve  # noqa: E402
import eve  # noqa: E402

FIXTURES = ROOT / 'tests' / 'fixtures'
ALL_SCENARIOS = {eve.CONTRACT, eve.BASE, *eve.SUPERVISORY}


def expected(case: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / 'tests' / 'expected' / f'{case}.json').read_text(encoding='utf-8'))
    return data


def within(value: float | Decimal | Fraction, reference: str, tolerance: str) -> bool:
    """The register's tolerance rule: ``exact``, ``abs e`` or ``rel e`` against a decimal or a fraction."""
    if tolerance == 'exact':
        return Fraction(value) == Fraction(reference)
    kind, size = tolerance.split()
    ref, bound = Fraction(reference), Fraction(size)
    if kind == 'rel':
        bound *= max(Fraction(1), abs(ref))
    return abs(Fraction(value) - ref) <= bound


def joined(key: tuple[str, ...]) -> str:
    return '|'.join(key)


def sign(value: Decimal | Fraction) -> int:
    return (value > 0) - (value < 0)


class EveCases(unittest.TestCase):
    def assert_near(self, value: float | Decimal | Fraction, reference: str, tolerance: str, label: str) -> None:
        self.assertTrue(within(value, reference, tolerance), f'{label}: {value!r} against {reference}')

    def assert_projection_rows(self, flows: list[eve.CashFlow]) -> None:
        """Fixture sanity: opening = scheduled + prepaid + repricing + closing, rows chained, ending at 0."""
        for key, group in eve.by_key(flows).items():
            for flow in group:
                self.assertEqual(flow.opening - flow.principal, flow.closing, f'{key} month {flow.k}')
            for before, after in zip(group, group[1:]):
                self.assertEqual(before.closing, after.opening, f'{key} month {after.k}')
            self.assertEqual(group[-1].closing, 0, key)

    def test_fixtures_are_consistent_projections(self) -> None:
        for case in ('EVE-PV-01', 'GAP-BUCKET-01', 'GAP-CONS-01', 'MEAS-01'):
            with self.subTest(case=case):
                self.assert_projection_rows(eve.read_cash_flows(FIXTURES / case / 'cash_flows.csv'))

    def test_eve_pv_01(self) -> None:
        spec = expected('EVE-PV-01')
        tol = spec['tolerance']
        flows = eve.read_cash_flows(FIXTURES / 'EVE-PV-01' / 'cash_flows.csv')
        curves = eve.read_curves(FIXTURES / 'EVE-PV-01' / 'curves.csv')
        self.assertEqual(sorted(joined(c) for c in curves), sorted(spec['curves']))
        for (scenario, currency), curve in curves.items():
            for k, want in spec['curves'][f'{scenario}|{currency}'].items():
                label = f'{scenario} {currency} month {k}'
                self.assert_near(eve.zero_rate(curve, int(k) / 12), want['zero_rate'], tol, f'z {label}')
                self.assert_near(eve.discount_factor(curve, int(k)), want['discount_factor'], tol, f'DF {label}')
        values = eve.present_values(flows, curves)
        self.assertEqual(sorted(joined(k) for k in values), sorted(spec['present_values']))
        for key, value in values.items():
            self.assert_near(value, spec['present_values'][joined(key)], tol, f'PV {key}')
        totals = eve.currency_totals(values)
        self.assertEqual(sorted(joined(k) for k in totals), sorted(spec['currency_totals']))
        for currency_key, total in totals.items():
            self.assert_near(total, spec['currency_totals'][joined(currency_key)], tol, f'PV total {currency_key}')

    def test_eve_delta_01(self) -> None:
        spec = expected('EVE-DELTA-01')
        tol = spec['tolerance']
        results = eve.delta_eve(eve.read_present_values(FIXTURES / 'EVE-DELTA-01' / 'present_values.csv'))
        # One result per layer and currency: no cross-currency total, no layer when it was not requested.
        self.assertEqual(sorted(joined(k) for k in results), sorted(spec['results']))
        for key, result in results.items():
            want = spec['results'][joined(key)]
            label = joined(key)
            self.assert_near(result.pv_base, want['pv_base'], tol, f'{label} PV_BASE')
            if want['pv_contract'] is None:
                self.assertIsNone(result.pv_contract, label)
            else:
                self.assertIsNotNone(result.pv_contract, label)
                self.assert_near(result.pv_contract or Decimal(0), want['pv_contract'], tol, f'{label} CONTRACT')
            self.assertEqual(sorted(result.delta), sorted(want['delta']), label)
            for scenario, delta in result.delta.items():
                self.assert_near(delta, want['delta'][scenario], tol, f'{label} {scenario}')
                self.assertEqual(sign(delta), sign(Fraction(want['delta'][scenario])), f'{label} {scenario} sign')
            self.assert_near(result.worst, want['worst'], tol, f'{label} worst')
            self.assertEqual(result.worst_scenario, want['worst_scenario'], label)
            self.assertEqual(result.label, eve.INDICATOR_LABEL)
            self.assertIsNone(result.ratio)
        for currency in ('EUR', 'USD'):
            # Both layers subtract the same PV_BASE (M15).
            self.assertEqual(results[('INTERNAL', currency)].pv_base, results[('STANDARDISED', currency)].pv_base)
        # The fixture makes each exclusion observable: CONTRACT and a user shock are lower than the worst.
        internal = spec['results']['INTERNAL|EUR']
        worst = Fraction(internal['worst'])
        self.assertLess(Fraction(internal['pv_contract']) - Fraction(internal['pv_base']), worst)
        self.assertLess(Fraction(internal['delta']['USER_UP_300']), worst)

    def test_delta_needs_complete_unlayered_bases(self) -> None:
        rows = eve.read_present_values(FIXTURES / 'EVE-DELTA-01' / 'present_values.csv')
        broken = {
            'missing supervisory scenario': [r for r in rows if (r.currency, r.scenario) != ('GBP', 'FLATTENER')],
            'missing BASE': [r for r in rows if (r.currency, r.scenario) != ('USD', 'BASE')],
            'layered BASE': [eve.PresentValue(r.currency, 'INTERNAL', r.scenario, r.pv)
                             if r.scenario == eve.BASE else r for r in rows],
            'unknown layer': [*rows, eve.PresentValue('EUR', 'OTHER', 'PAR_UP', Decimal(1))],
            'duplicate scenario': [*rows, rows[-1]],
        }
        for name, values in broken.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                eve.delta_eve(values)

    def test_eve_ratio_01(self) -> None:
        spec = expected('EVE-RATIO-01')
        rows = eve.read_present_values(FIXTURES / 'EVE-RATIO-01' / 'present_values.csv')
        allowlist = set(spec['currency_allowlist'])
        for name, variant in spec['variants'].items():
            settings = variant['settings']
            with self.subTest(variant=name):
                results = eve.run_eve(rows, settings['ratio_requested'], settings['tier1_amount'],
                                      settings['tier1_currency'], allowlist)
                self.assertEqual(sorted(joined(k) for k in results), sorted(variant['ratios']))
                for key, result in results.items():
                    want = variant['ratios'][joined(key)]
                    # dEVE is reported in every currency; only the Tier 1 currency gets a ratio.
                    self.assertTrue(within(result.worst, spec['worst'][joined(key)], 'exact'), key)
                    self.assertEqual(result.label, spec['label'])
                    if want is None:
                        self.assertIsNone(result.ratio, key)
                        self.assertIsNone(result.indicator, key)
                        continue
                    self.assertEqual(result.ratio, Fraction(want['ratio']), key)
                    self.assertIs(result.indicator, want['indicator'], key)
                    # The points are safe in double precision too: the same indicator from floats.
                    in_floats = -float(result.worst) / float(Decimal(settings['tier1_amount'])) > 0.15
                    self.assertIs(in_floats, want['indicator'], key)

    def test_invalid_tier1_stops_the_run(self) -> None:
        spec = expected('EVE-RATIO-01')
        rows = eve.read_present_values(FIXTURES / 'EVE-RATIO-01' / 'present_values.csv')
        without_base = [r for r in rows if r.scenario != eve.BASE]    # would fail in the calculation
        allowlist = set(spec['currency_allowlist'])
        for item in spec['invalid_tier1']:
            for values in (rows, without_base):
                with self.subTest(reason=item['reason'], complete=values is rows), \
                        self.assertRaises(eve.Tier1Error):
                    eve.run_eve(values, True, item['tier1_amount'], item['tier1_currency'], allowlist)
        with self.assertRaises(ValueError) as caught:
            eve.run_eve(without_base, True, '1000', 'EUR', allowlist)
        self.assertNotIsInstance(caught.exception, eve.Tier1Error)

    def assert_gaps(self, gaps: dict[eve.Key, list[Decimal]], want: dict[str, dict[str, str]],
                    tolerance: str) -> None:
        self.assertEqual(sorted(joined(k) for k in gaps), sorted(want))
        for key, gap in gaps.items():
            self.assertEqual(len(gap), eve.BUCKETS)
            buckets = want[joined(key)]
            for number in range(1, eve.BUCKETS + 1):
                self.assert_near(gap[number - 1], buckets.get(str(number), '0'), tolerance,
                                 f'{joined(key)} bucket {number}')

    def test_gap_bucket_01(self) -> None:
        spec = expected('GAP-BUCKET-01')
        flows = eve.read_cash_flows(FIXTURES / 'GAP-BUCKET-01' / 'cash_flows.csv')
        for k, number in spec['placements'].items():
            self.assertEqual(eve.bucket_of(int(k)), number, f'month {k}')
        gaps = eve.repricing_gap(flows)
        self.assert_gaps(gaps, spec['gaps'], spec['tolerance'])
        for gap in gaps.values():
            self.assertEqual(gap[0], 0, 'the overnight bucket is empty on a monthly grid')
        for key, reset in spec['resets'].items():
            group = [f for f in flows if joined(f.key) == key and f.repricing]
            self.assertEqual([(f.k, f.repricing) for f in group], [(reset['reset_month'], Decimal(reset['balance']))])
            self.assertEqual(eve.bucket_of(reset['reset_month']), reset['reset_bucket'])
            self.assertEqual(eve.bucket_of(reset['maturity_month']), reset['maturity_bucket'])
            self.assertNotEqual(reset['reset_bucket'], reset['maturity_bucket'])
            gap = gaps[tuple(key.split('|'))]
            self.assertGreaterEqual(gap[reset['reset_bucket'] - 1], Decimal(reset['balance']), key)
            self.assertEqual(gap[reset['maturity_bucket'] - 1], 0, key)
        for k in (0, -1):
            with self.assertRaises(ValueError):
                eve.bucket_of(k)

    def test_gap_cons_01(self) -> None:
        spec = expected('GAP-CONS-01')
        tol = spec['tolerance']
        flows = eve.read_cash_flows(FIXTURES / 'GAP-CONS-01' / 'cash_flows.csv')
        gaps = eve.repricing_gap(flows)
        self.assert_gaps(gaps, spec['gaps'], tol)
        pools = {}
        for row in eve.read_rows(FIXTURES / 'GAP-CONS-01' / 'outstanding.csv', ('segment', 'currency', 'outstanding')):
            pools[(row['segment'], row['currency'])] = Decimal(row['outstanding'])
        self.assertEqual({joined(k): str(v) for k, v in pools.items()}, spec['outstanding'])
        for (segment, currency), outstanding in pools.items():
            scenarios = {s for s, g, c in gaps if (g, c) == (segment, currency)}
            self.assertEqual(scenarios, ALL_SCENARIOS | {'USER_UP_300'}, 'every scenario has a gap')
        for (scenario, segment, currency), gap in gaps.items():
            outstanding = pools[(segment, currency)]
            self.assertTrue(eve.gap_conserves(gap, outstanding), (scenario, segment, currency))
            self.assert_near(sum(gap, Decimal(0)), str(outstanding), tol, f'{scenario} {segment} {currency}')
        # Negative control: a projection that loses its last principal flow breaks the identity.
        for key, group in eve.by_key(flows).items():
            with self.subTest(dropped=key):
                gap = eve.repricing_gap(group[:-1])[key]
                self.assertFalse(eve.gap_conserves(gap, pools[key[1:]]))

    def test_meas_01(self) -> None:
        spec = expected('MEAS-01')
        tol = spec['tolerance']
        flows = eve.read_cash_flows(FIXTURES / 'MEAS-01' / 'cash_flows.csv')
        times = eve.repricing_time(flows)
        self.assertEqual(sorted(joined(k) for k in times), sorted(spec['repricing_time']))
        for key, value in times.items():
            self.assertIsNotNone(value)
            self.assert_near(value or Fraction(0), spec['repricing_time'][joined(key)], tol, f'repricing time {key}')
        groups = eve.by_key(flows)
        for window, months in (('first_12_months', 12), ('projection', None)):
            cprs = eve.projected_cpr(flows, months)
            self.assertEqual(sorted(joined(k) for k in cprs), sorted(spec['projected_cpr']))
            for key, cpr in cprs.items():
                want = spec['projected_cpr'][joined(key)][window]
                counted = [k for k, smm in eve.projected_smms(groups[key])
                           if smm is not None and (months is None or k <= months)]
                self.assertEqual(len(counted), want['months'], f'n of {key} {window}')
                if want['cpr'] is None:
                    self.assertIsNone(cpr, f'{key} {window}')
                else:
                    self.assertIsNotNone(cpr, f'{key} {window}')
                    self.assert_near(cpr or 0.0, want['cpr'], tol, f'projected CPR {key} {window}')
        curves = eve.read_curves(FIXTURES / 'MEAS-01' / 'curves.csv')
        values = eve.present_values(flows, curves)
        shocks = spec['parallel_shock']
        self.assertEqual(sorted(spec['effective_duration']), ['MTG_FIX|EUR'])
        for pool, want in spec['effective_duration'].items():
            segment, currency = pool.split('|')
            base, down, up = (values[(s, segment, currency)] for s in (eve.BASE, 'PAR_DOWN', 'PAR_UP'))
            for name, pv in (('pv_base', base), ('pv_par_down', down), ('pv_par_up', up)):
                self.assert_near(pv, want[name], 'rel 1e-12', f'{pool} {name}')
            duration = eve.effective_duration(Fraction(base), Fraction(down), Fraction(up),
                                              Fraction(shocks[currency]))
            self.assertIsNotNone(duration)
            self.assert_near(duration or Fraction(0), want['effective_duration'], tol, f'{pool} effective duration')
        for point in spec['effective_duration_hand']:
            duration = eve.effective_duration(*(Fraction(point[name]) for name in
                                                ('pv_base', 'pv_par_down', 'pv_par_up', 'parallel_shock')))
            if point['effective_duration'] is None:
                self.assertIsNone(duration, point)
            else:
                self.assertEqual(duration, Fraction(point['effective_duration']), point)

    def test_projected_cpr_needs_every_month(self) -> None:
        flows = eve.read_cash_flows(FIXTURES / 'MEAS-01' / 'cash_flows.csv')
        gap = [f for f in flows if f.key == (eve.BASE, 'MTG_FIX', 'EUR') and f.k != 7]
        with self.assertRaises(ValueError):
            eve.projected_cpr(gap)

    def test_expected_values_equal_their_derivation(self) -> None:
        derived = derive_eve.derive()
        for case, values in derived.items():
            spec = expected(case)
            self.assertEqual({name: spec[name] for name in values}, values, case)


if __name__ == '__main__':
    unittest.main()
