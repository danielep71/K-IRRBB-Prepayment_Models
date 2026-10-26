"""Built (Python) cases: run the reference reader on each fixture and compare with its expected file."""
import hashlib
import json
import sys
import unittest
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
                self.assertEqual([list(w) for w in result.warnings], want['warnings'])
                for key, month in want.get('loan_months', {}).items():
                    available, prepaid = result.loan_months[tuple(key.split('|'))]
                    self.assertEqual(available, Decimal(month['available']))
                    self.assertEqual(prepaid, Decimal(month['prepaid']))
                    if 'smm' in month:
                        self.assertEqual(prepaid / available, Decimal(month['smm']))

    def test_data_ident_01(self) -> None:
        self.run_case('DATA-IDENT-01')

    def test_data_expo_01(self) -> None:
        self.run_case('DATA-EXPO-01')


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
