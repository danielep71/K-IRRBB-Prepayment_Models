# Governance

## Issue metadata

Milestones belong to issues only: the *Keep milestones issue-only* workflow removes any milestone set on a pull request. Every open and closed issue must include **danielep71**, a milestone, exactly one of **P1/P2/P3** (P1 only on a confirmed calculation bug, labelled `bug`), suitable type labels and verifiable acceptance criteria. Every open issue also needs a target end date before its milestone's due date, as a `- Target end date: YYYY-MM-DD` line or the issue-form field, and a *Dependencies* section that names its prerequisites (`#N`), an external condition on a line starting `External condition:`, or none; it carries `blocked` exactly while a named prerequisite is open or an external condition holds. Titles describe the change; versions belong in milestones. Close issues only with evidence, preserving the record when work is deferred.

The trusted-default-branch metadata workflow handles events and a daily sweep, skips pull requests, and reads back saved metadata. It adds **danielep71** as assignee, and gives an issue without a milestone the open milestone with the earliest due date after today; with none, it fails with a message saying so, so give the active milestone a due date. It never sets or changes a priority, and preserves existing milestones and other assignees and labels.

The read-only *Issue triage* workflow (`tools/check_issues.py`) audits every open issue on issue and milestone events, and by hand, against the rules above: assignee, exactly one priority, P1 only on bugs, an open milestone, the target end date, the dependency section, catalogue labels and `blocked`. It never changes an issue; a failed run lists what I must decide, and I resolve each finding by hand. The issue forms preset a priority (P2 for bugs and features, P3 for documentation) and ask for the dependencies and the target end date; I confirm the priority at triage.

## Branches and review

Default branch: **main**. Active release branch: the branch that `target-branch` names in [`.github/dependabot.yml`](../.github/dependabot.yml). One release branch per milestone, named `release/<milestone version>`, is created from main when the milestone opens and retired after its final integration into main. Subsequent changes use focused task PRs into the release branch, reviewer sign-off and green checks. The owner integrates the release branch into main and levels it with main afterwards. Dependabot targets the release branch.

Issue #9 records activation and read-back verification of the main-branch rules. The required policy is: PR before merge, all review conversations resolved, GitHub Actions `integrity` passing, and branch up to date with main. Force pushes and deletion are blocked, with no bypass actors. There is no mandatory approval count for this sole-maintainer repository; maintainer review remains required by policy. Integration into main uses merge commits. Do not bypass failing checks or rewrite published history.

Pull requests link issues by kind:

| Pull request | Base ← head | Issue link |
| --- | --- | --- |
| Task | active release branch ← task branch | `Resolves #N` |
| Integration | main ← active release branch | `Refs #N` for the issues and PRs it carries |
| Sync | active release branch ← main | `Refs #N` for the integration PR |

GitHub closes an issue from a keyword only when the PR merges into main, so close a task's issue by hand once its evidence is complete. An integration or sync PR never uses a closing keyword: it would close every named issue, including one still waiting for evidence. Before merging any PR, record its final-head review in the template: the final head SHA, the reviewed SHA, the review result and the CI run. Any push after that renews the review, the CI run and the record.

See [repository settings](REPOSITORY_SETTINGS.md) for the settings baseline and the release-branch rules. The saved GitHub ruleset is authoritative; an issue is not complete until it has been read back and verified.

## Definition of done

Satisfy the issue contract, name the exact source/evidence, cover applicable tests and failure behaviour, update docs/changelog and pass static checks. Excel compile/run evidence and independent numerical checks are additionally required for model behaviour or workbook packaging. Setup completion is not release permission: follow [RELEASING.md](../RELEASING.md).

## Provenance

Only independent work and synthetic examples belong here. Document source/permissions. [Provenance](PROVENANCE.md) records adaptations. Issue #4 records the owner's dated ownership/publication confirmation for the inspected snapshots; adopting the reference licence alone does not establish employer/client/vendor rights or copy an earlier project's approval. New contributions still require appropriate permissions and must exclude confidential or unapproved proprietary material.
