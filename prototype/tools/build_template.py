"""Build src/workbook/PPM_Template.xlsx, the macro-free K-PREPAY template.

The visual identity follows the K-SACCR template (danielep71/saccr,
src/workbook/SACCR_Template.xlsx): Aptos, a black product band in row 1, a
blue (#265A99) sheet band in row 2, navy (#1F3864) input headers, blue
(#2E75B6) output headers, yellow (#FFF2CC) input cells with light-grey
(#BFBFBF) borders, gridlines off, tab colours by role (amber inputs, blue
outputs, navy reference, green tests), A4 landscape fitted to width.

Every table starts in column C under a workbook name on its first header
cell; src/core/CORE_Config.bas holds the same layout. The illustrative data
and the expected test values come from tools/reference_model.py.

Usage:  python tools/build_template.py  (standard library + XlsxWriter)
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime

import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell, xl_col_to_name

sys.path.insert(0, os.path.dirname(__file__))
import reference_model as rm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "src", "workbook", "PPM_Template.xlsx")

PRODUCT = "K-PREPAY"

# Palette of the K-SACCR template
BLACK = "#000000"
AMBER = "#FFC000"
BAND = "#265A99"
NAVY = "#1F3864"
BLUE = "#2E75B6"
YELLOW = "#FFF2CC"
GRID = "#BFBFBF"
GREY = "#595959"
OLIVE = "#7F6000"
GOOD_FILL, GOOD_FONT = "#E2EFDA", "#375623"
BAD_FILL, BAD_FONT = "#FFC7CE", "#9C0006"
TAB_INPUT, TAB_OUTPUT, TAB_REF, TAB_TEST = "#BF9000", "#2E75B6", "#1F3864", "#548235"

FONT = "Aptos"
DATE_FMT = "yyyy\\-mm\\-dd"
FIRST_COL = 2          # column C (0-based)
LAST_BAND_COL = 27     # column AB (0-based), as in K-SACCR
INPUT_ROWS = {"Loans": 2000, "History": 5000, "Segments": 20, "Curve": 40}

SHOCK_DESC = {
    "CONTRACT": "Contractual cash flows, no prepayment, base curve",
    "BASE": "Behavioural cash flows, base curve",
    "PAR_UP": "Parallel shock up",
    "PAR_DOWN": "Parallel shock down",
    "STEEPENER": "Steepener (short down, long up)",
    "FLATTENER": "Flattener (short up, long down)",
    "SHORT_UP": "Short rates up",
    "SHORT_DOWN": "Short rates down",
}


class Book:
    def __init__(self, path):
        self.wb = xlsxwriter.Workbook(path, {
            "default_format_properties": {"font_name": FONT, "font_size": 10},
            "strings_to_numbers": False,
        })
        self.wb.set_properties({"title": "", "author": "", "company": "",
                                "comments": ""})
        self.wb.set_calc_mode("auto")
        self.cache = {}

    def f(self, **kw):
        key = tuple(sorted(kw.items()))
        if key not in self.cache:
            props = {"font_name": FONT, "valign": "vcenter"}
            props.update(kw)
            self.cache[key] = self.wb.add_format(props)
        return self.cache[key]

    # -- styles -------------------------------------------------------------
    def band1(self):
        return self.f(bg_color=BLACK, font_color=AMBER, font_size=14, indent=1, align="left")

    def band1_blank(self):
        return self.f(bg_color=BLACK)

    def band2(self):
        return self.f(bg_color=BAND, font_color="#FFFFFF", font_size=18, bold=True,
                      indent=1, align="left")

    def band2_blank(self):
        return self.f(bg_color=BAND)

    def note(self, size=10):
        return self.f(italic=True, font_color=GREY, font_size=size)

    def status(self):
        return self.f(italic=True, font_color=OLIVE, font_size=10)

    def header(self, output=False, size=11, align=None):
        kw = dict(bg_color=BLUE if output else NAVY, font_color="#FFFFFF", bold=True,
                  font_size=size, text_wrap=True, border=1, border_color=GRID)
        if align:
            kw["align"] = align
        return self.f(**kw)

    def group(self):
        return self.f(bg_color=NAVY, font_color="#FFFFFF", bold=True, font_size=10,
                      align="center", border=1, border_color=GRID)

    def inp(self, num_format=None, align=None):
        kw = dict(bg_color=YELLOW, font_size=9, border=1, border_color=GRID)
        if num_format:
            kw["num_format"] = num_format
        if align:
            kw["align"] = align
        return self.f(**kw)

    def out(self, num_format=None, align=None, bold=False):
        kw = dict(font_size=10)
        if num_format:
            kw["num_format"] = num_format
        if align:
            kw["align"] = align
        if bold:
            kw["bold"] = True
        return self.f(**kw)

    def section(self):
        return self.f(bold=True, font_size=14, font_color=NAVY, bottom=2,
                      bottom_color=NAVY, text_wrap=True)

    def label(self):
        return self.f(bold=True, font_size=10, text_wrap=True, top=1, bottom=3,
                      left=1, top_color=GRID, bottom_color=GRID, left_color=GRID)

    def text(self):
        return self.f(font_size=9, text_wrap=True, top=1, bottom=3, left=3,
                      right=1, top_color=GRID, bottom_color=GRID, left_color=GRID,
                      right_color=GRID)

    # -- sheet scaffold -------------------------------------------------------
    def sheet(self, name, code_name, title, subtitle, tab, last_col=LAST_BAND_COL,
              subtitle_height=30):
        ws = self.wb.add_worksheet(name)
        ws.set_vba_name(code_name)
        ws.set_tab_color(tab)
        ws.hide_gridlines(2)
        ws.set_landscape()
        ws.set_paper(9)
        ws.fit_to_pages(1, 0)
        ws.set_margins(left=0.4, right=0.4, top=0.5, bottom=0.5)
        ws.set_column(0, 0, 4)
        ws.set_column(1, 1, 13)
        ws.set_row(0, 24)
        ws.set_row(1, 26.1)
        ws.set_row(2, subtitle_height)
        last_col = max(last_col, LAST_BAND_COL)
        for c in range(1, last_col + 1):
            ws.write_blank(0, c, None, self.band1_blank())
            ws.write_blank(1, c, None, self.band2_blank())
        ws.write(0, 1, PRODUCT, self.band1())
        ws.write(1, 1, title, self.band2())
        if subtitle:
            ws.write(2, FIRST_COL, subtitle, self.note())
        return ws

    def headers(self, ws, row, labels, output=False, height=42, name=None, size=11,
                center_from=None):
        ws.set_row(row, height)
        for i, lab in enumerate(labels):
            align = "center" if (center_from is not None and i >= center_from) else None
            ws.write(row, FIRST_COL + i, lab, self.header(output, size, align))
        if name:
            self.wb.define_name(name, "=%s!%s" % (quote(ws.name),
                                                  abs_cell(row, FIRST_COL)))


PRINT_LAST_COL = {"README": 3, "Params": 5, "Curve": 4, "Segments": 12, "Loans": 13, "History": 6,
                  "Results": 23, "CashFlows": 31, "Gap": 14, "ScenarioCurves": 10, "LoanCalc": 20,
                  "Checks": 6, "Calibration": 21, "Tests": 13}


def quote(sheet):
    return "'%s'" % sheet if any(ch in sheet for ch in " -") else sheet


def abs_cell(r, c):
    return xl_rowcol_to_cell(r, c, row_abs=True, col_abs=True)


def col(i):
    """0-based column of table column i (1-based)."""
    return FIRST_COL + i - 1


# ===========================================================================
# README
# ===========================================================================
def build_readme(b: Book):
    ws = b.sheet("README", "shReadme", "ReadMe",
                 "Behavioural prepayment model for the banking book: conditional prepayment rate, "
                 "behavioural cash flows, IRRBB shock scenarios, EVE sensitivity and repricing gap.",
                 TAB_REF, subtitle_height=33.95)
    ws.freeze_panes(3, 0)
    ws.set_column(2, 2, 32)
    ws.set_column(3, 3, 150)
    r = 4
    sections = [
        ("How to use", [
            ("1. Enable macros", "Open the .xlsm and click \"Enable Content\". The workbook is built from this "
             "macro-free template and the VBA source; see INSTALLATION.md."),
            ("2. Parameters", "Params: as-of date, reporting currency, prepayment mode (BEHAVIOURAL or BCBS_SA), "
             "shock sizes, post-shock lower bound, Tier 1 capital, CPR multipliers and seasonality."),
            ("3. Curve", "Curve: risk-free zero curve of the reporting currency, continuously compounded, "
             "tenors in years in increasing order."),
            ("4. Segments", "Segments: parameters of the prepayment function per portfolio segment. "
             "Calibrate (on Calibration) fits CPR min, CPR max, slope and midpoint to History."),
            ("5. Loans", "Loans: one row per loan. Yellow cells are inputs; dropdowns guide the codes."),
            ("6. Run", "Click \"Run model\" (macro RunModel). Results, CashFlows, Gap, ScenarioCurves and "
             "LoanCalc are rewritten; Checks lists every rejected input and assumption."),
            ("7. Tests", "Tests: \"Run tests\" runs the model on the illustrative data and compares each "
             "output with the value of the independent Python reference (tools/reference_model.py)."),
        ]),
        ("Prepayment function (per loan and month)", [
            ("CPR", "CPR(t) = min(1, [CPRmin + (CPRmax - CPRmin) x B(t) x L(slope x (I(t) - midpoint))] x "
             "Ramp(t) x Season(t)),  L(x) = 1 / (1 + exp(-x))."),
            ("Incentive I(t)", "I(t) = client rate - (z_s(T) + refinancing margin) - penalty / max(T, 1), with "
             "T the remaining maturity in years at the start of the month and z_s the zero rate of "
             "scenario s for T."),
            ("Burnout B(t)", "B(t) = exp(-burnout x (1 - S(t))), S(t) = product of (1 - SMM) of the earlier "
             "months: the more of the loan has already prepaid, the less the rest responds to incentive."),
            ("Seasoning Ramp(t)", "Ramp(t) = min(1, age in months / seasoning ramp); 1 when the ramp is 0. "
             "Age = completed months since origination at the as-of date, plus the projection month."),
            ("Seasonality", "Calendar-month multiplier from Params, applied when the segment's flag is Y."),
            ("SMM", "SMM = 1 - (1 - CPR)^(1/12): the monthly prepayment share of the balance after the "
             "scheduled repayment."),
            ("Floating rate", "Floating-rate loans prepay at the segment's floating CPR x Ramp x Season, in "
             "every scenario, and reprice at par at the next reset date."),
            ("BCBS_SA mode", "Shocked CPR = min(1, gamma x base CPR of the same loan and month) (BCBS d368, "
             "Table 3) for fixed-rate loans; the base path is the behavioural one."),
        ]),
        ("Cash flows, scenarios and EVE", [
            ("Time grid", "Monthly, from the as-of date; month k ends at t = k / 12 years. Remaining months "
             "count a started month as one."),
            ("Schedule", "Interest accrues monthly at client rate / 12 and is paid on payment months "
             "(remaining months a multiple of the payment frequency). ANNUITY: principal "
             "B x j / ((1 + j)^n - 1), j = rate x frequency / 12, n = payments left; LINEAR: B / n; "
             "BULLET: at maturity. Prepayment settles the same share of accrued interest."),
            ("Scenarios", "Parallel, short, long shocks of Reg. (EU) 2024/856 Annex for EUR (200, 250, 100 bp) "
             "and BCBS d368 Annex 2 shapes: short x exp(-t/4), long x (1 - exp(-t/4)), steepener "
             "-0.65|short| + 0.9|long|, flattener 0.8|short| - 0.6|long|."),
            ("Lower bound", "Post-shock rate >= min(observed rate, -150 bp + 3 bp per year, capped at 0) "
             "(Reg. (EU) 2024/856 Art. 3(7)); switch with ApplyFloor."),
            ("EVE", "PV_s = sum of CF_s(k) x exp(-z_s(t_k) x t_k), commercial margins included; "
             "dEVE_s = PV_s - PV_BASE. Loan book only: the bank-level outlier test needs every position."),
            ("Gap", "Principal and total cash flows per BCBS d368 Table 1 time bucket (19 buckets)."),
        ]),
        ("Limitations", [
            ("Scope", "Loan book only (no deposits, hedges or equity); one currency; no NII, no new business, "
             "no basis risk. The refinancing benchmark is the zero rate, not the par rate, of the remaining "
             "maturity. Illustrative data only: no real portfolio."),
        ]),
    ]
    for title, rows in sections:
        ws.set_row(r, 30)
        ws.write(r, 2, title, b.section())
        ws.write_blank(r, 3, None, b.section())
        r += 1
        for lab, txt in rows:
            lines = max(1, len(txt) // 165 + 1)
            ws.set_row(r, max(20.1, 13.5 * lines + 6))
            ws.write(r, 2, lab, b.label())
            ws.write(r, 3, txt, b.text())
            r += 1
        r += 1


# ===========================================================================
# INPUT SHEETS
# ===========================================================================
PARAM_ROWS = [
    # code, description, value, format, reference, validation
    ("AsOfDate", "Reporting date of the run", rm.Params().as_of, DATE_FMT,
     "Cash flows start in the month after it", "date"),
    ("ReportingCcy", "Reporting currency; every loan must be in it", "EUR", "@",
     "Single-currency prototype", "ccy"),
    ("PrepayMode", "BEHAVIOURAL: S-curve in every scenario. BCBS_SA: gamma x base CPR", "BEHAVIOURAL", "@",
     "BCBS d368 Table 3", "mode"),
    ("ShockParallel", "Parallel shock size", 0.02, "0.00%", "Reg. (EU) 2024/856 Annex Part A: EUR 200 bp", "rate"),
    ("ShockShort", "Short-rate shock size", 0.025, "0.00%", "Reg. (EU) 2024/856 Annex Part A: EUR 250 bp", "rate"),
    ("ShockLong", "Long-rate shock size", 0.01, "0.00%", "Reg. (EU) 2024/856 Annex Part A: EUR 100 bp", "rate"),
    ("ShockDecay", "Decay x of the short and long shapes, years", 4, "0.00", "BCBS d368 Annex 2: x = 4", "pos"),
    ("ApplyFloor", "Apply the post-shock lower bound (Y / N)", "Y", "@", "Reg. (EU) 2024/856 Art. 3(7)", "yn"),
    ("FloorStart", "Lower bound at maturity 0", -0.015, "0.00%", "-150 bp", "rate"),
    ("FloorSlope", "Increase of the lower bound per year, capped at 0", 0.0003, "0.00%", "3 bp per year", "rate"),
    ("MaxProjectionMonths", "Longest remaining maturity accepted, months", 600, "0", "Loans beyond it are rejected", "int"),
    ("Tier1Capital", "Tier 1 capital, for dEVE / Tier 1", 6000000, "#,##0", "Illustrative", "pos"),
    ("OutlierThreshold", "Indicator threshold for dEVE / Tier 1", 0.15, "0%", "BCBS d368 outlier test: 15% of Tier 1", "rate"),
]


def build_params(b: Book):
    ws = b.sheet("Params", "shParams", "Parameters",
                 "Each value is read through the workbook name equal to its code in column C; only the yellow "
                 "values are meant to be changed.", TAB_INPUT)
    ws.set_column(2, 2, 25.6)
    ws.set_column(3, 3, 50.6)
    ws.set_column(4, 4, 15.6)
    ws.set_column(5, 5, 45.6)
    ws.set_row(3, 9.95)
    hdr = 4
    b.headers(ws, hdr, ["Code", "Description", "Value", "Reference"], height=30, size=12, center_from=2)
    b.wb.define_name("Params_Code", "=Params!$C$5")
    b.wb.define_name("Params_Value", "=Params!$E$5")
    for i, (code, desc, val, nf, ref, kind) in enumerate(PARAM_ROWS):
        r = hdr + 1 + i
        ws.set_row(r, 20.1)
        ws.write(r, 2, code, b.f(bold=True, font_size=10))
        ws.write(r, 3, desc, b.f(font_size=9))
        center = "center" if nf == "@" else None
        if isinstance(val, date):
            ws.write_datetime(r, 4, datetime(val.year, val.month, val.day), b.inp(nf))
        elif isinstance(val, str):
            ws.write_string(r, 4, val, b.inp(nf, center))
        else:
            ws.write_number(r, 4, val, b.inp(nf))
        ws.write(r, 5, ref, b.f(font_size=9, font_color=GREY))
        b.wb.define_name(code, "=Params!%s" % abs_cell(r, 4))
        dv = {"input_title": code[:32], "input_message": desc[:255]}
        if kind == "date":
            dv.update(validate="date", criteria=">", value=datetime(2000, 1, 1),
                      error_message="A date after 2000-01-01.")
        elif kind == "mode":
            dv.update(validate="list", source=["BEHAVIOURAL", "BCBS_SA"])
        elif kind == "yn":
            dv.update(validate="list", source=["Y", "N"])
        elif kind == "ccy":
            dv.update(validate="length", criteria="==", value=3,
                      error_message="Three-letter currency code, e.g. EUR.")
        elif kind == "int":
            dv.update(validate="integer", criteria="between", minimum=1, maximum=1200)
        elif kind == "pos":
            dv.update(validate="decimal", criteria=">", value=0)
        elif kind == "rate":
            dv.update(validate="decimal", criteria="between", minimum=-1, maximum=1)
        ws.data_validation(r, 4, r, 4, dv)
    # gamma table
    r = hdr + 1 + len(PARAM_ROWS) + 1
    ws.set_row(r, 26)
    ws.write(r, 2, "CPR multipliers per scenario (BCBS_SA mode)", b.f(bold=True, font_size=14, font_color=NAVY))
    r += 1
    b.headers(ws, r, ["Scenario", "Description", "Gamma (CPR)", "Reference"], height=30, size=11,
              name="Gamma_Table", center_from=2)
    for sc in rm.SHOCKS:
        r += 1
        ws.set_row(r, 20.1)
        ws.write(r, 2, sc, b.f(bold=True, font_size=10))
        ws.write(r, 3, SHOCK_DESC[sc], b.f(font_size=9))
        ws.write_number(r, 4, rm.GAMMA[sc], b.inp("0.00"))
        ws.write(r, 5, "BCBS d368 Table 3", b.f(font_size=9, font_color=GREY))
        ws.data_validation(r, 4, r, 4, {"validate": "decimal", "criteria": ">=", "value": 0,
                                        "input_title": "Gamma", "input_message":
                                        "Shocked CPR = min(1, gamma x base CPR) in BCBS_SA mode."})
    # seasonality
    r += 2
    ws.set_row(r, 26)
    ws.write(r, 2, "Seasonality of prepayments (calendar month)", b.f(bold=True, font_size=14, font_color=NAVY))
    r += 1
    b.headers(ws, r, ["Month", "Name", "Multiplier", "Note"], height=30, size=11, name="Seasonality_Table",
              center_from=2)
    names = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
             "October", "November", "December"]
    first = r + 1
    for m in range(12):
        r += 1
        ws.set_row(r, 20.1)
        ws.write_number(r, 2, m + 1, b.f(bold=True, font_size=10, align="left"))
        ws.write(r, 3, names[m], b.f(font_size=9))
        ws.write_number(r, 4, rm.SEASONALITY[m], b.inp("0.0000"))
    r += 1
    ws.write(r, 3, "Average (should be 1)", b.f(font_size=9, italic=True, font_color=GREY))
    ws.write_formula(r, 4, "=AVERAGE(%s:%s)" % (abs_cell(first, 4), abs_cell(r - 1, 4)),
                     b.f(font_size=9, num_format="0.0000", italic=True, font_color=GREY),
                     sum(rm.SEASONALITY) / 12.0)
    ws.freeze_panes(5, 0)


def build_curve(b: Book):
    ws = b.sheet("Curve", "shCurve", "Risk-free curve",
                 "Zero rates of the reporting currency, continuously compounded, decimals (0.02 = 2%). "
                 "Linear interpolation in the rate, flat beyond the first and last tenor.", TAB_INPUT)
    ws.set_column(2, 3, 15.6)
    ws.set_column(4, 4, 30.6)
    ws.set_row(3, 9.95)
    b.headers(ws, 4, ["Tenor (years)", "Zero rate", "Label"], height=30, name="Curve_Header")
    labels = ["1M", "3M", "6M", "1Y", "2Y", "3Y", "4Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y", "50Y"]
    for i in range(INPUT_ROWS["Curve"]):
        r = 5 + i
        ws.set_row(r, 20.1)
        if i < len(rm.CURVE_T):
            ws.write_number(r, 2, rm.CURVE_T[i], b.inp("0.0000"))
            ws.write_number(r, 3, rm.CURVE_R[i], b.inp("0.0000%"))
            ws.write_string(r, 4, labels[i], b.inp("@"))
        else:
            ws.write_blank(r, 2, None, b.inp("0.0000"))
            ws.write_blank(r, 3, None, b.inp("0.0000%"))
            ws.write_blank(r, 4, None, b.inp("@"))
    ws.data_validation(5, 2, 4 + INPUT_ROWS["Curve"], 2,
                       {"validate": "decimal", "criteria": ">", "value": 0, "input_title": "Tenor",
                        "input_message": "Years, strictly increasing down the table."})
    ws.data_validation(5, 3, 4 + INPUT_ROWS["Curve"], 3,
                       {"validate": "decimal", "criteria": "between", "minimum": -0.2, "maximum": 0.5,
                        "input_title": "Zero rate", "input_message": "Continuously compounded, decimal."})
    ws.freeze_panes(5, 0)
    ws.write(2, 6, "Illustrative EUR risk-free curve, not market data.", b.status())


SEG_HEADERS = ["SegmentID", "Description", "CPR min", "CPR max", "Slope (per unit of incentive)",
               "Midpoint (incentive)", "Seasoning ramp (months)", "Burnout", "Refinancing margin",
               "Floating-rate CPR", "Seasonality (Y/N)"]


def build_segments(b: Book):
    ws = b.sheet("Segments", "shSegments", "Prepayment segments",
                 "One row per segment. CPR min / max, slope and midpoint define the S-curve of fixed-rate loans; "
                 "floating-rate loans use the floating-rate CPR. Calibration writes the four S-curve values.",
                 TAB_INPUT)
    widths = [14.6, 40.6, 10.6, 10.6, 13.6, 12.6, 12.6, 10.6, 12.6, 12.6, 12.6]
    for i, w in enumerate(widths):
        ws.set_column(col(i + 1), col(i + 1), w)
    ws.set_row(3, 9.95)
    b.headers(ws, 4, SEG_HEADERS, height=50.1, name="Segments_Header", center_from=2)
    fmts = ["@", "@", "0.00%", "0.00%", "0.0", "0.00%", "0", "0.00", "0.00%", "0.00%", "@"]
    for i in range(INPUT_ROWS["Segments"]):
        r = 5 + i
        ws.set_row(r, 20.1)
        s = rm.SEGMENTS[i] if i < len(rm.SEGMENTS) else None
        vals = None
        if s:
            vals = [s.sid, s.desc, s.cpr_min, s.cpr_max, s.slope, s.mid, s.ramp, s.burnout, s.margin,
                    s.float_cpr, "Y" if s.seasonal else "N"]
        for j in range(11):
            al = "center" if j >= 2 else None
            if vals is None:
                ws.write_blank(r, col(j + 1), None, b.inp(fmts[j], al))
            elif isinstance(vals[j], str):
                ws.write_string(r, col(j + 1), vals[j], b.inp(fmts[j], al))
            else:
                ws.write_number(r, col(j + 1), vals[j], b.inp(fmts[j], al))
    last = 4 + INPUT_ROWS["Segments"]
    msgs = [
        (3, "CPR min", "Annual CPR at very negative incentive, 0 to 1."),
        (4, "CPR max", "Annual CPR at very positive incentive, CPR min to 1."),
        (5, "Slope", "Steepness per unit of incentive: 250 = factor e per 0.4% of incentive. > 0."),
        (6, "Midpoint", "Incentive (decimal) at which the CPR is halfway between min and max."),
        (7, "Seasoning ramp", "Months to full speed; 0 = no ramp."),
        (8, "Burnout", "Reduction of the incentive response as the loan prepays; 0 = none."),
        (9, "Refinancing margin", "Spread over the zero rate at which the borrower can refinance."),
        (10, "Floating-rate CPR", "Annual CPR of floating-rate loans of the segment."),
    ]
    for c, t, m in msgs:
        ws.data_validation(5, col(c), last, col(c), {"validate": "decimal", "criteria": "between",
                                                     "minimum": -1000, "maximum": 100000,
                                                     "input_title": t, "input_message": m})
    ws.data_validation(5, col(11), last, col(11), {"validate": "list", "source": ["Y", "N"]})
    ws.conditional_format(5, col(1), last, col(1), {
        "type": "formula", "criteria": "=AND(C6<>\"\",COUNTIF($C$6:$C$%d,C6)>1)" % (last + 1),
        "format": b.wb.add_format({"font_color": BAD_FONT, "bg_color": BAD_FILL})})
    ws.freeze_panes(5, 3)


LOAN_HEADERS = ["LoanID", "SegmentID", "Rate type", "Currency", "Outstanding balance", "Client rate",
                "Origination date", "Maturity date", "Amortisation", "Payment frequency (months)",
                "Next reset date (FLOAT)", "Prepayment penalty"]


def build_loans(b: Book, loans):
    ws = b.sheet("Loans", "shLoans", "Loans",
                 "One row per loan, in the reporting currency. Rates and penalty as decimals (0.03 = 3%). "
                 "FLOAT loans reprice at par at the next reset date; FIXED loans run to maturity.",
                 TAB_INPUT)
    widths = [12.6, 13.6, 9.6, 9.6, 15.6, 10.6, 12.6, 12.6, 12.6, 11.6, 12.6, 11.6]
    for i, w in enumerate(widths):
        ws.set_column(col(i + 1), col(i + 1), w)
    ws.set_row(3, 9.95)
    b.headers(ws, 4, LOAN_HEADERS, height=50.1, name="Loans_Header", center_from=2)
    fm = ["@", "@", "@", "@", "#,##0.00", "0.000%", DATE_FMT, DATE_FMT, "@", "0", DATE_FMT, "0.00%"]
    n = INPUT_ROWS["Loans"]
    for i in range(n):
        r = 5 + i
        ln = loans[i] if i < len(loans) else None
        for j in range(12):
            al = "center" if j in (2, 3, 6, 7, 8, 9, 10) else None
            fmt = b.inp(fm[j], al)
            if ln is None:
                ws.write_blank(r, col(j + 1), None, fmt)
                continue
            v = [ln.lid, ln.sid, ln.rate_type, ln.ccy, ln.balance, ln.rate, ln.orig, ln.mat, ln.amort,
                 ln.freq, ln.reset, ln.penalty][j]
            if v is None:
                ws.write_blank(r, col(j + 1), None, fmt)
            elif isinstance(v, date):
                ws.write_datetime(r, col(j + 1), datetime(v.year, v.month, v.day), fmt)
            elif isinstance(v, str):
                ws.write_string(r, col(j + 1), v, fmt)
            else:
                ws.write_number(r, col(j + 1), v, fmt)
    last = 4 + n
    ws.data_validation(5, col(3), last, col(3), {"validate": "list", "source": ["FIXED", "FLOAT"],
                                                 "input_title": "Rate type",
                                                 "input_message": "FIXED to maturity or FLOAT repricing at the reset date."})
    ws.data_validation(5, col(9), last, col(9), {"validate": "list", "source": ["ANNUITY", "LINEAR", "BULLET"],
                                                 "input_title": "Amortisation",
                                                 "input_message": "ANNUITY (French), LINEAR (Italian) or BULLET."})
    ws.data_validation(5, col(10), last, col(10), {"validate": "list", "source": ["1", "3", "6", "12"],
                                                   "input_title": "Payment frequency",
                                                   "input_message": "Months between payments: 1, 3, 6 or 12."})
    ws.data_validation(5, col(5), last, col(5), {"validate": "decimal", "criteria": ">", "value": 0,
                                                 "input_title": "Outstanding balance",
                                                 "input_message": "Principal outstanding at the as-of date, > 0."})
    ws.data_validation(5, col(6), last, col(6), {"validate": "decimal", "criteria": "between",
                                                 "minimum": -0.05, "maximum": 1,
                                                 "input_title": "Client rate",
                                                 "input_message": "Annual rate, decimal; current all-in rate for FLOAT."})
    ws.data_validation(5, col(12), last, col(12), {"validate": "decimal", "criteria": "between",
                                                   "minimum": 0, "maximum": 1,
                                                   "input_title": "Prepayment penalty",
                                                   "input_message": "Share of the prepaid amount; blank = 0."})
    ws.conditional_format(5, col(1), last, col(1), {
        "type": "formula", "criteria": "=AND(C6<>\"\",COUNTIF($C$6:$C$%d,C6)>1)" % (last + 1),
        "format": b.wb.add_format({"font_color": BAD_FONT, "bg_color": BAD_FILL})})
    ws.freeze_panes(5, 3)


def build_history(b: Book, hist):
    ws = b.sheet("History", "shHistory", "Prepayment history",
                 "Observed annual CPR per segment and month with the incentive of that month, seasoning- and "
                 "seasonality-adjusted. Calibration fits the S-curve to these rows, weighted by balance.",
                 TAB_INPUT)
    for i, w in enumerate([12.6, 13.6, 12.6, 12.6, 16.6]):
        ws.set_column(col(i + 1), col(i + 1), w)
    ws.set_row(3, 9.95)
    b.headers(ws, 4, ["Month", "SegmentID", "Incentive", "Observed CPR", "Weight (balance)"],
              height=42, name="History_Header", center_from=2)
    fm = [DATE_FMT, "@", "0.000%", "0.000%", "#,##0"]
    n = INPUT_ROWS["History"]
    for i in range(n):
        r = 5 + i
        h = hist[i] if i < len(hist) else None
        for j in range(5):
            fmt = b.inp(fm[j], "center" if j != 1 else None)
            if h is None:
                ws.write_blank(r, col(j + 1), None, fmt)
            elif j == 0:
                ws.write_datetime(r, col(1), datetime(h[0].year, h[0].month, h[0].day), fmt)
            elif j == 1:
                ws.write_string(r, col(2), h[1], fmt)
            else:
                ws.write_number(r, col(j + 1), h[j], fmt)
    ws.freeze_panes(5, 0)
    ws.write(2, 9, "Synthetic history generated from the Segments S-curves plus noise.", b.status())


# ===========================================================================
# OUTPUT SHEETS
# ===========================================================================
def buttons(ws, row, col0, items):
    x = 0
    for cap, macro, width in items:
        ws.insert_button(row, col0, {"macro": macro, "caption": cap, "width": width, "height": 26,
                                     "x_offset": x, "y_offset": 2})
        x += width + 8


RESULT_HEADERS = ["Scenario", "Description", "PV (EVE contribution)", "dEVE vs BASE", "dEVE / Tier 1",
                  "WAL principal (years)", "Average CPR, first 12 months", "Average CPR, lifetime",
                  "Prepayments (undiscounted)", "Interest (undiscounted)"]
SUMMARY_MEASURES = ["Prepayment mode", "Loans used", "Loans excluded", "Outstanding balance (used)",
                    "Projection months", "Worst scenario", "Worst dEVE", "Worst dEVE / Tier 1",
                    "Outlier indicator", "Effective duration (parallel)"]
SEGRES_HEADERS = ["SegmentID", "Loans", "Outstanding balance", "PV BASE"] + \
    ["dEVE " + s for s in rm.SHOCKS] + ["WAL BASE (years)", "Average CPR 12m BASE"]


def build_results(b: Book):
    ws = b.sheet("Results", "shResults", "Results",
                 "", TAB_OUTPUT, subtitle_height=33.95)
    ws.set_zoom(90)
    widths = [24.8, 40.8, 17.8, 15.8, 11.8, 11.8, 12.8, 12.8, 15.8, 15.8, 13.8, 13.8]
    for i, w in enumerate(widths):
        ws.set_column(col(i + 1), col(i + 1), w)
    for r in range(17, 27):
        ws.write_blank(r, col(1), None, b.out(bold=True))
        ws.write_blank(r, col(2), None, b.out(align="left"))
        ws.write_blank(r, col(3), None, b.f(font_size=9, font_color=GREY))
    buttons(ws, 2, 2, [("Run model", "RunModel", 110), ("Validate inputs", "ValidateInputs", 118),
                       ("Clear outputs", "ClearOutputs", 110)])
    ws.write(3, 2, "No results yet: press Run model.", b.status())
    ws.set_row(4, 9.95)
    b.headers(ws, 5, RESULT_HEADERS, output=True, height=42, name="Results_Header", center_from=2)
    ws.write(15, 2, "Summary", b.f(bold=True, font_size=14, font_color=NAVY))
    ws.set_row(15, 26)
    b.headers(ws, 16, ["Measure", "Value", "Note"], output=True, height=30, name="Summary_Header")
    ws.write(28, 2, "By segment", b.f(bold=True, font_size=14, font_color=NAVY))
    ws.set_row(28, 26)
    b.headers(ws, 29, SEGRES_HEADERS, output=True, height=42, name="SegResults_Header", center_from=1)
    ws.conditional_format(17, col(2), 26, col(2), {
        "type": "formula", "criteria": '=LEFT($D18,5)="ABOVE"',
        "format": b.wb.add_format({"font_color": BAD_FONT, "bg_color": BAD_FILL})})
    ws.conditional_format(6, col(4), 13, col(5), {
        "type": "cell", "criteria": "<", "value": 0, "format": b.wb.add_format({"font_color": BAD_FONT})})
    ws.freeze_panes(6, 3)
    # charts
    ch = b.wb.add_chart({"type": "column"})
    ch.add_series({"name": "dEVE vs BASE", "categories": "=Results!$C$9:$C$14",
                   "values": "=Results!$F$9:$F$14", "fill": {"color": BLUE}, "border": {"none": True},
                   "data_labels": {"value": False}})
    style_chart(ch, "dEVE by shock scenario", "#,##0")
    ws.insert_chart(5, col(12) + 1, ch, {"x_scale": 1.25, "y_scale": 1.1})
    ln = b.wb.add_chart({"type": "scatter", "subtype": "straight"})
    colours = {"CONTRACT": GREY, "BASE": NAVY, "PAR_UP": "#C00000", "PAR_DOWN": "#548235"}
    series = [("CONTRACT", 12), ("BASE", 9), ("PAR_UP", 14), ("PAR_DOWN", 17)]
    for nm, c in series:
        ln.add_series({"name": nm, "categories": "=CashFlows!$E$7:$E$606",
                       "values": "=CashFlows!$%s$7:$%s$606" % (xl_col_to_name(col(c)), xl_col_to_name(col(c))),
                       "line": {"color": colours[nm], "width": 1.75,
                                "dash_type": "dash" if nm == "CONTRACT" else "solid"}})
    style_chart(ln, "Outstanding balance by scenario", "#,##0", x_title="Years")
    ln.show_blanks_as("gap")
    ln.set_x_axis({"name": "Years", "num_format": "0", "min": 0, "major_unit": 5,
                   "num_font": {"name": FONT, "size": 8}, "name_font": {"name": FONT, "size": 9},
                   "line": {"color": GRID}})
    ws.insert_chart(22, col(12) + 1, ln, {"x_scale": 1.25, "y_scale": 1.1})


def style_chart(ch, title, num_format, x_title=None):
    ch.set_title({"name": title, "name_font": {"name": FONT, "size": 11, "bold": True, "color": NAVY}})
    ch.set_legend({"position": "bottom", "font": {"name": FONT, "size": 8}})
    ch.set_y_axis({"num_format": num_format, "num_font": {"name": FONT, "size": 8},
                   "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}},
                   "line": {"none": True}})
    ch.set_x_axis({"num_font": {"name": FONT, "size": 8}, "line": {"color": GRID}})
    ch.set_chartarea({"border": {"color": GRID}})
    ch.set_plotarea({"border": {"none": True}})


CF_BASE = ["Scheduled principal", "Prepayment", "Repricing (FLOAT)", "Interest", "Total cash flow",
           "Balance", "CPR"]


def cashflow_headers():
    h = ["Month", "Date", "t (years)"] + CF_BASE + ["Total cash flow", "Balance"]
    for _ in rm.SHOCKS:
        h += ["Total cash flow", "Balance", "CPR"]
    return h


def build_cashflows(b: Book):
    hdr = cashflow_headers()
    ws = b.sheet("CashFlows", "shCashFlows", "Cash flows by month",
                 "Loan book aggregated by month and scenario. Prepayment and repricing are principal; the CPR is "
                 "weighted by the balance at the start of the month.", TAB_OUTPUT, last_col=col(len(hdr)))
    ws.set_column(col(1), col(1), 7.8)
    ws.set_column(col(2), col(2), 11.8)
    ws.set_column(col(3), col(3), 8.8)
    ws.set_column(col(4), col(len(hdr)), 13.8)
    ws.write(3, 2, "No results yet: press Run model.", b.status())
    groups = [("BASE", 4, 10), ("CONTRACT", 11, 12)]
    for i, s in enumerate(rm.SHOCKS):
        groups.append((s, 13 + 3 * i, 15 + 3 * i))
    for nm, a, z in groups:
        ws.merge_range(4, col(a), 4, col(z), nm, b.group())
    ws.set_row(4, 20.1)
    b.headers(ws, 5, hdr, output=True, height=42, name="CashFlows_Header", center_from=1)
    ws.freeze_panes(6, 4)


GAP_HEADERS = ["Bucket", "Upper bound (years)", "Midpoint (years)", "CONTRACT principal", "BASE principal",
               "BASE total cash flow", "BASE PV"] + ["Total cash flow " + s for s in rm.SHOCKS]


def build_gap(b: Book):
    ws = b.sheet("Gap", "shGap", "Repricing gap (BCBS time buckets)",
                 "Cash flows of the loan book in the 19 time buckets of BCBS d368 Table 1, by the time of the "
                 "monthly cash flow (upper bound inclusive).", TAB_OUTPUT)
    widths = [7.8, 12.8, 10.8] + [15.8] * 10
    for i, w in enumerate(widths):
        ws.set_column(col(i + 1), col(i + 1), w)
    ws.write(3, 2, "No results yet: press Run model.", b.status())
    b.headers(ws, 5, GAP_HEADERS, output=True, height=42, name="Gap_Header", center_from=2)
    ws.freeze_panes(6, 3)
    ch = b.wb.add_chart({"type": "column"})
    ch.add_series({"name": "CONTRACT principal", "categories": "=Gap!$C$7:$C$25", "values": "=Gap!$F$7:$F$25",
                   "fill": {"color": "#A6A6A6"}, "border": {"none": True}})
    ch.add_series({"name": "BASE principal", "categories": "=Gap!$C$7:$C$25", "values": "=Gap!$G$7:$G$25",
                   "fill": {"color": BLUE}, "border": {"none": True}})
    style_chart(ch, "Principal by time bucket: contractual vs behavioural", "#,##0")
    ws.insert_chart(28, 2, ch, {"x_scale": 2.2, "y_scale": 1.15})


def build_curves(b: Book):
    hdr = ["Tenor (years)", "BASE"] + list(rm.SHOCKS) + ["Lower bound"]
    ws = b.sheet("ScenarioCurves", "shScenarioCurves", "Scenario curves",
                 "Zero rates after each shock and the lower bound, at the BCBS bucket midpoints.", TAB_OUTPUT)
    ws.set_column(col(1), col(len(hdr)), 13.8)
    ws.write(3, 2, "No results yet: press Run model.", b.status())
    b.headers(ws, 5, hdr, output=True, height=42, name="Curves_Header", center_from=1)
    ws.freeze_panes(6, 3)
    ch = b.wb.add_chart({"type": "scatter", "subtype": "straight"})
    cols = [NAVY, "#C00000", "#548235", "#BF9000", "#7030A0", "#ED7D31", "#00B0F0"]
    for i, nm in enumerate(["BASE"] + list(rm.SHOCKS)):
        c = xl_col_to_name(col(2 + i))
        ch.add_series({"name": "=ScenarioCurves!$%s$6" % c, "categories": "=ScenarioCurves!$C$7:$C$25",
                       "values": "=ScenarioCurves!$%s$7:$%s$25" % (c, c),
                       "line": {"color": cols[i], "width": 2.25 if i == 0 else 1.5}})
    style_chart(ch, "Zero curve by scenario", "0.00%")
    ch.set_x_axis({"name": "Years", "min": 0, "max": 25, "num_font": {"name": FONT, "size": 8},
                   "name_font": {"name": FONT, "size": 9}, "line": {"color": GRID}})
    ws.insert_chart(27, 2, ch, {"x_scale": 1.9, "y_scale": 1.2})


LOANCALC_HEADERS = ["LoanID", "SegmentID", "Status", "Remaining months", "Age (months)", "Cash-flow months",
                    "PV CONTRACT", "PV BASE"] + ["PV " + s for s in rm.SHOCKS] + \
                   ["WAL CONTRACT (years)", "WAL BASE (years)", "Duration BASE (years)",
                    "Average CPR 12m BASE", "Messages"]


def build_loancalc(b: Book):
    hdr = LOANCALC_HEADERS
    ws = b.sheet("LoanCalc", "shLoanCalc", "Loan-level results",
                 "One row per input loan. Excluded loans show the reason in Messages and are left out of every "
                 "total.", TAB_OUTPUT)
    widths = [12.8, 12.8, 10.8, 10.8, 9.8, 10.8] + [14.8] * 8 + [11.8] * 4 + [60.8]
    for i, w in enumerate(widths):
        ws.set_column(col(i + 1), col(i + 1), w)
    ws.write(3, 2, "No results yet: press Run model.", b.status())
    b.headers(ws, 5, hdr, output=True, height=42, name="LoanCalc_Header", center_from=2)
    ws.conditional_format(6, col(3), 6 + 5000, col(3), {
        "type": "cell", "criteria": "==", "value": '"EXCLUDED"',
        "format": b.wb.add_format({"font_color": BAD_FONT, "bg_color": BAD_FILL})})
    ws.freeze_panes(6, 3)


def build_checks(b: Book):
    ws = b.sheet("Checks", "shChecks", "Checks",
                 "ERROR: input rejected; the loan or segment is excluded, or the run stops. WARNING: accepted "
                 "with an assumption. INFO: information only.", TAB_OUTPUT)
    for i, w in enumerate([12.6, 13.6, 6.8, 20.6, 110.8]):
        ws.set_column(col(i + 1), col(i + 1), w)
    ws.write(3, 2, "No checks yet: press Run model or Validate inputs.", b.status())
    b.headers(ws, 5, ["Severity", "Sheet", "Row", "Reference", "Message"], output=True, height=42,
              name="Checks_Header")
    ws.conditional_format(6, col(1), 6 + 20000, col(1), {
        "type": "cell", "criteria": "==", "value": '"ERROR"',
        "format": b.wb.add_format({"font_color": BAD_FONT, "bg_color": BAD_FILL})})
    ws.conditional_format(6, col(1), 6 + 20000, col(1), {
        "type": "cell", "criteria": "==", "value": '"WARNING"',
        "format": b.wb.add_format({"font_color": OLIVE, "bg_color": YELLOW})})
    ws.freeze_panes(6, 0)


CAL_HEADERS = ["SegmentID", "Observations", "CPR min", "CPR max", "Slope", "Midpoint", "Weighted RMSE",
               "R-squared", "Iterations", "Status"]


def build_calibration(b: Book):
    ws = b.sheet("Calibration", "shCalibration", "S-curve calibration",
                 "", TAB_OUTPUT, subtitle_height=33.95)
    for i, w in enumerate([14.8, 12.8, 11.8, 11.8, 11.8, 11.8, 12.8, 11.8, 11.8, 30.8]):
        ws.set_column(col(i + 1), col(i + 1), w)
    buttons(ws, 2, 2, [("Calibrate", "RunCalibration", 110), ("Apply to Segments", "ApplyCalibration", 130)])
    ws.write(3, 2, "No calibration yet: press Calibrate.", b.status())
    ws.set_row(4, 9.95)
    b.headers(ws, 5, CAL_HEADERS, output=True, height=42, name="Calibration_Header", center_from=1)
    ws.write(28, 2, "Fitted curves", b.f(bold=True, font_size=14, font_color=NAVY))
    ws.set_row(28, 26)
    b.headers(ws, 29, ["Incentive"] + [""] * 8, output=True, height=30, name="CalCurve_Header", center_from=1)
    ch = b.wb.add_chart({"type": "scatter", "subtype": "straight"})
    cols = [NAVY, "#C00000", "#548235", "#BF9000", "#7030A0", "#ED7D31", "#00B0F0", GREY]
    for i in range(8):
        c = xl_col_to_name(col(2 + i))
        ch.add_series({"name": "=Calibration!$%s$30" % c, "categories": "=Calibration!$C$31:$C$63",
                       "values": "=Calibration!$%s$31:$%s$63" % (c, c),
                       "line": {"color": cols[i], "width": 1.75}})
    style_chart(ch, "Fitted CPR against incentive", "0%")
    ch.set_x_axis({"name": "Incentive", "num_format": "0.0%", "min": -0.03, "max": 0.05,
                   "num_font": {"name": FONT, "size": 8}, "name_font": {"name": FONT, "size": 9},
                   "line": {"color": GRID}})
    ws.insert_chart(5, col(11) + 1, ch, {"x_scale": 1.4, "y_scale": 1.3})
    ws.freeze_panes(6, 3)


# ===========================================================================
# TESTS
# ===========================================================================
def reference_tests(prm, out, cal, loans):
    res = out["res"]
    t = []

    def add(area, desc, sheet, key, column, exp, tol):
        t.append((area, desc, sheet, key, column, exp, tol))

    add("Inputs", "Loans used", "Results", "Loans used", "Value", len(loans), 0)
    add("Inputs", "Outstanding balance of the loans used", "Results", "Outstanding balance (used)", "Value",
        out["balance"], 1e-12)
    add("Inputs", "Projection months", "Results", "Projection months", "Value", out["nmax"], 0)
    for sc in rm.SCENARIOS:
        add("EVE", "PV of the loan book, " + sc, "Results", sc, "PV (EVE contribution)", res[sc]["pv"], 1e-9)
    for sc in ("PAR_UP", "PAR_DOWN", "STEEPENER", "FLATTENER", "SHORT_UP", "SHORT_DOWN"):
        add("EVE", "dEVE, " + sc, "Results", sc, "dEVE vs BASE", res[sc]["deve"], 1e-8)
    for sc in ("CONTRACT", "BASE", "PAR_DOWN"):
        add("Behaviour", "WAL of principal, " + sc, "Results", sc, "WAL principal (years)", res[sc]["wal"], 1e-9)
    for sc in ("BASE", "PAR_UP", "PAR_DOWN"):
        add("Behaviour", "Average CPR first 12 months, " + sc, "Results", sc, "Average CPR, first 12 months",
            res[sc]["cpr1"], 1e-9)
    add("Behaviour", "Average CPR lifetime, BASE", "Results", "BASE", "Average CPR, lifetime", res["BASE"]["cprl"],
        1e-9)
    add("EVE", "Effective duration (parallel)", "Results", "Effective duration (parallel)", "Value",
        out["eff_dur"], 1e-8)
    for lid in ("L0001", "L0025", "L0037", "L0049", "L0061"):
        rec = out["loan"][lid]
        add("Loan", "PV BASE, " + lid, "LoanCalc", lid, "PV BASE", rec["BASE"]["pv"], 1e-9)
        add("Loan", "PV PAR_DOWN, " + lid, "LoanCalc", lid, "PV PAR_DOWN", rec["PAR_DOWN"]["pv"], 1e-9)
        add("Loan", "WAL BASE, " + lid, "LoanCalc", lid, "WAL BASE (years)", rec["BASE"]["wal"], 1e-9)
    add("Gap", "BASE principal, bucket 2Y-3Y", "Gap", "2Y-3Y", "BASE principal", out["gap_prin"]["BASE"][8], 1e-9)
    add("Gap", "CONTRACT principal, bucket 10Y-15Y", "Gap", "10Y-15Y", "CONTRACT principal",
        out["gap_prin"]["CONTRACT"][16], 1e-9)
    add("Cash flow", "BASE prepayment, month 1", "CashFlows", "1", "Prepayment", out["agg"]["BASE"]["prep"][0], 1e-9)
    add("Cash flow", "BASE balance, month 60", "CashFlows", "60", "Balance", out["agg"]["BASE"]["bal"][59], 1e-9)
    for sid in ("MTG_FIX", "SME_FIX"):
        c = cal[sid]
        add("Calibration", "CPR min, " + sid, "Calibration", sid, "CPR min", c["cmin"], 1e-4)
        add("Calibration", "CPR max, " + sid, "Calibration", sid, "CPR max", c["cmax"], 1e-4)
        add("Calibration", "Slope, " + sid, "Calibration", sid, "Slope", c["slope"], 1e-3)
        add("Calibration", "Midpoint, " + sid, "Calibration", sid, "Midpoint", c["mid"], 1e-3)
    return t


def build_tests(b: Book, tests):
    hdr = ["#", "Area", "Description", "Sheet", "Key", "Column", "Expected", "Actual", "Abs. diff",
           "Rel. diff", "Tolerance", "Result"]
    ws = b.sheet("Tests", "shTests", "Reference tests",
                 "", TAB_TEST, subtitle_height=33.95)
    ws.set_zoom(90)
    for i, w in enumerate([5.8, 11.8, 40.8, 12.8, 26.8, 26.8, 17.8, 17.8, 11.8, 11.8, 10.8, 9.8]):
        ws.set_column(col(i + 1), col(i + 1), w)
    buttons(ws, 2, 2, [("Run tests", "RunTests", 110)])
    ws.write(3, 2, "Each test runs the model and calibration on the illustrative data and reads one output by key "
                   "and column header. Expected values come from tools/reference_model.py.", b.status())
    ws.set_row(4, 9.95)
    b.headers(ws, 5, hdr, output=True, height=42, name="Tests_Header", center_from=6)
    for i, (area, desc, sheet, key, column, exp, tol) in enumerate(tests):
        r = 6 + i
        ws.set_row(r, 18)
        ws.write_number(r, col(1), i + 1, b.out("0", "center"))
        ws.write_string(r, col(2), area, b.out())
        ws.write_string(r, col(3), desc, b.out())
        ws.write_string(r, col(4), sheet, b.out())
        ws.write_string(r, col(5), key, b.out())
        ws.write_string(r, col(6), column, b.out())
        ws.write_number(r, col(7), exp, b.out("#,##0.0#########"))
        ws.write_blank(r, col(8), None, b.out("#,##0.0#########"))
        ws.write_blank(r, col(9), None, b.out("0.0E+00"))
        ws.write_blank(r, col(10), None, b.out("0.0E+00"))
        ws.write_number(r, col(11), tol, b.out("0.0E+00"))
        ws.write_blank(r, col(12), None, b.out(None, "center", bold=True))
    last = 6 + len(tests) - 1
    ws.conditional_format(6, col(12), last, col(12), {"type": "cell", "criteria": "==", "value": '"PASS"',
                                                      "format": b.wb.add_format({"font_color": GOOD_FONT,
                                                                                 "bg_color": GOOD_FILL})})
    ws.conditional_format(6, col(12), last, col(12), {"type": "cell", "criteria": "==", "value": '"FAIL"',
                                                      "format": b.wb.add_format({"font_color": BAD_FONT,
                                                                                 "bg_color": BAD_FILL})})
    # unit tests of the worksheet functions
    r = last + 3
    ws.set_row(r, 26)
    ws.write(r, 2, "Unit tests of the worksheet functions (macros enabled)", b.f(bold=True, font_size=14,
                                                                                font_color=NAVY))
    r += 1
    b.headers(ws, r, ["#", "Function", "Case", "Input 1", "Input 2", "Input 3", "Expected (Excel)", "Actual (VBA)",
                      "Abs. diff", "Rel. diff", "Tolerance", "Result"], output=True, height=42,
              name="FormulaTests_Header", center_from=6)
    units = [
        ("PPM_SMM", "CPR 10%", 0.10, None, None, "=1-(1-{a})^(1/12)", "=PPM_SMM({a})"),
        ("PPM_SMM", "CPR 100%", 1.0, None, None, "=1-(1-{a})^(1/12)", "=PPM_SMM({a})"),
        ("PPM_CPRFromSMM", "SMM 1%", 0.01, None, None, "=1-(1-{a})^12", "=PPM_CPRFromSMM({a})"),
        ("PPM_SCurveCPR", "Incentive at midpoint", 0.01, None, None,
         "=0.03+(0.25-0.03)/(1+EXP(-250*({a}-0.01)))", "=PPM_SCurveCPR({a},0.03,0.25,250,0.01)"),
        ("PPM_SCurveCPR", "Incentive +2%", 0.02, None, None,
         "=0.03+(0.25-0.03)/(1+EXP(-250*({a}-0.01)))", "=PPM_SCurveCPR({a},0.03,0.25,250,0.01)"),
        ("PPM_SCurveCPR", "Incentive -3%", -0.03, None, None,
         "=0.03+(0.25-0.03)/(1+EXP(-250*({a}-0.01)))", "=PPM_SCurveCPR({a},0.03,0.25,250,0.01)"),
        ("PPM_AnnuityPrincipal", "100,000 at 3%, 240 monthly", 100000, 0.03, 240,
         "={a}*({b}/12)/((1+{b}/12)^{c}-1)", "=PPM_AnnuityPrincipal({a},{b},{c},1)"),
        ("PPM_AnnuityPrincipal", "Zero rate, 10 payments", 1000, 0, 10, "={a}/{c}",
         "=PPM_AnnuityPrincipal({a},{b},{c},1)"),
        ("PPM_Shock", "SHORT_UP at 2 years", 2, None, None, "=0.025*EXP(-{a}/4)",
         "=PPM_Shock(\"SHORT_UP\",{a},0.02,0.025,0.01,4)"),
        ("PPM_Shock", "STEEPENER at 10 years", 10, None, None,
         "=-0.65*0.025*EXP(-{a}/4)+0.9*0.01*(1-EXP(-{a}/4))",
         "=PPM_Shock(\"STEEPENER\",{a},0.02,0.025,0.01,4)"),
        ("PPM_Shock", "FLATTENER at 1 year", 1, None, None,
         "=0.8*0.025*EXP(-{a}/4)-0.6*0.01*(1-EXP(-{a}/4))",
         "=PPM_Shock(\"FLATTENER\",{a},0.02,0.025,0.01,4)"),
        ("PPM_LowerBound", "10 years, observed 2%", 10, 0.02, None, "=MIN(0,-0.015+0.0003*{a},{b})",
         "=PPM_LowerBound({a},{b},-0.015,0.0003)"),
        ("PPM_LowerBound", "60 years, observed 1%", 60, 0.01, None, "=MIN(0,-0.015+0.0003*{a},{b})",
         "=PPM_LowerBound({a},{b},-0.015,0.0003)"),
        ("PPM_LowerBound", "1 year, observed -2%", 1, -0.02, None, "=MIN(0,-0.015+0.0003*{a},{b})",
         "=PPM_LowerBound({a},{b},-0.015,0.0003)"),
    ]
    first_u = r + 1
    for i, (fn, case, a, bb, c, exp_f, act_f) in enumerate(units):
        r += 1
        ws.set_row(r, 18)
        ca, cb, cc = (xl_rowcol_to_cell(r, col(4)), xl_rowcol_to_cell(r, col(5)), xl_rowcol_to_cell(r, col(6)))
        ws.write_number(r, col(1), i + 1, b.out("0", "center"))
        ws.write_string(r, col(2), fn, b.out())
        ws.write_string(r, col(3), case, b.out())
        for j, v in enumerate((a, bb, c)):
            if v is None:
                ws.write_blank(r, col(4 + j), None, b.inp("General", "center"))
            else:
                ws.write_number(r, col(4 + j), v, b.inp("General", "center"))
        ws.write_formula(r, col(7), exp_f.format(a=ca, b=cb, c=cc), b.out("0.000000000"))
        ws.write_formula(r, col(8), act_f.format(a=ca, b=cb, c=cc), b.out("0.000000000"))
        e, g = xl_rowcol_to_cell(r, col(7)), xl_rowcol_to_cell(r, col(8))
        ws.write_formula(r, col(9), "=IFERROR(ABS(%s-%s),\"\")" % (g, e), b.out("0.0E+00"))
        ws.write_formula(r, col(10), "=IFERROR(ABS(%s-%s)/MAX(ABS(%s),1E-300),\"\")" % (g, e, e), b.out("0.0E+00"))
        ws.write_number(r, col(11), 1e-12, b.out("0.0E+00"))
        ws.write_formula(r, col(12), "=IF(ISNUMBER(%s),IF(%s<=%s,\"PASS\",\"FAIL\"),\"FAIL\")" % (
            xl_rowcol_to_cell(r, col(9)), xl_rowcol_to_cell(r, col(9)), xl_rowcol_to_cell(r, col(11))),
            b.out(None, "center", bold=True))
    ws.conditional_format(first_u, col(12), r, col(12), {"type": "cell", "criteria": "==", "value": '"PASS"',
                                                         "format": b.wb.add_format({"font_color": GOOD_FONT,
                                                                                    "bg_color": GOOD_FILL})})
    ws.conditional_format(first_u, col(12), r, col(12), {"type": "cell", "criteria": "==", "value": '"FAIL"',
                                                         "format": b.wb.add_format({"font_color": BAD_FONT,
                                                                                    "bg_color": BAD_FILL})})
    ws.freeze_panes(6, 0)


def main():
    prm, curve, loans, out, hist, cal = rm.build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    b = Book(OUT)
    build_readme(b)
    build_params(b)
    build_curve(b)
    build_segments(b)
    build_loans(b, loans)
    build_history(b, hist)
    build_results(b)
    build_cashflows(b)
    build_gap(b)
    build_curves(b)
    build_loancalc(b)
    build_checks(b)
    build_calibration(b)
    tests = reference_tests(prm, out, cal, loans)
    build_tests(b, tests)
    for ws in b.wb.worksheets():
        ws.print_area(0, 1, 1048575, PRINT_LAST_COL[ws.name])
    b.wb.close()
    print("written", OUT, "tests", len(tests))


if __name__ == "__main__":
    main()
