"""Generate the macro-free workbook template of docs/WORKBOOK_CONTRACT.md.

The template is generated at build time and never committed (decision of
2026-10-21, #43). It holds the sheets, CodeNames, tables, settings and
defined names of the contract and no VBA; tools/Build-Workbook.ps1 imports
the components of one commit into it through Excel.

Usage: python tools/build_template.py --build test --commit FULL_SHA --output build/template.xlsx
Requires XlsxWriter, pinned in tools/requirements-build.txt.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell
from xlsxwriter.workbook import Workbook
from xlsxwriter.worksheet import Worksheet

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workbook_layout as layout  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IGNORED_OUTPUT_DIRS = ('build', 'out')
PRODUCT = 'K-IRRBB-Prepayment_Models'

# Visual identity of the prototype template (#19); see docs/provenance.json.
BLACK, BAND, NAVY, BLUE = '#000000', '#265A99', '#1F3864', '#2E75B6'
YELLOW, GRID, GREY = '#FFF2CC', '#BFBFBF', '#595959'
TAB = {'Reference': NAVY, 'Input': '#BF9000', 'Output': BLUE, 'Parameters': BLUE,
       'Diagnostics': BLUE, 'Test build': '#548235'}
FONT = 'Aptos'
FIRST_COL = 2           # column C
STATUS_ROW = 3          # row 4
FIRST_TABLE_ROW = 5     # row 6
LAST_BAND_COL = 27      # column AB
INPUT_ROWS = 20

README_LINES = (
    'Loan prepayment workbook built from the exported VBA source of one commit.',
    'Layout: docs/WORKBOOK_CONTRACT.md. Data and models: docs/methodology/.',
    'Input files are read from CSV and never stored on worksheets.',
    'Nothing in this workbook is validated unless an Excel evidence record for its build commit says so.',
)


class Styles:
    def __init__(self, wb: Workbook) -> None:
        base = {'font_name': FONT, 'font_size': 10, 'valign': 'vcenter'}
        self.band1 = wb.add_format({**base, 'bold': True, 'font_size': 12, 'font_color': 'white',
                                    'bg_color': BLACK})
        self.band2 = wb.add_format({**base, 'bold': True, 'font_size': 14, 'font_color': 'white',
                                    'bg_color': BAND})
        self.text = wb.add_format(base)
        self.note = wb.add_format({**base, 'italic': True, 'font_color': GREY})
        self.section = wb.add_format({**base, 'bold': True, 'font_size': 12, 'font_color': NAVY})
        self.status = wb.add_format({**base, 'bold': True, 'font_color': GREY})
        self.label = wb.add_format({**base, 'bold': True})
        border = {'border': 1, 'border_color': GRID}
        self.header_in = wb.add_format({**base, **border, 'bold': True, 'font_color': 'white',
                                        'bg_color': NAVY, 'text_wrap': True})
        self.header_out = wb.add_format({**base, **border, 'bold': True, 'font_color': 'white',
                                         'bg_color': BLUE, 'text_wrap': True})
        self.input = wb.add_format({**base, **border, 'bg_color': YELLOW, 'locked': False})
        self.cell = wb.add_format({**base, **border})


def check_output(path: Path, force: bool) -> Path:
    """Refuse an output inside the checkout unless it is in an ignored build folder."""
    path = path.resolve()
    if path.suffix != '.xlsx':
        raise SystemExit(f'output must end in .xlsx: {path}')
    if path.is_relative_to(ROOT):
        top = path.relative_to(ROOT).parts[0]
        if top not in IGNORED_OUTPUT_DIRS:
            raise SystemExit(f'output inside the checkout must be under {IGNORED_OUTPUT_DIRS}: {path}')
    if path.exists() and not force:
        raise SystemExit(f'{path} exists; pass --force to replace it')
    return path


def scaffold(wb: Workbook, st: Styles, sheet: layout.Sheet) -> Worksheet:
    ws = wb.add_worksheet(sheet.tab)
    ws.set_vba_name(sheet.code_name)
    ws.set_tab_color(TAB[sheet.role])
    ws.hide_gridlines(2)
    ws.set_landscape()
    ws.set_paper(9)
    ws.fit_to_pages(1, 0)
    ws.set_column(0, 0, 4)
    ws.set_column(1, 1, 13)
    ws.set_column(FIRST_COL, LAST_BAND_COL, 16)
    for col in range(1, LAST_BAND_COL + 1):
        ws.write_blank(0, col, None, st.band1)
        ws.write_blank(1, col, None, st.band2)
    ws.write(0, 1, PRODUCT, st.band1)
    ws.write(1, 1, sheet.tab, st.band2)
    if sheet.has_status:
        ws.write(STATUS_ROW, FIRST_COL, 'STALE: no run yet', st.status)
        wb.define_name(f'{sheet.tab}_Status', f"='{sheet.tab}'!{xl_rowcol_to_cell(STATUS_ROW, FIRST_COL, True, True)}")
    return ws


def write_table(wb: Workbook, st: Styles, ws: Worksheet, sheet: layout.Sheet, table: layout.Table,
                row: int, col: int) -> int:
    """Write a table's title and headers at (row, col); return the first column after its gap."""
    is_input = sheet.role == 'Input'
    ws.write(row, col, table.name, st.section)
    row += 1
    for i, header in enumerate(table.headers):
        ws.write(row, col + i, header, st.header_in if is_input else st.header_out)
    wb.define_name(table.name, f"='{sheet.tab}'!{xl_rowcol_to_cell(row, col, True, True)}")
    body = list(table.rows)
    if is_input:
        body += [()] * max(INPUT_ROWS - len(body), 0)
    for offset, values in enumerate(body, start=1):
        for i in range(len(table.headers)):
            value = values[i] if i < len(values) else None
            ws.write(row + offset, col + i, value, st.cell if i < len(values) else st.input)
    return col + len(table.headers) + 1


