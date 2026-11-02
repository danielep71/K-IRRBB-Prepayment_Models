# Security policy

Main is pre-release and contains setup documentation, accepted methodology specifications, automation and branding, not a model workbook. A separate prototype branch contains experimental VBA and tooling; it is not an accepted or supported release. No release carries production support. Reports against main are handled best-effort.

## Reporting

Report privately to **danielep71@gmail.com**, subject **Private security report — K-IRRBB Prepayment Models**. GitHub private vulnerability reporting is an alternative if enabled. Never post exploit details, credentials or confidential records in public issues.

Include exact SHA, affected file, impact, prerequisites and a minimal synthetic reproduction. Sanitize diagnostics. Credential owners should revoke/rotate exposed secrets. No SLA or paid bounty is offered.

## Boundaries

Static checks and drift detection are read-only. CodeQL scans the Python tooling, the label scripts and the workflows with the `security-extended` suite on pushes and pull requests to `main` and `release/**`, and weekly; its pull-request job has no write permission and uploads nothing, keeping the results as an artifact. Label reconciliation and issue metadata automation use issue-write permissions on trusted events; the pull-request milestone workflow removes milestones from pull requests and never checks out or runs their code. Pull-request code must not receive write credentials. Actions use SHA pins; checkouts do not persist credentials. The daily traffic workflow's collect job alone requests the main-only `analytics` environment, where a dedicated GitHub App with only Administration: read issues a short-lived token to read GitHub traffic. The built-in token pushes the isolated traffic history from that job, and a separate alert job, with no environment, opens conditional alert issues. The environment uses `deployment: false`; see [traffic controls](docs/TRAFFIC.md).

The VBA modules are rate conversions, data-format primitives with a pure-VBA SHA-256, import validation on bytes, the import adapter `WB_Import` and a test harness whose fixtures are generated into the test build. Their only file access is the one agreed in decision W10 of the [workbook contract](docs/WORKBOOK_CONTRACT.md#file-access): `WB_Import` reads the three CSV files the user selects, read-only and whole, and keeps no directory path; the tests read no file. They have no network, operating-system or COM access. The repository's only approved binary is a digest-pinned branding PNG. Prototype and future executable code must preserve approved macro controls and document any new file/network/COM access. Never weaken Excel security automatically.

Use synthetic data only. No borrower histories, client/employer records, proprietary methods or vendor source belong in this public repository. Static checks are not a secret scanner or confidentiality guarantee.

Coordinate disclosure with the maintainer while impact and fixes are assessed. Ordinary defects use issue forms; conduct concerns use [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
