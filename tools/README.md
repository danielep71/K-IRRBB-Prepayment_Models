# Repository tooling

## Portable baseline

Run `python tools/check.py` from a fresh clone with Git, Python 3.10+ and Node.js 22+. No Python packages are required. Stage new files before checking: the gate inspects Git's tracked file list and current working contents.

The baseline enforces required layout guides and policies, UTF-8, final newlines, trailing whitespace, JSON parsing, Python syntax, tracked relative Markdown file targets, unapproved workbook/archive binaries (with one digest-pinned PNG exception documented in [assets](../docs/assets/README.md)) and full-SHA action pins. Filename checks reject spaces, case-insensitive collisions and Windows device names. The operational guides (`CONTRIBUTING.md`, `RELEASING.md`, `SECURITY.md`, `INSTALLATION.md`, `docs/GOVERNANCE.md`, `docs/REPOSITORY_SETTINGS.md`, `docs/TRAFFIC.md`) must not say "the owner" or "the maintainer": they state my rules in the first person. The structured [provenance register](../docs/provenance.json) requires immutable reference revisions, treatment notes and tracked paths for imported setup materials. These checks establish traceability, not ownership or permission to distribute; my separate confirmation for the inspected snapshots is recorded in [provenance](../docs/PROVENANCE.md). New material still requires provenance and permission review.

It runs metadata regressions, negative integrity/source fixtures, workbook-tooling tests, the independent DATA reference cases and both label-script self-tests. `tools/check_links.py` checks every relative link and anchor in the tracked Markdown files, through `tools/test_check_links.py`. External link availability is checked weekly instead, by the *Link check* workflow (`python tools/check_links.py --external`), because external sites change without a commit. VBA compilation and numerical correctness are outside this gate.

## Full quality gate

Create a virtual environment and install the hash-locked dependencies. Both requirement files list the SHA-256 of every wheel PyPI publishes for each pinned version, so the install verifies every download and never builds from source; the repository checks reject a requirement without a pin and hash, and a `pip install` without both flags. Dependabot proposes updates to them:

```sh
python -m venv .venv-quality
# Windows: use .venv-quality\Scripts\python.exe below.
.venv-quality/bin/python -m pip install --require-hashes --only-binary=:all: -r tools/requirements-quality-ci.txt
.venv-quality/bin/python tools/quality.py
```

