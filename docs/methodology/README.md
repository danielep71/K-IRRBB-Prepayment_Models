# Prepayment methodology contracts

Status: **accepted by the owner on 2026-10-21 (issue #14)**, with every decision as proposed. These documents specify what a future implementation must satisfy. No model, importer, calibration routine or numerical output exists, and nothing here is validated. Figures attributed to a source are provisional until that source is verified in the [source register](SOURCES.md).

| Document | Authoritative for |
| --- | --- |
| [Data contract](DATA_CONTRACT.md) | Input datasets, fields, units, loan events, validation codes, censoring and lineage |
| [Model contracts](MODEL_CONTRACTS.md) | CPR/SMM conventions, candidate models, rate incentive, estimation, outputs and the regulatory overlay |
| [Source register](SOURCES.md) | External sources relied on, and whether each has been verified |

Validation and Excel evidence requirements belong to issue #15; these contracts only name what each model must report so that #15 can test it.

## Scope

Loan prepayments in the banking book: partial and full early repayments of amortising or bullet loans, distinguished from scheduled principal, maturity and default. Deposits, decay and rate pass-through are out of scope and belong to [K-IRRBB-NMDs](https://github.com/danielep71/K-IRRBB-NMDs). EVE/NII aggregation, the supervisory outlier test, option pricing and model approval are outside the toolkit.

## Three layers, kept apart

Every number the toolkit produces belongs to exactly one layer, and outputs say which:

| Layer | What it is | Example | Changed by |
| --- | --- | --- | --- |
| **Statistical estimate** | Fitted to the loan data in the estimation window, with diagnostics | S-curve parameters, observed segment CPR | Re-estimation on new data |
| **Behavioural assumption** | A documented judgement that is not estimated | Burnout strength when the data cannot identify it, a CPR floor, the incentive lag | A reviewed parameter change with rationale |
| **Regulatory overlay** | A rule taken from a verified provision | Scenario multipliers on the base CPR, supervisory shock sizes, the post-shock rate floor | A change to the verified source or its applicability |

An overlay is applied after the fit and never changes fitted coefficients. A behavioural assumption is never reported as an estimate.

## Relationship to the prototype

The prototype in [danielep71/K-IRRBB-Prepayment_Models#19](https://github.com/danielep71/K-IRRBB-Prepayment_Models/pull/19) is a review draft, not an accepted design. Where it chose a convention, the [model contracts](MODEL_CONTRACTS.md) record that choice as a candidate or as a decision; nothing was adopted from the prototype by default.

## Decisions

Each contract ends with its decision table; all were accepted on 2026-10-21. Changing a decision needs an issue and a reviewed change to its table; nothing may silently pick another interpretation. Acceptance does not verify any source or validate any model.
