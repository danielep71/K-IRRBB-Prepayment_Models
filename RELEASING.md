# Release guide

No versions, tags or workbook artifacts have been released. Each milestone has one release branch, named `release/<milestone version>`, which I create from main when the milestone opens and retire after its final integration into main. The active release branch is the branch that `target-branch` names in [`.github/dependabot.yml`](.github/dependabot.yml); CI fails if that branch does not exist. When a milestone opens, its first PR points the Dependabot `target-branch` entries at the new branch. Dependabot reads its configuration only from main, so I integrate that PR into main before I delete the previous release branch. Neither a branch name nor closing a milestone authorizes or publishes a release.

Task PRs go into the active release branch and are squash-merged once the `integrity` check passes and every review finding is resolved. I review the release branch and integrate it into protected main with a merge commit, under the main rules in [repository settings](docs/REPOSITORY_SETTINGS.md). After each integration into main, I level the release branch with main. Code may reach the release branch before release evidence exists; nothing is released without it. Published history is never rewritten.

## Future gates

1. I explicitly request a release, and its scope is recorded.
2. My ownership, licensing and distribution review, recorded in [provenance](docs/PROVENANCE.md), covers the candidate, including material added since that review.
3. Freeze one candidate SHA, complete the changelog and run checks against it.
4. For VBA/workbooks, record real [Excel evidence](docs/EXCEL_EVIDENCE.md) and the independent numerical references and tolerances of the [case register](docs/methodology/TEST_CASES.md).
5. Build from certified source, inspect and hash artifacts. Source changes invalidate affected evidence.
6. Create an annotated vX.Y.Z tag and publish only approved artifacts; verify the result.

Versions are semantic. Changes stay under Unreleased until I approve release preparation; `VERSION` arrives with the first dated release entry. Published tags are never moved and assets never silently replaced; a correction is a new reviewed version.
