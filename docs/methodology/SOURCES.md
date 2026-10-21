# Source register

Status: **adopted with the contracts on 2026-10-21 (issue #14); no entry is verified.** This register is authoritative for which external sources the prepayment contracts rely on and whether each has been verified against its official text. Contracts cite sources by ID. Sources are cited by reference only; their text is never copied into the repository.

**No source has been verified for this repository.** `REG-3` provisions listed below were verified for [K-IRRBB-NMDs](https://github.com/danielep71/K-IRRBB-NMDs) on 2026-10-08 by the owner's research; that record is reused by reference and has not been re-checked here. A regulatory rule may be implemented only from a verified provision, recorded with its exact location and version.

## Regulatory and supervisory

| ID | Source | Relied on for | Verified |
| --- | --- | --- | :---: |
| `REG-1` | Basel Committee on Banking Supervision, *Interest rate risk in the banking book*, Standards, April 2016 (BCBS d368); consolidated in the Basel Framework, SRP31 | Standardised-framework treatment of prepayments on fixed-rate loans, including the scenario multipliers on the base CPR; the shapes of the shock scenarios; the time buckets of Table 1 used by the repricing gap; the 15 % of Tier 1 outlier threshold for ΔEVE (proposed use, #72) | ☐ |
| `REG-2` | European Banking Authority, *Guidelines on IRRBB and CSRBB*, EBA/GL/2022/14 (exact title and dates not yet verified) | Supervisory expectations on behavioural assumptions for prepayments | ☐ |
| `REG-3` | Commission Delegated Regulation (EU) 2024/856 of 1 December 2023 on regulatory technical standards specifying the supervisory shock scenarios, the common modelling and parametric assumptions and what constitutes a large decline. OJ L, 2024/856, 24.4.2024 | Names of the supervisory shock scenarios (Article 1); post-shock lower bound (Article 3(7), Article 4(1)); shock sizes per currency (Annex); common modelling assumptions on discounting and commercial margins (Article 3, proposed use, #72) | Partly, by reference: Articles 1, 3(7) and 4(1) per the NMD record; Annex not verified |
| `REG-5` | Directive 2013/36/EU (CRD), Article 98(5), as amended by Directive (EU) 2019/878 (exact consolidated text not yet identified) | EU supervisory outlier test threshold for ΔEVE, 15 % of Tier 1 (proposed use, #72) | ☐ |
| `REG-4` | EU regulatory technical standards on the IRRBB standardised approach (instrument not yet identified) | Possible EU-specific prepayment treatment in the standardised approach | ☐ |

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
