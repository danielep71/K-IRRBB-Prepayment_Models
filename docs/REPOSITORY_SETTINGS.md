# Repository settings baseline

The baseline is data: [`repository-settings.json`](repository-settings.json) holds the general settings, the security features, the GitHub Actions settings and the managed rulesets. [`tools/setup_repository.py`](../tools/setup_repository.py) compares it with the live repository through an authenticated GitHub CLI, so drift is detectable. This guide explains the rules; the JSON is authoritative for their values. The tool is adapted from MyTemplate `887f4b7`.

## Checking and applying

```sh
python tools/setup_repository.py --repo danielep71/K-IRRBB-Prepayment_Models          # preview; prints PLAN SHA-256
python tools/setup_repository.py --repo danielep71/K-IRRBB-Prepayment_Models --check \
    --report docs/reviews/YYYY-MM-DD-repository-settings.md \
    --evidence docs/reviews/repository-settings-{date}.json                           # read-only; exit 1 on drift
python tools/setup_repository.py --repo danielep71/K-IRRBB-Prepayment_Models --apply \
    --approve-plan PLAN_SHA256 --journal docs/reviews/settings-journal-YYYY-MM-DD.json  # approved plan, then read back
```

- **Preview and `--check` only read**, and need no admin rights. A value my token cannot read (a security feature, an Actions setting, a ruleset's bypass list, which GitHub reports only to a token that can write the ruleset) is shown as unknown, with its endpoint and HTTP status, and counts as drift; it is never taken as matching. A ruleset response without `bypass_actors` makes that ruleset `unknown`.
- **The plan has a digest.** Preview ends with `PLAN SHA-256`: the SHA-256 of the repository name, the configuration's SHA-256, every observed managed value and the exact planned writes. `--check`, `--report` and `--evidence` print or record it.
- **`--apply` writes only the approved plan.** It needs my admin token, `--approve-plan` with the digest preview printed and a new `--journal` path. It reads the repository again and refuses before any write when the digest differs, the journal exists, a managed value is unknown, the repository is archived, or `integrity` has not passed on the current `main`. The journal (JSON) is written before the first write and after each result, with each write's status and the read-back result; a failing write stops the run, and nothing is retried or rolled back. A ruleset that exists under the same name but differs is replaced only with `--update-existing`.
- **Records.** `--report` writes a dated Markdown record and `--evidence` a JSON record (`{date}` becomes the UTC date) with the configuration's path and SHA-256, every managed value as configured and as GitHub reports it with its source, each ruleset's status and the planned writes without their payloads. I commit them under `docs/reviews/`.
- **Equivalent protection.** A managed ruleset that other active rulesets already enforce at least as strictly, under any name, is `covered`: no write is planned for it. A ruleset counts only with the same target, a reported and empty bypass list, no excluded refs and every configured ref in its scope; each configured rule must be present with parameters at least as strict. Coverage is judged on the rulesets as the plan leaves them; a weaker named ruleset is replaced whatever else enforces it.
- Rulesets outside the baseline are reported as unmanaged and never changed or deleted; I delete one by hand when a managed ruleset replaces it. The script never runs in CI, and nothing else writes these settings.
- `tools/test_setup_repository.py` tests the script offline against a fake API, using MyTemplate's baseline as a fixture, and checks this repository's baseline separately.

## Merge methods

The repository allows merge commits and squash merges, and not rebase merges. The rulesets narrow them per branch: merge commits only into main, and merge or squash into a release branch. Task PRs are squash-merged; integration and sync PRs use merge commits.

## Rulesets

| Ruleset | Applies to | Rules |
| --- | --- | --- |
| Protect main | the default branch | PRs with resolved review threads, merge commits only, the `integrity` check on an up-to-date branch; no deletion or force push |
| Protect release branches | `release/**` | PRs with resolved review threads, merge or squash, the `integrity` check on an up-to-date branch; no deletion or force push |
| Protect release tags | `v*` tags | no deletion, update or force push |
| Protect traffic history | `traffic-history` | no deletion or force push; the traffic workflow pushes to it |

No ruleset has bypass actors, and none requires an approving review: I cannot approve my own PRs, and my review remains required by policy. `release/**` covers every release branch, so a new milestone's branch is protected from its creation.

The required check is the `integrity` job of the `Repository integrity` workflow (GitHub Actions, app 15368). Event-specific metadata, triage or label jobs are not required checks because they do not run on every PR. *CodeQL*, *Link check* and the *Minimum runtimes* job are not required checks either.

## Security features

Private vulnerability reporting, Dependabot alerts, secret scanning and push protection are on. Dependabot security updates are off: GitHub opens those PRs against `main`, outside the release-branch flow, so I take a security update through a task PR into the active release branch instead. Security updates that GitHub reports as enabled but paused are recorded as `on (paused)`: they are still enabled, so with the baseline off they count as drift until they are turned off.

## GitHub Actions settings

The baseline states five Actions settings, which the script reads and compares but never writes; a difference is set by hand in **Settings → Actions → General**, then confirmed with `--check`:

| Setting | Baseline |
| --- | --- |
| `sha_pinning_required` | `true`: every action must be pinned to a full commit SHA, as the integrity gate already requires |
| `default_workflow_permissions` | `read`: workflows get a read-only `GITHUB_TOKEN` unless a job asks for more |
| `can_approve_pull_request_reviews` | `false`: workflows cannot approve pull requests |
| `fork_pr_approval_policy` | `all_external_contributors`: workflows from every outside fork wait for my approval |
| `retention_days` | `90`: artifact and log retention, GitHub's default for public repositories; workflow artifacts set shorter periods |

## Settings outside the baseline

Visibility (public; `visibility` is `null` in the JSON, so it is reported, not checked), the default branch (`main`), the About text and topics, and wiki edit permissions are not managed. A change to them needs an issue, and these settings never publish a release, grant access or create credentials.

## Branches

Each milestone has one release branch, named `release/<milestone version>`, which I create from main when the milestone opens and retire after its final integration into main. The active release branch, the one `target-branch` names in [`.github/dependabot.yml`](../.github/dependabot.yml), is the integration target for task PRs and Dependabot. Task PRs into it are squash-merged once `integrity` passes and review findings are resolved. I review the release branch and integrate it into main with a merge commit.

After each integration into main, the release branch is levelled with main: I fast-forward it, or the main merge commit is merged into the release branch. Merged task branches are deleted automatically. A release branch name does not authorize a tag or GitHub Release; see [RELEASING.md](../RELEASING.md).