def write_settings(wb: Workbook, st: Styles, ws: Worksheet, name: str,
                   settings: tuple[layout.Setting, ...], row: int, col: int) -> int:
    """Write a settings table at (row, col); return the first column after its gap."""
    ws.write(row, col, name, st.section)
    row += 1
    for i, header in enumerate(layout.SETTING_HEADERS):
        ws.write(row, col + i, header, st.header_in)
    wb.define_name(name, f"='Settings'!{xl_rowcol_to_cell(row, col, True, True)}")
    for setting in settings:
        row += 1
        ws.write(row, col, setting.code, st.label)
        ws.write(row, col + 1, setting.description, st.text)
        ws.write_string(row, col + 2, setting.default, st.input)
        ws.write(row, col + 3, setting.unit, st.text)
        ws.write(row, col + 4, setting.contract, st.note)
        wb.define_name(f'cfg_{setting.code}', f"='Settings'!{xl_rowcol_to_cell(row, col + 2, True, True)}")
        if setting.choices:
            ws.data_validation(row, col + 2, row, col + 2, {'validate': 'list', 'source': list(setting.choices)})
    return col + len(layout.SETTING_HEADERS) + 1


def write_run_state(wb: Workbook, st: Styles, ws: Worksheet, row: int) -> int:
    for name in layout.RUN_NAMES:
        ws.write(row, FIRST_COL, name, st.label)
        ws.write_blank(row, FIRST_COL + 1, None, st.cell)
        wb.define_name(name, f"='Log'!{xl_rowcol_to_cell(row, FIRST_COL + 1, True, True)}")
        row += 1
    return row + 1


def build(build: str, commit: str, output: Path) -> None:
    wb = xlsxwriter.Workbook(str(output))
    wb.set_vba_name('ThisWorkbook')
    wb.set_properties({'title': PRODUCT, 'comments': f'{build} build template for commit {commit}',
                       'created': datetime(2000, 1, 1)})
    st = Styles(wb)
    for sheet in layout.sheets_for(build):
        ws = scaffold(wb, st, sheet)
        row = FIRST_TABLE_ROW
        if sheet.tab == 'README':
            for line in README_LINES:
                ws.write(row, FIRST_COL, line, st.text)
                row += 1
            row += 1
            ws.write(row, FIRST_COL, 'Build commit', st.label)
            ws.write_string(row, FIRST_COL + 1, commit, st.cell)
            wb.define_name('Build_Commit', f"='README'!{xl_rowcol_to_cell(row, FIRST_COL + 1, True, True)}")
            ws.write(row + 1, FIRST_COL, 'Build', st.label)
            ws.write_string(row + 1, FIRST_COL + 1, build, st.cell)
            continue
        # Tables of a sheet share a top row and sit side by side, so each can grow downward.
        col = FIRST_COL
        if sheet.tab == 'Settings':
            col = write_settings(wb, st, ws, 'Settings_Run', layout.RUN_SETTINGS, row, col)
            write_settings(wb, st, ws, 'Settings_Optimiser', layout.OPTIMISER_SETTINGS, row, col)
            continue
        if sheet.tab == 'Log':
            row = write_run_state(wb, st, ws, row)
        for table in sheet.tables:
            col = write_table(wb, st, ws, sheet, table, row, col)
    wb.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--build', choices=layout.BUILDS, required=True)
    parser.add_argument('--commit', required=True, help='full 40-character commit SHA of the build')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[0-9a-f]{40}', args.commit):
        raise SystemExit('--commit must be a full 40-character lower-case SHA')
    output = check_output(args.output, args.force)
    output.parent.mkdir(parents=True, exist_ok=True)
    build(args.build, args.commit, output)
    print(f'Template written: {output} ({args.build}, {args.commit})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
