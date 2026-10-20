# Changelog

All work is unreleased. The setup milestone does not imply a version tag or GitHub Release.

## [Unreleased]

- Add daily traffic history, idempotent snapshots, badges and milestone-bound alerts (#11). Use a main-only analytics environment without deployment records; live activation requires TRAFFIC_TOKEN. Upgrade pinned actionlint to 1.7.12 for current environment syntax.

### Added

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
