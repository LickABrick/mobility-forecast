"""Offline metadata/translation checks; not a replacement for Hassfest/HACS."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components/mobility_forecast"


def leaves(value, prefix=""):
    if isinstance(value, dict):
        return (
            set().union(*(leaves(v, f"{prefix}.{k}") for k, v in value.items()))
            if value
            else set()
        )
    assert isinstance(value, str) and value
    return {prefix}


def main():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest["domain"] == "mobility_forecast"
    for key in (
        "version",
        "documentation",
        "issue_tracker",
        "codeowners",
        "iot_class",
        "config_flow",
    ):
        assert manifest[key]
    reference = leaves(json.loads((INTEGRATION / "strings.json").read_text()))
    for language in ("en", "nl"):
        assert (
            leaves(
                json.loads((INTEGRATION / f"translations/{language}.json").read_text())
            )
            == reference
        )
    assert json.loads((ROOT / "hacs.json").read_text())["homeassistant"] == "2026.10.2"
    print("Manifest, HACS metadata and translation key parity passed (offline checks).")


if __name__ == "__main__":
    main()
