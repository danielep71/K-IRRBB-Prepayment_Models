# Repository settings baseline

Issue #9 records the saved settings and the main ruleset verification; this file specifies the agreed baseline. The setup comparison with K-IRRBB-NMDs is kept in the [foundation closeout](FOUNDATION_CLOSEOUT.md).

| Setting | Baseline |
| --- | --- |
| Visibility | Public |
| Default branch | main |
| Issues / Wiki | Enabled; wiki edits limited to collaborators |
| Projects / Discussions | Disabled |
| Repository merge options | Merge, squash, rebase enabled |
| Automatically delete merged head branches | Enabled |
| Auto-merge | Disabled; integration stays an explicit decision |
| About | Planned Excel/VBA prepayment benchmark; setup stage, no engine/workbook or validated outputs |
| Topics | irrbb, interest-rate-risk, banking-book, prepayment-modeling, loan-prepayments, behavioural-models, alm, model-validation, backtesting, risk-management, excel, vba |

## Main protection

Target the default branch. Require PRs, resolved review threads, an up-to-date branch and the successful GitHub Actions check **integrity** (app 15368). Block branch deletion and force pushes. Use merge commits into main. No bypass actors are configured. Zero required approvals avoids blocking a sole maintainer who cannot approve their own PR; maintainer review is still policy.

The workflow is named `Repository integrity`; the required check is its job, `integrity`. Event-specific metadata or label reconciliation jobs are not required merge checks because they do not run on every PR. Every PR runs the static integrity workflow.

## Branch decision and limits

At the owner's request, `release/0.1.0` was created on 2026-10-21 from main at `3461d891a4e076932c4c21ef30f569d62eafab3e`. It is the active release branch and the integration target for task PRs and Dependabot. Task PRs into it are squash-merged once `integrity` passes and review findings are resolved. The owner reviews and integrates the release branch into main with a merge commit, as above.

After each integration into main, level the release branch with main: the owner fast-forwards it, or the main merge commit is merged into a release branch opened before the integration. Short-lived task branches support PR integration; automatically remove them after merging.

On 2026-10-21 the owner reported that `release/0.1.0` is protected. The saved rules have not been read back into this record; until they are, this is the intended baseline: require PRs and the **integrity** check, block deletion and force pushes, allow squash merges. In practice, merges into it were refused until `integrity` passed on an up-to-date branch and every review conversation was resolved; this is observed behaviour, not a read-back. A release branch name does not authorize a tag or GitHub Release; see [RELEASING.md](../RELEASING.md).

Configure tag protections before introducing tags in an explicitly approved release scope. These settings do not publish a release, grant access, create credentials or change repository visibility. Issue #4 records the ownership/distribution review and owner confirmation for the inspected snapshots; #11 records traffic setup and #12 branding.
