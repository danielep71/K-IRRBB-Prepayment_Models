"""Offline coverage of metadata reconciliation; no GitHub calls."""
from __future__ import annotations

import copy
import importlib.util
import os
import subprocess
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("issue_metadata", ROOT / ".github/scripts/issue-metadata.py")
assert spec is not None and spec.loader is not None  # a .py path always has a source loader
policy: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class IssueMetadataTests(unittest.TestCase):
    def simulate(self, issue: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, str, Any]]]:
        current = copy.deepcopy(issue)
        calls: list[tuple[str, str, Any]] = []

        def api(endpoint: str, method: str = "GET", payload: Any = None, paginate: bool = False) -> Any:
            calls.append((endpoint, method, payload))
            if method == "GET":
                return copy.deepcopy(current)
            if endpoint.endswith("/assignees"):
                current["assignees"] += [{"login": name} for name in payload["assignees"]]
            elif endpoint.endswith("/labels"):
                current["labels"] += [{"name": name} for name in payload["labels"]]
            elif method == "DELETE":
                current["labels"] = [label for label in current["labels"]
                                     if label["name"] != endpoint.rsplit("/", 1)[1]]
            elif method == "PATCH":
                current["milestone"] = {"number": payload["milestone"]}
            return None

        with patch.object(policy, "api", side_effect=api):
            policy.reconcile("owner/repo", 10, lambda: 1)
        return current, calls

    def test_open_and_closed_issues_get_missing_metadata(self) -> None:
        for state in ("open", "closed"):
            result, _ = self.simulate({"state": state, "assignees": [], "labels": [{"name": "bug"}], "milestone": None})
            self.assertEqual(result, {"state": state, "assignees": [{"login": "danielep71"}],
                                     "labels": [{"name": "bug"}], "milestone": {"number": 1}})

    def test_priorities_are_never_set_or_changed(self) -> None:
        # Triage reports a missing or conflicting priority for a person to decide.
        for labels in ([], ["P3", "bug", "P1", "P2"]):
            with self.subTest(labels=labels):
                result, calls = self.simulate({"assignees": [{"login": "danielep71"}, {"login": "other"}],
                                              "labels": [{"name": name} for name in labels],
                                              "milestone": {"number": 99, "state": "closed"}})
                self.assertEqual(result["labels"], [{"name": name} for name in labels])
                self.assertEqual(result["milestone"]["number"], 99)
                self.assertEqual(len(result["assignees"]), 2)
                self.assertTrue(all(method == "GET" for _, method, _ in calls))

    def test_correct_issue_is_idempotent_and_pr_is_ignored(self) -> None:
        issue = {"assignees": [{"login": "danielep71"}], "labels": [{"name": "P2"}], "milestone": {"number": 1}}
        current: dict[str, Any]
        for current in (issue, {"pull_request": {}}):
            result, calls = self.simulate(current)
            self.assertEqual(result, current)
            self.assertTrue(all(method == "GET" for _, method, _ in calls))

    def test_the_milestone_is_looked_up_only_when_needed(self) -> None:
        issue = {"assignees": [{"login": "danielep71"}], "labels": [], "milestone": {"number": 2}}
        with patch.object(policy, "api", return_value=issue):
            policy.reconcile("owner/repo", 10, lambda: self.fail("no lookup expected"))

    def test_active_milestone_is_the_open_one_due_soonest_after_today(self) -> None:
        import datetime
        today = datetime.date(2026, 11, 2)
        pages = [[{"number": 1, "due_on": None}, {"number": 2, "due_on": "2026-11-02T08:00:00Z"},
                  {"number": 3, "due_on": "2026-12-31T08:00:00Z"}], [{"number": 4, "due_on": "2026-11-30T08:00:00Z"}]]
        with patch.object(policy, "api", return_value=pages) as api:
            self.assertEqual(policy.active_milestone("owner/repo", today), 4)
        api.assert_called_once_with("repos/owner/repo/milestones?state=open&per_page=100", paginate=True)
        no_due_date: list[list[list[dict[str, Any]]]] = [
            [[]], [[{"number": 1, "due_on": None}, {"number": 2, "due_on": "2026-11-01T08:00:00Z"}]]]
        for none_due in no_due_date:
            with self.subTest(pages=none_due), patch.object(policy, "api", return_value=none_due), \
                    self.assertRaisesRegex(RuntimeError, "No open milestone is due after today"):
                policy.active_milestone("owner/repo", today)


