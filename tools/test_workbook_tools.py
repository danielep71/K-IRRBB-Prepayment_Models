"""Offline tests of the workbook layout and component tools; no Excel is used."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import components  # noqa: E402
import vba_fixtures  # noqa: E402
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

    def types(self) -> dict[str, int]:
        kinds = {c['name']: components.VBA_TYPES[c['kind']] for c in self.manifest['components']}
        return {**kinds, **{n: 100 for n in self.manifest['document_modules']}}

    def test_vba_types(self) -> None:
        types = self.types()
        self.assertEqual(components.compare(self.manifest, self.export, self.refs, types), [])
        types['shGap'] = 1
        types['CORE_Math'] = 2
        errors = components.compare(self.manifest, self.export, self.refs, types)
        self.assertIn('wrong VBA type for shGap: 1, expected 100', errors)
        self.assertIn('wrong VBA type for CORE_Math: 2, expected 1', errors)
        del types['WB_Main']
        self.assertIn('component list and exported files differ: WB_Main',
                      components.compare(self.manifest, self.export, self.refs, types))

    def test_document_module_replaced_by_standard_module(self) -> None:
        # Review of #87: a deleted sheet whose CodeName is reused by an empty standard module.
        self.export['shGap.bas'] = 'Attribute VB_Name = "shGap"\r\nOption Explicit\r\n'
        del self.export['shGap.cls']
        self.assertIn('not a document module: shGap.bas', self.errors())
        types = self.types()
        types['shGap'] = 1
        self.assertIn('wrong VBA type for shGap: 1, expected 100',
                      components.compare(self.manifest, self.export, self.refs, types))

    def test_line_endings_and_trailing_space_are_not_changes(self) -> None:
        self.export['CORE_Math.bas'] = 'Attribute VB_Name = "CORE_Math"   \r\nOption Explicit\r\n\r\n\r\n'
        self.assertEqual(self.errors(), [])


class Fixtures(unittest.TestCase):
    def test_flatten(self) -> None:
        rows = vba_fixtures.flatten({'a': [1, None, True, 'x'], 'b': {'c': 2.5}})
        self.assertEqual(rows, [('', 'o', '2'), ('/~0', 's', 'a'), ('/a', 'a', '4'), ('/a/0', 'n', '1'),
                                ('/a/1', 'z', ''), ('/a/2', 'b', '1'), ('/a/3', 's', 'x'), ('/~1', 's', 'b'),
                                ('/b', 'o', '1'), ('/b/~0', 's', 'c'), ('/b/c', 'n', '2.5')])

    def test_generate(self) -> None:
        files = {'tests/fixtures/C/v/f.csv': b'ab\xe9\n', 'tests/fixtures/C/v/empty.csv': b'',
                 'tests/expected/C.json': b'{"provenance": {"tool": "hand"}, "k": 1}'}
        modules = vba_fixtures.generate(files, '0' * 40)
        self.assertEqual(list(modules), ['TEST_Fixtures', 'TEST_FixtureData1'])
        main, data = modules['TEST_Fixtures'], modules['TEST_FixtureData1']
        self.assertTrue(all(t.isascii() for t in modules.values()))
        self.assertIn('Case "C/v/f.csv": TEST_FixtureBytes = Decode(TEST_FixtureData1.F0001(), Length)', main)
        self.assertIn('Case "C": TEST_ExpectedBytes = Decode(TEST_FixtureData1.X0000(), Length)', main)
        self.assertIn('"6162e90a"', data)
        self.assertIn('Case "C/v/empty.csv": TEST_HasFixture = True', main)
        self.assertIn(b'\tn\t1\n'.hex(), data)
        self.assertNotIn('hand'.encode().hex(), data)    # provenance is left out
        for name, text in modules.items():
            self.assertEqual(components.collect(layout.TEST, {f'tests/modules/{name}.bas': text})[1], [])

    def test_data_modules_stay_small(self) -> None:
        files = {f'tests/fixtures/C/v/f{i:03d}.csv': bytes(range(256)) * 20 for i in range(60)}
        modules = vba_fixtures.generate(files, '0' * 40)
        self.assertGreater(len(modules), 3)
        for name, text in modules.items():
            self.assertLess(len(text), vba_fixtures.MODULE_LIMIT + 11_000, name)
            self.assertTrue(all(len(line) < 1023 for line in text.splitlines()), name)

    def test_generated_names_are_reserved(self) -> None:
        committed, _ = components.collect(layout.TEST, {**VALID, 'tests/modules/TEST_FixtureData1.bas':
                                                        module('TEST_FixtureData1')})
        errors = components.add_generated(committed, {}, {'TEST_Fixtures': module('TEST_Fixtures')})
        self.assertTrue(any('TEST_FixtureData1 is generated' in e for e in errors), errors)
        self.assertIn('TEST_Fixtures', [c.name for c in committed])


class Stage(unittest.TestCase):
    def test_stage_test_build_adds_fixture_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'stage'
            self.assertEqual(components.stage(layout.TEST, 'HEAD', out), 0)
            manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
            generated = [c for c in manifest['components'] if c['path'].startswith('generated/')]
            self.assertEqual(generated[0]['name'], 'TEST_Fixtures')
            for c in generated:
                self.assertTrue((out / 'components' / f'{c["name"]}.bas').read_bytes().isascii())

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
