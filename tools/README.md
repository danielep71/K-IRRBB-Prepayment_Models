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

`Repository integrity` runs on main, all PRs and future release branches. Its stable job ID is `integrity`. Logs include the exact source SHA, tool versions and check output and are retained for 14 days. Runner OS patch levels are managed by GitHub; action revisions, Python packages (including transitive dependencies) and the actionlint archive are pinned. Update pins deliberately and run the full gate. Passing checks is not Excel or model certification.

Dependabot checks GitHub Actions weekly on Monday, targets the active release branch (`release/0.1.0`, enforced exactly by `ACTIVE_RELEASE_BRANCH` in `tools/check_config.py`; change both together), assigns danielep71 and applies ci/P3. At most five dependency PRs remain open; updates require review and passing checks, never automatic merge. Python/tool pins are maintained through reviewed changes to the requirements file and workflow.

Metadata tests mock GitHub; normal local checks do not write issues. The live metadata workflow uses GitHub's scoped token and the explicit `ISSUE_MILESTONE_NUMBER` repository variable. See [governance](../docs/GOVERNANCE.md).
