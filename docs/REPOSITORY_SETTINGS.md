# Repository settings baseline

The baseline is data: [`repository-settings.json`](repository-settings.json) holds the general settings, the security features and the managed rulesets. [`tools/setup_repository.py`](../tools/setup_repository.py) compares it with the live repository through an authenticated GitHub CLI, so drift is detectable. This guide explains the rules; the JSON is authoritative for their values.

## Checking and applying

```sh
python tools/setup_repository.py --repo danielep71/K-IRRBB-Prepayment_Models            # preview, no changes
python tools/setup_repository.py --repo danielep71/K-IRRBB-Prepayment_Models --check \
    --report docs/reviews/YYYY-MM-DD-repository-settings.md                             # read-only; exit 1 on drift
python tools/setup_repository.py --repo danielep71/K-IRRBB-Prepayment_Models --apply    # change, then read back
```

- The script needs my admin token (`gh auth login`); it never runs in CI and nothing else writes these settings.
- `--check` is read-only; with `--report` it writes a dated Markdown evidence record of every managed setting as GitHub reports it, which I commit under `docs/reviews/`.
- `--apply` creates missing rulesets and changes settings, then reads everything back and fails if anything still differs. It refuses to run unless `integrity` has passed on the current `main`. A ruleset that exists under the same name but differs is replaced only with `--update-existing`, after I have read the preview.
- Rulesets outside the baseline are reported as unmanaged and never changed or deleted; I delete one by hand when a managed ruleset replaces it.
- `tools/test_setup_repository.py` tests the script offline against a fake API.

## Rulesets

| Ruleset | Applies to | Rules |
| --- | --- | --- |
| Protect main | the default branch | PRs with resolved review threads, merge commits only, the `integrity` check on an up-to-date branch; no deletion or force push |
| Protect release branches | `release/**` | PRs with resolved review threads, merge or squash, the `integrity` check on an up-to-date branch; no deletion or force push |
| Protect release tags | `v*` tags | no deletion, update or force push |
| Protect traffic history | `traffic-history` | no deletion or force push; the traffic workflow pushes to it |

No ruleset has bypass actors, and none requires an approving review: I cannot approve my own PRs, and my review remains required by policy. `release/**` covers every release branch, so a new milestone's branch is protected from its creation.

The required check is the `integrity` job of the `Repository integrity` workflow (GitHub Actions, app 15368). Event-specific metadata, triage or label jobs are not required checks because they do not run on every PR. *CodeQL*, *Link check* and the *Minimum Python* job are not required checks either.

## Security features

Private vulnerability reporting, Dependabot alerts, secret scanning and push protection are on. Dependabot security updates are off: GitHub opens those PRs against `main`, outside the release-branch flow, so I take a security update through a task PR into the active release branch instead.

## Settings outside the baseline

Visibility (public), the default branch (`main`), the About text and topics, and wiki edit permissions are not in the JSON. A change to them needs an issue, and these settings never publish a release, grant access or create credentials.

## Branches

Each milestone has one release branch, named `release/<milestone version>`, which I create from main when the milestone opens and retire after its final integration into main. The active release branch, the one `target-branch` names in [`.github/dependabot.yml`](../.github/dependabot.yml), is the integration target for task PRs and Dependabot. Task PRs into it are squash-merged once `integrity` passes and review findings are resolved. I review the release branch and integrate it into main with a merge commit.

After each integration into main, the release branch is levelled with main: I fast-forward it, or the main merge commit is merged into the release branch. Merged task branches are deleted automatically. A release branch name does not authorize a tag or GitHub Release; see [RELEASING.md](../RELEASING.md).
