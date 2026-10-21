# v0.1.0 foundation closeout

Status: **complete.** Every closeout gate of issue #16 was met on 2026-10-21; milestone 1 (v0.1.0 - Repo setup) closes once this record is integrated into `main`. This record collects the closeout gates of issue #16 and the final comparison with K-IRRBB-NMDs. It does not authorize a tag, a GitHub Release, a workbook or any model use; see [releasing](../RELEASING.md).

First recorded on 2026-10-21 against `release/0.1.0` at `2755bb0247c70e398a96de6351f5d4305e469a91`. Final state on 2026-10-21: all setup work integrated into `main` at `2bd2ecf377e4ef87445ccecf6916db4613321634` (#47), with `release/0.1.0` levelled at `776015032633b6c2a9f5a1edf2ed916503b9b72d` (#48). Later changes are not covered.

## Gates

| Gate (issue #16) | State on 2026-10-21 | Owner of the next step |
| --- | --- | --- |
| #14 and #15 completed or explicitly deferred | **Done.** The owner kept the convention merged in #30 for drawdown exposure and `RENEG` transfers; every item in both issue bodies was ticked with linked evidence, and both issues were closed as completed on 2026-10-21 | — |
| Final NMD gap comparison with a disposition per gap | **Done.** Recorded [below](#comparison-with-k-irrbb-nmds); the owner accepted every disposition on 2026-10-21 | — |
| Integration of `release/0.1.0` into `main`; governance, settings and milestone documents reconciled | **Done.** #34 (`f43107a`) and #47 (`2bd2ecf`) merged the release branch into `main` on the owner's instruction; #35 (`d0114c1`) and #48 (`7760150`) levelled `release/0.1.0` with `main` | — |
| Required checks and issue metadata verified on the final closeout commit | **Done.** On `main` at `2bd2ecf`: `integrity` passed on the push and in #48; issue-metadata enforcement passed; label drift passed in a manual run ([39648607572](https://github.com/danielep71/K-IRRBB-Prepayment_Models/actions/runs/39648607572)) | — |
| Successor milestone selected; `ISSUE_MILESTONE_NUMBER` updated and read back | **Done.** The owner created milestone 2, v0.2.0 - Prototype setup, and read back `ISSUE_MILESTONE_NUMBER = 2` on 2026-10-21 | — |

Supporting evidence:

- `integrity` passed on the head of every PR merged into `release/0.1.0` or `main` from #23 to #48, and on the `main` pushes after #34 and #47.
- The issue-metadata workflow, which enforces and reads back owner, milestone and one priority on every issue, succeeded on 2026-10-21 (scheduled sweep and later issue events). A read of issues #1–#16 on 2026-10-21 showed exactly one priority label each.
- Label drift succeeded in its scheduled run and in the manual run on `main` at `2bd2ecf` on 2026-10-21.

## Issue disposition

| Issue | Deliverable | State | Evidence |
| --- | --- | --- | --- |
| #1–#13 | README, layout, Git hygiene, policies, governance, templates, metadata enforcement, static CI, settings, Dependabot, traffic, branding, installation | Closed | Each issue body; commits up to `3461d89` on `main` |
| #14 | Data and model contracts | Closed as completed, 2026-10-21 | #24, acceptance #25, review fixes #29 and #30 |
| #15 | Validation plan, test cases, Excel evidence | Closed as completed, 2026-10-21 | #26, acceptance #27, review fixes #28, #29 and #30 |
| #16 | Changelog, release guide, closeout | Closes when this record is integrated into `main` | #32, #33, #36, #46 and this change |

Prototype PR #19 is separate future implementation work. It is neither setup evidence nor a release requirement.

## Comparison with K-IRRBB-NMDs

Reference: K-IRRBB-NMDs at `f703c7ab6bff207b5ce5917af8368cb24ea23f13`, inspected on 2026-10-21.

### Matched

| Area | Here |
| --- | --- |
| Editor, Git attributes and ignore rules | Adapted (#3) |
| Licence, conduct, security, contributing | Adapted (#4) |
| Governance, labels, issue forms, PR template, metadata enforcement | Adapted (#5–#7) |
| Static integrity CI with pinned tools | Adapted (#8) |
| Dependabot, traffic history, branding | Adapted (#10–#12) |
| Methodology README, data contract, model contracts, source register | Written for prepayments (#14) |
| Validation plan, test-case register, Excel evidence | Written for prepayments (#15) |
| Changelog, release guide, milestone guide | Present (#16) |

### Deliberate differences

| NMD | Here | Reason |
| --- | --- | --- |
| No settings or provenance register | `docs/REPOSITORY_SETTINGS.md`, `docs/PROVENANCE.md`, `docs/provenance.json`, `docs/reviews/` | Added for #4 and #9; kept |
| Social preview built from HTML | Editable SVG source | #12; kept |
| Release branch named for the NMD version | `release/0.1.0`, created at the owner's request | Not copied from NMD |

### Gaps and dispositions

| NMD has | Here | Disposition | Issue |
| --- | --- | --- | --- |
| `docs/WORKBOOK_CONTRACT.md` | Absent | Deferred to the workbook milestone; no workbook exists | #38 |
| `docs/PUBLIC_API.txt` | Absent | Deferred; introduced with the first facade, as [repository structure](REPOSITORY_STRUCTURE.md) requires | #39 |
| Milestone guides v0.2.0–v1.0.0 and an approved roadmap | Only v0.1.0 | Successor milestone v0.2.0 - Prototype setup created by the owner on 2026-10-21; its guide is deferred | #40 |
| VBA source, harness and modules under `src/` and `tests/` | Guides only | Deferred; implementation needs its own milestones | #42 |
| Built fixtures and expected files for the data contract | Cases registered only | Deferred; listed as future scope in the [validation plan](methodology/VALIDATION_PLAN.md#future-scope) | #41 |
| Workbook builder, export/compare and development tooling under `tools/` | Static checks only | Deferred; same future-scope list | #43 |
| Example module under `examples/` | Guide only | Deferred until a public facade exists | #44 |
| Sources verified against official texts (`REG-1`, `REG-3` for NMD provisions) | No source verified for prepayments | Deferred; any regulatory overlay waits for verification ([source register](methodology/SOURCES.md)) | #45 |

No gap is resolved by copying NMD content. Every deferred item has an issue in milestone v0.2.0 - Prototype setup, created on 2026-10-21 with owner `danielep71` and one priority. The owner accepted these dispositions on 2026-10-21.

## Closeout steps

1. ~~Owner closes #14 and #15~~: closed on 2026-10-21.
2. ~~Owner accepts the dispositions above~~: accepted on 2026-10-21.
3. ~~Owner integrates `release/0.1.0` into `main` and levels the release branch~~: #34 and #35 on 2026-10-21.
4. ~~Owner creates the successor milestone; `ISSUE_MILESTONE_NUMBER` is updated~~: milestone 2 created and `ISSUE_MILESTONE_NUMBER = 2` read back by the owner, 2026-10-21.
5. ~~Create one issue in the successor milestone for each deferred gap~~: #38–#45 in v0.2.0 - Prototype setup, 2026-10-21.
6. ~~Integrate the closeout into `main` and re-run the gates~~: #47 and #48; all three gates passed on `2bd2ecf`, 2026-10-21.
7. Integrate this documentation correction into `main`, then close #16 and milestone 1.
