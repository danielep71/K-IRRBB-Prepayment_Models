"""Run the K-PREPAY VBA source headlessly in LibreOffice and check it.

This is a development aid, not a substitute for the Excel validation
required before release: LibreOffice runs VBA through its compatibility
layer, which differs from Excel in places (see the adaptations below).
It loads src/workbook/PPM_Template.xlsx, inserts every module of src/ and
tests/modules/, runs the model, the calibration and the reference tests
in silent mode, saves the filled workbook, and compares every reference
test with tools/reference_model.py.

Adaptations made to a copy of the source for LibreOffice only:
  - "Attribute VB_Name" lines removed and "Option VBASupport 1" added;
  - "Option Private Module" removed;
  - vbObjectError replaced by its value in constant declarations;
  - Debug.Print routed to a no-op (the Immediate window does not exist).

Usage:  python tools/run_vba_headless.py [--mode BCBS_SA] [--out file.xlsx]
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = sorted(glob.glob(os.path.join(ROOT, "src", "**", "*.bas"), recursive=True)) + \
    sorted(glob.glob(os.path.join(ROOT, "tests", "modules", "*.bas")))

DRIVER = '''Option VBASupport 1
Option Explicit

Public Sub ZZ_Drive()
    Dim Line As String
    Dim Sheet As Object
    Set Sheet = ThisComponent.Sheets.getByName("Tests")
    On Error GoTo Failed
    gSilent = True
    Line = RunModel_Silent()
    Sheet.getCellRangeByName("AA1").setString("RUN:" & Line)
    Line = TEST_PPM.RunReferenceTests()
    Sheet.getCellRangeByName("AA2").setString("TESTS:" & Line)
    Exit Sub
Failed:
    Sheet.getCellRangeByName("AA3").setString("ERROR:" & Err.Number & " " & Err.Description & " @ " & Erl)
End Sub

Public Sub ZZ_Ops()
    Dim Sheet As Object
    Set Sheet = ThisComponent.Sheets.getByName("Tests")
    On Error GoTo Failed
    gSilent = True
    ValidateInputs
    Sheet.getCellRangeByName("AA4").setString("VALIDATE:" & gLastMessage)
    ClearOutputs
    Sheet.getCellRangeByName("AA5").setString("CLEAR:" & gLastMessage)
    RunCalibration
    Sheet.getCellRangeByName("AA6").setString("CALIBRATE:" & gLastMessage)
    ApplyCalibration
    Sheet.getCellRangeByName("AA7").setString("APPLY:" & gLastMessage)
    RunModel
    Sheet.getCellRangeByName("AA8").setString("RUN:" & gLastMessage)
    Exit Sub
Failed:
    Sheet.getCellRangeByName("AA3").setString("ERROR:" & Err.Number & " " & Err.Description)
End Sub

Public Sub ZZ_Log(ByVal Text As String)
End Sub

Public Sub ZZ_Probe()
    ThisComponent.Sheets.getByName("Tests").getCellRangeByName("AA9").setString("PROBE")
End Sub
'''


def adapt(code: str) -> str:
    lines = []
    for ln in code.replace("\r\n", "\n").split("\n"):
        if ln.startswith("Attribute VB_Name"):
            continue
        if ln.strip() == "Option Private Module":
            continue
        ln = ln.replace("Debug.Print ", "ZZ_Log ")
        if "Const" in ln and "vbObjectError" in ln:
            ln = ln.replace("vbObjectError", "(-2147221504)")
        lines.append(ln)
    return "Option VBASupport 1\n" + "\n".join(lines)


def module_name(code: str) -> str:
    m = re.search(r'Attribute VB_Name = "([^"]+)"', code)
    return m.group(1)


def require_driver_success(statuses, ops=False):
    """Fail closed on a driver error, missing output or failed reference test."""
    if statuses.get("AA3", "").strip():
        raise RuntimeError(statuses["AA3"])
    required = ("AA4", "AA5", "AA6", "AA7", "AA8") if ops else ("AA1", "AA2")
    for cell in required:
        value = statuses.get(cell, "")
        if ":" not in value or not value.split(":", 1)[1].strip():
            raise RuntimeError("Missing driver result in " + cell)
    if not ops:
        match = re.search(r": (\d+) of (\d+) PASS(?: [|] |$)", statuses["AA2"])
        if not match or int(match[2]) == 0 or int(match[1]) != int(match[2]):
            raise RuntimeError("Reference tests failed or summary missing: " + statuses["AA2"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=None)
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "ppm_headless_out.xlsx"))
    ap.add_argument("--port", default="2003")
    ap.add_argument("--ops", action="store_true", help="run the button macros instead of the tests")
    ap.add_argument("--template", default=os.path.join(ROOT, "src", "workbook", "PPM_Template.xlsx"))
    args = ap.parse_args()

    import uno  # noqa: F401  (LibreOffice Python bridge)
    from com.sun.star.beans import PropertyValue

    def pv(n, v):
        p = PropertyValue()
        p.Name = n
        p.Value = v
        return p

    work = tempfile.mkdtemp()
    src = os.path.join(work, "in.xlsx")
    shutil.copy(args.template, src)
    if args.mode:
        import openpyxl
        wb = openpyxl.load_workbook(src)
        wb["Params"]["E8"].value = args.mode
        wb.save(src)
    proc = subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore",
                             "-env:UserInstallation=file://" + work + "/profile",
                             "--accept=socket,host=localhost,port=%s;urp;" % args.port],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ctx = None
        for _ in range(120):
            try:
                local = uno.getComponentContext()
                res = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
                ctx = res.resolve("uno:socket,host=localhost,port=%s;urp;StarOffice.ComponentContext" % args.port)
                break
            except Exception:
                time.sleep(0.5)
        desk = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desk.loadComponentFromURL("file://" + src, "_blank", 0,
                                        (pv("Hidden", True), pv("MacroExecutionMode", 4)))
        libs = doc.BasicLibraries
        if not libs.hasByName("Standard"):
            libs.createLibrary("Standard")
        lib = libs.getByName("Standard")
        names = []
        for path in SOURCES:
            code = open(path, encoding="cp1252").read()
            name = module_name(code)
            body = adapt(code) + "\n\nPublic Sub ZZ_Probe_%s()\n    ThisComponent.Sheets.getByName(\"Tests\")" \
                                 ".getCellRangeByName(\"AB1\").setString(\"%s\")\nEnd Sub\n" % (name, name)
            if lib.hasByName(name):
                lib.removeByName(name)
            lib.insertByName(name, body)
            names.append(name)
        lib.insertByName("ZZ_Driver", DRIVER)
        sp = doc.getScriptProvider()
        sheet = doc.Sheets.getByName("Tests")
        bad = []
        for name in names:
            sheet.getCellRangeByName("AB1").setString("")
            sp.getScript("vnd.sun.star.script:Standard.%s.ZZ_Probe_%s?language=Basic&location=document"
                         % (name, name)).invoke((), (), ())
            if sheet.getCellRangeByName("AB1").getString() != name:
                bad.append(name)
        if bad:
            raise RuntimeError("COMPILE FAILURE in modules: " + ", ".join(bad))
        for row in range(1, 9):
            sheet.getCellRangeByName("AA%d" % row).setString("")
        t0 = time.time()
        entry = "ZZ_Ops" if args.ops else "ZZ_Drive"
        sp.getScript("vnd.sun.star.script:Standard.ZZ_Driver.%s?language=Basic&location=document" % entry).invoke(
            (), (), ())
        print("driver %.1f s" % (time.time() - t0))
        statuses = {}
        for a in ("AA1", "AA2", "AA3", "AA4", "AA5", "AA6", "AA7", "AA8"):
            s = sheet.getCellRangeByName(a).getString()
            statuses[a] = s
            if s:
                print(a, s)
        require_driver_success(statuses, args.ops)
        doc.calculateAll()
        # LibreOffice does not bind the PPM_* formulas of the template to the
        # Basic functions, so call each one directly with the inputs of its
        # unit-test row and compare with the Excel-formula expectation.
        unit_calls = [
            ("PPM_SMM", lambda a, b, c: (a,)), ("PPM_SMM", lambda a, b, c: (a,)),
            ("PPM_CPRFromSMM", lambda a, b, c: (a,)),
            ("PPM_SCurveCPR", lambda a, b, c: (a, 0.03, 0.25, 250.0, 0.01, 1.0)),
            ("PPM_SCurveCPR", lambda a, b, c: (a, 0.03, 0.25, 250.0, 0.01, 1.0)),
            ("PPM_SCurveCPR", lambda a, b, c: (a, 0.03, 0.25, 250.0, 0.01, 1.0)),
            ("PPM_AnnuityPrincipal", lambda a, b, c: (a, b, c, 1.0)),
            ("PPM_AnnuityPrincipal", lambda a, b, c: (a, b, c, 1.0)),
            ("PPM_Shock", lambda a, b, c: ("SHORT_UP", a, 0.02, 0.025, 0.01, 4.0)),
            ("PPM_Shock", lambda a, b, c: ("STEEPENER", a, 0.02, 0.025, 0.01, 4.0)),
            ("PPM_Shock", lambda a, b, c: ("FLATTENER", a, 0.02, 0.025, 0.01, 4.0)),
            ("PPM_LowerBound", lambda a, b, c: (a, b, -0.015, 0.0003)),
            ("PPM_LowerBound", lambda a, b, c: (a, b, -0.015, 0.0003)),
            ("PPM_LowerBound", lambda a, b, c: (a, b, -0.015, 0.0003)),
        ]
        hdr = None
        for r in range(1, 400):
            if sheet.getCellByPosition(2, r).getString() == "#" and sheet.getCellByPosition(3, r).getString() == "Function":
                hdr = r
        if hdr is None:
            raise RuntimeError("Worksheet-function test table missing")
        passed = 0
        for i, (fn, argf) in enumerate(unit_calls):
            row = hdr + 1 + i
            a, b, c = (sheet.getCellByPosition(5 + j, row).getValue() for j in range(3))
            exp = sheet.getCellByPosition(8, row).getValue()
            got = sp.getScript("vnd.sun.star.script:Standard.PPM_Formulas.%s?language=Basic&location=document"
                               % fn).invoke(argf(a, b, c), (), ())[0]
            ok = isinstance(got, (int, float)) and abs(got - exp) <= 1e-12 * max(abs(exp), 1.0)
            passed += ok
            if not ok:
                print("UNIT FAIL", fn, a, b, c, exp, got)
        print("unit tests of the worksheet functions: %d of %d PASS" % (passed, len(unit_calls)))
        if passed != len(unit_calls):
            raise RuntimeError("Worksheet-function tests failed")
        doc.storeToURL("file://" + args.out, (pv("FilterName", "Calc MS Excel 2007 XML"),))
        doc.close(True)
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
    print("saved", args.out)


if __name__ == "__main__":
    sys.exit(main())
