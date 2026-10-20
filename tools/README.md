# Repository tooling

Run `python tools/check.py` from a fresh clone with Git, Python 3.10+ and Node.js 22+. No Python packages are required. Stage newly added files before checking: the gate inspects Git's tracked file list and current working contents.

The command checks required policy files, UTF-8, final newlines, trailing whitespace, JSON parsing, Python syntax, relative Markdown file targets, unapproved workbook/archive binaries and full-SHA action pins. It runs metadata reconciliation regression tests, negative integrity fixtures and both label-script self-tests. Markdown anchors, remote link availability, complete YAML schemas, VBA compilation and numerical correctness are not validated by this command.

`Repository integrity` runs on main, pull requests and future release branches and retains logs for 14 days. Python lint/type checking and comprehensive workflow validation remain tracked in issue #8. A green setup check is not Excel or model certification.

Dependabot checks GitHub Actions weekly on Monday, targets main, assigns danielep71 and applies ci/P3. At most five dependency PRs remain open; updates require review and passing checks, never automatic merge.

Metadata tests mock GitHub; normal local checks do not write issues. The live metadata workflow uses GitHub's scoped token and the explicit `ISSUE_MILESTONE_NUMBER` repository variable. See [governance](../docs/GOVERNANCE.md).
