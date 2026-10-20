"""Offline atomic release metadata validation; optional strict tag validation."""

import argparse
import ast
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z"
)


def validate(root=ROOT, tag=None):
    version = (root / "version.txt").read_text().strip()
    assert SEMVER.fullmatch(version), "Invalid canonical SemVer"
    integration = root / "custom_components/mobility_forecast"
    manifest = json.loads((integration / "manifest.json").read_text())
    project = tomllib.loads((root / "pyproject.toml").read_text())
    tree = ast.parse((integration / "const.py").read_text())
    constants = [
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    ]
    assert constants == [version], "Runtime version mismatch/duplicate"
    assert manifest["version"] == project["project"]["version"] == version, (
        "Version mismatch"
    )
    assert json.loads((root / ".release-please-manifest.json").read_text()) == {
        ".": version
    }
    changelog = (root / "CHANGELOG.md").read_text()
    assert changelog.startswith("# Changelog\n")
    headings = re.findall(r"^## (.+)$", changelog, re.M)
    assert headings and len(headings) == len(set(headings)), (
        "Missing/duplicate changelog headings"
    )
    releases = re.findall(r"^## \[?([0-9][0-9A-Za-z.+-]*)(?=\]|\s|$)", changelog, re.M)
    assert len(releases) == len(set(releases)), "Duplicate release headings"
    assert json.loads((root / "hacs.json").read_text())["homeassistant"] == "2026.10.2"
    if tag:
        assert tag == f"v{version}", "Tag must match manifest"
        assert re.search(
            rf"^## (?:\[)?{re.escape(version)}(?:\]|\s|$)", changelog, re.M
        ), "Tagged version missing from changelog"
    return version


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    args = parser.parse_args()
    print(f"Release metadata consistent: {validate(tag=args.tag)}")


if __name__ == "__main__":
    main()
