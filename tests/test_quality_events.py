"""Project-specific trigger filters keep required PR checks without duplicate pushes."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_quality_event_filters_and_required_jobs():
    data = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    events = data[True]  # YAML 1.1's spelling of the GitHub Actions `on` key.
    assert set(events) == {"push", "pull_request", "workflow_dispatch", "workflow_call"}
    for event in ("push", "pull_request"):
        assert set(events[event]) == {"branches"}
        assert set(events[event]["branches"]) == {"main", "development"}
    assert events["workflow_dispatch"] is None
    assert events["workflow_call"] is None
    # No paths, actor or PR-type exclusions: opened/synchronize/reopened defaults
    # cover feature, Renovate and Release Please PRs on either long-lived branch.
    assert data["name"] == "Quality"
    assert set(data["jobs"]) == {"tests", "hassfest", "hacs"}
    assert data["permissions"] == {"contents": "read"}
    assert (
        "secrets.RELEASE_PLEASE_TOKEN"
        not in (ROOT / ".github/workflows/ci.yml").read_text()
    )


def test_preparation_serialized_and_stale_sha_rejected():
    data = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    assert data["concurrency"] == {
        "group": "controlled-release",
        "cancel-in-progress": False,
    }
    steps = data["jobs"]["prepare"]["steps"]
    check = steps[0]
    assert check["env"]["VALIDATED_SHA"] == "${{ github.event.workflow_run.head_sha }}"
    assert '"$head" = "$VALIDATED_SHA"' in check["run"]
    assert "current=false" in check["run"]
    assert all("current.outputs.current == 'true'" in step["if"] for step in steps[1:])
