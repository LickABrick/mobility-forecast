"""Release metadata validation is independent of the checked-out release state."""

import ast
import json
import re
import shutil

import pytest

from scripts.check_release import ROOT, validate


def copy_metadata(tmp_path):
    for name in (
        "version.txt",
        "pyproject.toml",
        ".release-please-manifest.json",
        "CHANGELOG.md",
        "hacs.json",
        "custom_components/mobility_forecast/manifest.json",
        "custom_components/mobility_forecast/const.py",
    ):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, target)
    return tmp_path


def current_version(root):
    return (root / "version.txt").read_text().strip()


def future_versions(version):
    major, minor, patch = map(int, version.split("-", 1)[0].split("+", 1)[0].split("."))
    return (
        f"{major + 1}.0.0",
        f"{major}.{minor + 1}.0",
        f"{major}.{minor}.{patch + 1}",
    )


def set_metadata_version(root, file, version):
    """Change one structured value, never unrelated occurrences of the version."""
    target = root / file
    if file.endswith(".json"):
        data = json.loads(target.read_text())
        data["." if file == ".release-please-manifest.json" else "version"] = version
        target.write_text(json.dumps(data))
    elif file == "pyproject.toml":
        text, count = re.subn(
            r'^version = "[^"]+"$',
            f'version = "{version}"',
            target.read_text(),
            count=1,
            flags=re.M,
        )
        assert count == 1
        target.write_text(text)
    elif file.endswith("const.py"):
        text = target.read_text()
        node = next(
            node
            for node in ast.parse(text).body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in node.targets)
        )
        lines = text.splitlines(keepends=True)
        lines[node.lineno - 1] = f'VERSION = "{version}"  # x-release-please-version\n'
        target.write_text("".join(lines))
    else:
        target.write_text(version + "\n")


def test_current_metadata():
    assert validate() == current_version(ROOT)


def test_published_release_has_no_version_override():
    config = json.loads((ROOT / "release-please-config.json").read_text())
    assert "release-as" not in config
    assert all("release-as" not in package for package in config["packages"].values())


@pytest.mark.parametrize(
    "file",
    [
        "version.txt",
        "pyproject.toml",
        "custom_components/mobility_forecast/const.py",
        "custom_components/mobility_forecast/manifest.json",
        ".release-please-manifest.json",
    ],
)
def test_drift_rejected(tmp_path, file):
    root = copy_metadata(tmp_path)
    set_metadata_version(root, file, future_versions(current_version(root))[2])
    with pytest.raises(AssertionError):
        validate(root)


def test_tag_requires_real_changelog(tmp_path):
    root = copy_metadata(tmp_path)
    version = current_version(root)
    changelog = root / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## Unreleased\n\nPending changes.\n")
    assert validate(root) == version
    with pytest.raises(AssertionError, match="missing from changelog"):
        validate(root, f"v{version}")
    changelog.write_text(
        changelog.read_text() + f"\n## [{version}]\n\nInitial public release.\n"
    )
    assert validate(root, f"v{version}") == version
    for other in future_versions(version):
        with pytest.raises(AssertionError, match="Tag must match"):
            validate(root, f"v{other}")


@pytest.mark.parametrize("style", ["plain", "linked"])
def test_release_heading_and_notes(tmp_path, style):
    root = copy_metadata(tmp_path)
    version = current_version(root)
    heading = (
        version
        if style == "plain"
        else f"[{version}](https://example.com/releases) (2026-10-20)"
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## {heading}\n\nSee [setup](docs/setup.md).\n"
    )
    assert validate(root, f"v{version}") == version
    # Two headings for one release must fail even if their links/dates differ.
    with (root / "CHANGELOG.md").open("a") as stream:
        stream.write(f"\n## [{version}](https://example.com/other) (2026-10-21)\n")
    with pytest.raises(AssertionError, match="[Dd]uplicate"):
        validate(root, f"v{version}")


@pytest.mark.parametrize("tag", ["not-a-tag", "v01.0.0", "refs/tags/v1.0.0"])
def test_incorrect_tag(tmp_path, tag):
    with pytest.raises(AssertionError, match="Tag must match"):
        validate(copy_metadata(tmp_path), tag)


@pytest.mark.parametrize(
    "version",
    ["01.0.0", "1.0", "v1.0.0", "1.0.0-01", "1.0.0-", "1.0.0+", "1.0.0\nextra"],
)
def test_invalid_semver(tmp_path, version):
    root = copy_metadata(tmp_path)
    (root / "version.txt").write_text(version)
    with pytest.raises(AssertionError, match="SemVer"):
        validate(root)


def test_missing_changelog(tmp_path):
    root = copy_metadata(tmp_path)
    (root / "CHANGELOG.md").unlink()
    with pytest.raises(FileNotFoundError):
        validate(root)


@pytest.mark.parametrize(
    "stage", ["development", "release_pr", "published", "patch_pr", "minor_pr"]
)
def test_repository_stages(tmp_path, stage):
    root = copy_metadata(tmp_path)
    version = current_version(root)
    if stage in ("patch_pr", "minor_pr"):
        version = future_versions(version)[2 if stage == "patch_pr" else 1]
        for file in (
            "version.txt",
            "pyproject.toml",
            "custom_components/mobility_forecast/const.py",
            "custom_components/mobility_forecast/manifest.json",
            ".release-please-manifest.json",
        ):
            set_metadata_version(root, file, version)
    heading = (
        "Unreleased"
        if stage == "development"
        else f"[{version}](https://example.com/release) (2026-10-20)"
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## {heading}\n\nRelease notes.\n"
    )
    assert validate(root) == version
    if stage != "development":
        assert validate(root, f"v{version}") == version
    # Published tags are not required or read by this offline metadata validator.
