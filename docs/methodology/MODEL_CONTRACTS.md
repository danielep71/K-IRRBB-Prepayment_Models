# Model contracts

Status: **accepted by the owner on 2026-10-21 (issue #14)**, with every [decision](#decisions) as proposed. Regulatory figures name their source in the [source register](SOURCES.md); every figure resting on an unverified source is provisional and may not be implemented as a rule until the source is verified.

This document is authoritative for the prepayment-rate conventions, the candidate models, the rate incentive, estimation and failure handling, projected behavioural cash flows, scenario and parameter outputs, and the separation of statistical estimates, behavioural assumptions and regulatory overlays. Inputs come from the [data contract](DATA_CONTRACT.md). Validation thresholds and evidence are in the [validation plan](VALIDATION_PLAN.md).

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

A scenario is a shocked refinancing curve applied at the as-of date and held. It reaches the model only through the incentive `I`, so each scenario has its own CPR path. The shocked curve also discounts cash flows in downstream use, which is outside the toolkit.

| Scenario | Source |
| --- | --- |
| `BASE` | Observed curve at the as-of date |
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

The toolkit can report the internal-model CPR path and the standardised-multiplier CPR path side by side. Which one a bank uses for a regulatory purpose is outside the toolkit, which neither establishes compliance nor approves a model.

## Parameter and scenario outputs

A **parameter set** is immutable once created and holds: ID; model ID and version; segment and currency; data window and input fingerprints from the [lineage](DATA_CONTRACT.md#lineage); estimation and test windows; run settings (curve series and convention, lag, margin, bucket width, optimiser settings, data decisions D4 and D5); each value with unit and layer (estimate, assumption or overlay); diagnostics; timestamp; and toolkit commit SHA.

A **scenario result** names its parameter set and holds, per segment, currency, scenario and month: SMM, CPR and the projected cash flows above. Exporting never re-estimates. The export file format is decision M10.

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
