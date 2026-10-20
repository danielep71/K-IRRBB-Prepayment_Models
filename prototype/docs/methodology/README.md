# 📐 Methodology

This document is authoritative for **what K-PREPAY calculates**. The
executable specification is `tools/reference_model.py`; the VBA engine
follows it operation for operation and the Tests sheet compares the two.

## 1. Scope

A run-off loan book in one currency, projected monthly from the as-of date
under eight scenarios: `CONTRACT` (no prepayment, base curve), `BASE`
(behavioural, base curve) and the six IRRBB shocks `PAR_UP`, `PAR_DOWN`,
`STEEPENER`, `FLATTENER`, `SHORT_UP`, `SHORT_DOWN`. The output is the
loan-book contribution to EVE and its sensitivity, not the bank-level
supervisory outlier test, which needs every banking-book position.

## 2. Time grid and calendar

| Quantity | Convention |
| --- | --- |
| Month k | Ends at t = k / 12 years; cash flows are paid at month ends |
| Remaining months | `MonthsUp(as-of, maturity)`: a started month counts as one |
| Age | `MonthsDown(origination, as-of)`, completed months, floored at 0 |
| Repricing (FLOAT) | `min(remaining months, MonthsUp(as-of, next reset))` |
| Calendar month of month k | `((month(as-of) - 1 + k) mod 12) + 1` |

## 3. Contractual schedule

Interest accrues each month at `rate / 12` on the balance at the start of
the month and is paid on payment months, where `(remaining months - k)` is a
multiple of the payment frequency f. With `n = (remaining - k) \ f + 1`
payments left and `j = rate x f / 12`:

| Amortisation | Scheduled principal on a payment month |
| --- | --- |
| ANNUITY | `B x j / ((1 + j)^n - 1)`; `B / n` when `|j| < 1e-12` |
| LINEAR | `B / n` |
| BULLET | 0, the balance at maturity |

The schedule is recomputed on the balance after earlier prepayments, so
an annuity keeps its term and its instalment falls (re-amortisation). In
the last month the whole balance is repaid with the accrued interest; for a
FLOAT loan repricing before maturity the balance is a repricing cash flow at
par and the projection stops.

## 4. Prepayment

After the scheduled principal, a share SMM of the balance prepays and
settles the same share of accrued interest:

```text
SMM = 1 - (1 - CPR)^(1/12)
```

**Fixed-rate loans, BEHAVIOURAL mode and BASE scenario:**

```text
CPR = min(1, max(0, [CPRmin + (CPRmax - CPRmin) x B x L(slope x (I - mid))] x Ramp x Season))
I   = client rate - (z_s(T) + refinancing margin) - penalty / max(T, 1)
B   = exp(-burnout x (1 - S)),   S = product of (1 - SMM) over the earlier months
Ramp = min(1, (age + k) / seasoning ramp), 1 when the ramp is 0
```

`T = (remaining - k + 1) / 12` is the maturity left at the start of month k
and `z_s(T)` the zero rate of scenario s for T, so a shock changes the
refinancing rate and therefore the incentive. The penalty is a share of the
prepaid amount, spread over the remaining years (at least one).

**Fixed-rate loans, BCBS_SA mode, shock scenarios:**
`CPR_s(k) = min(1, gamma_s x CPR_BASE(k))` with the base path of the same
loan and gamma of BCBS d368 Table 3 (0.8 up / steepener / short up, 1.2 down
/ flattener / short down), editable on Params.

**Floating-rate loans:** `CPR = min(1, floating CPR x Ramp x Season)` in every
scenario except CONTRACT; their rate risk sits in the repricing date.

## 5. Curves and shocks

Zero rates are continuously compounded, interpolated linearly in the rate
and flat outside the input tenors. With x = 4 (BCBS d368 Annex 2):

| Scenario | Shock at t |
| --- | --- |
| PAR_UP / PAR_DOWN | `+/- R_parallel` |
| SHORT_UP / SHORT_DOWN | `+/- R_short x exp(-t / x)` |
| STEEPENER | `-0.65 |short(t)| + 0.9 |long(t)|`, `long(t) = R_long x (1 - exp(-t / x))` |
| FLATTENER | `+0.8 |short(t)| - 0.6 |long(t)|` |

EUR sizes 200 / 250 / 100 bp (Reg. (EU) 2024/856 Annex Part A). The shocked
rate is floored at `min(observed rate, min(0, -150 bp + 3 bp x t))`
(Art. 3(7)), switchable with `ApplyFloor`.

## 6. Measures

| Measure | Definition |
| --- | --- |
| PV_s | `sum_k CF_s(k) x exp(-z_s(k/12) x k/12)`, commercial margins included |
| dEVE_s | `PV_s - PV_BASE`; dEVE / Tier 1 against the Params value |
| WAL | `sum t x principal / sum principal` (scheduled + prepaid + repricing) |
| Average CPR | Weighted by the balance at the start of each month (first 12 months; lifetime) |
| Effective duration | `(PV_PAR_DOWN - PV_PAR_UP) / (2 x PV_BASE x R_parallel)` |
| Gap | Monthly cash flows in the 19 BCBS d368 Table 1 buckets, upper bound inclusive |
| Outlier indicator | `-worst dEVE / Tier 1 > OutlierThreshold` (15% of Tier 1, the BCBS d368 outlier test) |

## 7. Calibration

For each segment with History rows, CPR min, CPR max, slope and midpoint
minimise the weighted mean squared error `sum w (CPR_obs - f(I))^2 / sum w`
of the S-curve without burnout, ramp or seasonality, so History must hold
seasoning- and seasonality-adjusted observations. The search runs on
`a, b, c, d` with `CPRmin = L(a)`, `CPRmax = CPRmin + (1 - CPRmin) L(b)`,
`slope = e^c`, `mid = d` (Nelder-Mead 1 / 2 / 0.5 / 0.5, relative
tolerance 1e-13, at most 4,000 iterations, one restart). On the synthetic
History the fit recovers the generating parameters within the noise
(R² 0.89 to 0.99).

## 8. Validation of inputs

| Finding | Effect |
| --- | --- |
| Invalid parameter, gamma, seasonality or curve | ERROR, the run stops and outputs are cleared |
| Invalid segment | ERROR; its loans are excluded |
| Invalid loan (ID, segment, rate type, currency, balance, rate, dates, amortisation, frequency, reset, penalty, maturity beyond MaxProjectionMonths) | ERROR; the loan is excluded and shown on LoanCalc |
| Origination after the as-of date; reset on or after maturity; reset date on a FIXED loan; seasonality average not 1 | WARNING; the stated assumption is applied |

## 9. Known simplifications

- Refinancing benchmark: zero rate, not par rate, of the remaining maturity.
- Instantaneous, permanent shocks; no curve dynamics, no path dependency
  beyond burnout.
- No NII measure (constant balance sheet), no new business, no basis risk,
  no behavioural assumptions for deposits, no automatic options (caps/floors).
- Floating-rate loans: no rate reset of the client rate within the
  projection; they reprice at par at the next reset.

## 10. Sources

- BCBS, *Interest rate risk in the banking book*, d368, April 2016:
  Annex 2 (shocks), para 124 and Table 3 (prepayment), Table 1 (buckets).
- Commission Delegated Regulation (EU) 2024/856 (supervisory shock
  scenarios, common modelling assumptions): Art. 3(7) lower bound, Annex
  Part A shock sizes.
