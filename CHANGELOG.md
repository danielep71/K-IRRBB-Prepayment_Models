# Changelog

All work is unreleased. The setup milestone does not imply a version tag or GitHub Release.

## [Unreleased]

- Add daily traffic history, idempotent snapshots, badges and milestone-bound alerts (#11). Use a main-only analytics environment without deployment records; live activation requires TRAFFIC_TOKEN. Upgrade pinned actionlint to 1.7.12 for current environment syntax.

### Added

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
