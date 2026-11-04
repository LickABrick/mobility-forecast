"""Offline guardrails for the single development dependency-update stream."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def renovate():
    return json.loads((ROOT / ".github/renovate.json").read_text())


def workflow(name):
    return yaml.safe_load((ROOT / f".github/workflows/{name}.yml").read_text())


def test_single_dependency_update_stream():
    config = renovate()
    assert config["$schema"] == "https://docs.renovatebot.com/renovate-schema.json"
    assert "config:best-practices" in config["extends"]
    assert config["baseBranchPatterns"] == ["development"], (
        "Dependency PRs must target only development, never main or $default"
    )
    assert set(config["enabledManagers"]) == {"pep621", "github-actions"}
    assert config["dependencyDashboard"] is True
    for name in ("dependabot.yml", "dependabot.yaml"):
        assert not (ROOT / ".github" / name).exists(), (
            "Do not restore competing Dependabot version updates"
        )


def test_no_local_automerge_or_direct_branch_updates():
    def inspect(value):
        if isinstance(value, dict):
            if "automerge" in value:
                assert value["automerge"] is False, "Local automerge must stay disabled"
            assert value.get("automergeType") != "branch"
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    config = renovate()
    assert config["automerge"] is False
    inspect(config)
    # Special vulnerability PR overrides need a separately reviewed policy before
    # enabling: normal approval and compatibility rules must not be bypassed.
    assert config["vulnerabilityAlerts"]["enabled"] is False


def test_major_approval_and_compatibility_exceptions():
    rules = renovate()["packageRules"]
    assert any(
        rule.get("matchUpdateTypes") == ["major"]
        and rule.get("dependencyDashboardApproval") is True
        for rule in rules
    ), "Major updates need Dependency Dashboard approval before PR creation"
    assert any(
        "homeassistant" in rule.get("matchPackageNames", [])
        and set(rule.get("matchUpdateTypes", [])) == {"major", "minor"}
        and rule.get("enabled") is False
        for rule in rules
    ), "Home Assistant monthly/major upgrades must remain manual; patches are allowed"
    assert any(
        "pep621" in rule.get("matchManagers", [])
        and "requires-python" in rule.get("matchDepTypes", [])
        and rule.get("enabled") is False
        for rule in rules
    ), "Renovate must not raise the supported Python minimum"


def test_quality_covers_both_long_lived_branches():
    data = workflow("ci")
    events = data[True]  # PyYAML YAML 1.1 treats the key 'on' as True.
    for event in ("push", "pull_request"):
        assert set(events[event]["branches"]) == {"main", "development"}
    assert {"workflow_dispatch", "workflow_call"} <= events.keys()
    assert data["name"] == "Quality"
    assert {"tests", "hassfest", "hacs"} <= data["jobs"].keys()
    assert data["permissions"] == {"contents": "read"}
    assert "RELEASE_PLEASE_TOKEN" not in json.dumps(data)


def test_external_actions_use_tags_or_immutable_shas_not_branches():
    def inspect(value):
        if isinstance(value, dict):
            uses = value.get("uses")
            if uses and not uses.startswith("./"):
                assert "@" in uses, f"External action needs a ref: {uses}"
                ref = uses.rsplit("@", 1)[1]
                assert re.fullmatch(r"(?:[0-9a-f]{40}|v?\d[\w.+-]*)", ref), (
                    f"Use an immutable SHA for branch-based action refs: {uses}"
                )
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    for path in (ROOT / ".github/workflows").glob("*.y*ml"):
        inspect(yaml.safe_load(path.read_text()))
