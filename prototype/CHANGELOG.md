# 📜 Changelog

All notable changes to **K-PREPAY** are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html), as in K-SACCR.

## [Unreleased]

### Fixed

- Reject a zero parallel shock before model output is written.
- Return `#NUM!` for negative worksheet shock magnitudes.
- Make the headless runner fail on compile probes, driver errors, missing
  results, incomplete reference-test success or worksheet-function failures;
  clear old driver statuses before each invocation.

These fixes still require real Excel validation.

## [0.1.0] - 2026-10-20

### Added

- Prepayment engine: logistic S-curve CPR in the refinancing incentive with
  penalty, burnout, seasoning ramp and calendar seasonality; floating-rate
  loans repricing at par at the next reset; ANNUITY, LINEAR and BULLET
  schedules with 1 to 12-month payment frequency.
- Eight scenarios (CONTRACT, BASE and the six IRRBB shocks of BCBS d368
  Annex 2 with the EUR sizes and lower bound of Reg. (EU) 2024/856);
  BEHAVIOURAL and BCBS_SA prepayment modes.
- Outputs: PV, dEVE, dEVE / Tier 1, WAL, CPR averages, effective duration,
  outlier indicator, segment table, monthly cash flows, BCBS 19-bucket gap,
  scenario curves, loan-level results, Checks.
- Weighted least-squares calibration of the S-curve (Nelder-Mead) with
  fitted curves and Apply to Segments.
- Worksheet functions PPM_SMM, PPM_CPRFromSMM, PPM_SCurveCPR,
  PPM_AnnuityPrincipal, PPM_Shock, PPM_LowerBound.
- Python reference model, template builder, headless LibreOffice runner,
  static source checks and Excel build script.

### Validation

- Headless LibreOffice host: 52 / 52 reference tests and 14 / 14
  worksheet-function tests PASS; BCBS_SA mode, invalid-input and fatal-input
  runs checked against the reference model.
- Not yet compiled or run in Excel.
