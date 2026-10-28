# Excel evidence

Status: **accepted by the owner on 2026-10-21 (issue #15)**, with every [decision](#decisions) as proposed. **No Excel evidence exists.** The builder and export/compare tools (#43) and the first VBA modules and test harness (#42) exist but have not been run in Excel, so every stage below is currently `NOT_RUN`.

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
| Security context | Macro setting and *Trust access to the VBA project object model*, as found and not changed, except as recorded for stages 1 and 6 |
| Operator and time | Who ran it; start and finish time with UTC offset |
| Outcomes | One outcome per stage, with the copied output that supports it |

Any source change after the record invalidates it for the affected components. Evidence is never carried from one commit to another.

## Required stages

1. **Clean build.** Build the workbook from source at the candidate commit, outside the checkout or in a Git-ignored location, with `tools/Build-Workbook.ps1 -Build Test`; see [tooling](../tools/README.md#workbook-build). The builder generates the template, imports the components of the commit, exports the saved workbook again and compares it with the commit before writing anything. `PASS`: the builder reports `PASS` (every component imported from the one commit, none missing or extra, only the default references) and writes its build record; copy both into the log. Importing needs *Trust access to the VBA project object model*: if it had to be enabled for the build, record that and that it was turned off afterwards.
2. **Compile.** Run **Debug → Compile VBAProject**. `PASS`: no error dialog. On failure, record the exact error text and component.
3. **Smoke run.** Open the saved workbook afresh with macros enabled through the existing trust mechanism, run the harness entry point and copy its status and case table into the log. Check that `Calculation`, `EnableEvents`, `ScreenUpdating` and `DisplayAlerts` are the same after the run as before. `PASS`: the run completes, reports a pass with the expected number of cases, and restores Excel state.
4. **Failure path.** Run the harness with an injected failure, then normally again. `PASS`: the injected case is reported as `FAIL` and noted as injected, every other executed case passes, and the following normal run passes cleanly. This proves a passing smoke run is able to fail.
5. **Cleanup.** Close the workbook without saving into the checkout and record that it was closed. A built workbook is never committed.
6. **Source round trip.** Export the VBA from the saved workbook into a new folder with `tools/Export-Workbook.ps1` and compare it with the candidate commit with `python tools/components.py compare`, using a manifest staged from the candidate (`python tools/components.py stage`). `PASS`: the workbook holds exactly the components at the candidate commit. If *Trust access to the VBA project object model* had to be enabled for the export, record that and that it was turned off afterwards.

Evidence uses the **test build**, which adds `tests/modules/`, the generated fixture modules `TEST_Fixtures` and `TEST_FixtureData<n>` and the `Tests` sheet ([workbook contract](WORKBOOK_CONTRACT.md#build-components)). The **production build** of the same commit excludes both and must pass stages 1, 2 and 6 before release. The harness entry point is the macro `TEST_RunAll` (module `TEST_Harness`); it writes the `Tests_Cases` table and `Tests_Status`, and its expected result today is `15 of 15 PASS`. The injection procedure is the macro `TEST_RunInjected`, which injects a failure into `RATE-CONV-02`; its expected result is `14 of 15 PASS (injected failure in RATE-CONV-02)`, with `RATE-CONV-02` reported as `FAIL` and its message starting `INJECTED:`. Both macros show the summary line in a message box; a harness error is reported as `FAILED` in the message box and, where the sheet can still be written, in `Tests_Status`, and fails stages 3 and 4.

## Bitness

| Host | Stages required | When no host is available |
| --- | --- | --- |
| Windows Excel, 64-bit | All six | The candidate cannot be released; record `UNAVAILABLE` and stop |
| Windows Excel, 32-bit | Stages 1 and 2, best effort | Record `NOT_RUN` with the reason; the change may proceed |

A 32-bit `PASS` is reported as best-effort compile evidence, never as certification. Mac and Excel for the web are not supported targets.

## Procedure

Execution is manual (decision E1): a person runs Excel interactively. The procedure never changes macro security or Trust Center settings, apart from the recorded stage 1 and 6 exceptions; the tools never change them.

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

| # | Decision | Outcome | Status |
| ---: | --- | --- | --- |
| E1 | Execution | Manual, interactive; an automated runner (such as the prototype's headless script) counts only after a reviewed design shows it records the same bindings and outcomes | Accepted 2026-10-21 |
| E2 | Required hosts | 64-bit Windows Excel all stages; 32-bit compile best effort | Accepted 2026-10-21 |
| E3 | Where records live | Attached to the issue or pull request of the candidate; never committed with workbook content | Accepted 2026-10-21 |
