"""Config-flow compatibility tests against Home Assistant 2026.8.1."""

from __future__ import annotations

from importlib.metadata import version
from typing import Any

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.mobility_forecast.config_flow import DOMAIN
from custom_components.mobility_forecast.ha_calendar import CONF_CALENDAR_ENTITY_IDS


async def test_user_flow_creates_explicit_synthetic_profile(
    hass: HomeAssistant,
) -> None:
    """Exercise selector schema and entry creation through HA's real flow manager."""

    assert version("homeassistant") == "2026.8.1"

    form: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "user"
    assert form["errors"] is None
    assert form["data_schema"](
        {
            CONF_NAME: "Synthetic commute",
            CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_work"],
        }
    ) == {
        CONF_NAME: "Synthetic commute",
        CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_work"],
    }

    result: dict[str, Any] = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        user_input={
            CONF_NAME: "Synthetic commute",
            CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_work"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Synthetic commute"
    assert result["data"] == {CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_work"]}
    assert result["result"].version == 1
    assert result["result"].minor_version == 2
