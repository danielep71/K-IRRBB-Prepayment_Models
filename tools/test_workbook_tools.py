"""Offline tests of the workbook layout and component tools; no Excel is used."""
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import components  # noqa: E402
import workbook_layout as layout  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / 'docs/WORKBOOK_CONTRACT.md').read_text(encoding='utf-8')


def module(name: str, body: str = "Option Explicit\n") -> str:
    return f'Attribute VB_Name = "{name}"\n{body}'


VALID = {
    'src/core/CORE_Math.bas': module('CORE_Math'),
    'src/modules/PREPAY_Api.bas': module('PREPAY_Api'),
    'src/workbook/WB_Main.bas': module('WB_Main'),
    'tests/modules/TEST_Harness.bas': module('TEST_Harness'),
    'src/README.md': 'guide\n',
}


class LayoutMatchesContract(unittest.TestCase):
    def test_sheet_order_names_and_code_names(self) -> None:
        rows = re.findall(r'^\| (\d+) \| `([A-Za-z]+)` \| `(sh[A-Za-z]+)` \|', CONTRACT, re.M)
        self.assertEqual([(t, c) for _, t, c in rows], [(s.tab, s.code_name) for s in layout.SHEETS])
        self.assertEqual([int(n) for n, _, _ in rows], list(range(1, len(layout.SHEETS) + 1)))

    def test_every_table_and_setting_is_named_in_the_contract(self) -> None:
        for sheet in layout.SHEETS:
            for table in sheet.tables:
                self.assertIn(f'`{table.name}`', CONTRACT)
        settings_section = CONTRACT.split('### Settings', 1)[1].split('### Assumptions', 1)[0]
        for setting in layout.RUN_SETTINGS:
            self.assertIn(f'`{setting.code}`', settings_section)
        for name in layout.RUN_NAMES + ('Build_Commit',):
            self.assertIn(f'`{name}`', CONTRACT)

    def test_builds(self) -> None:
        self.assertNotIn('shTests', layout.document_modules(layout.PRODUCTION))
        self.assertIn('shTests', layout.document_modules(layout.TEST))
        self.assertEqual(layout.document_modules(layout.TEST)[0], 'ThisWorkbook')
        names = layout.defined_names(layout.TEST)
        self.assertEqual(len(names), len(set(names)), 'duplicate defined names')
        self.assertFalse([n for n in names if n.endswith('_Status') and n not in
                          {f'{s.tab}_Status' for s in layout.SHEETS} | {'Run_Status'}])
        with self.assertRaises(ValueError):
            layout.sheets_for('release')


class Collect(unittest.TestCase):
    def test_valid_builds(self) -> None:
        prod, errors = components.collect(layout.PRODUCTION, VALID)
        self.assertEqual(errors, [])
        self.assertEqual([c.name for c in prod], ['CORE_Math', 'PREPAY_Api', 'WB_Main'])
        test, errors = components.collect(layout.TEST, VALID)
        self.assertEqual(errors, [])
        self.assertIn('TEST_Harness', [c.name for c in test])

    def assert_error(self, files: dict[str, str], fragment: str) -> None:
        _, errors = components.collect(layout.TEST, {**VALID, **files})
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_rejections(self) -> None:
        self.assert_error({'src/core/Math.bas': module('Math')}, 'must start with CORE_')
        self.assert_error({'src/core/CORE_X.bas': module('CORE_Y')}, 'Attribute VB_Name')
        self.assert_error({'src/core/CORE_X.bas': 'Option Explicit\n'}, 'Attribute VB_Name')
        self.assert_error({'src/core/CORE_X.bas': module('CORE_X', "' café\n")}, 'ASCII')
        self.assert_error({'src/core/CORE_X.cls': module('CORE_X')}, 'only .bas')
        self.assert_error({'src/forms/F.frm': 'x\n'}, '.frx')
        self.assert_error({'src/classes/shReadme.cls': module('shReadme')}, 'already used')
        self.assert_error({'src/workbook/WB_Main2.bas': module('WB_Main2'),
                           'src/core/CORE_main.bas': module('CORE_main'),
                           'src/modules/PREPAY_x.bas': module('PREPAY_x'),
                           'src/classes/core_math.cls': module('core_math')}, 'already used')


class Compare(unittest.TestCase):
    def setUp(self) -> None:
        comps, _ = components.collect(layout.TEST, VALID)
        self.manifest: dict[str, Any] = {
            'schema': 1, 'build': layout.TEST, 'commit': '0' * 40,
            'components': [c.__dict__ for c in comps],
            'document_modules': list(layout.document_modules(layout.TEST)),
            'references': sorted(components.DEFAULT_REFERENCES),
        }
        self.export = {Path(c.path).name: VALID[c.path].replace('\n', '\r\n') + '\r\n' for c in comps}
        for name in self.manifest['document_modules']:
            self.export[f'{name}.cls'] = ('VERSION 1.0 CLASS\r\nBEGIN\r\n  MultiUse = -1  \'True\r\nEND\r\n'
                                          f'Attribute VB_Name = "{name}"\r\nAttribute VB_Base = "0{{x}}"\r\n')
        self.refs = sorted(components.DEFAULT_REFERENCES)

    def errors(self) -> list[str]:
        return components.compare(self.manifest, self.export, self.refs)

    def test_match(self) -> None:
        self.assertEqual(self.errors(), [])

    def test_missing_extra_changed(self) -> None:
        del self.export['WB_Main.bas']
        self.export['CORE_Extra.bas'] = module('CORE_Extra')
        self.export['PREPAY_Api.bas'] = module('PREPAY_Api', 'Option Explicit\nPublic X As Long\n')
        del self.export['shGap.cls']
        errors = self.errors()
        self.assertIn('missing component: WB_Main', errors)
        self.assertIn('extra component: CORE_Extra.bas', errors)
        self.assertTrue(any(e.startswith('changed component: PREPAY_Api') for e in errors))
        self.assertIn('missing document module: shGap', errors)

    def test_document_code_type_and_references(self) -> None:
        self.export['ThisWorkbook.cls'] += 'Option Explicit\r\nPrivate Sub Workbook_Open()\r\nEnd Sub\r\n'
        self.export['CORE_Math.cls'] = self.export.pop('CORE_Math.bas')
        self.refs = self.refs + ['Scripting']
        self.refs.remove('Office')
        errors = self.errors()
        self.assertTrue(any(e.startswith('document module ThisWorkbook contains code') for e in errors))
        self.assertTrue(any(e.startswith('wrong component type: CORE_Math.cls') for e in errors))
        self.assertIn('non-default reference: Scripting', errors)
        self.assertIn('missing default reference: Office', errors)

    def test_line_endings_and_trailing_space_are_not_changes(self) -> None:
        self.export['CORE_Math.bas'] = 'Attribute VB_Name = "CORE_Math"   \r\nOption Explicit\r\n\r\n\r\n'
        self.assertEqual(self.errors(), [])


class Stage(unittest.TestCase):
    def test_stage_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'stage'
            self.assertEqual(components.stage(layout.PRODUCTION, 'HEAD', out), 0)
            manifest = (out / 'manifest.json').read_text(encoding='utf-8')
            self.assertIn('"build": "production"', manifest)
            self.assertNotIn('shTests', manifest)
            with self.assertRaises(SystemExit):
                components.stage(layout.PRODUCTION, 'HEAD', out)


if __name__ == '__main__':
    unittest.main()
