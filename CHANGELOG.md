# Changelog

All work is unreleased. Closing the setup milestone (v0.1.0 - Repo setup) on 2026-10-21 did not create a version tag or GitHub Release.

## [Unreleased]

### Branding correction

- Align the README/social-preview SVG and PNG status with Specifications only after setup closeout (#63); refresh the reviewed PNG digest. Planned scope and unvalidated-output statements remain explicit.

### Added

- Proposed workbook contract (#38): sheet order, names and CodeNames, defined names, input, parameter, result and diagnostics areas, operations, staleness, build components and file access, with decisions W1–W10. Not accepted; no workbook, template or VBA exists.
- RENEG successor reconciliation (#49): decision D11 amending D4 and D6, accepted by the owner on 2026-10-26; error `E16`, warning `W06` and case `DATA-RENEG-01`. The reverse link is checked only for successors originated inside the data window (review of #79). Nothing implemented.
- EVE sensitivity and repricing-gap contracts (#72): decisions M12–M18 and D10, accepted by the owner on 2026-10-21; source `REG-5`, validation rows and registered cases. Sources unverified; nothing implemented. Review follow-up names the measure weighted average repricing time (including principal repricing at the next reset), and computes EVE, worst scenarios, ratios and indicators separately per labelled CPR layer.
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
- Prepayment data contract, model contracts and source register under `docs/methodology`, accepted by the owner on 2026-10-21 with decisions D1–D9 and M1–M11 (#14). After review, positive `other_change` counts as SMM exposure and prepayment above exposure is rejected (`E15`), so SMM stays within [0, 1]; a `RENEG` transfer is recorded as negative `other_change` and is the numerator when `RENEG` inclusion is selected; M11 defines the predicted bucket value of the `PM1` fit. No source is verified and nothing is implemented.
- Validation plan, numerical test-case register and Excel evidence requirements, accepted by the owner on 2026-10-21 with decisions V1–V6 and E1–E3 (#15). After review, only (origin, horizon) pairs with a complete horizon are scored and others are `INCOMPLETE`; later origins may follow 12 complete ones; zero realised prepayment uses absolute error and is excluded from the ±10 % test. Every case is registered only; no check, harness or Excel run has been executed.
- Foundation closeout record (#16): closeout gates, issue dispositions and the final comparison with K-IRRBB-NMDs, accepted by the owner on 2026-10-21. Every deferred gap has an issue in v0.2.0 - Prototype setup (#38–#45).
- Setup milestone v0.1.0 with 16 issues, each with owner, milestone and one priority; closed on 2026-10-21.

### Changed

- About wording describes setup-stage capabilities, with prepayment topics; feature and merge settings aligned; main protection and the exact `integrity` check context documented (#9).
- Release branches follow milestones: one `release/<milestone version>` branch per milestone is the integration target for task PRs and Dependabot. Task PRs are squash-merged into it; the owner integrates it into main with a merge commit, and it is levelled with main after each integration. `release/0.1.0` served v0.1.0 - Repo setup and is retired; `release/0.2.0`, created from main at `14a45c8` on 2026-10-21, is active for v0.2.0 - Prototype setup (#59). No release, tag or version is implied.
- Upgraded pinned actionlint to 1.7.12 for current environment syntax (#11).
- Brought the Markdown documentation in line with the closed setup milestone and removed setup-history comparisons with K-IRRBB-NMDs from the settings, governance and label guides (#53). Documentation only.

### Fixed

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
