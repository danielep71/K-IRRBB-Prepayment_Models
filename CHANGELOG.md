# Changelog

All work is unreleased. The setup milestone does not imply a version tag or GitHub Release.

## [Unreleased]

- Add daily traffic history, idempotent snapshots, badges and milestone-bound alerts (#11). Use a main-only analytics environment without deployment records; live activation requires TRAFFIC_TOKEN. Upgrade pinned actionlint to 1.7.12 for current environment syntax.

### Fixed

- Fixed four findings from the review of #34: forecast leakage tests alter only data after the origin, while the lag cutoff applies to the historical incentive; decision M11 defines the predicted bucket value of the `PM1` fit; V1 now allows later origins with `INCOMPLETE` pairs after 12 complete ones; the Dependabot check enforces the exact active release branch.

- Aligned the structure guide with accepted contracts (#25), made the already accepted chronological test-window rule explicit in the model contract (#24), and registered a window-boundary test. Tests remain registered only; remaining contract findings stay tracked in #14, while #28 handles the validation-plan findings from #26.

### Added

- Opened #38–#45 in milestone v0.2.0 - Prototype setup for every deferred gap of the foundation closeout (#16) and linked them from the closeout record.

- Updated the foundation closeout (#16): #14 and #15 closed, release integrated into main (#34) and levelled (#35), successor milestone reported. Added the step to open successor-milestone issues for every deferred gap before closing milestone 1.

- Recorded the owner's acceptance of the NMD gap dispositions on 2026-10-21 in the foundation closeout (#16). #14 and #15 stay open for their remaining review items; integration into main, final checks and a successor milestone remain.

- Foundation closeout record for milestone 1 (#16): gate status, issue dispositions and the final comparison with K-IRRBB-NMDs, with each gap kept, deferred or left to an owner decision. The milestone is not closed; integration into main, final checks and a successor milestone remain.

- Amended data decisions D4 and D7 after review of #24 (#14): positive `other_change` counts as SMM exposure and prepayment above exposure is rejected (`E15`), so SMM stays within [0, 1]; a `RENEG` transfer is recorded as negative `other_change` and is the numerator when `RENEG` inclusion is selected. Registered `DATA-EXPO-01`.

- Amended validation decisions V1 and V3 after review of #26 (#15): only (origin, horizon) pairs with a complete horizon are scored, others are `INCOMPLETE`; zero realised prepayment uses absolute error and is excluded from the ±10 % test. Registered `DATA-REJECT-01` for all-or-nothing import rejection.

- Owner accepted all validation and Excel evidence decisions (V1-V6, E1-E3) as proposed on 2026-10-21 (#15). Nothing is executed; every case remains registered only. Recorded the owner's report that `release/0.1.0` is protected; the saved rules are not read back.

- Proposed validation plan, numerical test-case register and Excel evidence requirements (#15). Not accepted; every case is registered only and no check, harness or Excel run has been executed.

- Owner accepted all data and model contract decisions (D1-D9, M1-M10) as proposed on 2026-10-21 (#14). Sources remain unverified and nothing is implemented or validated.

- Proposed prepayment data contract, model contracts and source register under docs/methodology (#14). Specifications only, not accepted; every decision is listed as open and no source is verified for this repository.

- Adopted `release/0.1.0`, created from main on 2026-10-21 at the owner's request, as the integration target for task PRs and Dependabot. Documented squash merges into it, owner integration into main and levelling after each integration. No release, tag or version is implied.

- Recorded the owner’s confirmation of ownership/publication permission and clarified that the prototype uses SACCR only as a visual reference (#4). Existing setup-source attributions remain in place.

- Recorded reachable-history secret scan and provenance inspection for #4, including the separate prototype branch; owner distribution confirmation was recorded on 2026-10-20. Corrected security-policy descriptions for live traffic credentials and branding assets.

- Prepayment-specific blue/violet social preview and README image, editable SVG source and documented provenance (#12); planned scope and setup status remain explicit.

- SACCR-aligned 20-label catalogue, synchronisation and drift workflows.
- Setup milestone and 16 issues with owner, priority and milestone.
- Source-first architecture, directory guides, developer setup and future VBA conventions.
- Editing/Git rules with no approved workbook exception.
- Contribution, security, conduct, governance, provenance and release guides; MPL-2.0 text.
- Issue forms, PR template, metadata enforcement and offline regression tests.
- Portable integrity checks, static CI and weekly dependency updates.

## Version rules

Use a dated X.Y.Z heading only after release approval. Keep an Unreleased section for later work and record actual dates/evidence rather than planned releases as completed.

### CI hardening (#8)

- Added pinned Ruff, mypy, YAML and actionlint checks, with checksum verification of the actionlint archive and retained source/tool evidence.
- Enforced portable filenames, tracked documentation links and structured source provenance.
- Added negative fixtures for invalid configuration, provenance, paths and workflows.

### Repository settings (#9)

- Corrected About wording to setup-stage capabilities and added prepayment topics.
- Aligned feature/merge settings and documented main protection, exact integrity check context and the decision to defer release branches.
