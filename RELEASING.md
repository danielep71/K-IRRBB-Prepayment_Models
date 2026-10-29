# Release guide

No versions, tags or workbook artifacts have been released. One release branch per milestone, named `release/<milestone version>`, is created from main when the milestone opens and retired after its final integration into main. The active release branch is `release/0.2.0`, created from main at `14a45c8` on 2026-10-21 for v0.2.0 - Prototype setup. `release/0.1.0` served v0.1.0 - Repo setup; its history is in main and it is retired. When a milestone opens, its first PR points `ACTIVE_RELEASE_BRANCH` and the Dependabot target at the new branch; Dependabot reads its configuration only from main, so integrate that PR into main before deleting the previous release branch. A branch name does not authorize a release. Closing v0.1.0 - Repo setup on 2026-10-21 did not publish a release.

Open task PRs into the active release branch and squash-merge them once the `integrity` check passes and every review finding is resolved. The maintainer reviews and integrates the release branch into protected main with a merge commit, under the main rules in [repository settings](docs/REPOSITORY_SETTINGS.md). After each integration into main, level the release branch with main. Code may reach the release branch before release evidence exists; nothing is released without it. Never rewrite published history.

## Future gates

1. Explicit maintainer release authorization and its scope are recorded.
2. The ownership/licensing and distribution review recorded in issue #4 covers the candidate, and material added since has been reviewed.
3. Freeze one candidate SHA, complete the changelog and run checks against it.
4. For VBA/workbooks, record real [Excel evidence](docs/EXCEL_EVIDENCE.md) and the independent numerical references and tolerances of the [case register](docs/methodology/TEST_CASES.md).
5. Build from certified source, inspect and hash artifacts. Source changes invalidate affected evidence.
6. Create an annotated vX.Y.Z tag and publish only approved artifacts; verify the result.

Use semantic versions. Keep changes under Unreleased until approved release preparation; introduce VERSION with the first dated release entry. Do not move published tags or silently replace assets; use a new reviewed version for corrections.
