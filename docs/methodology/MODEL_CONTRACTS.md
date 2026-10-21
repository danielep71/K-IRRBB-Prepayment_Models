# Model contracts

Status: **accepted by the owner on 2026-10-21 (issue #14)**, with every [decision](#decisions) as proposed. Regulatory figures name their source in the [source register](SOURCES.md); every figure resting on an unverified source is provisional and may not be implemented as a rule until the source is verified. The [EVE sensitivity and repricing gap](#eve-sensitivity-and-repricing-gap) section and decisions M12–M18 are **proposed in issue #72 and not accepted**.

This document is authoritative for the prepayment-rate conventions, the candidate models, the rate incentive, estimation and failure handling, projected behavioural cash flows, EVE sensitivity and the repricing gap, scenario and parameter outputs, and the separation of statistical estimates, behavioural assumptions and regulatory overlays. Inputs come from the [data contract](DATA_CONTRACT.md). Validation thresholds and evidence are in the [validation plan](VALIDATION_PLAN.md).

Notation: `t` is a month end; loan-month `(i, t)` runs from `t-1` to `t`; amounts are in currency units; rates are decimals per annum unless marked monthly; `T` is a remaining term in years.

## Common rules

- Every model runs per **segment × currency**. Loans in different currencies are never pooled.
- A run declares an **estimation window** and an optional **test window**, both inside the data window. The test window must be disjoint from and strictly after the estimation window: `test_start > estimation_end`. Overlapping, equal or earlier test windows are rejected before estimation or scoring. Parameters are estimated once on the estimation window and then **frozen**; nothing is re-estimated in the test window. A recalibration is a separate run that creates a new parameter set.
- Each month end in the test window is a forecast origin. A forecast from origin `t` uses only the [point-in-time view](DATA_CONTRACT.md#point-in-time-availability) at `t`.
- A segment and currency below the minimum sample is not estimated; the run reports it and produces no parameters for it. Minimum (decision M9): 36 consecutive month ends and 5,000 risk-set loan-months, with at least 100 `FULL` events.

## CPR and SMM

For a loan-month in the [risk set](DATA_CONTRACT.md#risk-set-missing-observations-and-censoring):

```text
A(i,t) = balance(i,t-1) - scheduled_principal(i,t) + max(other_change(i,t), 0)   amount available to prepay
P(i,t) = prepaid_principal(i,t)                                                    PARTIAL or FULL prepayment
```

A loan-month with `A <= 0` (for example the final scheduled payment) is excluded. A positive `other_change` (a drawdown or capitalisation in the month) counts as exposure, because it can be prepaid in the same month; the import rejects `P > A` (`E15`), so `0 <= SMM <= 1`. A negative `other_change` does not reduce `A`.

When `RENEG` inclusion is selected (data decision D4), a `RENEG` row contributes `P = -other_change`, the principal transferred to its successor, and is reported as `SMM_reneg`; otherwise it enters neither sum.

**Pool SMM** for a segment, currency and month is balance-weighted, never an average of loan rates:

```text
SMM(t) = sum_i P(i,t) / sum_i A(i,t)
SMM_partial(t) = sum over PARTIAL rows of P / sum_i A(i,t)
SMM_full(t)    = sum over FULL rows of P    / sum_i A(i,t)
```

so `SMM = SMM_partial + SMM_full`, plus `SMM_reneg` when `RENEG` is included. `DEFAULT`, `SALE` and `RENEG` loan-months enter the sums as set by data decisions D4 and D5.

**CPR** is the annualised equivalent of a constant monthly rate:

```text
CPR = 1 - (1 - SMM)^12
SMM = 1 - (1 - CPR)^(1/12)
```

`CPR / 12` is never used as a monthly rate. A realised CPR over a period of `n` months compounds the monthly rates: `1 - (prod_t (1 - SMM(t)))^(12/n)`. Averages of CPR values are not reported as realised rates.

Worked check: `balance(t-1) = 100,000`, `scheduled_principal = 1,000`, `prepaid_principal = 2,000` give `A = 99,000`, `SMM = 0.02020202` and `CPR = 0.21722224`; the wrong shortcut `CPR / 12 = 0.01810185` understates the monthly rate.

A count-based full-prepayment rate (number of `FULL` events over risk-set loans) is reported as a diagnostic only.

## Rate incentive

For a fixed-rate loan-month the refinancing incentive is:

```text
I(i,t) = client_rate(i,t-1) - [ R(t-L, T(i,t)) + m ] - penalty(i,t)
```

| Term | Definition | Layer |
| --- | --- | --- |
| `T(i,t)` | Remaining fixed term in years at `t-1`: to `maturity_date` for `FIXED`, to `fixed_until` for `RESET` | Data |
| `R(s, T)` | Market rate for term `T` at month end `s`, interpolated linearly in rate between the configured series and held flat outside them | Data |
| `L` | Incentive lag in months, for application and completion time (decision M4) | Behavioural assumption |
| `m` | New-business margin over the market rate (decision M5) | Behavioural assumption or estimate |
| `penalty` | `PCT`: `penalty_value / max(T, 1)`. `MONTHS_INTEREST`: `penalty_value x client_rate / 12 / max(T, 1)`. `NONE`: 0 | Data, with the annualisation an assumption |

Whether `R` is a par (swap) rate or a zero rate, and its compounding, is decision M3; the prototype uses a zero rate. `FLOAT` loans and `RESET` loans past `fixed_until` have no refinancing incentive in this version.

Other drivers, all computed from the point-in-time view:

| Driver | Definition |
| --- | --- |
| Age | Whole months from the origination month end to `t-1` |
| Calendar month | Month of `t` |
| Burnout | Pool factor of the loan's origination cohort within the segment: cumulative `prod (1 - SMM)` since origination, as a proxy for past exposure to incentive |

## Candidate models

| ID | Model | Applies to | Role |
| --- | --- | --- | --- |
| `PM0` | Constant CPR per segment and currency, the realised CPR of the estimation window | All segments | Benchmark; always produced |
| `PM1` | Rate-incentive S-curve with seasoning, seasonality and burnout | Fixed-rate segments and `RESET` loans in their fixed period | First implementation candidate |
| `PM2` | Loan-level logistic hazard for full prepayment, with a separate partial-prepayment rate | Fixed-rate segments | Future candidate; out of scope for the first implementation |

Floating-rate loans and `RESET` loans after their fixed period use `PM0`, with the seasoning and seasonality factors of `PM1` if those are adopted for the segment.

### PM1 specification

```text
CPR(i,t) = min(1, max(0, [c_min + (c_max - c_min) x B x logistic(k x (I - x0))] x Ramp(age) x Season(month)))
logistic(z) = 1 / (1 + exp(-z))
Ramp(age) = min(1, age / a_ramp); 1 when a_ramp = 0
B = exp(-b x (1 - pool factor))
Season(month): 12 factors with mean 1
```

| Parameter | Meaning | Layer (decision M7) |
| --- | --- | --- |
| `c_min`, `c_max` | CPR at strongly negative and strongly positive incentive | Estimated; `0 <= c_min <= c_max <= 1` |
| `k` | Steepness of the S-curve | Estimated; `k > 0` |
| `x0` | Incentive at the midpoint | Estimated |
| `a_ramp` | Seasoning months to full speed | Behavioural assumption unless estimated with diagnostics |
| `Season` | Calendar-month factors | Estimated from the residuals, or assumption |
| `b` | Burnout strength | Behavioural assumption unless the data identify it |

Whether `PM1` fits total SMM or separate curves for partial and full prepayment is decision M2.

### Estimation, convergence and failure

- **Sample:** risk-set loan-months of the estimation window, grouped into incentive buckets of 25 basis points (decision M8). Bucket SMM is the pool SMM of the bucket.
- **Objective:** weighted least squares on monthly SMM, weights `sum A` of each bucket and month; the model's CPR is converted to SMM before comparison. Fitting CPR directly is not allowed.
- **Predicted bucket value** (decision M11): for each bucket and month, `sum_i A(i,t) x SMM_model(i,t) / sum_i A(i,t)` over its loan-months, each loan evaluated at its own incentive, age, calendar month and burnout. The curve is never evaluated at the bucket midpoint.
- **Constraints** are enforced by parametrisation: `c_min = logistic(p1)`, `c_max = c_min + (1 - c_min) x logistic(p2)`, `k = exp(p3)`, `x0 = p4`.
- **Optimiser:** Nelder–Mead with recorded start values, initial step, tolerance, iteration limit and number of restarts. Settings are deterministic; the same data and settings give the same parameters.
- **Failure:** non-convergence, a parameter at a numerical boundary, or a non-finite objective means the model is **not estimated** for that segment and currency. The run reports why. A failed fit is never replaced by default values without a recorded behavioural assumption.

### Diagnostics reported

Observed vs fitted SMM and CPR by incentive bucket; weighted R²; residuals by age, calendar month and origination cohort; the `PM0` comparison; optimiser status, iterations and objective; and, for the test window, bias and mean absolute error of monthly SMM and the cumulative prepaid amount, per horizon. Pass/fail thresholds are decision V3 of the [validation plan](VALIDATION_PLAN.md#decisions).

## Behavioural cash-flow projection

Each loan is projected monthly from the as-of date on the contractual schedule:

1. interest for the month at `client_rate / 12` on the opening balance;
2. scheduled principal on payment months, from the amortisation type and the balance after earlier prepayments;
3. prepayment `SMM(i,k) x (opening balance - scheduled principal)`;
4. final repayment at maturity; for `RESET` and `FLOAT` loans, the balance at the next reset is a repricing cash flow.

After a prepayment an annuity is re-amortised over the remaining term, keeping the maturity and lowering the instalment (decision M6). Penalty income is not projected.

Outputs per segment, currency, scenario and month: opening balance, interest, scheduled principal, prepaid principal, repricing principal and closing balance, with conservation `opening = scheduled + prepaid + repricing + closing` checked to 0.005 currency units.

## Scenarios

A scenario is a shocked refinancing curve applied at the as-of date and held. It reaches the model only through the incentive `I`, so each scenario has its own CPR path. Under proposed decision M13, the scenario's shocked and floored discount curve also discounts its projected cash flows ([EVE sensitivity](#eve-sensitivity-and-repricing-gap)).

| Scenario | Source |
| --- | --- |
| `BASE` | Observed curve at the as-of date |
| `CONTRACT` | Observed curve at the as-of date with no prepayment (`SMM = 0`): a reference for the repricing gap and EVE, never a supervisory scenario. Proposed decision M17 (#72) |
| `PAR_UP`, `PAR_DOWN`, `STEEPENER`, `FLATTENER`, `SHORT_UP`, `SHORT_DOWN` | Supervisory shock scenarios, `REG-3` |
| User-defined parallel or ramp shocks | Run settings, recorded with the results |

## Regulatory overlay

Overlays are applied after the fit, change no fitted parameter and are labelled in every output.

| Overlay | Rule | Source | Status |
| --- | --- | --- | --- |
| Supervisory scenarios | The six EVE scenarios and two NII scenarios named in `REG-3` Article 1 | `REG-3` | Scenario list verified in the NMD register; shock sizes per currency **not verified** |
| Post-shock floor | `min(observed rate, min(0, -150bp + 3bp x m))` at maturity `m` years | `REG-3` Art. 3(7) | Verified in the NMD register |
| Standardised prepayment multipliers | `CPR_s = min(1, gamma_s x CPR_BASE)` with `gamma_s = 0.8` for up, steepener and short-up and `1.2` for down, flattener and short-down, as reported by the prototype | `REG-1` | **Not verified**; provisional |
| Supervisory expectations on behavioural assumptions | Governance of prepayment assumptions | `REG-2` | **Not verified** |
| Loan-book ΔEVE indicator | Raised when `-worst dEVE / Tier1 > 0.15` | `REG-1`, `REG-5` | **Not verified**; proposed (M16, #72) |
| Repricing-gap buckets | The 19 time buckets of `REG-1` Table 1 | `REG-1` | **Not verified**; proposed (M17, #72) |

The toolkit can report the internal-model CPR path and the standardised-multiplier CPR path side by side. Which one a bank uses for a regulatory purpose is outside the toolkit, which neither establishes compliance nor approves a model.

## EVE sensitivity and repricing gap

Status: **proposed in issue #72; not accepted.** Nothing in this section may be implemented until the owner accepts decisions M12–M18 and data decision D10. Every regulatory figure below is provisional until its source is verified (#45).

The toolkit measures the **loan book's contribution** to the economic value of equity: the present value of the projected cash flows of the loans in the run, per segment and currency and in total per currency. It is not the bank-level supervisory outlier test, which needs every banking-book position, and it does not measure NII (decision M12).

### Present value

```text
PV_s    = sum_k CF_s(k) x DF_s(k)
DF_s(k) = exp(-z_s(k/12) x k/12)
CF_s(k) = interest_s(k) + scheduled_s(k) + prepaid_s(k) + repricing_s(k)
```

- `k` is the month after the as-of date; cash flows are paid at month ends, `k/12` years after the as-of date.
- `CF_s(k)` are the projected cash flows of [scenario](#scenarios) `s` from the [behavioural projection](#behavioural-cash-flow-projection); penalty income is not projected.
- `z_s(t)` is the zero rate of scenario `s` at `t` years. The discount curve is a run setting naming market-rate series supplied as continuously compounded zero rates, interpolated linearly in rate and held flat outside the series; each scenario shocks and floors it like the refinancing curve (decision M13). The toolkit does not bootstrap zero rates from par rates; a discount curve not declared as zero rates rejects the run.
- Interest is projected at the client rate, so commercial margins are included in `PV_s` (decision M14).
- Present values are per currency and never added across currencies.
- Each CPR layer of the [regulatory overlay](#regulatory-overlay) gives its own cash flows: `PV_s`, `dEVE_s`, the worst case, the ratio and the indicator are computed and labelled separately for the internal-model CPR path and, when requested, for the standardised-multiplier path. `BASE` uses `CPR_BASE` in both layers, so `PV_BASE` is the same (decision M15). Layers are never mixed in one result.

### ΔEVE and worst case

```text
dEVE_s = PV_s - PV_BASE
worst dEVE = min over the six supervisory scenarios of dEVE_s
```

A negative `dEVE_s` is a loss of value. User-defined shocks report their own `dEVE_s` but do not enter the worst case. The `CONTRACT` scenario reports its PV for comparison and never enters the worst case (decision M15).

### ΔEVE / Tier 1 and loan-book indicator

```text
ratio = -worst dEVE / Tier1
indicator raised when ratio > 0.15
```

Tier 1 capital is a run setting ([data contract](DATA_CONTRACT.md#tier-1-capital), decision D10). The ratio is computed only for the currency of the Tier 1 amount; other currencies report `dEVE_s` without a ratio, because no implicit FX conversion is allowed. The indicator is a regulatory overlay labelled "loan-book indicator; not the supervisory outlier test" in every output (decision M16).

### Repricing gap

Principal cash flows (scheduled, prepaid and repricing) are placed in the time buckets of `REG-1` Table 1 by their payment time `k/12` years; each bucket includes its upper bound (decision M17).

| # | Bucket (`t` in years) | # | Bucket (`t` in years) |
| ---: | --- | ---: | --- |
| 1 | Overnight | 11 | 4 < t <= 5 |
| 2 | Overnight < t <= 1/12 | 12 | 5 < t <= 6 |
| 3 | 1/12 < t <= 3/12 | 13 | 6 < t <= 7 |
| 4 | 3/12 < t <= 6/12 | 14 | 7 < t <= 8 |
| 5 | 6/12 < t <= 9/12 | 15 | 8 < t <= 9 |
| 6 | 9/12 < t <= 1 | 16 | 9 < t <= 10 |
| 7 | 1 < t <= 1.5 | 17 | 10 < t <= 15 |
| 8 | 1.5 < t <= 2 | 18 | 15 < t <= 20 |
| 9 | 2 < t <= 3 | 19 | t > 20 |
| 10 | 3 < t <= 4 | | |

- The gap is reported per segment and currency for `CONTRACT` (contractual principal, no prepayment), for `BASE` (behavioural principal) and for each scenario.
- A `RESET` loan in its fixed period and a `FLOAT` loan place their balance at the next reset as repricing principal in the bucket of the reset month.
- On a monthly grid the overnight bucket is always empty; it is kept so that the table matches `REG-1`.
- For each gap, the sum over buckets equals the outstanding balance at the as-of date within 0.005 currency units.

### Other measures

| Measure | Definition (decision M18) |
| --- | --- |
| Weighted average repricing time | `sum_k (k/12) x principal_s(k) / sum_k principal_s(k)` in years, per scenario, where `principal_s(k)` includes the repricing principal of `RESET` and `FLOAT` loans at their next reset. For loans fixed to maturity it equals the weighted average life; it is never labelled as life for a book with resetting loans |
| Effective duration | `(PV_PAR_DOWN - PV_PAR_UP) / (2 x PV_BASE x dr)`, with `dr` the nominal parallel shock size of the currency, also where the floor binds; not reported when `PV_BASE <= 0` |
| Projected CPR | Pool SMM of each projected month, `sum prepaid / sum (opening - scheduled)`, compounded as `1 - (prod (1 - SMM))^(12/n)` over the first 12 months and over the projection; never an average of CPR values |

## Parameter and scenario outputs

A **parameter set** is immutable once created and holds: ID; model ID and version; segment and currency; data window and input fingerprints from the [lineage](DATA_CONTRACT.md#lineage); estimation and test windows; run settings (curve series and convention, lag, margin, bucket width, optimiser settings, data decisions D4 and D5); each value with unit and layer (estimate, assumption or overlay); diagnostics; timestamp; and toolkit commit SHA.

A **scenario result** names its parameter set and holds, per segment, currency, scenario and month: SMM, CPR and the projected cash flows above; under the proposed decisions M12–M18, also PV, `dEVE`, the ratio and indicator with the Tier 1 amount and currency used, the repricing gap and the other measures. Exporting never re-estimates. The export file format is decision M10.

## Independent validation

Each model needs independent expected values with stated tolerances, an out-of-time backtest with frozen parameters, and real Excel compile and run evidence on the candidate commit. These requirements are in the [validation plan](VALIDATION_PLAN.md), the [case register](TEST_CASES.md) and [Excel evidence](../EXCEL_EVIDENCE.md). Nothing in this document is validated.

## Decisions

| # | Decision | Outcome | Status |
| ---: | --- | --- | --- |
| M1 | First implemented model | `PM0` and `PM1`; `PM2` deferred | Accepted 2026-10-21 |
| M2 | Partial vs full prepayment | One `PM1` curve on total SMM; partial and full SMM reported separately | Accepted 2026-10-21 |
| M3 | Refinancing rate convention | Par swap rate for the remaining fixed term, linear interpolation, flat extrapolation | Accepted 2026-10-21 |
| M4 | Incentive lag `L` | 1 month | Accepted 2026-10-21 |
| M5 | New-business margin `m` | Behavioural assumption per segment, recorded in the parameter set | Accepted 2026-10-21 |
| M6 | Annuity after partial prepayment | Re-amortise over the remaining term (keep maturity) | Accepted 2026-10-21 |
| M7 | Estimated vs assumed `PM1` components | `c_min`, `c_max`, `k`, `x0` estimated; ramp, seasonality and burnout assumed unless identified with diagnostics | Accepted 2026-10-21 |
| M8 | Incentive bucket width | 25 basis points | Accepted 2026-10-21 |
| M9 | Minimum sample | 36 month ends, 5,000 loan-months, 100 `FULL` events | Accepted 2026-10-21 |
| M10 | Export format | CSV with the parameter-set ID in every row | Accepted 2026-10-21 |
| M11 | Predicted bucket value in the `PM1` fit | Exposure-weighted mean of loan-level model SMM over the bucket's loan-months | Accepted 2026-10-21 after review of #34 |
| M12 | EVE scope | Loan-book contribution per segment and currency, in total per currency; no NII; not the supervisory outlier test | Proposed (#72) |
| M13 | Discount curve | Supplied continuously compounded zero rates on the `k/12` grid, linear interpolation, flat extrapolation, shocked and floored per scenario; no bootstrapping | Proposed (#72) |
| M14 | Commercial margins | Included: interest projected at the client rate; an exclusion option waits for verification of `REG-3` (#45) | Proposed (#72) |
| M15 | ΔEVE and worst case | `PV_s - PV_BASE` per CPR layer (internal model; standardised multipliers when requested), never mixed; worst over the six supervisory scenarios; `CONTRACT` and user shocks excluded from the worst case | Proposed (#72) |
| M16 | ΔEVE / Tier 1 and indicator | `-worst dEVE / Tier1` in the Tier 1 currency only; indicator above 0.15; overlay, provisional | Proposed (#72) |
| M17 | Repricing gap | 19 `REG-1` buckets, upper bound inclusive; principal only; `CONTRACT`, `BASE` and each scenario; reset balances at the next reset | Proposed (#72) |
| M18 | Other measures | Weighted average repricing time (repricing principal at the next reset), effective duration from the parallel shocks, projected CPR by compounding pool SMM | Proposed (#72) |