Install **actionlint 1.7.12** from its [official release](https://github.com/rhysd/actionlint/releases/tag/v1.7.12) and put it on PATH before the last command. Choose the archive for your operating system and verify its release checksum. CI uses the Linux amd64 archive with a literal SHA-256 checksum. No downloaded installer script is executed.

The full gate includes the portable baseline, duplicate-key-safe YAML parsing, issue form labels/priorities/assignee/field IDs, Dependabot branch/labels, workflow steps that run Python or Node.js only after a setup action installs an exact version, Ruff lint, import and complexity checks (no function above a complexity of 15, except in the independent reference reader under `tests/reference/`), strict mypy checking with unreachable-code warnings, and actionlint workflow syntax/expression validation. Negative fixtures verify invalid configuration and an invalid workflow actually fail. `pyproject.toml` states the selected rules and their exemptions: test modules are type-checked but need not annotate every test method, and each new test module is added to that list. Actionlint's optional ShellCheck and Pyflakes integrations are disabled for consistent local/CI behaviour; Python is checked separately.

`Repository integrity` runs on pushes to main and `release/**` branches, on all PRs and on manual dispatch. Its stable job ID is `integrity`. Logs include the exact source SHA, tool versions and check output and follow the repository's retention (`retention_days` in the settings baseline); the integrity report artifact is kept for 30 days. Runner OS patch levels are managed by GitHub; action revisions, Python packages (including transitive dependencies) and the actionlint archive are pinned. Update pins deliberately and run the full gate. Passing checks is not Excel or model certification.

Dependabot checks GitHub Actions and the hash-locked Python requirements weekly on Monday, assigns danielep71 and applies ci/P3. Its `target-branch` is the one place that names the active release branch: every entry must name the same `release/X.Y.Z` (`tools/check_config.py`), and CI fails if that branch does not exist. GitHub reads the Dependabot configuration only from main, so a new target takes effect only after integration into main. At most five dependency PRs remain open; updates require review and passing checks, never automatic merge. Python/tool pins are maintained through reviewed changes to the requirements file and workflow.

## Workbook build

The workbook is generated, never committed ([workbook contract](../docs/WORKBOOK_CONTRACT.md)). The tools are build tooling only; the workbook never depends on them.

| Tool | Runs on | Does |
| --- | --- | --- |
| `workbook_layout.py` | Any | The sheets, CodeNames, tables, settings and defined names of the workbook contract, as data |
| `build_template.py` | Any, with `requirements-build.txt` | Generates the macro-free `.xlsx` template of a `production` or `test` build; refuses outputs in the checkout outside `build/` and `out/` |
| `components.py stage` | Any, Git | Lists the components of a build from the commit object, checks prefixes, `VB_Name`, ASCII and name clashes, adds the generated fixture modules to a test build, and writes `manifest.json` with CRLF copies |
| `vba_fixtures.py` | Any | Generates `TEST_Fixtures` (dispatch) and `TEST_FixtureData<n>` (hex data, about 48,000 characters each) from a commit's `tests/fixtures/` and `tests/expected/`; called by `components.py stage`, never committed |
| `components.py compare` | Any | Compares an export with a manifest: missing, extra or changed components, a wrong VBA type (a sheet's module must be a document module), code in document modules and non-default references fail |
| `Build-Workbook.ps1` | Windows Excel | Stage 1: stages, generates the template, imports the components with macros disabled, saves, exports again and compares; writes the `.xlsm` and its `.build.json` record only on `PASS` |
| `Export-Workbook.ps1` | Windows Excel | Stage 6: exports every component, its VBA type and the reference names of a saved workbook into a new folder, without saving it |

The **test build** adds `tests/modules/` (`TEST_`), the generated fixture modules and the `Tests` sheet; the **production build** excludes them and `examples/`. Source folders map to prefixes: `src/core/` `CORE_`, `src/modules/` `PREPAY_`, `src/workbook/` `WB_`, `tests/modules/` `TEST_`; `src/classes/` holds `.cls` files. UserForms are rejected until a reviewed `.frx` binary exception exists. VBA source must be ASCII, because Git holds UTF-8 and the VBE imports Windows-1252.

On Windows, from a clean checkout of the candidate commit:

```powershell
python -m pip install --require-hashes --only-binary=:all: -r tools/requirements-build.txt
powershell.exe -NoProfile -File .\tools\Build-Workbook.ps1 -Build Test -OutputPath C:\Work\prepay-test.xlsm
powershell.exe -NoProfile -File .\tools\Export-Workbook.ps1 -WorkbookPath C:\Work\prepay-test.xlsm -OutputFolder C:\Work\export
python tools/components.py stage --build test --commit HEAD --out C:\Work\stage
python tools/components.py compare --manifest C:\Work\stage\manifest.json --export C:\Work\export
```

Importing and exporting need *Trust access to the VBA project object model*. The scripts never change it or any macro setting; when access is refused they stop. Record in the [Excel evidence](../docs/EXCEL_EVIDENCE.md) whether it had to be enabled and that it was turned off afterwards. Offline tests cover the layout, staging and comparison logic and the generated template's sheets, CodeNames and names; the PowerShell scripts have no automated test and run only on a real Excel host. A tool `PASS` is not compile, run or numerical evidence.

Metadata tests mock GitHub; normal local checks do not write issues. The live metadata workflow uses GitHub's scoped token and chooses the open milestone with the earliest due date after today. `tools/check_issues.py` is the read-only triage check (`--check-config` checks the issue forms and label catalogue offline; `--repository` audits the live issues), unit-tested by `tools/test_check_issues.py`. See [governance](../docs/GOVERNANCE.md).
