"""Enforce the owner's issue policy with narrow API updates and read-back checks.

It sets what has a rule: the assignee, and the milestone of an issue that has
none. It never sets or changes a priority; the read-only triage check
(tools/check_issues.py) reports a missing or conflicting one for a person to decide.
"""
from __future__ import annotations

import datetime
import functools
import json
import os
import re
import subprocess
import sys

OWNER = "danielep71"
SECRET = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")
DETAIL_LIMIT = 500


def failure_detail(text):
    """Return API error text safe for a public log: token-like strings redacted, length capped."""
    detail = SECRET.sub("[REDACTED]", " ".join(text.split()))
    return detail if len(detail) <= DETAIL_LIMIT else detail[:DETAIL_LIMIT] + "..."


def api(endpoint, method="GET", payload=None, paginate=False):
    command = ["gh", "api", endpoint, "--method", method]
    if paginate:
        command += ["--paginate", "--slurp"]
    if payload is not None:
        command += ["--input", "-"]
    completed = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                               capture_output=True, text=True)
    if completed.returncode != 0:
        # gh prints the HTTP status and reason on stderr and the response body on stdout;
        # the request payload is never echoed.
        detail = failure_detail(f"{completed.stderr} {completed.stdout}")
        raise RuntimeError(f"{method} {endpoint} failed (gh exit {completed.returncode}): {detail}")
    return json.loads(completed.stdout) if completed.stdout.strip() else None


def reconcile(repository, number, default_milestone):
    """default_milestone is called only when the issue has no milestone."""
    endpoint = f"repos/{repository}/issues/{number}"
    issue = api(endpoint)
    if "pull_request" in issue:
        return
    if OWNER not in {person["login"] for person in issue["assignees"]}:
        api(endpoint + "/assignees", "POST", {"assignees": [OWNER]})
    if issue["milestone"] is None:
        api(endpoint, "PATCH", {"milestone": default_milestone()})
    verified = api(endpoint)
    if OWNER not in {person["login"] for person in verified["assignees"]} or verified["milestone"] is None:
        raise RuntimeError(f"Issue #{number}: post-update metadata verification failed")
    print(f"Issue #{number}: owner and milestone verified")


def active_milestone(repository, today=None):
    """The open milestone with the earliest due date after today (UTC); no fallback."""
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    pages = api(f"repos/{repository}/milestones?state=open&per_page=100", paginate=True)
    due = sorted((milestone["due_on"][:10], milestone["number"]) for page in pages for milestone in page
                 if milestone.get("due_on") and milestone["due_on"][:10] > today.isoformat())
    if not due:
        raise RuntimeError("No open milestone is due after today; give the active milestone a due date")
    return due[0][1]


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    number = os.environ.get("ISSUE_NUMBER", "")
    if number and os.environ.get("ISSUE_IS_PULL_REQUEST", "") == "true":
        # GitHub also sends issues events (for example milestoned) for pull requests. The
        # workflow token has no pull-requests permission, so reading one through the issues
        # API fails; pull requests are out of scope, so skip before any API call.
        print(f"#{number} is a pull request; issue metadata policy does not apply")
        return 0
    milestone = functools.cache(lambda: active_milestone(repository))
    if number:
        numbers = [int(number)]
    else:
        pages = api(f"repos/{repository}/issues?state=all&per_page=100", paginate=True)
        numbers = [issue["number"] for page in pages for issue in page if "pull_request" not in issue]
    for issue_number in numbers:
        reconcile(repository, issue_number, milestone)
    return 0


if __name__ == "__main__":
    sys.exit(main())
