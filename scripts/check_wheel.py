"""Lightweight CI assertion against accidental root-directory package discovery."""

from pathlib import Path
from zipfile import ZipFile

wheels = list(Path("dist").glob("mobility_forecast-*.whl"))
assert len(wheels) == 1, wheels
with ZipFile(wheels[0]) as wheel:
    names = wheel.namelist()
    assert "custom_components/mobility_forecast/coordinator.py" in names
    assert "custom_components/mobility_forecast/ev/scheduling.py" in names
    for asset in (
        "manifest.json",
        "services.yaml",
        "strings.json",
        "translations/en.json",
        "translations/nl.json",
        "brand/icon.png",
        "brand/logo@2x.png",
        "brand/dark_logo.png",
    ):
        assert f"custom_components/mobility_forecast/{asset}" in names, asset
    assert all(
        name.startswith("custom_components/") or ".dist-info/" in name for name in names
    ), names
print("Wheel contains only the intended integration and distribution metadata")
