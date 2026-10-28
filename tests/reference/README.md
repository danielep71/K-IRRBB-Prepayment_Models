# Reference tooling

Independent offline references for the [case register](../../docs/methodology/TEST_CASES.md) (decision V4). They use the Python standard library only, run through `python tools/check.py` (`tools/test_reference_cases.py`), and are never a runtime dependency. They are written from the contracts, not from toolkit source, and no expected value is copied from toolkit output.

## `data_reader.py`

Reads the three input files of one import, and optional control totals, and applies the [data contract](../../docs/methodology/DATA_CONTRACT.md): file format, errors `E01`–`E17` in the first-error order, warnings `W01`–`W06`, the data window, RENEG successor reconciliation (D11, D15), reconciliation totals (D12) and control totals (D13), loan-month exposure, the risk-set outcome of each loan-month, the point-in-time view at a forecast origin and SHA-256 fingerprints. Amounts use exact decimal arithmetic in a wide context that traps rounding: an amount is never rounded silently, and an input that would need rounding stops the reader.

### Validation conventions (D16)

These points were reader choices where the contract was silent. The owner decided them on 2026-10-28 as data decision D16; the [data contract](../../docs/methodology/DATA_CONTRACT.md#validation-conventions) now states them, and expected files may assert them.

| # | Point | Convention |
| ---: | --- | --- |
| 1 | Previous row of a loan | The loan's row at the previous month end. After a gap (`W01`) the balance identity, exposure and RENEG flow checks are not applied; a `RENEG` row without a previous-month row fails `E14` |
| 2 | Exposure on a loan's first row | In its origination month, `E15` is checked against `original_balance`, as the balance identity is; any other first row is not checked |
| 3 | Window exclusion | `W04` is decided after the single-row checks and `E11`; excluded rows enter no cross-row rule (`E05`, `E08`, `E10`, `E12`–`E16`) |
| 4 | Duplicates | `E05` counts only rows that passed the earlier rules |
| 5 | Location of `W01` | `loan_panel.csv` line 0, once per missing month, as `E12` (D14) |
| 6 | Decimal sign | An optional leading `-`; `+` is rejected; leading zeros are accepted |
| 7 | Loan-month table | `NONE`, `PARTIAL` and `FULL` outcomes only, as under the default of D4 and D5; `MATURITY` is left out |
| 8 | A failed row as previous row | A row that failed an earlier rule still serves as the previous row of the next month |
| 9 | Order of findings | By file (register, panel, market rates), then line; `E17` follows on `Controls_Totals` (D13) |
| 10 | Self-link | A register row whose `predecessor_id` is its own `loan_id` fails `E16`, because D6 continues a modified loan under a new `loan_id` |
| 11 | Past maturity at the window end | A loan-month starting at or after the maturity month end is `PAST_MATURITY` even when it also starts at the window end; the contract excludes it from the risk set but also lists the window end as censoring, which matters for the censored last balances of the lineage |
| 12 | Control totals input | Read from `controls.csv` in the import folder, standing for the workbook table `Controls_Totals` and numbered like the input files (header line 1). A header that differs is one `E17` at line 1. A key must be a month-end date, a known segment and a three-letter code; counts are unsigned integers below 10^15 (D17), amounts decimals with at most four places. An invalid row still stands for its key, which gets no further finding |
| 13 | Prepayment on a `MATURITY` row | Counted in neither `prepaid_partial` nor `prepaid_full`, since the contract splits prepaid principal into `PARTIAL` and `FULL` only |

The point-in-time view filters register and panel rows, as the contract states. Market rates dated after an origin are a model-level concern, tested by `INC-LAG-01` and `OOS-LEAK-01`.
