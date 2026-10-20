# Governance

## Issue metadata

Every open and closed issue must include **danielep71**, a milestone, exactly one of **P1/P2/P3**, suitable type labels and verifiable acceptance criteria. Titles describe the change; versions belong in milestones. Close issues only with evidence, preserving the record when work is deferred.

The trusted-default-branch metadata workflow handles events and a daily sweep, skips pull requests, and reads back saved metadata. It preserves existing milestones and other assignees/type labels. Missing priority becomes P3; conflicts retain highest severity. Missing milestones use `ISSUE_MILESTONE_NUMBER`, intended to be **1** for setup, with no fallback. Change the variable to an open successor before closing the configured milestone.

## Branches and review

Current branch: **main**. No release branch exists. Initial bootstrap establishes checks and documentation. Subsequent changes use focused task PRs, reviewer sign-off and green checks. Do not create a release branch solely to copy NMD's current version. If the owner chooses one later, align Dependabot, milestone guides and rules.

Issue #9 records activation and read-back verification of the main-branch rules. The required policy is: PR before merge, all review conversations resolved, GitHub Actions `integrity` passing, and branch up to date with main. Force pushes and deletion are blocked, with no bypass actors. There is no mandatory approval count for this sole-maintainer repository; maintainer review remains required by policy. Main accepts merge commits, as in NMD. Do not bypass failing checks or rewrite published history.

See [repository settings](REPOSITORY_SETTINGS.md) for the comparison and deliberate differences. The saved GitHub ruleset is authoritative; an issue is not complete until it has been read back and verified.

## Definition of done

Satisfy the issue contract, name the exact source/evidence, cover applicable tests and failure behaviour, update docs/changelog and pass static checks. Excel compile/run evidence and independent numerical checks are additionally required for model behaviour or workbook packaging. Setup completion is not release permission: follow [RELEASING.md](../RELEASING.md).

## Provenance

Only independent work and synthetic examples belong here. Document source/permissions. [Provenance](PROVENANCE.md) records adaptations. Issue #4 stays open for the owner's ownership/distribution review; adopting the reference licence does not establish employer/client/vendor rights or copy an earlier project's approval.
