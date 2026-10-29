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

One release branch per milestone, named `release/<milestone version>`, is created from main when the milestone opens and retired after its final integration into main. `release/0.1.0` was created on 2026-10-21 from main at `3461d891a4e076932c4c21ef30f569d62eafab3e` for v0.1.0 - Repo setup and is retired; its history is in main. `release/0.2.0` was created on 2026-10-21 from main at `14a45c8616cf06b0d1dbbe754a94ab18d8c1efa5` for v0.2.0 - Prototype setup. It is the active release branch and the integration target for task PRs and Dependabot. Task PRs into it are squash-merged once `integrity` passes and review findings are resolved. The maintainer reviews and integrates the release branch into main with a merge commit, as above.

After each integration into main, level the release branch with main by fast-forwarding it or merging the main merge commit into a release branch opened before the integration. Short-lived task branches support PR integration; automatically remove them after merging.

On 2026-10-21 the owner saved and verified the release-branch ruleset that covers `release/0.2.0`: PRs required, the **integrity** check required, branch up to date, review conversations resolved, squash merges allowed, force pushes and deletion blocked, and no bypass actors. A new milestone's release branch needs the same ruleset before it receives task PRs. A release branch name does not authorize a tag or GitHub Release; see [RELEASING.md](../RELEASING.md).

Configure tag protections before introducing tags in an explicitly approved release scope. These settings do not publish a release, grant access, create credentials or change repository visibility. Issue #4 records the ownership/distribution review and owner confirmation for the inspected snapshots; #11 records traffic setup and #12 branding.
