"""Template generator tests; need XlsxWriter from tools/requirements-build.txt."""
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_template  # noqa: E402
import workbook_layout as layout  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'a' * 40


def parts(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n).decode('utf-8') for n in z.namelist() if n.endswith('.xml')}


class Template(unittest.TestCase):
    def build(self, build: str) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / f'{build}.xlsx'
            self.assertEqual(build_template.main(['--build', build, '--commit', COMMIT, '--output', str(out)]), 0)
            return parts(out)

    def test_sheets_code_names_and_names(self) -> None:
        for build in layout.BUILDS:
            xml = self.build(build)
            book = xml['xl/workbook.xml']
            self.assertEqual(re.findall(r'<sheet name="([^"]+)"', book), [s.tab for s in layout.sheets_for(build)])
            self.assertIn('codeName="ThisWorkbook"', book)
            code_names = [re.search(r'codeName="([^"]+)"', xml[f'xl/worksheets/sheet{i}.xml']).group(1)  # type: ignore[union-attr]
                          for i in range(1, len(layout.sheets_for(build)) + 1)]
            self.assertEqual(code_names, [s.code_name for s in layout.sheets_for(build)])
            names = re.findall(r'<definedName name="([^"]+)"', book)
            self.assertEqual(sorted(names), sorted(layout.defined_names(build)))
            self.assertNotIn('hidden=', book)
            self.assertFalse([p for p in xml if 'vbaProject' in p or 'externalLink' in p])
            self.assertIn(COMMIT, xml['xl/sharedStrings.xml'])

    def test_tables_share_a_row_and_do_not_overlap(self) -> None:
        book = self.build(layout.TEST)['xl/workbook.xml']
        cells = dict(re.findall(r'<definedName name="([^"]+)">([^<]+)<', book))
        for sheet in layout.SHEETS:
            refs = [cells[t.name] for t in sheet.tables]
            self.assertEqual(len({re.sub(r'\$[A-Z]+\$', '', r) for r in refs}), min(len(refs), 1))

    def test_output_location_is_checked(self) -> None:
        with self.assertRaises(SystemExit):
            build_template.check_output(ROOT / 'template.xlsx', False)
        with self.assertRaises(SystemExit):
            build_template.check_output(ROOT / 'build' / 'template.xlsm', False)
        self.assertEqual(build_template.check_output(ROOT / 'build' / 't.xlsx', False), ROOT / 'build' / 't.xlsx')
        with self.assertRaises(SystemExit):
            build_template.main(['--build', 'test', '--commit', 'HEAD', '--output', '/tmp/x.xlsx'])

    def test_build_requirement_is_pinned_in_both_files(self) -> None:
        build = (ROOT / 'tools/requirements-build.txt').read_text(encoding='utf-8').split()
        quality = (ROOT / 'tools/requirements-quality-ci.txt').read_text(encoding='utf-8').split()
        self.assertTrue(build and all('==' in line for line in build))
        self.assertTrue(set(build) <= set(quality))


if __name__ == '__main__':
    unittest.main()
