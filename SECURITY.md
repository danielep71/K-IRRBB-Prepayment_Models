# Security policy

This project is pre-release and currently contains documentation and automation, not a model workbook. No release carries production support. Reports against main are handled best-effort.

## Reporting

Report privately to **danielep71@gmail.com**, subject **Private security report — K-IRRBB Prepayment Models**. GitHub private vulnerability reporting is an alternative if enabled. Never post exploit details, credentials or confidential records in public issues.

Include exact SHA, affected file, impact, prerequisites and a minimal synthetic reproduction. Sanitize diagnostics. Credential owners should revoke/rotate exposed secrets. No SLA or paid bounty is offered.

## Boundaries

Static checks and drift detection are read-only. Label reconciliation and issue metadata automation use issue-write permissions on trusted events. Pull-request code must not receive write credentials. Actions use SHA pins; checkouts do not persist credentials. This batch needs no traffic token.

No VBA runtime, importer or binary exists yet. Future executable code must preserve approved macro controls and document any new file/network/COM access. Never weaken Excel security automatically.

Use synthetic data only. No borrower histories, client/employer records, proprietary methods or vendor source belong in this public repository. Static checks are not a secret scanner or confidentiality guarantee.

Coordinate disclosure with the maintainer while impact and fixes are assessed. Ordinary defects use issue forms; conduct concerns use [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
