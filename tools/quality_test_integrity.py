"""Check how the integrity workflow keeps its report and which runs it cancels."""
import unittest
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def upload_step() -> dict[str, Any]:
    workflow = yaml.safe_load((ROOT / '.github/workflows/static-checks.yml').read_text(encoding='utf-8'))
    steps = [step for step in workflow['jobs']['integrity']['steps']
             if str(step.get('uses', '')).startswith('actions/upload-artifact@')]
    assert len(steps) == 1, steps
    step: dict[str, Any] = steps[0]
    return step


class IntegrityArtifactTests(unittest.TestCase):
    def test_report_is_kept_per_run_and_required(self) -> None:
        step = upload_step()
        settings = step['with']
        self.assertEqual(step['if'], 'always()')
        for part in ('${{ github.sha }}', '${{ github.run_id }}', '${{ github.run_attempt }}'):
            self.assertIn(part, settings['name'])
        self.assertEqual(settings['path'], 'test-results/integrity.txt')
        self.assertEqual(settings['if-no-files-found'], 'error')
        self.assertEqual(settings['retention-days'], 30)

    def test_the_uploaded_report_is_the_one_the_gate_writes(self) -> None:
        workflow = (ROOT / '.github/workflows/static-checks.yml').read_text(encoding='utf-8')
        self.assertIn('| tee test-results/integrity.txt', workflow)

    def test_only_a_superseded_pull_request_run_is_cancelled(self) -> None:
        workflow = yaml.safe_load((ROOT / '.github/workflows/static-checks.yml').read_text(encoding='utf-8'))
        concurrency = workflow['concurrency']
        # A pull request's runs share a group; every other run, a push to a
        # protected branch included, has its own and is never cancelled.
        self.assertIn("github.event_name == 'pull_request'", concurrency['group'])
        self.assertIn('github.event.pull_request.number', concurrency['group'])
        self.assertIn('github.run_id', concurrency['group'])
        self.assertNotIn('github.ref', concurrency['group'])
        self.assertEqual(concurrency['cancel-in-progress'], "${{ github.event_name == 'pull_request' }}")


if __name__ == '__main__':
    unittest.main()
