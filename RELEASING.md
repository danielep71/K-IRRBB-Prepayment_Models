# Release guide

No versions, tags or workbook artifacts have been released. The active release branch is `release/0.1.0`, created from main on 2026-10-21 at the owner's request. The branch name does not authorize a release. Completing v0.1.0 - Repo setup does not publish a release.

Open task PRs into `release/0.1.0` and squash-merge them once the `integrity` check passes and every review finding is resolved. The owner reviews and integrates the release branch into protected main with a merge commit, under the main rules in [repository settings](docs/REPOSITORY_SETTINGS.md). After each integration into main, level the release branch with main. Code may reach the release branch before release evidence exists; nothing is released without it. Never rewrite published history.

## Future gates

1. Owner explicitly requests a release and scope is recorded.
2. Ownership/licensing and distribution review in issue #4 is resolved.
3. Freeze one candidate SHA, complete the changelog and run checks against it.
4. For VBA/workbooks, record real [Excel evidence](docs/EXCEL_EVIDENCE.md) and the independent numerical references and tolerances of the [case register](docs/methodology/TEST_CASES.md).
5. Build from certified source, inspect and hash artifacts. Source changes invalidate affected evidence.
6. Create an annotated vX.Y.Z tag and publish only approved artifacts; verify the result.

Use semantic versions. Keep changes under Unreleased until approved release preparation; introduce VERSION with the first dated release entry. Do not move published tags or silently replace assets; use a new reviewed version for corrections.
