"""Contextual help remains deterministic, translated and offline-validatable."""

import json

import pytest

from custom_components.mobility_forecast.config_flow import HELP_TARGETS, help_link
from scripts.check_docs import ROOT, check_link


@pytest.mark.parametrize("step", list(HELP_TARGETS))
def test_help_target(step):
    url = help_link(step)["help_url"]
    assert url.startswith(
        "https://github.com/LickABrick/mobility-forecast/blob/main/docs/"
    )
    assert url.endswith(HELP_TARGETS[step])
    check_link(ROOT / "README.md", url)
    for language in ("en", "nl"):
        data = json.loads(
            (
                ROOT
                / f"custom_components/mobility_forecast/translations/{language}.json"
            ).read_text()
        )
        section = "config" if step == "user" else "options"
        assert "{help_url}" in data[section]["step"][step]["description"]


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/LickABrick/mobility-forecast/blob/master/docs/index.md",
        "https://github.com/Other/mobility-forecast/blob/main/docs/index.md",
        "https://github.com/LickABrick/mobility-forecast/blob/main/docs/missing.md",
        "https://github.com/LickABrick/mobility-forecast/blob/main/docs/index.md#missing",
        "https://github.com/LickABrick/mobility-forecast/blob/main/docs/index.md?raw=1",
    ],
)
def test_bad_help_url(url):
    with pytest.raises(AssertionError):
        check_link(ROOT / "README.md", url)


def test_approved_external_url():
    check_link(
        ROOT / "README.md",
        "https://developers.home-assistant.io/docs/config_entries_config_flow_handler/",
    )
