# 📦 Installation

## Generate the template first

In this repository the template is not committed. From `prototype/`:

```sh
python -m pip install XlsxWriter
python tools/build_template.py      # writes src/workbook/PPM_Template.xlsx
```

## Build with the script (recommended)

Requirements: Windows desktop Excel (Microsoft 365 or 2016 and later,
64-bit primary), and "Trust access to the VBA project object model"
(Excel > Options > Trust Center > Macro Settings) enabled while you build.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Build-PPM-Workbook.ps1 -OutputPath "C:\Work\K-PREPAY.xlsm"
```

`-Mode Production` leaves out the test module; `-Force` replaces an existing
output file. The script never changes the template or the source files.

## Build by hand (no trust setting needed)

1. Copy `src\workbook\PPM_Template.xlsx` and open the copy.
2. `Alt+F11` → **File → Import File…** and import, in this order:
   `src\core\CORE_Config.bas`, `CORE_Util.bas`, `CORE_Curve.bas`,
   `CORE_Prepay.bas`, `CORE_Engine.bas`, `CORE_Calibrate.bas`,
   `src\modules\PPM_Formulas.bas`, `src\workbook\M_Main.bas` and, for a
   development workbook, `tests\modules\TEST_PPM.bas`.
3. **Debug → Compile VBAProject**: it must compile with no message.
4. **File → Save As** → *Excel Macro-Enabled Workbook (\*.xlsm)*.

The `.bas` files must have CRLF line endings (a Git clone with the
repository's `.gitattributes` gives them; GitHub's Raw view does not).
References: only the four defaults of a new workbook.

## First run

1. Open the `.xlsm`, enable macros as your policy allows.
2. **Results → Run model.** Expect `66 of 66 loans used | 0 errors, 0 warnings`.
3. **Tests → Run tests.** Expect `52 of 52 PASS`. The worksheet-function unit
   tests below the reference tests recalculate on their own (14 PASS).
4. **Calibration → Calibrate**, then **Apply to Segments** if you want the
   fitted S-curves to replace the Segments values.

## Development checks (any platform)

```sh
python tools/check_source.py                      # house-style static checks
python tools/reference_model.py                   # reference results
python tools/build_template.py                    # rebuild the template (needs XlsxWriter)
python tools/run_vba_headless.py                  # run the VBA in LibreOffice (needs soffice)
python tools/run_vba_headless.py --ops            # exercise the button macros
```

`run_vba_headless.py` is a development aid: it adapts four constructs that
LibreOffice lacks (see its header) and does not replace an Excel run.
