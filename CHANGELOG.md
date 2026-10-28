# Changelog

All work is unreleased. Closing the setup milestone (v0.1.0 - Repo setup) on 2026-10-21 did not create a version tag or GitHub Release.

## [Unreleased]

### Branding correction

- Align the README/social-preview SVG and PNG status with Specifications only after setup closeout (#63); refresh the reviewed PNG digest. Planned scope and unvalidated-output statements remain explicit.

### Added

- `DATA-VALID-01`, `DATA-INVALID-01`, `DATA-EVENT-01` and `DATA-RECON-01` built (#41): the reference reader applies D12–D15 (reconciliation totals, control totals with `E17`, `E12` at line 0, zero-residual `RENEG`); hand-constructed fixtures cover every event and warning, one invalid line per error `E01`–`E16`, every event boundary and each kind of control-total difference. `DATA-REJECT-01` remains `Registered`. After review of #104, control totals with a header and no rows are an empty `Controls_Totals` table, so no control totals were supplied.
- Data decisions D12–D15 (#41), decided by the owner on 2026-10-27: the reconciliation totals use the reported balance of terminal rows (D12); a control-total mismatch is the new error `E17`, with the `Controls_Totals` column order (D13); `E12` is reported at `loan_panel.csv` line 0 (D14); a zero-residual `RENEG` needs no successor (D15, amending D11). Subsequently applied by the independent reader in #103; no production VBA importer is delivered.
- `DATA-PIT-01` and `DATA-PIT-02` built (#41): the reference reader assigns the risk-set outcome of every loan-month (observed by event, gap, censored, past maturity, end of window) and builds the point-in-time view at a forecast origin; four hand-assigned variants, and a seeded property test with a negative control showing that changes after an origin never reach the view at that origin.
- `DATA-RENEG-01` built (#41): eleven hand-constructed variants of RENEG successor reconciliation (D11), from the 0.005 boundary to successors outside the data window, checked by the reference reader through `python tools/check.py`.
- First fixtures, expected files and reference reader (#41): `tests/reference/data_reader.py` (standard library, exact decimals) applies the data contract; hand-constructed fixtures and expected files make `DATA-PARSE-01`, `DATA-IDENT-01`, `DATA-EXPO-01` and `DATA-SHA-01` `Built (Python)`, run by `python tools/check.py`. Points the contract leaves open are listed in `tests/reference/README.md` and asserted by no case.
- First VBA source and test harness (#42, #39): `CORE_Rates` and the `PREPAY_Rates` facade (SMM and CPR conversions through `log1p`/`expm1`, range errors at the facade), `docs/PUBLIC_API.txt`, and `TEST_Harness` with a case registry, the outcomes `NOT RUN`, `ERROR`, `FAIL` and `PASS`, the entry points `TEST_RunAll` and `TEST_RunInjected`, and `TEST_Rates`. `RATE-CONV-01` and `RATE-CONV-02` are `Built (VBA)`. Not compiled or run in Excel.
- Workbook build tooling (#43): `tools/workbook_layout.py`, `tools/build_template.py` (macro-free template generated at build time, XlsxWriter pinned in `tools/requirements-build.txt`), `tools/components.py` (stage and compare), `tools/Build-Workbook.ps1` and `tools/Export-Workbook.ps1`, with offline tests and the production and test builds. Named in Excel evidence stages 1 and 6, which now both record the VBA project trust exception. Not run in Excel; the first VBA components were delivered separately under #42/#91.
- Workbook contract (#38): sheet order, names and CodeNames, defined names, input, parameter, result and diagnostics areas, operations, staleness, build components and file access, with decisions W1–W10, accepted on 2026-10-26. After review of #83, no table anchor collides with a status name, and a failure clears only result areas. The specification itself adds no workbook, template or VBA; build tooling was delivered separately under #43.
- RENEG successor reconciliation (#49): decision D11 amending D4 and D6, accepted on 2026-10-26; error `E16`, warning `W06` and case `DATA-RENEG-01`. The reverse link is checked only for successors originated inside the data window (review of #79). Subsequently implemented in the independent reader with fixtures under #41.
- EVE sensitivity and repricing-gap contracts (#72): decisions M12–M18 and D10, accepted on 2026-10-21; source `REG-5`, validation rows and registered cases. Sources unverified; nothing implemented. Review follow-up names the measure weighted average repricing time (including principal repricing at the next reset), and computes EVE, worst scenarios, ratios and indicators separately per labelled CPR layer.
- Source-first architecture, directory guides, developer installation and future VBA conventions (#2, #13).
- Editing and Git rules with no approved workbook exception (#3).
- Contribution, security, conduct, governance, provenance and release guides; MPL-2.0 text (#4, #5, #16).
- Reachable-history secret scan, provenance inspection and the owner's ownership and publication confirmation of 2026-10-20, including the separate prototype branch, which uses SACCR only as a visual reference (#4). Existing setup-source attributions remain in place.
- 20-label catalogue adapted from VBA-SACCR-Toolkit, with synchronisation and drift workflows (#5).
- Issue forms, PR template, issue-metadata enforcement and offline regression tests (#6, #7).
- Portable integrity checks and static CI (#8): pinned Ruff, mypy, YAML and actionlint checks with checksum verification of the actionlint archive and retained source/tool evidence; portable filenames, tracked documentation links and structured source provenance; negative fixtures for invalid configuration, provenance, paths and workflows.
- Weekly Dependabot updates for GitHub Actions, targeting the active release branch (#10).
- Daily traffic history, idempotent snapshots, badges and milestone-bound alerts (#11). Uses a main-only analytics environment without deployment records; live activation requires `TRAFFIC_TOKEN`.
- Prepayment-specific blue/violet social preview and README image, editable SVG source and documented provenance (#12).
- Prepayment data contract, model contracts and source register under `docs/methodology`, accepted on 2026-10-21 with decisions D1–D9 and M1–M11 (#14). After review, positive `other_change` counts as SMM exposure and prepayment above exposure is rejected (`E15`), so SMM stays within [0, 1]; a `RENEG` transfer is recorded as negative `other_change` and is the numerator when `RENEG` inclusion is selected; M11 defines the predicted bucket value of the `PM1` fit. No source is verified. Independent data references and the initial VBA rate conversions were delivered separately under #41/#42; the remaining production model work is outstanding.
- Validation plan, numerical test-case register and Excel evidence requirements, accepted on 2026-10-21 with decisions V1–V6 and E1–E3 (#15). After review, only (origin, horizon) pairs with a complete horizon are scored and others are `INCOMPLETE`; later origins may follow 12 complete ones; zero realised prepayment uses absolute error and is excluded from the ±10 % test. At adoption every case was registered only. Eleven DATA cases were later built and run in Python under #41, and two rate-conversion cases built in VBA under #42/#91; no Excel execution is established.
- Foundation closeout record (#16): closeout gates, issue dispositions and the final comparison with K-IRRBB-NMDs, accepted on 2026-10-21. Every deferred gap has an issue in v0.2.0 - Prototype setup (#38–#45).
- Setup milestone v0.1.0 with 16 issues, each with assignee, milestone and one priority; closed on 2026-10-21.

### Changed

- `RATE-CONV-01` (#42): at SMM 0.999999 the CPR rounds to 1 in double precision, so that grid point checks `CPR = 1` instead of a round trip.
- Workbook contract layout (#43): the tables of a sheet sit side by side from column C, so a growing table cannot overwrite the one below it; found while generating the template.
- About wording describes setup-stage capabilities, with prepayment topics; feature and merge settings aligned; main protection and the exact `integrity` check context documented (#9).
- Release branches follow milestones: one `release/<milestone version>` branch per milestone is the integration target for task PRs and Dependabot. Task PRs are squash-merged into it; integration into main uses a merge commit, and it is levelled with main after each integration. `release/0.1.0` served v0.1.0 - Repo setup and is retired; `release/0.2.0`, created from main at `14a45c8` on 2026-10-21, is active for v0.2.0 - Prototype setup (#59). No release, tag or version is implied.
- Upgraded pinned actionlint to 1.7.12 for current environment syntax (#11).
- Brought the Markdown documentation in line with the closed setup milestone and removed setup-history comparisons with K-IRRBB-NMDs from the settings, governance and label guides (#53). Documentation only.

### Fixed

- Maintenance documentation reflects the eleven executed DATA reference cases and reconciles stale delivery statements, preserving the separate Windows Excel evidence requirements (#41, #42, #43; #92).

- The component comparison checks VBA types, so a sheet's document module replaced by a standard module of the same name fails (review of #87, #43).
- Tightened the #30 contract boundaries (#14): E15 rejects every positive excess of prepayment over exposure at input decimal precision, and RENEG requires nonnegative residual principal. Extended the registered boundary cases; no importer or Excel execution is claimed.
- Forecast leakage tests alter only data after the origin, while the lag cutoff applies to the historical incentive (review of #34).
- The Dependabot check enforces the exact active release branch (review of #34).
- Aligned the structure guide with the accepted contracts (#25), made the chronological test-window rule explicit in the model contract (#24) and registered a window-boundary test.
- Corrected security-policy descriptions of live traffic credentials and branding assets (#4).
- Brought the foundation closeout record in line with the final evidence (#16).
- Governance and traffic guides give `ISSUE_MILESTONE_NUMBER` as 2 (v0.2.0 - Prototype setup), not 1 (#53).
- The post-shock floor is stated as a lower bound on the shocked rate, and projected CPR excludes months with no exposure from the product and from `n` (review of #75, #72).
- Comments in configuration, tooling and workflows no longer cite K-IRRBB-NMDs issue numbers or describe the repository as in setup, private or a template; `docs/LABELS.md` priority meanings follow `.github/labels.json` (#65).

## Version rules

Use a dated X.Y.Z heading only after release approval. Keep an Unreleased section for later work and record actual dates/evidence rather than planned releases as completed.
