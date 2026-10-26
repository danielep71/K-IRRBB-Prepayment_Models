# Repository tooling

## Portable baseline

Run `python tools/check.py` from a fresh clone with Git, Python 3.10+ and Node.js 22+. No Python packages are required. Stage new files before checking: the gate inspects Git's tracked file list and current working contents.

The baseline enforces required layout guides and policies, UTF-8, final newlines, trailing whitespace, JSON parsing, Python syntax, tracked relative Markdown file targets, unapproved workbook/archive binaries (with one digest-pinned PNG exception documented in [assets](../docs/assets/README.md)) and full-SHA action pins. Filename checks reject spaces, case-insensitive collisions and Windows device names. The structured [provenance register](../docs/provenance.json) requires immutable reference revisions, treatment notes and tracked paths for imported setup materials. These checks establish traceability, not ownership or permission to distribute; issue #4 records the separate owner confirmation for the inspected snapshots. New material still requires provenance and permission review.

It runs metadata regression tests, negative integrity/source fixtures and both label-script self-tests. Markdown anchors, external link availability, VBA compilation and numerical correctness are outside this gate.

## Full quality gate

Create a virtual environment and install the version-pinned dependencies:

```sh
python -m venv .venv-quality
# Windows: use .venv-quality\Scripts\python.exe below.
.venv-quality/bin/python -m pip install -r tools/requirements-quality-ci.txt
.venv-quality/bin/python tools/quality.py
```

Install **actionlint 1.7.12** from its [official release](https://github.com/rhysd/actionlint/releases/tag/v1.7.12) and put it on PATH before the last command. Choose the archive for your operating system and verify its release checksum. CI uses the Linux amd64 archive with a literal SHA-256 checksum. No downloaded installer script is executed.

The full gate includes the portable baseline, duplicate-key-safe YAML parsing, issue form labels/priorities/assignee/field IDs, Dependabot branch/labels, Ruff lint/import checks, mypy checking (including bodies of unannotated legacy functions), and actionlint workflow syntax/expression validation. Negative fixtures verify invalid configuration and an invalid workflow actually fail. Ruff's selected correctness/import rules and mypy coverage are explicit in `pyproject.toml`; this is not strict typing of every legacy boundary. Actionlint's optional ShellCheck and Pyflakes integrations are disabled for consistent local/CI behaviour; Python is checked separately.

`Repository integrity` runs on pushes to main and `release/**` branches, on all PRs and on manual dispatch. Its stable job ID is `integrity`. Logs include the exact source SHA, tool versions and check output and are retained for 14 days. Runner OS patch levels are managed by GitHub; action revisions, Python packages (including transitive dependencies) and the actionlint archive are pinned. Update pins deliberately and run the full gate. Passing checks is not Excel or model certification.

Dependabot checks GitHub Actions weekly on Monday, targets the active release branch (`release/0.2.0`, enforced exactly by `ACTIVE_RELEASE_BRANCH` in `tools/check_config.py`; change both together), assigns danielep71 and applies ci/P3. GitHub reads the Dependabot configuration only from main, so a new target takes effect only after integration into main. At most five dependency PRs remain open; updates require review and passing checks, never automatic merge. Python/tool pins are maintained through reviewed changes to the requirements file and workflow.

## Workbook build

The workbook is generated, never committed ([workbook contract](../docs/WORKBOOK_CONTRACT.md), decision of #43). The tools are build tooling only; the workbook never depends on them.

| Tool | Runs on | Does |
| --- | --- | --- |
| `workbook_layout.py` | Any | The sheets, CodeNames, tables, settings and defined names of the workbook contract, as data |
| `build_template.py` | Any, with `requirements-build.txt` | Generates the macro-free `.xlsx` template of a `production` or `test` build; refuses outputs in the checkout outside `build/` and `out/` |
| `components.py stage` | Any, Git | Lists the components of a build from the commit object, checks prefixes, `VB_Name`, ASCII and name clashes, and writes `manifest.json` with CRLF copies |
| `components.py compare` | Any | Compares an export with a manifest: missing, extra or changed components, a wrong VBA type (a sheet's module must be a document module), code in document modules and non-default references fail |
| `Build-Workbook.ps1` | Windows Excel | Stage 1: stages, generates the template, imports the components with macros disabled, saves, exports again and compares; writes the `.xlsm` and its `.build.json` record only on `PASS` |
| `Export-Workbook.ps1` | Windows Excel | Stage 6: exports every component, its VBA type and the reference names of a saved workbook into a new folder, without saving it |

The **test build** adds `tests/modules/` (`TEST_`) and the `Tests` sheet; the **production build** excludes them and `examples/`. Source folders map to prefixes: `src/core/` `CORE_`, `src/modules/` `PREPAY_`, `src/workbook/` `WB_`, `tests/modules/` `TEST_`; `src/classes/` holds `.cls` files. UserForms are rejected until a reviewed `.frx` binary exception exists. VBA source must be ASCII, because Git holds UTF-8 and the VBE imports Windows-1252.

On Windows, from a clean checkout of the candidate commit:

```powershell
python -m pip install -r tools/requirements-build.txt
powershell.exe -NoProfile -File .\tools\Build-Workbook.ps1 -Build Test -OutputPath C:\Work\prepay-test.xlsm
powershell.exe -NoProfile -File .\tools\Export-Workbook.ps1 -WorkbookPath C:\Work\prepay-test.xlsm -OutputFolder C:\Work\export
python tools/components.py stage --build test --commit HEAD --out C:\Work\stage
python tools/components.py compare --manifest C:\Work\stage\manifest.json --export C:\Work\export
```

Importing and exporting need *Trust access to the VBA project object model*. The scripts never change it or any macro setting; when access is refused they stop. Record in the [Excel evidence](../docs/EXCEL_EVIDENCE.md) whether it had to be enabled and that it was turned off afterwards. Offline tests cover the layout, staging and comparison logic and the generated template's sheets, CodeNames and names; the PowerShell scripts have no automated test and run only on a real Excel host. A tool `PASS` is not compile, run or numerical evidence.

Metadata tests mock GitHub; normal local checks do not write issues. The live metadata workflow uses GitHub's scoped token and the explicit `ISSUE_MILESTONE_NUMBER` repository variable. See [governance](../docs/GOVERNANCE.md).
