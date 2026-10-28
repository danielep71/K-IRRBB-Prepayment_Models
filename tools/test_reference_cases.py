"""Built (Python) cases: run the reference reader on each fixture and compare with its expected file."""
import hashlib
import json
import random
import sys
import tempfile
import unittest
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests' / 'reference'))
import data_reader as reader  # noqa: E402

FIXTURES = ROOT / 'tests' / 'fixtures'
CODE_SETS = {'rate_type': reader.RATE_TYPES, 'event': reader.EVENTS, 'payment_months': reader.PAYMENT_MONTHS,
             'segment': reader.SEGMENTS}


def expected(case: str) -> dict:
    return json.loads((ROOT / 'tests' / 'expected' / f'{case}.json').read_text(encoding='utf-8'))


class ImportCases(unittest.TestCase):
    def run_case(self, case: str) -> None:
        spec = expected(case)
        settings = spec['settings']
        for variant, want in spec['variants'].items():
            with self.subTest(case=case, variant=variant):
                result = reader.read_import(FIXTURES / case / variant, date.fromisoformat(settings['window_start']),
                                            date.fromisoformat(settings['window_end']),
                                            set(settings['currency_allowlist']))
                self.assertEqual(result.accepted, want['accepted'])
                self.assertEqual([list(e) for e in result.errors], want['errors'])
                if 'warnings' in want:
                    self.assertEqual([list(w) for w in result.warnings], want['warnings'])
                if 'warning_counts' in want:
                    self.assertEqual(dict(Counter(w[2] for w in result.warnings)), want['warning_counts'])
                if 'totals' in want:
                    got_totals = {'|'.join(k): v for k, v in result.totals.items()}
                    self.assertEqual(sorted(got_totals), sorted(want['totals']))
                    for key, measures in want['totals'].items():
                        full = {m: Decimal(measures.get(m, '0')) for m in reader.RECON_MEASURES}
                        self.assertEqual(got_totals[key], full, key)
                if 'gaps' in want:
                    self.assertEqual([list(g) for g in result.gaps], want['gaps'])
                if 'missing_extracts' in want:
                    self.assertEqual(result.missing_extracts, want['missing_extracts'])
                if 'control_differences' in want:
                    self.assertEqual([list(d) for d in result.control_differences], want['control_differences'])
                for key, month in want.get('loan_months', {}).items():
                    available, prepaid = result.loan_months[tuple(key.split('|'))]
                    self.assertEqual(available, Decimal(month['available']))
                    self.assertEqual(prepaid, Decimal(month['prepaid']))
                    if 'smm' in month:
                        self.assertEqual(prepaid / available, Decimal(month['smm']))
                if 'outcomes' in want:
                    got = {f'{loan}|{start}': outcome for (loan, start), outcome in result.outcomes.items()}
                    self.assertEqual(got, want['outcomes'])

    def test_data_ident_01(self) -> None:
        self.run_case('DATA-IDENT-01')

    def test_data_expo_01(self) -> None:
        self.run_case('DATA-EXPO-01')

    def test_data_reneg_01(self) -> None:
        self.run_case('DATA-RENEG-01')

    def test_data_pit_01(self) -> None:
        self.run_case('DATA-PIT-01')

    def test_data_valid_01(self) -> None:
        self.run_case('DATA-VALID-01')

    def test_data_recon_01(self) -> None:
        self.run_case('DATA-RECON-01')

    def test_data_invalid_01(self) -> None:
        self.run_case('DATA-INVALID-01')
        codes = {e[2] for e in expected('DATA-INVALID-01')['variants']['every-rule']['errors']}
        self.assertEqual(codes, {f'E{n:02d}' for n in range(1, 17)})

    def test_data_event_01(self) -> None:
        self.run_case('DATA-EVENT-01')


