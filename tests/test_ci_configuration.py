"""Contract tests for the bounded, read-only quality workflow."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "quality.yml"
REQUIREMENTS = ROOT / "requirements-dev.txt"


class QualityWorkflowTests(unittest.TestCase):
    """Keep CI reproducible, least-privileged, and free of release behavior."""

    def test_quality_workflow_runs_every_configured_check(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("timeout-minutes:", workflow)
        self.assertIn("python-version: \"3.13\"", workflow)
        self.assertIn("python -m pip install -r requirements-dev.txt", workflow)
        self.assertIn("python scripts/check_checkpoint.py", workflow)
        self.assertIn("ruff check custom_components/mobility_forecast", workflow)
        self.assertIn("pyright", workflow)
        self.assertIn("pytest", workflow)

        action_references = re.findall(r"uses: ([^\s#]+)", workflow)
        self.assertTrue(action_references)
        self.assertTrue(
            all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", item) for item in action_references)
        )

        forbidden = ("pull_request_target", "workflow_dispatch", "secrets.", "publish", "release")
        self.assertFalse(any(item in workflow.casefold() for item in forbidden))

    def test_quality_tools_are_exactly_pinned(self) -> None:
        requirements = REQUIREMENTS.read_text(encoding="utf-8").splitlines()

        self.assertEqual(
            requirements,
            [
                "pytest==9.1.1",
                "pyright==1.1.411",
                "ruff==0.16.4",
            ],
        )
        self.assertTrue(all(re.fullmatch(r"[a-z]+==[0-9.]+", line) for line in requirements))


if __name__ == "__main__":
    unittest.main()
