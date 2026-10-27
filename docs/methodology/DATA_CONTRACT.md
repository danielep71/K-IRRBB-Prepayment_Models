# Data contract

Status: **accepted by the owner on 2026-10-21 (issue #14)**, with every [decision](#decisions) as proposed; decision D10 was accepted on 2026-10-21 (issue #72). Decision D11 and the [RENEG successors](#reneg-successors) section were **accepted by the owner on 2026-10-26 (issue #49)**. Decisions D12–D15 were **decided by the owner on 2026-10-27 (issue #41)**. Only synthetic data is ever committed or attached; real loan data is loaded locally and never enters Git, issues or pull requests.

This document is authoritative for the input datasets, their fields, units and validation, the classification of loan events, censoring and missing observations, reconciliation and lineage. Model definitions are in the [model contracts](MODEL_CONTRACTS.md); units follow [repository structure](../REPOSITORY_STRUCTURE.md).

## Datasets

| Dataset | File | Granularity | Used by |
| --- | --- | --- | --- |
| **Loan register** | `loans.csv` | One row per loan | Segmentation, schedule terms, penalties |
| **Loan panel** | `loan_panel.csv` | One row per loan per month end while it is outstanding, plus the month end of its terminal event | Prepayment rates, calibration, backtesting, reconciliation |
| **Market rates** | `market_rates.csv` | One row per rate series per month end | Refinancing rate, rate incentive, scenarios |

SMM, CPR, incentives, ages and segment aggregates are **derived** by the toolkit, never supplied.

The granularity is loan level. Segment-level input (pre-aggregated balances and prepayments) is not accepted in this version, because aggregates cannot be checked against the balance identity or re-segmented; see decision D1.

## File format

All three files use the same plain, locale-independent CSV subset:

- ASCII text; LF or CRLF line endings; no byte-order mark;
- comma separator, no quoting, no embedded commas or line breaks;
- the first line is the exact header given below, fields in the listed order;
- dates as `YYYY-MM-DD`, year 1900 to 9999;
- decimals with `.`, no thousands separator or exponent, at least one digit on each side of the `.`;
- an empty field means *missing*. No sentinel values (`0`, `-999`, `N/A`).

Parsing never uses Excel's locale-dependent conversions, so the same file gives the same result on every host.

## Loan register

Header:
`loan_id,segment,currency,origination_date,maturity_date,original_balance,rate_type,fixed_until,reset_months,amortisation,payment_months,penalty_type,penalty_value,predecessor_id`

| Field | Type and format | Unit | Required | Rules |
| --- | --- | --- | :---: | --- |
| `loan_id` | 1–32 characters `A–Z a–z 0–9 _ -` | — | ✅ | Opaque pseudonymous key; never a real contract or customer number |
| `segment` | Code | — | ✅ | One of the [segment codes](#segmentation) |
| `currency` | ISO 4217, 3 upper-case letters | — | ✅ | In the run's currency allowlist |
| `origination_date` | ISO date | — | ✅ | |
| `maturity_date` | ISO date | — | ✅ | After `origination_date` |
| `original_balance` | Decimal, up to 4 places | Currency units | ✅ | > 0 |
| `rate_type` | `FIXED`, `RESET` or `FLOAT` | — | ✅ | `FIXED`: fixed to maturity. `RESET`: fixed until `fixed_until`, then resets every `reset_months`. `FLOAT`: resets every `reset_months` |
| `fixed_until` | ISO date | — | `RESET` only | After `origination_date`, before `maturity_date`; empty otherwise |
| `reset_months` | Positive integer | Months | `RESET`, `FLOAT` | Empty for `FIXED` |
| `amortisation` | `ANNUITY`, `LINEAR` or `BULLET` | — | ✅ | |
| `payment_months` | `1`, `3`, `6` or `12` | Months | ✅ | Scheduled payment frequency |
| `penalty_type` | `NONE`, `PCT` or `MONTHS_INTEREST` | — | ✅ | Contractual early-repayment charge |
| `penalty_value` | Decimal, up to 8 places | Decimal share (`PCT`) or months (`MONTHS_INTEREST`) | Unless `NONE` | ≥ 0; empty for `NONE` |
| `predecessor_id` | As `loan_id` | — | — | The loan this one replaced after a [modification](#loan-events); must exist in the register and, under decision D11, must have ended with `RENEG` in this loan's origination month ([RENEG successors](#reneg-successors)) |

The key is `loan_id`. Register fields are the terms at origination of that `loan_id`. A change of rate, maturity, amortisation or penalty terms is a modification and creates a new `loan_id` (decision D6); the register is never edited in place to reflect it.

## Loan panel

Header:
`as_of_date,loan_id,balance,client_rate,scheduled_principal,prepaid_principal,other_change,event`

| Field | Type and format | Unit | Required | Rules |
| --- | --- | --- | :---: | --- |
| `as_of_date` | ISO date | — | ✅ | Calendar month end |
| `loan_id` | As in the register | — | ✅ | Must exist in the register |
| `balance` | Decimal, up to 4 places | Currency units | ✅ | Outstanding principal at month end after all payments in the month, ≥ 0 |
| `client_rate` | Decimal, up to 8 places | Decimal per annum | ✅ | Contractual rate in force at month end; −0.05 to 0.50 |
| `scheduled_principal` | Decimal, up to 4 places | Currency units | ✅ | Scheduled (contractual) principal **received** in the month, ≥ 0 |
| `prepaid_principal` | Decimal, up to 4 places | Currency units | ✅ | Principal received in the month **in excess of** the schedule, ≥ 0 |
| `other_change` | Decimal, up to 4 places | Currency units | ✅ | Signed principal change not from repayment: further drawdowns, capitalised interest or fees; on a `RENEG` row, minus the principal transferred to the successor. `0` when none |
| `event` | Code | — | ✅ | One of the [event codes](#loan-events) |

The key is (`as_of_date`, `loan_id`). The currency of every amount is the loan's register currency.

**Balance identity.** For consecutive rows of a loan at month ends `t-1` and `t`:

```text
balance(t) = balance(t-1) - scheduled_principal(t) - prepaid_principal(t) + other_change(t)
```

within 0.005 currency units; a break is `E13`. For a loan's first row the identity uses `original_balance` when the first row is the origination month, and is not checked otherwise.

Scheduled and prepaid principal are **supplied** by the source system, not derived by the toolkit from the contractual schedule (decision D3). A shortfall against the schedule (arrears) reduces `scheduled_principal` and is never recorded as negative prepayment.

## Loan events

Each panel row carries exactly one event, the one that describes the loan's month. Classification is supplied, not inferred; the import checks it against the flows (`E14`).

| Event | Meaning | Required flows | Terminal |
| --- | --- | --- | :---: |
| `NONE` | Scheduled activity only | `prepaid_principal = 0`; `balance > 0` | |
| `PARTIAL` | Partial prepayment (curtailment) | `prepaid_principal > 0`; `balance > 0` | |
| `FULL` | Full prepayment before the maturity month, including external refinancing | `prepaid_principal > 0`; `balance = 0`; `as_of_date` before the month end of `maturity_date` | ✅ |
| `MATURITY` | Final scheduled repayment | `balance = 0`; `as_of_date` is the month end of `maturity_date` | ✅ |
| `DEFAULT` | Loan enters default | `prepaid_principal = 0`; `balance` is the defaulted principal | ✅ |
| `RENEG` | Modified or internally refinanced; replaced by a loan whose `predecessor_id` is this one | `prepaid_principal = 0`; `balance = 0`; `scheduled_principal(t) <= balance(t-1)`; `other_change = -(balance(t-1) - scheduled_principal(t)) <= 0`, so the transferred principal is nonnegative; reconciled with its successor under decision D11 ([RENEG successors](#reneg-successors)) | ✅ |
| `SALE` | Sold or transferred out of the portfolio | `prepaid_principal = 0`; `balance` is the transferred principal | ✅ |

- No row is dated after a terminal event (`E10`).
- A partial prepayment followed by full repayment in the same month is one `FULL` row; `prepaid_principal` holds both.
- Prepayment in the maturity month is not distinguished from maturity; the row is `MATURITY`.
- External refinancing cannot be told apart from other full prepayments and is recorded as `FULL`. Internal refinancing is `RENEG`; whether `RENEG` counts as prepayment is decision D4.
- Defaults, recoveries and write-offs are never prepayments. Sales are never prepayments.

## RENEG successors

Status: **accepted by the owner on 2026-10-26 (issue #49)** (decision D11, amending D4 and D6). Nothing here is implemented or validated.

A `RENEG` row ends a loan and transfers its remaining principal, `T = -other_change(t)`, to exactly one successor: the register row whose `predecessor_id` is the renegotiated loan (decision D6). The import reconciles the two, so a source cannot transfer one amount and open the successor with another.

| Rule | Check |
| --- | --- |
| One successor | Every `RENEG` row inside the data window that transfers `T > 0.005` has exactly one register row with `predecessor_id` equal to its `loan_id`. None, or more than one, is `E16` |
| Zero residual | A `RENEG` row with `T <= 0.005` (scheduled principal equal to the opening balance, within the tolerance of D9) needs no successor; a register row naming it as predecessor is `E16` on that register row (decision D15) |
| Same month | The month end of the successor's `origination_date` equals the `as_of_date` of the `RENEG` row |
| Same currency | The successor's `currency` equals the predecessor's; amounts are never converted |
| Amount | `abs(original_balance(successor) - T) <= 0.005` currency units (decision D9) |
| Reverse link | A register row with a `predecessor_id` needs that predecessor to end with a `RENEG` row in the successor's origination month, only when that month is inside the data window; a successor originated before or after the window is not checked |
| Segment | The successor may be in another segment; the change is reported as `W06`, never re-assigned |

- A failure of any rule is `E16`, reported on the `RENEG` panel row, or on the successor's register row for a broken reverse link.
- A `RENEG` row outside the data window (`W04`) is not reconciled, because its flows are not imported; for the same reason, a successor originated outside the window is not reverse-linked.
- A successor in its origination month needs no panel row to reconcile; once it has a first panel row in its origination month, that row checks the balance identity against `original_balance`, as for any loan.
- A split into several successors or a merge of several predecessors cannot be represented with one `predecessor_id` and is rejected (`E16`). Supporting either needs a new decision.

## Market rates

Header: `as_of_date,rate_id,currency,tenor_months,rate`

| Field | Type and format | Unit | Required | Rules |
| --- | --- | --- | :---: | --- |
| `as_of_date` | ISO date | — | ✅ | Calendar month end |
| `rate_id` | 1–32 characters `A–Z a–z 0–9 _ -` | — | ✅ | Series identifier, e.g. `EUR_SWAP_60M` |
| `currency` | ISO 4217 code | — | ✅ | Constant for a series |
| `tenor_months` | Positive integer | Months | ✅ | Constant for a series |
| `rate` | Decimal, up to 8 places | Decimal per annum | ✅ | −0.05 to 0.25 |

The key is (`as_of_date`, `rate_id`). Which series form the refinancing curve, and their compounding convention, are run settings recorded in the parameter set ([model contracts](MODEL_CONTRACTS.md#rate-incentive)).

## Tier 1 capital

Status: **accepted by the owner on 2026-10-21 (issue #72, decision D10).**

Tier 1 capital is a run setting, not a dataset. The user enters one amount and one currency for the run; the toolkit never derives it. It is used only for the ΔEVE / Tier 1 ratio of the [model contracts](MODEL_CONTRACTS.md#eve-sensitivity-and-repricing-gap) and is recorded with every scenario result that uses it.

| Setting | Type and format | Unit | Rules |
| --- | --- | --- | --- |
| `tier1_amount` | Decimal, up to 4 places | Currency units | > 0 |
| `tier1_currency` | ISO 4217, 3 upper-case letters | — | In the run's currency allowlist |

A missing or invalid Tier 1 setting when the ratio is requested stops the run before any calculation, with no partial output. It is not an import error and leaves the accepted datasets unchanged.

## Segmentation

Segment codes (decision D2):

| Code | Segment |
| --- | --- |
| `MTG_FIX` | Residential mortgages, fixed to maturity |
| `MTG_RST` | Residential mortgages, initial fixed period then reset |
| `MTG_FLT` | Residential mortgages, floating |
| `CON_FIX` | Consumer instalment loans, fixed |
| `SME_FIX` | Small-business loans, fixed |

Segment is supplied per loan and never inferred or re-assigned by the toolkit. Because a modification creates a new `loan_id`, a loan's segment never changes over its life. Adding a segment needs an issue and a change to this table.

## Validation and invalid input

**The import is all-or-nothing.** Any error rejects all three datasets together: no partial dataset is kept, and earlier results stay marked stale. Warnings do not stop the import; they are reported and recorded in the lineage. Each row reports its **first** failing rule, in the order below, so the same files always give the same findings in the same order.

| Code | Error | Checked on |
| --- | --- | --- |
| `E01` | Header or field count does not match, or a non-ASCII character | File, then each row |
| `E03` | A required field is empty, or a field that must be empty is not | Each row |
| `E02` | Invalid ISO date, or `as_of_date` not a month end | Each row |
| `E04` | Value cannot be parsed or is out of range | Each row |
| `E06` | Unknown code (segment, rate type, amortisation, payment frequency, penalty type, event) | Each row |
| `E07` | Currency not in the run allowlist | Each row |
| `E09` | Negative balance, scheduled or prepaid principal | Each row |
| `E11` | Inconsistent dates: maturity not after origination, `fixed_until` outside the loan's life, `as_of_date` before the origination month end | Each row |
| `E05` | Duplicate key | Second and later occurrences |
| `E08` | `loan_id` or `predecessor_id` not in the register; market series currency or tenor differs from its earlier rows | Each row |
| `E14` | Event inconsistent with its required flows or dates | Each row |
| `E10` | Row dated after the loan's terminal event | Each row |
| `E13` | Balance identity broken | The later row |
| `E15` | **Prepayment above exposure**: `prepaid_principal` exceeds `balance(t-1) - scheduled_principal(t) + max(other_change(t), 0)` by any positive amount; compare at the input's exact decimal precision, without tolerance or clamping | The later row |
| `E16` | **RENEG successor mismatch** (D11, D15): no successor or more than one where one is required, a successor for a `RENEG` row that transfers at most 0.005, successor in another month or currency, transferred principal and successor `original_balance` differing by more than 0.005, or a successor whose predecessor did not end with `RENEG` in its origination month | The `RENEG` row, or the successor's register row |
| `E12` | **Missing extract**: a month end in the data window has no panel rows | Once per missing month end, at `loan_panel.csv` line 0 with the month end as key (D14) |
| `E17` | **Control-total mismatch** (D13): against the user's [control totals](#reconciliation), a count differs, an amount differs by more than 0.005, a (`as_of_date`, `segment`, `currency`) is in only one of the computed and control totals, or a control row is empty, duplicated or does not parse | Once per key and measure (once per row for an invalid control row), at its `Controls_Totals` row, or line 0 when the key has no control row; after the findings of the three files, and only when they have no other error |

| Code | Warning | Reported at |
| --- | --- | --- |
| `W01` | **Gap**: loan missing in a month between its first and last row | The missing month |
| `W02` | **Censored disappearance**: loan stops before the window end without a terminal event | Its last row |
| `W03` | Non-zero `other_change` | The row |
| `W04` | Row outside the data window; excluded and counted | The row |
| `W05` | **Past maturity**: positive balance after the month end of `maturity_date` | The row |
| `W06` | **Segment change at RENEG** (D11): the successor is in another segment than its predecessor | The successor's register row |

## Risk set, missing observations and censoring

A **loan-month** runs from month end `t-1` to `t`. It is in the prepayment risk set when the loan has a row at `t-1` with `balance > 0`, `t-1` is before the month end of `maturity_date`, and the loan's next row is at `t`. Its outcome is the event of the row at `t`.

| Situation | Treatment |
| --- | --- |
| Row at `t` exists | Observed: contributes to the numerator and denominator of [SMM](MODEL_CONTRACTS.md#cpr-and-smm) according to its event |
| No row at `t`, a later row exists (`W01`) | Excluded; the gap is never filled or interpolated |
| No row at `t`, no later row, no terminal event (`W02`) | Right-censored after `t-1`; never counted as prepayment |
| `t-1` is the last month end of the window | Right-censored |
| Loan past maturity (`W05`) | Months after maturity are excluded from the risk set |
| First row of a loan | Opens the loan; no loan-month ends there |
| Missing extract (`E12`) | Import rejected; never treated as mass prepayment or censoring |

`DEFAULT`, `SALE` and `RENEG` outcomes are treated as decided in D4 and D5.

## Point-in-time availability

Every run declares a data window (first and last month end). The **point-in-time view at forecast origin `t`** contains only register rows of loans originated on or before `t` and panel rows with `as_of_date <= t`. Register terms are known at origination; panel flows and events are known at the month end of the month in which they occur. Predictors at `t` use only the point-in-time view; outcomes after `t` never enter a predictor at `t`.

The contract assumes events are reported by the month end in which they occur. A source that back-fills events or corrects flows in later extracts must not be loaded as-is; the user attests timely reporting for each import, and the attestation is part of the [lineage](#lineage). Corrections are a new import, never an edit.

## Reconciliation

After import, the toolkit reports for every (`as_of_date`, `segment`, `currency`): number of loans, total balance, total scheduled principal, total prepaid principal split into `PARTIAL` and `FULL`, total `other_change`, and the count and the reported `balance` of the rows of each terminal event: 0 for `FULL`, `MATURITY` and `RENEG`, the defaulted or transferred principal for `DEFAULT` and `SALE` (decision D12). Totals cover the accepted rows inside the data window. It checks that:

- segment totals add up to the panel total for each date and currency;
- if the user supplies control totals (workbook table `Controls_Totals`: `as_of_date`, `segment`, `currency`, then `loans`, `balance`, `scheduled_principal`, `prepaid_partial`, `prepaid_full`, `other_change` and `<event>_count`, `<event>_balance` for `full`, `maturity`, `default`, `reneg` and `sale`), counts match exactly and amounts within 0.005 currency units, for every key on either side; every failure is `E17` (decision D13).

Amounts in different currencies are never added together. Totals keep input precision; rounding is for presentation only. A reconciliation difference fails the import (`E17`).

## Dataset size

A worksheet holds at most 1,048,576 rows; 50,000 loans over 120 months already exceed it. The input route (decision D1) streams the CSV files with VBA file input into in-memory arrays and aggregates, keeping only summaries, parameters and results on worksheets. Reading a user-selected file is a file-system access that [SECURITY.md](../../SECURITY.md) requires to be agreed in an issue before implementation. Nothing about performance is claimed here.

## Lineage

Every successful import records, in the workbook and in each parameter set built from it:

| Item | Content |
| --- | --- |
| Source | File name without directory, size in bytes and SHA-256 of each file |
| Counts | Rows read, accepted and excluded by window; loans; warnings by code |
| Outcomes | Per month end, segment and currency: loan-months by outcome and event, censored last balances |
| Settings | Data window, segment list, currency allowlist, refinancing-curve series |
| Attestation | Events and flows reported by the month end in which they occur |
| Code | Toolkit commit SHA |
| Time | Import timestamp |

The same files, settings and commit give the same dataset, findings in the same order and the same fingerprints on any supported host.

## Synthetic fixtures

None yet. Before an importer is implemented, hand-constructed fixtures must cover every event, error and warning code above, with hand-computed expected totals and outcomes and an independent reference reader. The cases are registered in [TEST_CASES.md](TEST_CASES.md).

## Decisions

| # | Decision | Outcome | Status |
| ---: | --- | --- | --- |
| D1 | Input granularity and route | Loan-level CSV files streamed by VBA file input; no segment-level input | Accepted 2026-10-21 |
| D2 | Segment list | `MTG_FIX`, `MTG_RST`, `MTG_FLT`, `CON_FIX`, `SME_FIX` | Accepted 2026-10-21 |
| D3 | Scheduled vs prepaid principal | Supplied by the source and checked by the balance identity; no toolkit derivation from the contractual schedule | Accepted 2026-10-21 |
| D4 | Internal refinancing (`RENEG`) | Excluded from the SMM numerator and denominator by default, reported separately; inclusion is a run setting recorded in the parameter set. When included, the transferred principal `-other_change` is the numerator | Accepted 2026-10-21; amended 2026-10-21 after review of #24; amended 2026-10-26 by D11 (#49) |
| D5 | Default and sale in the SMM denominator | Excluded from numerator and denominator in their exit month (competing exits) | Accepted 2026-10-21 |
| D6 | Contract modifications | End the loan with `RENEG` and continue under a new `loan_id` with `predecessor_id` | Accepted 2026-10-21; amended 2026-10-26 by D11 (#49) |
| D7 | Drawdowns and capitalisation | Allowed through `other_change` with warning `W03`; not part of prepayment. A positive `other_change` counts as exposure in the month, and prepayment above that exposure is rejected (`E15`) | Accepted 2026-10-21; amended 2026-10-21 after review of #24 |
| D8 | Import timestamp time zone | Host local time without offset, as decided in K-IRRBB-NMDs | Accepted 2026-10-21 |
| D9 | Tolerances | 0.005 currency units for the balance identity and control totals | Accepted 2026-10-21 |
| D10 | Tier 1 capital | A run setting (amount and currency) entered by the user, validated before any calculation and recorded with each result; never a dataset or derived | Accepted 2026-10-21 (#72) |
| D11 | RENEG successor reconciliation | Exactly one successor per `RENEG` row, in the same month and currency, with `original_balance` within 0.005 of the transferred principal; reverse link checked for successors originated inside the data window; segment change allowed with `W06`; splits and merges rejected; failures are `E16`, ordered after `E15` | Accepted 2026-10-26 (#49); amends D4 and D6; amended 2026-10-27 by D15 (#41) |
| D12 | Terminal-event balance in reconciliation | The reported `balance` of each terminal row (0 for `FULL`, `MATURITY` and `RENEG`) | Decided 2026-10-27 (#41) |
| D13 | Control-total mismatch | Error `E17`, once per key and measure (once per row for an invalid control row) at the `Controls_Totals` row (line 0 for a missing control row); a key on only one side, or an empty, duplicated or unparseable control row, is a mismatch; ordered after the three files and checked only when they have no other error | Decided 2026-10-27 (#41) |
| D14 | Location of `E12` | `loan_panel.csv`, line 0, once per missing month end, with the month end as key | Decided 2026-10-27 (#41) |
| D15 | Zero-residual `RENEG` | A `RENEG` row transferring `T <= 0.005` needs no successor; a successor naming it is `E16` | Decided 2026-10-27 (#41); amends D11 |
