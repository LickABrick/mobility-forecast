"""Workflow security/event wiring is checked in addition to actionlint."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())


def test_preparation_trust_boundary():
    data = workflow()
    events = data[True]  # PyYAML YAML 1.1 reads 'on' as True.
    assert "push" not in events
    assert events["workflow_run"] == {
        "workflows": ["Quality"],
        "types": ["completed"],
        "branches": ["main"],
    }
    job = data["jobs"]["prepare"]
    assert "needs" not in job
    for guard in (
        "conclusion == 'success'",
        "event == 'push'",
        "head_repository.full_name == github.repository",
        "head_branch == github.event.repository.default_branch",
    ):
        assert guard in job["if"]
    assert not any(
        "checkout" in step.get("uses", "")
        or "download-artifact" in step.get("uses", "")
        for step in job["steps"]
    )
    token_step = next(
        step
        for step in job["steps"]
        if step.get("name") == "Require preparation credential"
    )
    assert "RELEASE_PLEASE_TOKEN" in token_step["run"]
    assert "exit 1" in token_step["run"]
    action = next(
        step for step in job["steps"] if "release-please-action" in step.get("uses", "")
    )
    assert action["with"]["skip-github-release"] is True
    assert "current.outputs.current" in action["if"]


def test_publication_explicit_and_quality_gated():
    jobs = workflow()["jobs"]
    assert "workflow_dispatch" in jobs["quality"]["if"]
    publish = jobs["publish"]
    assert publish["needs"] == "quality"
    assert "inputs.publish" in publish["if"]
    assert "workflow_dispatch" in publish["if"]
    assert publish["environment"] == "release"
    assert any(
        "check_release_candidate.py" in step.get("run", "") for step in publish["steps"]
    )
    assert jobs["prepare"]["permissions"] == {"contents": "read"}