class FieldCases(unittest.TestCase):
    def test_data_parse_01(self) -> None:
        spec = expected('DATA-PARSE-01')
        for item in spec['dates']:
            self.assertEqual(reader.parse_date(item['input']) is not None, item['valid'], item)
        for item in spec['month_ends']:
            parsed = reader.parse_date(item['input'])
            self.assertIsNotNone(parsed, item)
            self.assertEqual(reader.is_month_end(parsed), item['valid'], item)  # type: ignore[arg-type]
        for item in spec['decimals']:
            value = reader.parse_decimal(item['input'], item['places'])
            self.assertEqual(value, None if item['value'] is None else Decimal(item['value']), item)
        for item in spec['codes']:
            self.assertEqual(item['input'] in CODE_SETS[item['set']], item['valid'], item)


class ReaderEdges(unittest.TestCase):
    """Reader behaviour outside the registered cases (review of #96)."""

    def read(self, loans: list[str], panel: list[str], start: date, end: date) -> reader.Result:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            files = {reader.LOANS: loans, reader.PANEL: panel,
                     reader.RATES: [f'{end.isoformat()},EUR_SWAP_60M,EUR,60,0.03']}
            for name, lines in files.items():
                text = '\n'.join([','.join(reader.HEADERS[name]), *lines]) + '\n'
                (folder / name).write_text(text, encoding='ascii')
            return reader.read_import(folder, start, end, {'EUR'})

    def test_self_link_is_not_a_successor(self) -> None:
        result = self.read(['L1,MTG_FIX,EUR,2024-01-15,2030-01-15,100,FIXED,,,ANNUITY,1,NONE,,L1'],
                           ['2024-01-31,L1,0,0.03,0,0,-100,RENEG'], date(2024, 1, 31), date(2024, 1, 31))
        self.assertFalse(result.accepted)
        self.assertIn([reader.LOANS, 2, 'E16'], [list(e) for e in result.errors])

    def test_large_amounts_are_not_rounded(self) -> None:
        big = '999999999999999.9999'    # the largest amount D17 allows
        result = self.read(['L1,MTG_FIX,EUR,2023-01-15,2030-01-15,1,FIXED,,,ANNUITY,1,NONE,,'],
                           [f'2024-01-31,L1,{big},0.03,0,0,0,NONE', f'2024-02-29,L1,{big},0.03,0.0001,0,0,NONE'],
                           date(2024, 1, 31), date(2024, 2, 29))
        self.assertEqual([list(e) for e in result.errors], [])
        result = self.read(['L1,MTG_FIX,EUR,2023-01-15,2030-01-15,1,FIXED,,,ANNUITY,1,NONE,,'],
                           ['2024-01-31,L1,1000000000000000,0.03,0,0,0,NONE'], date(2024, 1, 31), date(2024, 1, 31))
        # The month's only row fails E04, so the month also has no panel rows (E12).
        self.assertEqual([list(e) for e in result.errors], [[reader.PANEL, 0, 'E12'], [reader.PANEL, 2, 'E04']])
        # Review of #110: an amount longer than the reader's 1,000-digit context is E04, not a crash.
        result = self.read(['L1,MTG_FIX,EUR,2023-01-15,2030-01-15,1,FIXED,,,ANNUITY,1,NONE,,'],
                           [f'2024-01-31,L1,{"9" * 1001},0.03,0,0,0,NONE'], date(2024, 1, 31), date(2024, 1, 31))
        self.assertEqual([list(e) for e in result.errors], [[reader.PANEL, 0, 'E12'], [reader.PANEL, 2, 'E04']])

    def test_window_ending_in_9999(self) -> None:
        result = self.read(['L1,MTG_FIX,EUR,9999-01-15,9999-12-31,1,FIXED,,,ANNUITY,1,NONE,,'],
                           ['9999-12-31,L1,0,0.03,1,0,0,MATURITY'], date(9999, 12, 31), date(9999, 12, 31))
        self.assertTrue(result.accepted, result.errors)


