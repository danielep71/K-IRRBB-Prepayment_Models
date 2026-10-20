# Release guide

No versions, tags or workbook artifacts have been released. main is the bootstrap branch; no release branch has been approved. Completing v0.1.0 - Repo setup does not publish a release.

After bootstrap, integrate reviewed PRs with green checks. If the owner later chooses a release branch, document its merge methods and checks, and align Dependabot/milestone automation. Never rewrite published history.

## Future gates

1. Owner explicitly requests a release and scope is recorded.
2. Ownership/licensing and distribution review in issue #4 is resolved.
3. Freeze one candidate SHA, complete the changelog and run checks against it.
4. For VBA/workbooks, record real Excel compile/run evidence and independent numerical references/tolerances.
5. Build from certified source, inspect and hash artifacts. Source changes invalidate affected evidence.
6. Create an annotated vX.Y.Z tag and publish only approved artifacts; verify the result.

Use semantic versions. Keep changes under Unreleased until approved release preparation; introduce VERSION with the first dated release entry. Do not move published tags or silently replace assets; use a new reviewed version for corrections.
