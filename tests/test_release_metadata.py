"""Metadata checker rejects drift without requiring any local tags."""

import shutil
from pathlib import Path

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


def test_current_metadata():
    assert validate() == (ROOT / "version.txt").read_text().strip()


@pytest.mark.parametrize(
    "file",
    [
        "version.txt",
        "pyproject.toml",
        "custom_components/mobility_forecast/const.py",
        "custom_components/mobility_forecast/manifest.json",
    ],
)
def test_drift_rejected(tmp_path, file):
    root = copy_metadata(tmp_path)
    target = root / file
    target.write_text(target.read_text().replace("1.0.0", "1.0.1"))
    with pytest.raises(AssertionError):
        validate(root)


def test_tag_requires_real_changelog(tmp_path):
    root = copy_metadata(tmp_path)
    with pytest.raises(AssertionError):
        validate(root, "v9.0.0")
    with pytest.raises(AssertionError):
        validate(root, "v1.0.0")
    path = Path(root / "CHANGELOG.md")
    path.write_text(path.read_text() + "\n## 1.0.0\n\nInitial public release.\n")
    assert validate(root, "v1.0.0") == "1.0.0"
