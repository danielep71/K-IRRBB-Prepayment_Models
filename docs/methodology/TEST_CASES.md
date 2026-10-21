# Numerical test cases

Status: **accepted by the owner on 2026-10-21 (issue #15). Every case is `Registered`: no fixture, expected file, reference script or VBA test exists.** Cases under [EVE sensitivity and repricing gap](#eve-sensitivity-and-repricing-gap-proposed-72) test decisions proposed in #72 and not accepted.

This register is authoritative for which numerical cases test the prepayment contracts, where their expected values must come from, and how closely an implementation must match them. The evidence protocol and status vocabulary are in the [validation plan](VALIDATION_PLAN.md); the specifications under test are the [data contract](DATA_CONTRACT.md) and [model contracts](MODEL_CONTRACTS.md).

## Provenance rules

- Expected values are produced **outside the toolkit**: by hand, or by an independent script run offline. Reference tooling is never a runtime dependency.
- Each expected file records the producing tool and version, the script or steps, the date and the producer. A script that produces reference values is committed next to its expected file.
- Fixtures are synthetic. A generated fixture records its process, parameters and seed.
- An expected value is never copied from toolkit output. When the toolkit and the reference disagree, the disagreement is investigated; the reference is not edited to match.

## Tolerances

| Kind | Rule |
| --- | --- |
| `exact` | Identical after the stated rounding; for counts, codes, events and hand-constructed identities |
| `abs e` | `abs(x - x_ref) <= e` |
| `rel e` | `abs(x - x_ref) <= e x max(1, abs(x_ref))` |

Tolerances cover numerical-method differences only, never sampling error. Whether an estimator recovers a known generating process is a separate statistical check.

## Register

### Data contract

| ID | Checks | Reference | Tolerance | Status |
| --- | --- | --- | --- | --- |
| `DATA-VALID-01` | Totals per date, segment and currency; warnings `W01`–`W05`; all three files accepted | Hand computation from a small synthetic register and panel covering every event | `abs 0.005` amounts; `exact` counts and codes | Registered |
| `DATA-INVALID-01` | First error per line for every error code, including file-level `E01` and `E12` | Hand construction, one invalid line per rule | `exact` | Registered |
| `DATA-REJECT-01` | All-or-nothing import: one invalid row in any of the three files rejects all three; the previously accepted dataset stays unchanged and its outputs are marked stale | Hand construction: an accepted import followed by one rejected import per file | `exact` | Registered |
| `DATA-EVENT-01` | Event/flow consistency (`E14`) for every event, at and around each boundary; `RENEG` accepts zero residual and rejects scheduled principal above opening balance, including opening 100, scheduled 120, `other_change = 20`, closing 0 | Hand construction | `exact` | Registered |
| `DATA-IDENT-01` | Balance identity (`E13`) accepted at a difference of 0.005 and rejected just above it | Hand construction | `exact` | Registered |
| `DATA-EXPO-01` | Prepayment above exposure (`E15`): accepted at `P = A` including a same-month drawdown, rejected at the smallest positive input excess (0.0001), with no tolerance; `A = 0.0001`, `P = 0.0051` is rejected even when `E13` passes; the review example of #24 (opening 100, drawdown 100, prepayment 150) is accepted with `A = 200` and `SMM = 0.75` | Hand construction | `exact` | Registered |
| `DATA-PIT-01` | Risk-set outcome of every loan-month: observed by event, gap, censored, past maturity, end of window | Hand assignment | `exact` | Registered |
| `DATA-PIT-02` | Leakage: changing information after an origin leaves the point-in-time view at that origin unchanged; negative control without the filter | Property test | `exact` | Registered |
| `DATA-RECON-01` | Reconciliation against user control totals; a mismatch rejects the import | Hand construction | `abs 0.005`; `exact` counts | Registered |
| `DATA-SHA-01` | SHA-256 fingerprint of each input file | Published FIPS 180 examples and an independent digest | `exact` | Registered |
| `DATA-PARSE-01` | ISO dates, month ends, decimals and codes; locale-like forms rejected | [File format](DATA_CONTRACT.md#file-format) | `exact` | Registered |

### Prepayment rates

| ID | Checks | Reference | Tolerance | Status |
| --- | --- | --- | --- | --- |
| `RATE-CONV-01` | `SMM -> CPR -> SMM` and `CPR -> SMM -> CPR` round trips on a grid including 0, 1e-8, 0.02, 0.5, 0.999999 and 1 | Independent script using `log1p`/`expm1` | `rel 1e-12` | Registered |
| `RATE-CONV-02` | The worked check of the model contracts: `A = 99,000`, `SMM = 2,000 / 99,000`, `CPR = 1 - (1 - SMM)^12` | Hand computation and independent script | `abs 1e-12` | Registered |
| `RATE-POOL-01` | Pool SMM is `sum P / sum A`, not the mean of loan SMMs; `SMM = SMM_partial + SMM_full`; `A <= 0` excluded; a positive `other_change` counted in `A` | Hand computation on three loans with different balances | `abs 1e-12` | Registered |
| `RATE-POOL-02` | `DEFAULT` and `SALE` excluded from numerator and denominator; `RENEG` excluded by default, and when the run setting includes it, `P = -other_change` reported as `SMM_reneg` | Hand computation | `abs 1e-12` | Registered |
| `RATE-PERIOD-01` | Realised CPR over `n` months compounds monthly SMM; never the average of monthly CPRs | Hand computation over 3 and 12 months | `abs 1e-12` | Registered |

### Rate incentive

| ID | Checks | Reference | Tolerance | Status |
| --- | --- | --- | --- | --- |
| `INC-CALC-01` | Incentive with lag, margin and each penalty type; remaining term below one year uses `max(T, 1)` | Hand computation | `abs 1e-12` | Registered |
| `INC-CURVE-01` | Linear interpolation between curve tenors, flat extrapolation, compounding per decision M3 | Hand computation | `abs 1e-12` | Registered |
| `INC-LAG-01` | Changing market rates after `t - L` leaves the incentive at `t` unchanged | Property test | `exact` | Registered |

### Models

| ID | Checks | Reference | Tolerance | Status |
| --- | --- | --- | --- | --- |
| `PM0-CALC-01` | `PM0` equals the realised CPR of the estimation window | Hand computation | `abs 1e-12` | Registered |
| `PM1-FORM-01` | S-curve, ramp, seasonality, burnout and clamp evaluated at fixed parameters | Independent script | `rel 1e-12` | Registered |
| `PM1-FIT-01` | Weighted least-squares fit on synthetic bucket data, with predicted bucket values per decision M11: parameters and objective | Independent optimiser on the same objective, offline | Decision V5 | Registered |
| `PM1-FAIL-01` | Non-convergence, a parameter at a numerical boundary or a non-finite objective gives "not estimated" and stores no parameters | Hand-constructed samples | `exact` | Registered |
| `PM1-MIN-01` | A segment below the minimum sample is not estimated | Hand construction | `exact` | Registered |
| `PM1-DGP-01` | Recovery of known generating parameters from a large synthetic sample; reported, not a tolerance test | Generated fixture with recorded seed | Statistical, reported | Registered |

### Cash-flow projection

| ID | Checks | Reference | Tolerance | Status |
| --- | --- | --- | --- | --- |
| `CF-SCHED-01` | Annuity, linear and bullet schedules for each payment frequency, including rate near zero | Independent script | `abs 1e-8` | Registered |
| `CF-PREPAY-01` | After a partial prepayment an annuity keeps its maturity and its instalment falls | Hand computation | `abs 1e-8` | Registered |
| `CF-RESET-01` | `RESET` and `FLOAT` balances leave as repricing cash flows at the next reset | Hand computation | `abs 1e-8` | Registered |
| `CF-CONS-01` | `opening = scheduled + prepaid + repricing + closing` every month; lifetime principal equals the opening balance | Identity on every projected month | `abs 0.005` | Registered |

### Scenarios and overlay

| ID | Checks | Reference | Tolerance | Status |
| --- | --- | --- | --- | --- |
| `SCN-BASE-01` | A zero shock reproduces `BASE` cash flows exactly | Property test | `exact` | Registered |
| `SCN-MONO-01` | Parallel up gives CPR no higher than `BASE` at every month; parallel down no lower | Property test on a synthetic book | `exact` (sign) | Registered |
| `SCN-FLOOR-01` | Post-shock floor `min(observed, min(0, -150bp + 3bp x m))` | Hand computation with synthetic shock sizes | `abs 1e-12` | Registered |
| `SCN-GAMMA-01` | Multiplier overlay `min(1, gamma x CPR_BASE)`; provisional until `REG-1` is verified | Hand computation | `abs 1e-12` | Registered |
| `SCN-LAYER-01` | Overlays change no fitted parameter, and every output is labelled with its layer | Property test | `exact` | Registered |

### EVE sensitivity and repricing gap (proposed, #72)

| ID | Checks | Reference | Tolerance | Status |
| --- | --- | --- | --- | --- |
| `EVE-PV-01` | PV of hand-built cash flows on a two-tenor zero curve: linear interpolation, flat extrapolation, `k/12` grid | Independent script | `rel 1e-12` | Registered |
| `EVE-DELTA-01` | ΔEVE sign, worst over the six supervisory scenarios, `CONTRACT` and user shocks excluded, currencies never added; internal-model and standardised-multiplier layers reported separately with the same `PV_BASE` | Hand computation | `rel 1e-12` | Registered |
| `EVE-RATIO-01` | Ratio and indicator at exactly 0.15 (not raised) and just above (raised); Tier 1 in another currency gives no ratio; invalid Tier 1 stops the run | Hand construction | `exact` | Registered |
| `GAP-BUCKET-01` | Cash flows at each bucket's upper bound fall in that bucket; reset balances fall in the bucket of the next reset | Hand construction | `exact` | Registered |
| `GAP-CONS-01` | Sum over buckets equals the outstanding balance at the as-of date for `CONTRACT`, `BASE` and every scenario | Identity | `abs 0.005` | Registered |
| `MEAS-01` | Weighted average repricing time (with `RESET` and `FLOAT` loans repricing at the next reset), effective duration and projected CPR over 12 months and over the projection | Hand computation | `abs 1e-12` | Registered |

### Common

| ID | Checks | Reference | Tolerance | Status |
| --- | --- | --- | --- | --- |
| `OOS-WINDOW-01` | Reject test windows overlapping, equal to or earlier than estimation; accept a strictly later disjoint window subject to V1 and complete-horizon requirements | Hand-constructed month-end boundaries | `exact` | Registered |
| `OOS-FREEZE-01` | Parameters identical across all forecast origins in the test window | Property test | `exact` | Registered |
| `OOS-LEAK-01` | A forecast from origin `t` is unchanged when rows or market rates dated after `t` are altered; rates at `t` are not altered; negative control | Property test | `exact` | Registered |
| `OOS-SCORE-01` | Bias, MAE and cumulative prepaid error on a small hand case, including an `INCOMPLETE` pair at the end of the data window and a `ZERO_REALISED` pair | Hand computation | `abs 1e-12` | Registered |
| `SEG-ISO-01` | Altering one segment leaves other segments' parameters and forecasts unchanged; currencies never pooled | Property test | `exact` | Registered |
| `REPEAT-01` | Same inputs, settings and commit give identical outputs and fingerprints | Two runs compared | `exact` | Registered |
| `PARAM-01` | A parameter set is immutable; exporting never re-estimates | Property test | `exact` | Registered |

## Adding or building a case

1. Register the ID, what it checks, its reference and tolerance here.
2. Commit the synthetic fixture under `tests/fixtures/` and the expected file under `tests/expected/`, with the provenance fields above and any reference script.
3. Raise the status in the same pull request, using the [validation plan's vocabulary](VALIDATION_PLAN.md#planned-versus-executed).
