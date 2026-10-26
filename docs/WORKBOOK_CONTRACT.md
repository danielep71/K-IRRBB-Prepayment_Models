# Workbook contract

Status: **proposed in issue #38; decisions W1–W10 are not accepted.** No workbook, template, builder or VBA exists. This is a specification only; nothing here is built, compiled or run.

This document is authoritative for the layout of the future analysis workbook: sheet order, names and CodeNames, defined names, the input, parameter, result and diagnostics areas, and which areas the toolkit writes. What is calculated is specified in the [data contract](methodology/DATA_CONTRACT.md) and the [model contracts](methodology/MODEL_CONTRACTS.md); the code boundaries are in [repository structure](REPOSITORY_STRUCTURE.md); what a real Excel run must record is in [Excel evidence](EXCEL_EVIDENCE.md).

## Principles

- **Built, never committed.** The owner decided on 2026-10-21 (#43) that the macro-free template is generated at build time by a committed builder script and never committed. The builder (#43) creates the template, imports the exported VBA of one commit and saves the `.xlsm` outside the checkout or in a Git-ignored location. No `.xlsx`, `.xlsm` or `.xlsb` file enters Git.
- **Datasets never on worksheets.** The three input files are streamed by VBA file input into memory (data decision D1). Worksheets hold run settings, behavioural assumptions, lineage, findings, reconciliation, parameter sets, results and diagnostics only.
- **No model formulas on sheets.** Every calculated value is written by VBA through the facade. Toolkit-written areas contain values only; input areas use data validation only. Conditional formats and charts may read written values.
- **Adapters own the sheets.** Only `WB_` modules in `src/workbook/` read or write worksheets. They address sheets by CodeName and ranges by defined name, never by tab name or hard-coded address. `CORE_` and `PREPAY_` modules never touch a workbook object.
- **No partial results.** An operation validates first, calculates in memory, then clears and writes all of its result areas. On failure it writes none of them and marks them `FAILED`; earlier results are never presented as current. [Status and staleness](#status-and-staleness) sets which areas a failure clears and which it keeps.

## Sheets

Order is the tab order. Every sheet is visible; there are no hidden or very hidden sheets (W1).

| # | Tab name | CodeName | Role | Toolkit writes | Content |
| ---: | --- | --- | --- | :---: | --- |
| 1 | `README` | `shReadme` | Reference | Builder only | Purpose, limitations, build commit, links to the contracts |
| 2 | `Settings` | `shSettings` | Input | | Run settings and optimiser settings ([Settings](#settings)) |
| 3 | `Assumptions` | `shAssumptions` | Input | | Behavioural assumptions per segment ([Assumptions](#assumptions)) |
| 4 | `Scenarios` | `shScenarios` | Input | | Shock sizes per currency and user-defined shocks ([Scenarios](#scenarios)) |
| 5 | `Controls` | `shControls` | Input | | Optional control totals for [reconciliation](methodology/DATA_CONTRACT.md#reconciliation) |
| 6 | `Import` | `shImport` | Output | ✅ | Lineage of the accepted dataset and the import outcome |
| 7 | `Findings` | `shFindings` | Diagnostics | ✅ | Errors and warnings of the last import or run |
| 8 | `Reconciliation` | `shReconciliation` | Output | ✅ | Totals per month end, segment and currency; control-total comparison |
| 9 | `Parameters` | `shParameters` | Parameters | ✅ append only | Immutable parameter sets |
| 10 | `Calibration` | `shCalibration` | Diagnostics | ✅ | `PM0` and `PM1` fit diagnostics |
| 11 | `Backtest` | `shBacktest` | Diagnostics | ✅ | Out-of-time scores and V3 outcome |
| 12 | `CashFlows` | `shCashFlows` | Output | ✅ | Projected cash flows, SMM and CPR by month |
| 13 | `EVE` | `shEVE` | Output | ✅ | PV, ΔEVE, worst case, ratio and indicator |
| 14 | `Gap` | `shGap` | Output | ✅ | Repricing gap in the 19 buckets |
| 15 | `Measures` | `shMeasures` | Output | ✅ | Weighted average repricing time, effective duration, projected CPR |
| 16 | `Log` | `shLog` | Diagnostics | ✅ append only | One row per operation |
| 17 | `Tests` | `shTests` | Test build only | ✅ | Harness case table; absent from the production build (W8) |

The toolkit never writes an input sheet or `README`. Users never edit an output, parameter or diagnostics sheet; the next operation overwrites or appends to it.

## Layout

All sheets share one layout, following the prototype template of #19, whose visual identity uses K-SACCR as a visual reference only; #43 records that reference in `docs/provenance.json`.

- Row 1 carries the product band and row 2 the sheet title. Row 4 of every output, parameter and diagnostics sheet is the status line, named `<Sheet>_Status` ([Status and staleness](#status-and-staleness)).
- Every table starts in column C. Its first header cell carries a workbook-scoped name `<Sheet>_<Table>`; data rows start on the row below and run to the last used row.
- Input cells are visually distinct from output cells. Gridlines are off and print areas are set by the builder.
- A table that would exceed 1,048,576 rows fails the operation before anything is written; it is never truncated.

## Defined names

- All names are workbook-scoped, refer to one cell in this workbook with an absolute reference, and are visible (W2). External references, relative references, hidden names and names created by users for the toolkit are not allowed.
- **Scalar settings:** `cfg_<code>`, on the value cell of the setting row, for every code in [Settings](#settings).
- **Table anchors:** `<Sheet>_<Table>`, on the first header cell, for every table below. No table is named `Status`, so a table anchor never collides with a `<Sheet>_Status` name.
- **Workbook state:** `Run_Status`, `Run_ID`, `Run_Operation`, `Run_Timestamp`, `Run_Commit` on `Log`, and `Build_Commit` on `README`.
- The builder creates every name. Before an operation, the adapter checks that each name exists and points to the expected sheet; a missing or moved name stops the operation before any calculation.

## Input areas

### Settings

Table `Settings_Run`, one row per setting: code, description, value, unit and contract reference. The value cell is named `cfg_<code>`.

| Code | Type | Rule | Contract |
| --- | --- | --- | --- |
| `as_of_date` | ISO date | Month end inside the data window; projection start and `BASE` curve date | Model contracts, [scenarios](methodology/MODEL_CONTRACTS.md#scenarios) |
| `data_window_start`, `data_window_end` | ISO date | Month ends, start before end | [Point-in-time availability](methodology/DATA_CONTRACT.md#point-in-time-availability) |
| `estimation_start`, `estimation_end` | ISO date | Month ends inside the data window | [Common rules](methodology/MODEL_CONTRACTS.md#common-rules) |
| `test_start`, `test_end` | ISO date or empty | Both empty, or both set with `test_start > estimation_end` | Common rules; V1 |
| `segment_list` | Comma-separated codes | Non-empty subset of the D2 segment codes | D2 |
| `currency_allowlist` | Comma-separated ISO 4217 codes | Non-empty | [Validation](methodology/DATA_CONTRACT.md#validation-and-invalid-input) `E07` |
| `refi_curve_series` | Comma-separated `rate_id` values | Par swap series, at least one per currency in `currency_allowlist` (M3) | [Rate incentive](methodology/MODEL_CONTRACTS.md#rate-incentive) |
| `discount_curve_series` | Comma-separated `rate_id` values | Series supplied as continuously compounded zero rates (M13) | [Present value](methodology/MODEL_CONTRACTS.md#present-value) |
| `discount_curve_convention` | `ZERO_CC` | Any other value rejects the run (M13) | Present value |
| `reneg_inclusion` | `EXCLUDE` or `INCLUDE` | Default `EXCLUDE` (D4) | [CPR and SMM](methodology/MODEL_CONTRACTS.md#cpr-and-smm) |
| `standardised_layer` | `Y` or `N` | `Y` adds the standardised-multiplier CPR layer (M15) | [Regulatory overlay](methodology/MODEL_CONTRACTS.md#regulatory-overlay) |
| `tier1_amount` | Decimal, up to 4 places | > 0 when a ratio is requested (D10) | [Tier 1 capital](methodology/DATA_CONTRACT.md#tier-1-capital) |
| `tier1_currency` | ISO 4217 | In `currency_allowlist` (D10) | Tier 1 capital |
| `timely_reporting_attested` | `Y` or `N` | Import refuses to start unless `Y` | Point-in-time availability; [lineage](methodology/DATA_CONTRACT.md#lineage) |
| `calibration_run_id` | Run ID or empty | The calibration run whose parameter sets, one per segment and currency, are used by backtest, projection and export; empty means the latest successful calibration | [Parameter and scenario outputs](methodology/MODEL_CONTRACTS.md#parameter-and-scenario-outputs) |

Table `Settings_Optimiser`, the Nelder–Mead settings the model contracts require to be recorded: `opt_start_p1` to `opt_start_p4`, `opt_initial_step`, `opt_tolerance`, `opt_max_iterations` and `opt_restarts`, each named `cfg_<code>`. Defaults are delivered with the facade (#42) and recorded in every parameter set.

Accepted contract decisions that fix a value (the incentive lag `L` of M4, the 25 bp buckets of M8, the minimum sample of M9, the 0.005 tolerance of D9, the post-shock floor and the standardised multipliers) are **code constants**, not settings; each parameter set and result records them (W3).

### Assumptions

Table `Assumptions_Segments`, one row per segment in `segment_list`: `segment`, new-business margin `m` (M5), seasoning months `a_ramp`, burnout strength `b`, the 12 calendar-month factors `season_01` to `season_12` and a source note. Every row is labelled a behavioural assumption (M7). The seasonality factors must have mean 1 within 1e-9; a segment in `segment_list` without a row, or with an invalid row, stops the operation.

### Scenarios

- Table `Scenarios_Shocks`, one row per currency in `currency_allowlist`: parallel, short and long shock sizes in decimals and a status note. Shock sizes per currency come from `REG-3`, which is **not verified** (#45), so they are user inputs labelled provisional; the supervisory shapes are code constants.
- Table `Scenarios_User`, optional user-defined shocks: `scenario_id`, `currency`, type `PARALLEL` or `RAMP`, size in decimals and ramp months. They report their own ΔEVE and never enter the worst case (M15).

### Controls

Table `Controls_Totals`, optional, one row per (`as_of_date`, `segment`, `currency`) with the reconciliation measures of the data contract. An empty table means no control totals were supplied.

## Output, parameter and diagnostics areas

| Sheet | Tables | Written by | Content |
| --- | --- | --- | --- |
| `Import` | `Import_Lineage`, `Import_Counts` | Import | Every lineage item of the data contract: file name without directory, size and SHA-256, counts, settings, attestation, commit SHA, timestamp |
| `Findings` | `Findings_Summary`, `Findings_Rows` | Import, every run | Count per code; then one row per finding in the contract order: code, file, line, key, message. At most 100,000 rows are listed; the summary always has every count (W4) |
| `Reconciliation` | `Reconciliation_Totals`, `Reconciliation_Controls` | Import | Totals per month end, segment and currency; control-total differences |
| `Parameters` | `Parameters_Sets`, `Parameters_Values` | Calibration | One header row per set (every item of a [parameter set](methodology/MODEL_CONTRACTS.md#parameter-and-scenario-outputs)) and one row per value with unit and layer. Append only (W5) |
| `Calibration` | `Calibration_Optimiser`, `Calibration_Buckets`, `Calibration_Residuals` | Calibration | Optimiser status, iterations and objective; observed vs fitted SMM and CPR per bucket; weighted R²; residuals by age, calendar month and cohort; `PM0` comparison; "not estimated" segments with the reason |
| `Backtest` | `Backtest_Scores`, `Backtest_Outcome` | Backtest | Bias, MAE and cumulative prepaid error per segment, currency, origin and horizon, with `INCOMPLETE` and `ZERO_REALISED` pairs and their counts; V3 pass or fail |
| `CashFlows` | `CashFlows_Table` | Projection | One row per segment, currency, CPR layer, scenario and month: opening, interest, scheduled, prepaid, repricing, closing, SMM, CPR, parameter-set ID |
| `EVE` | `EVE_Scenarios`, `EVE_Summary` | Projection | PV and ΔEVE per segment, currency, layer and scenario, and in total per currency; worst ΔEVE, ratio and indicator in the Tier 1 currency with the Tier 1 amount used, labelled "loan-book indicator; not the supervisory outlier test" (M16) |
| `Gap` | `Gap_Table` | Projection | Principal per bucket for `CONTRACT`, `BASE` and each scenario, per segment, currency and layer, with the conservation check |
| `Measures` | `Measures_Table` | Projection | Weighted average repricing time, effective duration and projected CPR over 12 months and over the projection, per segment, currency, layer and scenario |
| `Log` | `Log_Runs` | Every operation | Run ID, operation, start and finish time, outcome, parameter-set ID, Excel state restored or not, first error |
| `Tests` | `Tests_Cases` | Harness (test build) | Case ID, outcome (`NOT RUN`, `ERROR`, `FAIL`, `PASS`), injected flag, message |

Every result row that depends on parameters carries the parameter-set ID; layers and scenarios are labelled in every row, never mixed in one value.

## Operations

| Entry point | Reads | Writes | Requires |
| --- | --- | --- | --- |
| `WB_Import` | Three user-selected CSV files; `Settings`, `Controls` | `Import`, `Findings`, `Reconciliation`, `Log`; marks every other output `STALE` | `timely_reporting_attested = Y` |
| `WB_Calibrate` | In-memory dataset; `Settings`, `Assumptions` | `Parameters` (append), `Calibration`, `Findings`, `Log` | Current import |
| `WB_Backtest` | In-memory dataset; the parameter sets of `calibration_run_id` | `Backtest`, `Findings`, `Log` | A test window |
| `WB_Project` | In-memory dataset; the parameter sets of `calibration_run_id`; `Settings`, `Assumptions`, `Scenarios` | `CashFlows`, `EVE`, `Gap`, `Measures`, `Findings`, `Log` | Current import |
| `WB_Export` | The parameter sets of `calibration_run_id` or the current results | CSV in a user-selected folder (M10); `Log` | Current results |
| `WB_ClearOutputs` | — | Clears every result area and `Findings`; marks them `STALE`. Keeps `Import`, `Reconciliation`, `Parameters` and `Log` | — |

Names are proposed (W6) and become binding with the facade register (#39). Every entry point saves `Calculation`, `EnableEvents`, `ScreenUpdating` and `DisplayAlerts` and restores them on every exit path, as stage 3 of [Excel evidence](EXCEL_EVIDENCE.md#required-stages) checks.

**In-memory dataset (W7).** The accepted dataset lives in memory for the Excel session only; the workbook keeps its lineage, not its rows. After the workbook is reopened or the VBA project is reset, operations that need the dataset stop and ask for a new import. A re-import of the same files is recognised by the SHA-256 fingerprints in `Import_Lineage`.

## Status and staleness

`Run_Status` and each `<Sheet>_Status` hold one of `CURRENT`, `STALE` or `FAILED`, with the run ID and timestamp.

- A successful import makes `Import`, `Findings` and `Reconciliation` `CURRENT` and every result sheet `STALE`. A rejected import keeps the previously accepted dataset and lineage and marks every result sheet `STALE`, as `DATA-REJECT-01` requires.
- Areas fall into four kinds, each with its own failure rule:
  - **Result areas** (`Calibration`, `Backtest`, `CashFlows`, `EVE`, `Gap`, `Measures`): a successful operation replaces those it owns and marks them `CURRENT`; a failed one clears them and marks them `FAILED`.
  - **Dataset areas** (`Import`, `Reconciliation`): replaced only by a successful import; a failed import or any other failed operation leaves them unchanged.
  - **`Findings`**: rewritten by every operation, successful or not, so the findings that explain a failure are always shown.
  - **Append-only areas** (`Parameters`, `Log`): never cleared, edited or deleted by the toolkit. A failed calibration appends no parameter set; every operation, including a failed one, appends one `Log` row.
- The workbook has no worksheet event handlers (W9). A result therefore records the fingerprint of the settings, assumptions and scenarios it used; every operation compares it with the current inputs and marks the result `STALE` on any difference. An edit made after a run is flagged at the next operation, not when it is typed.

## Build components

Stage 1 of [Excel evidence](EXCEL_EVIDENCE.md#required-stages) requires every component to come from one commit, with none missing or extra and only the default references.

| Component | Production build | Test build |
| --- | :---: | :---: |
| `ThisWorkbook` and one document module per sheet, attributes only, no code | ✅ | ✅ |
| Standard modules from `src/core/` (`CORE_`), `src/modules/` (`PREPAY_`) and `src/workbook/` (`WB_`) | ✅ | ✅ |
| `src/classes/` and `src/forms/`, when introduced | ✅ | ✅ |
| `tests/modules/` (`TEST_`) and the `Tests` sheet | | ✅ |
| `examples/` | | |

The builder (#43) holds the expected component list of each build and fails on any missing or extra component; the export/compare tool checks the same list in stage 6. CodeNames are set by the builder and checked at build time.

## File access

Under W10, the workbook reads exactly three user-selected CSV files, read-only, during `WB_Import`, and writes CSV files only to a user-selected folder during `WB_Export`. It never stores a directory path, opens other workbooks, uses the network or non-default COM references, or changes macro or Trust Center settings. Acceptance of W10 is the agreement that [SECURITY.md](../SECURITY.md) and the [data contract](methodology/DATA_CONTRACT.md#dataset-size) require before file input is implemented.

## Open decisions

| # | Decision | Proposal | Status |
| ---: | --- | --- | --- |
| W1 | Sheet set and order | The 17 sheets above, all visible; `Tests` in the test build only | Proposed (#38) |
| W2 | Defined names | Workbook-scoped, absolute, visible; `cfg_<code>` for settings, `<Sheet>_<Table>` for tables, `<Sheet>_Status`, `Run_*` and `Build_Commit` | Proposed (#38) |
| W3 | Fixed contract values | Code constants recorded in outputs, not editable settings | Proposed (#38) |
| W4 | Findings volume | At most 100,000 listed rows; complete counts per code | Proposed (#38) |
| W5 | Parameter sets in the workbook | Append-only `Parameters` sheet; the toolkit never edits or deletes a set; a result whose set is missing is `STALE` | Proposed (#38) |
| W6 | Entry points | `WB_Import`, `WB_Calibrate`, `WB_Backtest`, `WB_Project`, `WB_Export`, `WB_ClearOutputs`; harness entry point named by #42 | Proposed (#38) |
| W7 | Dataset persistence | In memory for the session only; re-import after reopening, recognised by fingerprint | Proposed (#38) |
| W8 | Test build | A separate build with `tests/modules/` and the `Tests` sheet; production excludes both | Proposed (#38) |
| W9 | Event handlers | None; staleness detected by input fingerprints at the next operation | Proposed (#38) |
| W10 | File access | Three user-selected CSV inputs, read-only; CSV exports to a user-selected folder; nothing else | Proposed (#38) |

## Not covered

The facade signatures (#39), the builder and round-trip tools (#43), fixtures (#41) and the VBA itself (#42) are separate issues. Visual details beyond the layout rules above, chart content and README wording are left to the builder.
