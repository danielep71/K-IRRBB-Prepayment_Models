<div align="center">

# 🏦 K-PREPAY

### Behavioural prepayment model for IRRBB in Excel VBA

**S-curve CPR · Seasoning, seasonality, burnout · Six IRRBB shocks · EVE sensitivity · BCBS repricing gap · Calibration · Independent reference tests**

<br>

[![Excel VBA](https://img.shields.io/badge/Excel_VBA-64--bit-217346?style=for-the-badge&logo=microsoft-excel&logoColor=white)](#requirements)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](#requirements)
[![Framework](https://img.shields.io/badge/Framework-BCBS_d368_%C2%B7_Reg._(EU)_2024%2F856-1f3a5f?style=for-the-badge)](docs/methodology/README.md)
[![Status](https://img.shields.io/badge/Status-Prototype_0.1.0-d97706?style=for-the-badge)](#status)
[![Reference tests](https://img.shields.io/badge/Reference_tests-52-2ea44f?style=for-the-badge)](#validation)

<br>

**No add-in · No external reference · No DLL · No installer · Reviewable source for every calculation**

</div>

> [!IMPORTANT]
> **Prototype.** The engine has been executed end to end only in a headless
> LibreOffice host (52 of 52 reference tests passing, largest relative
> difference 5e-13). It has **not yet been compiled and run in Excel**; do
> that before relying on any number ([validation](#validation)).

> [!WARNING]
> **Prototype outside the agreed architecture.** This folder is a draft for
> review, not production source. It departs from
> [`docs/REPOSITORY_STRUCTURE.md`](../docs/REPOSITORY_STRUCTURE.md) in three
> ways to be resolved before it can move to `src/`:
> the facade prefix is `PPM_` instead of `PREPAY_`;
> `CORE_Util`, `CORE_Engine` and `CORE_Calibrate` read and write sheets,
> while core must use arrays and scalars only;
> and it needs a macro-free template, which has no approved exception.
> The template is therefore **not committed**: generate it with
> `python tools/build_template.py` (needs XlsxWriter) from this folder.
> The data and model contracts of issue #14 and the evidence of issue #15
> are not yet agreed.

> [!NOTE]
> As in K-SACCR, the workbook is **not stored as a macro-enabled file**. It is
> built from the macro-free template `src/workbook/PPM_Template.xlsx` and the
> exported VBA source, so every line of calculation code is reviewable.

## ✨ What it does

For a book of fixed- and floating-rate loans, the model projects monthly
cash flows under eight scenarios — contractual, behavioural base and the six
IRRBB shocks — with a conditional prepayment rate that responds to the
refinancing incentive on each scenario curve:

```text
CPR(t) = min(1, [CPRmin + (CPRmax - CPRmin) x B(t) x L(slope x (I(t) - mid))] x Ramp(t) x Season(t))
I(t)   = client rate - (z_s(T) + refinancing margin) - penalty / max(T, 1)
SMM    = 1 - (1 - CPR)^(1/12)
PV_s   = sum CF_s(k) x exp(-z_s(k/12) x k/12)        dEVE_s = PV_s - PV_BASE
```

It then reports, per scenario, PV, ΔEVE and ΔEVE / Tier 1, WAL, average
CPR and the BCBS 19-bucket gap, and fits the S-curve of each segment to an
observation history.

## 🗂️ Workbook

| Sheet | Role | Tab |
| --- | --- | --- |
| README | How to use, formulas, limitations | navy |
| Params | As-of date, currency, mode, shock sizes, lower bound, Tier 1, γ multipliers, seasonality | amber (input) |
| Curve | Risk-free zero curve, continuously compounded | amber |
| Segments | S-curve, seasoning ramp, burnout, refinancing margin, floating CPR per segment | amber |
| Loans | One row per loan (FIXED / FLOAT, ANNUITY / LINEAR / BULLET, 1–12 month frequency, penalty) | amber |
| History | Observed CPR by segment and incentive, for calibration | amber |
| Results | Scenario table, summary (worst ΔEVE, outlier indicator, effective duration), segment table, charts | blue (output) |
| CashFlows | Monthly book cash flows by scenario | blue |
| Gap | BCBS d368 Table 1 buckets: contractual vs behavioural principal, cash flows by shock | blue |
| ScenarioCurves | Shocked zero curves and lower bound at the bucket midpoints | blue |
| LoanCalc | One row per loan: status, PV by scenario, WAL, duration, CPR, findings | blue |
| Checks | Every rejected input and assumption (ERROR / WARNING / INFO) | blue |
| Calibration | Fitted CPR min, CPR max, slope, midpoint, RMSE, R², fitted curves | blue |
| Tests | Reference tests against the Python model; worksheet-function unit tests | green |

Palette, fonts, bands, header styles, input-cell convention, tab colours,
names-based table location, buttons and print setup follow the
[K-SACCR](https://github.com/danielep71/saccr) template.

## 🧱 Repository

```text
src/core/        CORE_Config, CORE_Util, CORE_Curve, CORE_Prepay, CORE_Engine, CORE_Calibrate
src/modules/     PPM_Formulas      worksheet functions (PPM_SMM, PPM_SCurveCPR, PPM_Shock, ...)
src/workbook/    PPM_Template.xlsx (macro-free) and M_Main (button macros)
tests/modules/   TEST_PPM          reference-test runner
tools/           reference_model.py      executable specification (standard library)
                 build_template.py       builds the template and the expected test values
                 run_vba_headless.py     runs the VBA in LibreOffice and checks it
                 check_source.py         static house-style checks
                 Build-PPM-Workbook.ps1  builds the .xlsm through Excel
docs/methodology/README.md
```

<a id="requirements"></a>

## 🚀 Quick start

1. Build the workbook (Windows, Excel, "Trust access to the VBA project
   object model" enabled for the build):

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Build-PPM-Workbook.ps1 -OutputPath "C:\Work\K-PREPAY.xlsm"
   ```

   Where policy forbids that setting, import the nine `.bas` files by hand
   ([INSTALLATION.md](INSTALLATION.md)).
2. Open `K-PREPAY.xlsm`, enable macros, press **Run model** on Results.
3. Press **Run tests** on Tests: all 52 reference tests must PASS on the
   illustrative data before you change any input.

<a id="validation"></a>

## ✅ Validation

| Check | Result |
| --- | --- |
| Python reference (`tools/reference_model.py`) vs VBA, BEHAVIOURAL mode | 52 / 52 PASS, max relative difference 4.5e-13 (LibreOffice host) |
| Worksheet functions vs native Excel formulas (Tests, lower table) | 14 / 14 PASS (called directly in the LibreOffice host) |
| Same, BCBS_SA mode with 8 invalid / edge-case loans added | All scenario PVs within 3e-15; every rejection reported on Checks |
| Fatal input (non-increasing curve) | Run stops, outputs cleared, ERROR on Checks |
| Button macros (validate, clear, calibrate, apply, run) | Executed in sequence without error |
| Static checks (`tools/check_source.py`) | 9 / 9 modules OK |
| **Excel 64-bit compile and run** | **Not yet performed** |

## ⚠️ Limitations

Loan book only (no deposits, hedges, equity), one currency, no NII, no new
business, no basis risk; the outlier indicator is therefore indicative, not
the bank-level supervisory test. The refinancing benchmark is the zero rate,
not the par rate, of the remaining maturity. All data are synthetic.
See the [methodology](docs/methodology/README.md).