class IssueMetadataEntryTests(unittest.TestCase):
    """Event routing in main() and API failure reporting."""

    def run_main(self, **env: str) -> Any:
        environment = {"GITHUB_REPOSITORY": "owner/repo", **env}
        with patch.dict(os.environ, environment, clear=True):
            return policy.main()

    def test_no_workflow_reads_a_milestone_variable(self) -> None:
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            with self.subTest(workflow=path.name):
                self.assertNotIn("ISSUE_MILESTONE_NUMBER", path.read_text(encoding="utf-8"))

    def test_pull_request_event_is_skipped_before_any_api_call(self) -> None:
        with patch.object(policy, "api", side_effect=AssertionError("no API call expected")), \
                patch.object(policy, "reconcile", side_effect=AssertionError("no reconcile expected")):
            self.assertEqual(self.run_main(ISSUE_NUMBER="38", ISSUE_IS_PULL_REQUEST="true"), 0)

    def test_genuine_issue_event_is_reconciled(self) -> None:
        with patch.object(policy, "reconcile") as reconcile, \
                patch.object(policy, "active_milestone", return_value=2) as active:
            self.assertEqual(self.run_main(ISSUE_NUMBER="41", ISSUE_IS_PULL_REQUEST=""), 0)
            repository, number, milestone = reconcile.call_args.args
            self.assertEqual((repository, number), ("owner/repo", 41))
            active.assert_not_called()  # looked up only when an issue needs it
            self.assertEqual((milestone(), milestone()), (2, 2))
            active.assert_called_once_with("owner/repo")

    def test_sweep_reconciles_every_issue_and_no_pull_request(self) -> None:
        pages = [[{"number": 1}, {"number": 38, "pull_request": {}}], [{"number": 41}]]
        with patch.object(policy, "api", return_value=pages) as api, \
                patch.object(policy, "reconcile") as reconcile:
            self.assertEqual(self.run_main(), 0)
        api.assert_called_once_with("repos/owner/repo/issues?state=all&per_page=100", paginate=True)
        self.assertEqual([call.args[1] for call in reconcile.call_args_list], [1, 41])

    def test_api_failure_reports_status_and_redacts_tokens(self) -> None:
        token = "ghs_" + "A" * 36
        failed = subprocess.CompletedProcess(
            [], 1, stdout='{"message": "Not Found", "note": "' + token + '"}',
            stderr="gh: Not Found (HTTP 404)\n")
        with patch.object(policy.subprocess, "run", return_value=failed):
            with self.assertRaises(RuntimeError) as raised:
                policy.api("repos/owner/repo/issues/38")
        message = str(raised.exception)
        self.assertIn("GET repos/owner/repo/issues/38 failed (gh exit 1)", message)
        self.assertIn("HTTP 404", message)
        self.assertIn("[REDACTED]", message)
        self.assertNotIn(token, message)

    def test_failure_detail_is_bounded(self) -> None:
        self.assertLessEqual(len(policy.failure_detail("x" * 5000)), policy.DETAIL_LIMIT + 3)

    def test_workflow_passes_pull_request_flag_from_event_payload(self) -> None:
        workflow = (ROOT / ".github/workflows/issue-metadata.yml").read_text(encoding="utf-8")
        self.assertIn("ISSUE_IS_PULL_REQUEST: ${{ github.event.issue.pull_request && 'true' || '' }}",
                      workflow)


if __name__ == "__main__":
    unittest.main()
