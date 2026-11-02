# Repository traffic analytics

`Daily traffic export` collects GitHub views, clones, referrers and popular
paths at 06:23 UTC every day, off the hour because GitHub delays scheduled runs
most on the hour. You can also run it from the Actions tab using `main`. It
runs separately from CI and does not validate VBA or models. Its Python lives in
`tools/traffic_history.py`, unit-tested by `tools/test_traffic_history.py` under
`python tools/check.py`; `tools/quality_test_traffic.py` checks the workflow's
credentials, job permissions and schedule.

## Jobs

| Job | Permissions | Environment | Does |
| --- | --- | --- | --- |
| `collect` | `contents: write` | `analytics` | Creates the App token, fetches the traffic API, merges into `traffic-history` and pushes |
| `alert` | `contents: read`, `issues: write` | none | Reads `traffic-history` and opens the day's alert issue, if one is due |

The alert job declares no environment, so it never receives the App's key or
token; only the collect job can push the history.

## Credentials and access

The traffic API needs **Administration: read**, which the built-in workflow
token cannot have. A dedicated GitHub App supplies it:

1. Create a GitHub App owned by `danielep71`, with no webhook and one
   repository permission, **Administration: Read-only**; nothing else.
2. Install it on this repository only.
3. In the `analytics` environment, set the variable `TRAFFIC_APP_CLIENT_ID`
   to the App's client ID and the secret `TRAFFIC_APP_PRIVATE_KEY` to a
   private key generated for it. Never commit either.
4. Delete the old `TRAFFIC_TOKEN` secret and revoke that personal access
   token; the workflow no longer reads it.

Each run creates a short-lived installation token with
`actions/create-github-app-token`, limited to Administration: read on this
repository. It expires after an hour and is revoked when the job ends, so
nothing needs rotating; replace the private key immediately after suspected
exposure. A missing variable or secret fails the run with a message naming them.

- Environment: `analytics`, with branch access restricted to `main`.
- `deployment: false` retains environment access controls without creating deployments.
- Only the token step receives the key, and only the fetch step the token;
  neither runs repository code. GitHub's built-in `GITHUB_TOKEN` writes the
  history branch and creates alert issues.
- Keep the environment out of build, test and release jobs. Any workflow on an
  allowed branch can request it; its name is not a boundary that binds the key
  to this one workflow.

## Outputs

The first successful run creates the orphan `traffic-history` branch. Runs
maintain `data/traffic.csv`, `data/traffic_daily.csv`,
`data/referrers.csv`, `data/popular_paths.csv` and badge JSON files.
Repeated runs on the same day replace that day's snapshot rather than duplicate
it. A failed remote lookup or fetch stops the workflow instead of replacing
existing history.

GitHub's traffic API returns a rolling 14-day window; retained snapshots keep
a longer record. Unique visitors over several days cannot be obtained by adding
daily unique counts. The visitors badge is the 14-day unique count; the visits
badge sums daily unique counts and can count a returning visitor on several days.

The repository is public, so the `traffic-history` branch is readable by
anyone. It holds aggregate counts only (views, clones, referrers, popular
paths), the same data GitHub shows repository admins, and no visitor
identities. Its badge JSON files can therefore back shields.io endpoint badges.
Traffic does not require GitHub Pages.

After at least two snapshots, a views spike (the 14-day count at least doubles
and grows by 100), more stars or forks, or a new referrer with at least five
views create a `repository` / `P3` issue assigned to `danielep71` in the
open milestone with the earliest due date after today (UTC), as the
issue-metadata workflow chooses it. There is no fallback: if no open milestone
is due after today, the run fails with a message saying so; give the active
milestone a due date.
The workflow prevents duplicate alerts for the same day. Clones are never an
alert reason, because every workflow checkout of this repository counts as a
clone; they are still recorded in the CSV files, shown in the alert and counted
in the clones badge.

## Verification

After integration into `main`, use **Actions → Daily traffic export → Run
workflow → main**. Confirm that the run succeeds, that `traffic-history`
contains the expected files, and that they hold aggregate counts only.
A run from a different branch is skipped. A missing App configuration or API error
fails the run; it must not be reported as a successful traffic snapshot.

## Repository backlog metric

`data/traffic.csv` uses `open_issues_and_prs` for the REST repository count,
which includes both open issues and pull requests. It is not an issue-only
backlog. The next export renames the legacy `open_issues` column while
preserving its historical values; no historical issue-only count is inferred.
Consumers of the CSV must use the new column name.

## Implementation and activation

Adapted from K-IRRBB-NMDs commit `973501c82f2f9011acfdc9d741ab2af0132cb96c`.
Checkout credentials are not persisted; an ephemeral credential helper uses the
built-in token only for the history push. The App token is scoped only to the
API-fetch step. The history branch never merges into main. A merge validates
every API response and every existing history file first, and writes nothing
if any is invalid.

The first snapshot may include up to 14 days preceding activation. Cumulative
badges describe the retained daily history, not the repository's entire lifetime.
Snapshots cannot recover gaps longer than GitHub's retention window.

The App, its variable and its secret must be configured before the first successful run.
Until then, badges may show unavailable data; they must not be read as zero.

GitHub documents the no-deployment setting in
[Deploying to a specific environment](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/deploy-to-environment).
