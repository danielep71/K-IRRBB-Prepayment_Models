# Validation plan

Status: **accepted by the owner on 2026-10-21 (issue #15)**, with every [decision](#decisions) as proposed. **Nothing in this plan has been executed.** A VBA test harness (#42) and the first fixtures, expected files and reference reader (#41) exist; the harness has not run in Excel, no workbook build or Excel record exists, and every other check below is planned. Rows marked "#72" cover the EVE and repricing-gap decisions accepted on 2026-10-21; rows marked "#49" cover RENEG successor reconciliation (D11), accepted on 2026-10-26.

This document is authoritative for what independent validation a prepayment implementation must pass before its results can be relied on: the evidence layers, the validation matrix, out-of-time testing, leakage, segmentation, edge cases and scenario sensitivity. Numerical cases are registered in [TEST_CASES.md](TEST_CASES.md); real-host evidence is defined in [EXCEL_EVIDENCE.md](../EXCEL_EVIDENCE.md). The models and data being validated are specified in the [model contracts](MODEL_CONTRACTS.md) and the [data contract](DATA_CONTRACT.md).

## Three evidence layers

| Layer | Establishes | Does not establish | Where recorded | Today |
| --- | --- | --- | --- | --- |
| **Static** | Repository integrity: files, links, provenance register, configuration, tooling tests | That VBA compiles, runs, or calculates correctly | CI check `integrity`; `python tools/check.py` | Executed on every PR |
| **Numerical** | That each calculation matches an independent reference within a stated tolerance, and that models behave as specified out of time | That the workbook runs on a real host | Case register, fixtures and expected files | Partly built: five data cases `Built (Python)` and run by `python tools/check.py`; `RATE-CONV-01` and `RATE-CONV-02` built in VBA, not executed; all other cases registered |
| **Real host** | That the workbook built from one exact commit compiles and runs on a stated Excel host | Model correctness beyond the cases it ran | Excel evidence record | Planned; no record exists |

A pass in one layer is never reported as a pass in another. A green CI run or a Python reference check is not Excel evidence.

## Separation of responsibilities

Calibration, independent challenge and acceptance are distinct and identifiable:

- **Calibration** produces a parameter set from the estimation window.
- **Independent challenge** compares toolkit outputs with references produced outside the toolkit, and runs the out-of-time and property checks below.
- **Acceptance** is the owner's decision, recorded with the evidence it relied on. The toolkit never accepts its own outputs, and code review or green CI is not acceptance.

## Validation matrix

| Area | Minimum independent checks |
| --- | --- |
| Data import | Every validation code, first-error ordering, balance identity at its tolerance, event/flow consistency, RENEG successor reconciliation (D11, #49), reconciliation totals, fingerprint, all-or-nothing rejection |
| CPR/SMM | Conversion both ways, balance weighting, partial/full split, exits per decisions D4 and D5, multi-month compounding |
| Rate incentive | Lag, margin, penalty annualisation, remaining term, curve interpolation and extrapolation |
| `PM0` | Equals the realised CPR of the estimation window |
| `PM1` | Formula evaluation at fixed parameters; fit against an independent optimiser; constraints; failure and minimum-sample handling; recovery of a known generating process (a statistical check, not a tolerance test) |
| Cash-flow projection | Annuity, linear and bullet schedules; payment frequency; re-amortisation after prepayment; repricing at reset; monthly and lifetime conservation |
| Scenarios and overlay | Zero shock reproduces `BASE`; sign and monotonicity of the CPR response; post-shock floor; multiplier overlay; overlays change no fitted parameter |
| EVE and repricing gap (#72) | PV against an independent discounting script; ΔEVE sign and worst scenario; ratio and indicator at the threshold and in another currency; bucket boundaries; gap conservation; CPR layers kept separate; weighted average repricing time, effective duration and projected CPR |
| Common | Leakage, parameter freeze, segment isolation, repeatability, units, failures that withdraw stale outputs |

## Out-of-time validation

The estimation and test windows are set in the [model contracts](MODEL_CONTRACTS.md#common-rules).

1. Estimate once on the estimation window and freeze the parameter set. A recalibration is a separate run, never part of the test.
2. Each month end in the test window is a forecast origin. From each origin, project the loans in the point-in-time view with the frozen parameters and the market curve observed at the origin.
3. Score per segment and currency, at horizons 1 to 12 months:
   - bias and mean absolute error of monthly pool SMM, balance-weighted;
   - error of the cumulative prepaid amount over the horizon, as a share of the realised amount; when the realised amount is zero, the absolute error in currency units instead, with the pair classified `ZERO_REALISED`;
   - the same scores for `PM0`, so `PM1` is always compared with the benchmark.
4. Score an (origin, horizon) pair only when the month end `h` months after the origin lies inside the data window. Every other pair is classified `INCOMPLETE` and reported with its count; it is never scored and never silently dropped.
5. Report every origin and horizon with its scores or classification. Do not drop origins, average away a failing segment or pool currencies.

Pass/fail thresholds are decision V3: a segment and currency passes only when both criteria hold; otherwise it fails and is reported with its scores. `INCOMPLETE` pairs enter neither criterion. `ZERO_REALISED` pairs are excluded from the ±10 % criterion and reported with their absolute error; the SMM criterion still applies to them.

## Leakage prevention

- Every predictor and forecast at origin `t` uses only the [point-in-time view](DATA_CONTRACT.md#point-in-time-availability) at `t`.
- **Property test, forecasts:** altering, adding or removing any row or market rate dated after `t` leaves every predictor and forecast from origin `t` unchanged. Forecasts use the curve observed at `t`, so rates at `t` are not altered by this test.
- **Property test, historical incentive:** for the loan-month ending at `t`, altering any market rate dated after `t - L` leaves its incentive unchanged (`INC-LAG-01`).
- **Negative control:** the same test with the point-in-time filter disabled must detect a change, proving the test can fail.
- Parameters are frozen across the test window: re-running at a later origin with the same parameter set gives identical parameters.

## Segmentation

- Each segment and currency is estimated, scored and reported separately; amounts in different currencies are never added.
- **Isolation:** altering one segment's data leaves every other segment's parameters and forecasts unchanged.
- A segment and currency below the minimum sample is reported as not estimated and produces no parameters or scores.

## Edge cases

Each needs at least one case with a hand-derived or independently computed result:

- available amount `A <= 0`, including the final scheduled payment;
- `SMM = 0`, `SMM = 1` (full prepayment of the whole pool), and CPR at 0 and 1;
- annuity with rate near zero, linear and bullet loans, quarterly to annual payment frequencies;
- negative client and market rates within the contract bounds;
- each penalty type, and remaining term below one year;
- `RESET` loans at `fixed_until`, `FLOAT` loans at reset;
- loans past maturity, gaps, censored disappearances and loans in their first month;
- `RENEG` chains, including a successor at the 0.005 boundary, a missing or duplicated successor and a segment change (D11, #49), `DEFAULT` and `SALE` exits;
- non-zero `other_change`;
- very small and very large balances within the parse limits; leap years and month ends;
- Tier 1 in a currency other than the loans, `PV_BASE <= 0` for duration, and cash flows exactly on a bucket boundary (#72).

## Scenario sensitivity

- A zero shock reproduces `BASE` exactly.
- For `PM1` loans, a parallel up shock gives a CPR path no higher than `BASE` at every month, and a parallel down shock no lower. Steepener, flattener and short-rate shocks follow the sign of the change in the refinancing rate at each loan's remaining term.
- The post-shock floor is applied before the incentive is computed.
- The standardised multiplier overlay gives `min(1, gamma x CPR_BASE)` and changes no fitted parameter. It stays provisional until `REG-1` is verified.
- Projected cash flows conserve balance in every scenario.
- Each scenario discounts with its own shocked and floored curve, and `CONTRACT` never enters the worst ΔEVE (#72).

## Evidence protocol

Each executed check records the source commit SHA, the case ID, fixture and expected-file names, the expected value's provenance, the tolerance, the observed result, the host (for Excel) and the reviewer. Only synthetic data enters Git or evidence. Reference values are never copied from toolkit output.

## Planned versus executed

Every case and check carries one status:

| Status | Meaning |
| --- | --- |
| `Registered` | Defined here or in the case register; nothing built |
| `Built (Python)` | Fixture, expected file and independent reference script committed and run by `python tools/check.py` |
| `Built (VBA)` | A VBA test exists in the harness; not yet run in Excel |
| `Built (Python, VBA)` | Both of the above |
| `Executed (Excel)` | Passed in an Excel evidence record for the candidate commit, linked |

Today every `DATA-*` case except `DATA-REJECT-01` is `Built (Python)`, of which `DATA-PARSE-01`, `DATA-SHA-01`, `DATA-IDENT-01`, `DATA-EXPO-01`, `DATA-RENEG-01`, `DATA-EVENT-01`, `DATA-INVALID-01` and `DATA-PIT-01` are `Built (Python, VBA)`, `RATE-CONV-01` and `RATE-CONV-02` are `Built (VBA)`, and every other case is `Registered`. A status is raised only in the change that delivers it.

## Future scope

This plan does not build anything. The following work needs its own issues in a later milestone:

1. independent reference scripts and pinned offline tooling for the expected values (decision V4);
2. synthetic fixtures and expected files for the data contract and each registered case;
3. the VBA test harness, its failure-injection path and its case registry;
4. the workbook builder and the source round-trip export/compare tool;
5. the first Excel evidence record on a release candidate.

## Decisions

| # | Decision | Outcome | Status |
| ---: | --- | --- | --- |
| V1 | Test window | At least 12 forecast origins after the estimation window with a complete 12-month horizon inside the data window. Later origins may follow; their pairs that end beyond the data window are classified `INCOMPLETE` | Accepted 2026-10-21; amended 2026-10-21 after reviews of #26 and #34 |
| V2 | Horizons | 1 to 12 months, plus the cumulative prepaid amount at 12 months | Accepted 2026-10-21 |
| V3 | Out-of-time pass criteria | `PM1` MAE of monthly SMM no worse than `PM0` at every horizon, and cumulative prepaid error within ±10 % at 12 months, per segment and currency; `INCOMPLETE` pairs excluded from both, `ZERO_REALISED` pairs from the ±10 % test | Accepted 2026-10-21; amended 2026-10-21 after review of #26 |
| V4 | Reference tooling | Python with pinned NumPy/SciPy, offline only, never a runtime dependency | Accepted 2026-10-21 |
| V5 | `PM1` fit tolerance | Parameters `rel 1e-6` and objective `rel 1e-9` against the independent optimiser | Accepted 2026-10-21 |
| V6 | Status vocabulary | The four statuses above | Accepted 2026-10-21 |
