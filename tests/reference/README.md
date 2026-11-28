# Reference tooling

Independent offline references for the [case register](../../docs/methodology/TEST_CASES.md) (decision V4). They use the Python standard library only, run through `python tools/check.py` (`tools/test_reference_cases.py`), and are never a runtime dependency. They are written from the contracts, not from toolkit source, and no expected value is copied from toolkit output.

## `data_reader.py`

Reads the three input files of one import, and optional control totals, and applies the [data contract](../../docs/methodology/DATA_CONTRACT.md): file format, errors `E01`–`E17` in the first-error order, warnings `W01`–`W06`, the data window, RENEG successor reconciliation (D11, D15), reconciliation totals (D12) and control totals (D13) with every measure compared, loan-month exposure, the risk-set outcome of each loan-month, the lineage counts of each file and the outcome summary of an accepted import (W12), the point-in-time view at a forecast origin and SHA-256 fingerprints. Amounts use exact decimal arithmetic in a wide context that traps rounding: an amount is never rounded silently, and an input that would need rounding stops the reader.

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

## `rates.py`

Applies the [CPR and SMM conventions](../../docs/methodology/MODEL_CONTRACTS.md#cpr-and-smm) of the model contracts: `SMM -> CPR` and `CPR -> SMM` in binary floating point through `log1p` and `expm1`, rates outside [0, 1] refused; the pool SMM of each segment, currency and month end as `sum P / sum A`, split into `PARTIAL`, `FULL` and, when the run setting includes it, `RENEG` (`P = -other_change`); `DEFAULT`, `SALE` and `MATURITY` in neither sum and `A <= 0` excluded (D4, D5); the realised CPR over `n` months, `1 - (prod (1 - SMM))^(12/n)`. Its input is a table of risk-set loan-months (`loan_months.csv`: opening balance, flows and event of each); the import rules that produce them are covered by `DATA-*` and `data_reader.py`.

## `derive_rates.py`

Derives the decimal expected values of `RATE-CONV-01`, `RATE-CONV-02` and `RATE-PERIOD-01` without `rates.py`: exactly in rationals, and the twelfth root in decimal at 60 digits, each rounded to 40 significant digits. `tools/test_reference_cases.py` checks that the committed expected files still equal this derivation. The amounts and SMM fractions of `RATE-POOL-01` and `RATE-POOL-02` are hand computations written into their expected files.

## `incentive.py`

Applies the [rate incentive](../../docs/methodology/MODEL_CONTRACTS.md#rate-incentive) of the model contracts: `I = client_rate(t-1) - (R(t-L, T) + m) - penalty`, with the lag `L = 1` of decision M4 read as the month end `L` months before `t`, the segment margin `m` of M5, and the penalty `PCT` `value / max(T, 1)`, `MONTHS_INTEREST` `value x client_rate / 12 / max(T, 1)`, `NONE` 0. `R(s, T)` comes from the configured refinancing series of the loan's currency at month end `s`, at `tenor_months / 12` years, interpolated linearly in rate and held flat outside the nodes, looking only at rows dated at or before `s`. It also gives the end of the fixed term at `t-1`: `maturity_date` for `FIXED`, `fixed_until` for `RESET` in its fixed period, none for `FLOAT` or a `RESET` loan past it. Rates use binary floating point. Its inputs are loan-months with `T` already in years (`loan_months.csv`) and market rates in the data-contract format. What the contract does not state is left open, and refused where the module would otherwise have to guess: the year fraction from dates to `T`, the compounding of `R` (M3), a `RESET` loan with `t-1` exactly at `fixed_until`, and a configured series missing at `s` or two series sharing one tenor. `INC-CALC-01` therefore pins `I` only where every configured rate at `t-L` is 0, and `INC-LAG-01` is a property that holds for any convention.

## `overlay.py`

Applies two rules of the [regulatory overlay](../../docs/methodology/MODEL_CONTRACTS.md#regulatory-overlay). The post-shock floor `max(shocked, min(observed, min(0, -150bp + 3bp x m)))` at a given maturity `m` years is a lower bound that never replaces a shocked rate above it. The standardised multipliers give `min(1, gamma_s x CPR_BASE)`, with `gamma_s` 0.8 for `PAR_UP`, `STEEPENER` and `SHORT_UP` and 1.2 for `PAR_DOWN`, `FLATTENER` and `SHORT_DOWN`; `BASE` keeps `CPR_BASE` (M15). A CPR outside [0, 1] and any other scenario are refused. Where the floor is applied on a curve (series tenors or the interpolated rate) is not part of it.

## `derive_inc_scn.py`

Derives the expected values of `INC-CALC-01`, `INC-CURVE-01`, `SCN-FLOOR-01` and `SCN-GAMMA-01` exactly in rationals. It reads the fixtures with the csv module and does not use `incentive.py` or `overlay.py`; it finds curve nodes by bracketing `T x 12` months rather than by walking sorted segments. `INC-CALC-01` is derived only where every configured series is 0 at the rate date, which the script checks. `tools/test_reference_inc_scn.py` checks that the committed expected files still equal this derivation. The term ends of `INC-CALC-01` and the rate dates and perturbation settings of `INC-LAG-01` are hand assignments written into their expected files.