class PointInTime(unittest.TestCase):
    """DATA-PIT-02: information after an origin never enters the view at that origin."""

    def setUp(self) -> None:
        self.spec = expected('DATA-PIT-02')
        self.rows = reader.read_rows(FIXTURES / self.spec['fixture'])
        self.rng = random.Random(self.spec['seed'])
        self.serial = 0

    def test_views(self) -> None:
        for origin, want in self.spec['views'].items():
            view = reader.point_in_time_view(self.rows, date.fromisoformat(origin))
            self.assertEqual(sorted(r[0] for r in view[reader.LOANS]), want['loans'], origin)
            self.assertEqual(len(view[reader.PANEL]), want['panel_rows'], origin)

    def later_date(self, origin: date) -> str:
        month = origin
        for _ in range(self.rng.randint(1, 6)):
            month = reader.next_month_end(month)
        return month.isoformat()

    def change_after(self, rows: dict[str, list[dict[str, str]]], origin: date) -> None:
        """Apply one random change to information that becomes known only after the origin.

        Edits and deletions touch fixture rows only, so no change undoes an addition of the same trial.
        """
        self.serial += 1
        later_panel = [r for r in rows[reader.PANEL] if not r['loan_id'].startswith('NEW')
                       and date.fromisoformat(r['as_of_date']) > origin]
        later_loans = [r for r in rows[reader.LOANS] if not r['loan_id'].startswith('NEW')
                       and date.fromisoformat(r['origination_date']) > origin]
        kinds = ['add_panel', 'add_loan'] + ['edit_panel', 'move_panel', 'delete_panel'] * bool(later_panel) \
            + ['edit_loan', 'delete_loan'] * bool(later_loans)
        kind = self.rng.choice(kinds)
        if kind == 'edit_panel':
            row = self.rng.choice(later_panel)
            row[self.rng.choice(reader.HEADERS[reader.PANEL][1:])] = f'CHANGED{self.serial}'
        elif kind == 'move_panel':
            row = self.rng.choice(later_panel)
            row['as_of_date'], row['balance'] = self.later_date(origin), f'MOVED{self.serial}'
        elif kind == 'delete_panel':
            rows[reader.PANEL].remove(self.rng.choice(later_panel))
        elif kind == 'edit_loan':
            row = self.rng.choice(later_loans)
            field = self.rng.choice([f for f in reader.HEADERS[reader.LOANS] if f != 'origination_date'])
            row[field] = f'CHANGED{self.serial}'
        elif kind == 'delete_loan':
            rows[reader.LOANS].remove(self.rng.choice(later_loans))
        elif kind == 'add_panel':
            row = dict(self.rng.choice(rows[reader.PANEL]))
            row['as_of_date'], row['loan_id'] = self.later_date(origin), f'NEW{self.serial}'
            rows[reader.PANEL].append(row)
        else:
            row = dict(self.rng.choice(rows[reader.LOANS]))
            row['origination_date'], row['loan_id'] = self.later_date(origin), f'NEW{self.serial}'
            rows[reader.LOANS].append(row)

    def test_changes_after_the_origin_do_not_leak(self) -> None:
        unfiltered = date(9999, 12, 31)    # negative control: no row is after this origin
        for origin_text in self.spec['views']:
            origin = date.fromisoformat(origin_text)
            before = reader.point_in_time_view(self.rows, origin)
            for trial in range(self.spec['trials']):
                rows = {name: [dict(r) for r in kept] for name, kept in self.rows.items()}
                for _ in range(self.rng.randint(1, 3)):
                    self.change_after(rows, origin)
                with self.subTest(origin=origin_text, trial=trial):
                    self.assertEqual(reader.point_in_time_view(rows, origin), before)
                    self.assertNotEqual(reader.point_in_time_view(rows, unfiltered),
                                        reader.point_in_time_view(self.rows, unfiltered))


class Fingerprints(unittest.TestCase):
    def test_data_sha_01(self) -> None:
        spec = expected('DATA-SHA-01')
        for item in spec['messages']:
            digest = hashlib.sha256((item['text'] * item['repeat']).encode('ascii')).hexdigest()
            self.assertEqual(digest, item['sha256'])
        result = reader.read_import(FIXTURES / spec['fixture'], date(2024, 1, 31), date(2024, 3, 31), {'EUR'})
        self.assertEqual(result.fingerprints, spec['files'])


if __name__ == '__main__':
    unittest.main()
