# Source register

Status: **adopted with the contracts on 2026-10-21 (issue #14); `REG-1` to `REG-5` verified on 2026-11-12 (issue #45).** This register is authoritative for which external sources the prepayment contracts rely on and whether each has been verified against its official text. Contracts cite sources by ID. Sources are cited by reference only; their text is never copied into the repository.

The [verification record](../reviews/2026-11-12-regulatory-sources.md) gives, for each regulatory source, the text and version obtained, the provisions checked, every figure the contracts attribute to it and the corrections made. Reviewer: Daniele Penza. A regulatory rule may be implemented only from a verified provision, recorded with its exact location and version. Industry, academic and numerical sources remain unverified.

## Regulatory and supervisory

| ID | Source | Relied on for | Verified |
| --- | --- | --- | :---: |
| `REG-1` | Basel Committee on Banking Supervision, Basel Framework, SRP31 *Interest rate risk in the banking book*, version effective 1 January 2026 (last updated 16 July 2024), consolidating the Standards of April 2016 (BCBS d368) | Standardised CPR under the shock scenarios, `min(1, gamma x CPR_0)` with the multipliers of Table 5 (SRP31.118–SRP31.119); shock shapes (SRP31.91–SRP31.92); the 19 time buckets of Table 3 (SRP31.96); the outlier test against 15 % of Tier 1 (SRP31.82–SRP31.84) | Yes, 2026-11-12 (#45) |
| `REG-2` | European Banking Authority, *Guidelines on the management of interest rate risk and credit spread risk arising from non-trading book activities*, EBA/GL/2022/14, final report of 20 October 2022; apply from 30 June 2023 (sections 4.5 and 4.6 from 31 December 2023) and repeal EBA/GL/2018/02 | Supervisory expectations on prepayment assumptions: paragraphs 66, 67(c)–(d), 71(c), 106(a) and (d), 107, 108(a) and 109 | Yes, 2026-11-12 (#45) |
| `REG-3` | Commission Delegated Regulation (EU) 2024/856 of 1 December 2023 on regulatory technical standards specifying the supervisory shock scenarios, the common modelling and parametric assumptions and what constitutes a large decline. OJ L, 2024/856, 24.4.2024; in force from 14 May 2024, not amended | Names of the supervisory shock scenarios (Article 1); their shapes (Article 2); commercial margins in EVE (Article 3(5)) and NII (Article 4(3)); post-shock lower bound (Article 3(7), Article 4(1)); shock sizes per currency (Annex, Part A) | Yes, 2026-11-12 (#45) |
| `REG-4` | Commission Delegated Regulation (EU) 2024/857 of 1 December 2023 on regulatory technical standards specifying a standardised methodology and a simplified standardised methodology for IRRBB. OJ L, 2024/857, 24.4.2024; in force from 14 May 2024; English text unchanged by Delegated Regulation (EU) 2025/1275 | EU standardised treatment of fixed-rate retail loans subject to early repayment: multipliers 0.8 and 1.2 by scenario class (Articles 4 and 9(3)) and allocation of prepaid amounts to buckets (Article 9(4)–(5)); repricing time buckets (Annex, points 1 and 2) | Yes, 2026-11-12 (#45) |
| `REG-5` | Directive 2013/36/EU (CRD), Article 98(5), second subparagraph, point (a), as replaced by Article 1, point (29)(b), of Directive (EU) 2019/878, applicable from 28 June 2021; paragraph 5 not amended by Directive (EU) 2024/1619 | EU supervisory outlier test: a decline of the institution's EVE by more than 15 % of Tier 1 under any of the six supervisory scenarios (#72) | Yes, 2026-11-12 (#45) |

`REG-1` Table 2 (recalibrated shocks effective 1 January 2026) and the `REG-3` Annex give different shock sizes; EU scenarios use `REG-3`.

## Industry, academic and numerical

| ID | Source | Relied on for | Verified |
| --- | --- | --- | :---: |
| `IND-1` | Securities Industry and Financial Markets Association (SIFMA), *Uniform Practices for the Clearance and Settlement of Mortgage-Backed Securities and Other Related Securities*, standard formulas (edition not yet identified) | Market conventions for SMM and CPR | ☐ |
| `ACA-1` | Richard, S. F. and Roll, R. (1989), "Prepayments on fixed-rate mortgage-backed securities", *Journal of Portfolio Management* 15(3), 73–82 | Refinancing incentive, seasoning, seasonality and burnout as prepayment drivers | ☐ |
| `ACA-2` | Schwartz, E. S. and Torous, W. N. (1989), "Prepayment and the valuation of mortgage-backed securities", *Journal of Finance* 44(2), 375–392 | Hazard-based prepayment modelling (`PM2` candidate) | ☐ |
| `NUM-1` | Nelder, J. A. and Mead, R. (1965), "A simplex method for function minimization", *The Computer Journal* 7(4), 308–313 | Derivative-free optimiser for `PM1` | ☐ |

The CPR/SMM identity `CPR = 1 - (1 - SMM)^12` is a definition, not a rule taken from a source; `IND-1` is cited for market convention only.

## Applicability

Statistical estimates rest on the loan data, not on these sources. `ACA-*` and `NUM-1` support the choice of model form and method; they set no parameter values. `REG-*` sources supply overlays only, and only once verified. Whether a bank applies `REG-1`, `REG-3`, `REG-4` or `REG-5` to a portfolio is a regulatory-scope question outside the toolkit.

## Verifying an entry

1. Obtain the official text from its publisher.
2. Record the exact title, version or publication date, and the article, paragraph or table relied on.
3. Check every figure or rule the contracts attribute to it.
4. Mark the entry verified in a reviewed change that names the reviewer, and correct the contracts where they differ.

A source that cannot be obtained stays unverified, and anything resting on it stays a proposal.
