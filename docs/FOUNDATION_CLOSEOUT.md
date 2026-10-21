# v0.1.0 foundation closeout

Status: **open.** Milestone 1 (v0.1.0 - Repo setup) is not closed. This record collects the closeout gates of issue #16 and the final comparison with K-IRRBB-NMDs. It does not authorize a tag, a GitHub Release, a workbook or any model use; see [releasing](../RELEASING.md).

Recorded on 2026-10-21 against `release/0.1.0` at `2755bb0247c70e398a96de6351f5d4305e469a91`. Later changes are not covered; the [check gate](#gates) must be repeated on the final closeout commit.

## Gates

| Gate (issue #16) | State on 2026-10-21 | Owner of the next step |
| --- | --- | --- |
| #14 and #15 completed or explicitly deferred | Every acceptance criterion of both issues is ticked with linked evidence; review findings on #24, #25 and #26 are fixed (#28, #29, #30). Both issues remain open for owner closure | Owner closes #14 and #15 |
| Final NMD gap comparison with a disposition per gap | Recorded [below](#comparison-with-k-irrbb-nmds) | Owner accepts the dispositions |
| Integration of `release/0.1.0` into `main`; governance, settings and milestone documents reconciled | **Not done.** `main` is at `3461d89`; `release/0.1.0` holds every PR from #23 onwards | Owner integrates and levels the release branch |
| Required checks and issue metadata verified on the final closeout commit | **Not done.** Interim evidence below; it does not certify later commits | Repeat after integration |
| Successor milestone selected; `ISSUE_MILESTONE_NUMBER` updated and read back | **Not done.** No successor milestone exists | Owner selects it, then the variable is updated |

Interim evidence:

- `integrity` passed on the head of every PR merged into `release/0.1.0` (#23–#30) and on `release/0.1.0` pushes.
- The issue-metadata workflow, which enforces and reads back owner, milestone and one priority on every issue, succeeded on 2026-10-21 (scheduled sweep and later issue events). A read of issues #1–#16 on 2026-10-21 showed exactly one priority label each.
- The scheduled label-drift check succeeded on 2026-10-21.

## Issue disposition

| Issue | Deliverable | State | Evidence |
| --- | --- | --- | --- |
| #1–#13 | README, layout, Git hygiene, policies, governance, templates, metadata enforcement, static CI, settings, Dependabot, traffic, branding, installation | Closed | Each issue body; commits up to `3461d89` on `main` |
| #14 | Data and model contracts | Open; all criteria evidenced | #24, acceptance #25, review fixes #29 and #30 |
| #15 | Validation plan, test cases, Excel evidence | Open; all criteria evidenced | #26, acceptance #27, review fixes #28 |
| #16 | Changelog, release guide, closeout | Open; this record | This change |

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

| NMD has | Here | Disposition |
| --- | --- | --- |
| `docs/WORKBOOK_CONTRACT.md` | Absent | Deferred to the workbook milestone; no workbook exists |
| `docs/PUBLIC_API.txt` | Absent | Deferred; introduced with the first facade, as [repository structure](REPOSITORY_STRUCTURE.md) requires |
| Milestone guides v0.2.0–v1.0.0 and an approved roadmap | Only v0.1.0 | **Owner decision.** A successor milestone is required before milestone 1 closes |
| VBA source, harness and modules under `src/` and `tests/` | Guides only | Deferred; implementation needs its own milestones |
| Built fixtures and expected files for the data contract | Cases registered only | Deferred; listed as future scope in the [validation plan](methodology/VALIDATION_PLAN.md#future-scope) |
| Workbook builder, export/compare and development tooling under `tools/` | Static checks only | Deferred; same future-scope list |
| Example module under `examples/` | Guide only | Deferred until a public facade exists |
| Sources verified against official texts (`REG-1`, `REG-3` for NMD provisions) | No source verified for prepayments | Deferred; any regulatory overlay waits for verification ([source register](methodology/SOURCES.md)) |

No gap is resolved by copying NMD content. Every deferred item needs a future issue in a successor milestone.

## Closeout steps

1. Owner closes #14 and #15, or records why they stay open.
2. Owner accepts the dispositions above.
3. Owner integrates `release/0.1.0` into `main` and levels the release branch.
4. Re-run the gates on the resulting commit: `integrity`, issue metadata, label drift.
5. Owner creates the successor milestone; `ISSUE_MILESTONE_NUMBER` is updated and read back.
6. Close #16 with this record and the final evidence, then close milestone 1.
