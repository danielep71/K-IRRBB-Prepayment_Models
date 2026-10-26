# Governance

## Issue metadata

Every open and closed issue must include **danielep71**, a milestone, exactly one of **P1/P2/P3**, suitable type labels and verifiable acceptance criteria. Titles describe the change; versions belong in milestones. Close issues only with evidence, preserving the record when work is deferred.

The trusted-default-branch metadata workflow handles events and a daily sweep, skips pull requests, and reads back saved metadata. It preserves existing milestones and other assignees/type labels. Missing priority becomes P3; conflicts retain highest severity. Missing milestones use `ISSUE_MILESTONE_NUMBER`, currently **2** (v0.2.0 - Prototype setup), with no fallback. Change the variable to an open successor before closing the configured milestone.

## Branches and review

Default branch: **main**. Active release branch: **release/0.2.0**, created from main on 2026-10-21 for v0.2.0 - Prototype setup. One release branch per milestone, named `release/<milestone version>`, is created from main when the milestone opens and retired after its final integration into main. Subsequent changes use focused task PRs into the release branch, reviewer sign-off and green checks. Integrate the release branch into main and level it with main afterwards. Dependabot targets the release branch.

Issue #9 records activation and read-back verification of the main-branch rules. The required policy is: PR before merge, all review conversations resolved, GitHub Actions `integrity` passing, and branch up to date with main. Force pushes and deletion are blocked, with no bypass actors. There is no mandatory approval count for this sole-maintainer repository; maintainer review remains required by policy. Integration into main uses merge commits. Do not bypass failing checks or rewrite published history.

See [repository settings](REPOSITORY_SETTINGS.md) for the settings baseline and the release-branch rules. The saved GitHub ruleset is authoritative; an issue is not complete until it has been read back and verified.

## Definition of done

Satisfy the issue contract, name the exact source/evidence, cover applicable tests and failure behaviour, update docs/changelog and pass static checks. Excel compile/run evidence and independent numerical checks are additionally required for model behaviour or workbook packaging. Setup completion is not release permission: follow [RELEASING.md](../RELEASING.md).

## Provenance

Only independent work and synthetic examples belong here. Document source/permissions. [Provenance](PROVENANCE.md) records adaptations. Issue #4 records the owner's dated ownership/publication confirmation for the inspected snapshots; adopting the reference licence alone does not establish employer/client/vendor rights or copy an earlier project's approval. New contributions still require appropriate permissions and must exclude confidential or unapproved proprietary material.
