# Repository settings baseline

Reference: K-IRRBB-NMDs settings inspected on 2026-10-20. Issue #9 records the saved settings and ruleset verification; this file specifies the agreed setup baseline.

| Setting | Prepayment baseline | NMD comparison |
| --- | --- | --- |
| Visibility | Public | Same |
| Default branch | main | Same |
| Issues / Wiki | Enabled; wiki edits limited to collaborators | Features match |
| Projects / Discussions | Disabled | Same |
| Repository merge options | Merge, squash, rebase enabled | Same |
| Automatically delete merged head branches | Enabled | Same |
| Auto-merge | Disabled | Retain explicit integration decision |
| About | Planned Excel/VBA prepayment benchmark; setup only, no engine/workbook or validated outputs | Adapted domain/status |
| Topics | irrbb, interest-rate-risk, banking-book, prepayment-modeling, loan-prepayments, behavioural-models, alm, model-validation, backtesting, risk-management, excel, vba | Replace deposit-specific topics |

## Main protection

Target the default branch. Require PRs, resolved review threads, an up-to-date branch and the successful GitHub Actions check **integrity** (app 15368). Block branch deletion and force pushes. Use merge commits into main, matching NMD's integration convention. No bypass actors are configured. Zero required approvals avoids blocking a sole maintainer who cannot approve their own PR; maintainer review is still policy.

NMD's check is named `Repository integrity`; this repository's actual job/check is `integrity`. Event-specific metadata or label reconciliation jobs are not required merge checks because they do not run on every PR. Every PR runs the static integrity workflow.

## Branch decision and limits

Keep main as the only long-lived development branch during setup. The owner has not requested a release branch. Short-lived task branches support PR integration; automatically remove them after merging. Do not copy NMD's release version, bypass exceptions or historical release branch names.

Configure release-branch and tag protections before introducing those artifacts in an explicitly approved release scope. This setup does not publish a release, grant access, create credentials or change repository visibility. Issue #4 records the ownership/distribution review and owner confirmation for the inspected snapshots; #11 records traffic setup and #12 branding.
