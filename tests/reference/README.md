# Reference tooling

Independent offline references for the [case register](../../docs/methodology/TEST_CASES.md) (decision V4). They use the Python standard library only, run through `python tools/check.py` (`tools/test_reference_cases.py`), and are never a runtime dependency. They are written from the contracts, not from toolkit source, and no expected value is copied from toolkit output.

## `data_reader.py`

Reads the three input files of one import and applies the [data contract](../../docs/methodology/DATA_CONTRACT.md): file format, errors `E01`–`E16` in the first-error order, warnings `W01`–`W06`, the data window, RENEG successor reconciliation (D11), loan-month exposure and SHA-256 fingerprints. Amounts use exact decimal arithmetic.

### Choices where the contract is silent

The reader needs a behaviour for the points below. The contract does not settle them, so **no expected file asserts them**; a case that depends on one needs an owner decision first.

| # | Point | Choice in the reader |
| ---: | --- | --- |
| 1 | Previous row of a loan | The loan's row at the previous month end. After a gap (`W01`) the balance identity, exposure and RENEG flow checks are not applied; a `RENEG` row without a previous-month row fails `E14` |
| 2 | Exposure on a loan's first row | `E15` is not checked on a loan's first row, also in its origination month, because no loan-month ends there |
| 3 | Window exclusion | `W04` is decided after the single-row checks and `E11`; excluded rows enter no cross-row rule (`E05`, `E08`, `E10`, `E12`–`E16`) |
| 4 | Duplicates | `E05` counts only rows that passed the earlier rules |
| 5 | Location of `W01` and `E12` | `W01` at the line of the row after the gap, once per missing month; `E12` at line 0 |
| 6 | Decimal sign | An optional leading `-`; `+` is rejected; leading zeros are accepted |
| 7 | Loan-month table | `NONE`, `PARTIAL` and `FULL` outcomes only, as under the default of D4 and D5; `MATURITY` is left out |
| 8 | A failed row as previous row | A row that failed an earlier rule still serves as the previous row of the next month |
| 9 | Order of findings | By file (register, panel, market rates), then line |

Open question for `DATA-EVENT-01`: a `RENEG` row with zero residual transfers `T = 0`, while D11 needs exactly one successor with `abs(original_balance - T) <= 0.005` and `original_balance > 0`. Only successors with an original balance of at most 0.005 reconcile. The case is not built until this is decided.
