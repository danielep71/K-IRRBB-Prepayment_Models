# Excel evidence

Status: **proposed in issue #15, not accepted. No Excel evidence exists.** There is no workbook, builder, test harness or export tool yet, so every stage below is currently `NOT_RUN`. Open [decisions](#decisions) are listed at the end.

This document is authoritative for the Excel evidence record: what a build, compile and test run must capture, how it is bound to one commit, and which outcomes count. Numerical validation is separate and is defined in the [validation plan](methodology/VALIDATION_PLAN.md). Supported hosts are in [installation](../INSTALLATION.md); release gates are in [releasing](../RELEASING.md).

`python tools/check.py` and CI never compile VBA or run Excel. Only a record made on a real Excel host, bound to an exact commit, is Excel evidence.

## Outcomes

Every stage of a record has exactly one outcome.

| Outcome | Meaning | Counts as a pass |
| --- | --- | :---: |
| `PASS` | The stage ran on the stated host and met every expectation | ✅ |
| `FAIL` | The stage ran and at least one expectation was not met | ❌ |
| `NOT_RUN` | The stage was not executed; the reason is stated | ❌ |
| `UNAVAILABLE` | No suitable host was available; the reason is stated | ❌ |

A skipped, interrupted or cleanup-failed run is not a pass. A later passing run never replaces an earlier failing one; both are kept.

## What a record binds

| Item | Recorded |
| --- | --- |
| Candidate | Full 40-character commit SHA; the checkout was clean |
| Sources | Every imported VBA component and template asset, all from that commit |
| Host | Excel version and build, Office bitness, Windows edition, version and architecture |
| References | The VBA project references, which must be exactly the defaults named in [installation](../INSTALLATION.md) |
| Security context | Macro setting and *Trust access to the VBA project object model*, as found and not changed, except as recorded for stage 6 |
| Operator and time | Who ran it; start and finish time with UTC offset |
| Outcomes | One outcome per stage, with the copied output that supports it |

Any source change after the record invalidates it for the affected components. Evidence is never carried from one commit to another.

## Required stages

1. **Clean build.** Build the workbook from source at the candidate commit, outside the checkout or in a Git-ignored location, with the builder delivered by future work. `PASS`: every component imported from the one commit, none missing or extra, only the default references.
2. **Compile.** Run **Debug → Compile VBAProject**. `PASS`: no error dialog. On failure, record the exact error text and component.
3. **Smoke run.** Open the saved workbook afresh with macros enabled through the existing trust mechanism, run the harness entry point and copy its status and case table into the log. Check that `Calculation`, `EnableEvents`, `ScreenUpdating` and `DisplayAlerts` are the same after the run as before. `PASS`: the run completes, reports a pass with the expected number of cases, and restores Excel state.
4. **Failure path.** Run the harness with an injected failure, then normally again. `PASS`: the injected case is reported as `FAIL` and noted as injected, every other executed case passes, and the following normal run passes cleanly. This proves a passing smoke run is able to fail.
5. **Cleanup.** Close the workbook without saving into the checkout and record that it was closed. A built workbook is never committed.
6. **Source round trip.** Export the VBA from the saved workbook into a new folder and compare it with the candidate commit using the export/compare tool delivered by future work. `PASS`: the workbook holds exactly the components at the candidate commit. If *Trust access to the VBA project object model* had to be enabled for the export, record that and that it was turned off afterwards.

The harness entry point, injection procedure, builder and export tool are named in this document when they are delivered.

## Bitness

| Host | Stages required | When no host is available |
| --- | --- | --- |
| Windows Excel, 64-bit | All six | The candidate cannot be released; record `UNAVAILABLE` and stop |
| Windows Excel, 32-bit | Stages 1 and 2, best effort | Record `NOT_RUN` with the reason; the change may proceed |

A 32-bit `PASS` is reported as best-effort compile evidence, never as certification. Mac and Excel for the web are not supported targets.

## Procedure

Execution is manual (decision E1): a person runs Excel interactively. The procedure never changes macro security or Trust Center settings, apart from the recorded stage 6 exception.

1. Check out the candidate in a clean tree: `git switch --detach FULL_SHA`, then `git status`.
2. Create a record folder outside the checkout and start a UTF-8 `session.log` with the SHA and start time.
3. Record the host and security context without changing them.
4. Run the stages in order, copying each output into the log as it appears.
5. Write the outcome of every stage, with the reason for any `NOT_RUN` or `UNAVAILABLE`.
6. Attach the log, or a summary quoting its outcome lines, to the issue or pull request. Remove any path, user name or workbook content that is not needed.

Never fill in a host, stage or result that was not observed.

## Data in evidence

Evidence uses synthetic data only. Do not attach screenshots, workbooks or logs containing client data, internal paths beyond what is needed, or proprietary content; see the [security policy](../SECURITY.md).

## Decisions

| # | Decision | Proposed | Status |
| ---: | --- | --- | --- |
| E1 | Execution | Manual, interactive; an automated runner (such as the prototype's headless script) counts only after a reviewed design shows it records the same bindings and outcomes | Open |
| E2 | Required hosts | 64-bit Windows Excel all stages; 32-bit compile best effort | Open |
| E3 | Where records live | Attached to the issue or pull request of the candidate; never committed with workbook content | Open |
