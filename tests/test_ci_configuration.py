"""Contract tests for the bounded, read-only quality workflow."""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "quality.yml"
REQUIREMENTS = ROOT / "requirements-dev.txt"
HA_REQUIREMENTS = ROOT / "requirements-ha-test.txt"
PYPROJECT = ROOT / "pyproject.toml"


class QualityWorkflowTests(unittest.TestCase):
    """Keep CI reproducible, least-privileged, and free of release behavior."""

    def test_quality_workflow_runs_every_configured_check(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("timeout-minutes:", workflow)
        self.assertIn('python-version: "3.13"', workflow)
        self.assertIn("python -m pip install -r requirements-dev.txt", workflow)
        self.assertIn("python scripts/check_checkpoint.py", workflow)
        self.assertIn("ruff check .", workflow)
        self.assertIn("ruff format --check .", workflow)
        self.assertIn("pyright", workflow)
        self.assertIn("run: python -m pytest", workflow)
        self.assertNotIn("run: pytest", workflow)

        self.assertIn("ha-compatibility:", workflow)
        self.assertIn('python-version: "3.14"', workflow)
        self.assertIn("python -m pip install -r requirements-ha-test.txt", workflow)
        self.assertIn("python -m pytest -o asyncio_mode=auto tests_real_ha", workflow)

        self.assertIn("hassfest:", workflow)
        self.assertIn(
            "home-assistant/actions/hassfest@a7c616ce81ccda50150bf1595786c71b1883fabb",
            workflow,
        )
        self.assertIn("hacs-validation:", workflow)
        self.assertIn(
            "ghcr.io/hacs/action@"
            "sha256:dc92fdad2f6ffbe74bffb7269d781ea8e064f52d9bb486cdf3925d74e7ab6ebf",
            workflow,
        )
        self.assertIn("scripts/validate_hacs.py", workflow)
        self.assertIn("--network=none", workflow)
        self.assertNotIn("uses: hacs/action@", workflow)

        action_references = re.findall(r"uses: ([^\s#]+)", workflow)
        self.assertTrue(action_references)
        self.assertTrue(
            all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", item) for item in action_references)
        )

        forbidden = (
            "pull_request_target",
            "workflow_dispatch",
            "secrets.",
            "publish",
            "release",
        )
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
        self.assertTrue(
            all(re.fullmatch(r"[a-z]+==[0-9.]+", line) for line in requirements)
        )

        self.assertEqual(
            HA_REQUIREMENTS.read_text(encoding="utf-8").splitlines(),
            ["pytest-homeassistant-custom-component==0.13.355"],
        )

    def test_strict_typing_boundary_is_explicit(self) -> None:
        pyright = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"][
            "pyright"
        ]

        self.assertEqual(pyright["typeCheckingMode"], "strict")
        self.assertEqual(
            pyright["include"],
            [
                "custom_components/mobility_forecast/__init__.py",
                "custom_components/mobility_forecast/domain",
                "custom_components/mobility_forecast/coordinator.py",
                "custom_components/mobility_forecast/calendar_profile_source.py",
                "custom_components/mobility_forecast/storage.py",
                "custom_components/mobility_forecast/runtime.py",
                "custom_components/mobility_forecast/ha_storage.py",
                "custom_components/mobility_forecast/ha_calendar.py",
                "custom_components/mobility_forecast/ha_zone_anchors.py",
                "custom_components/mobility_forecast/profile_config.py",
                "custom_components/mobility_forecast/route_provider_config.py",
                "custom_components/mobility_forecast/google_routes.py",
            ],
        )
        self.assertEqual(pyright["stubPath"], "typings")


if __name__ == "__main__":
    unittest.main()
