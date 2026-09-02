"""Explicit provider selection and private route configuration per profile."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from .domain.routing import RouteOptions

CONF_ROUTE_PROVIDER = "route_provider"
CONF_ROUTE_PROVIDER_API_KEY = "route_provider_api_key"
CONF_TOLL_POLICY = "toll_policy"
CONF_HIGHWAY_POLICY = "highway_policy"


class RouteProviderKind(StrEnum):
    """Production route adapters available to a profile."""

    GOOGLE_ROUTES = "google_routes"


class RoutePreference(StrEnum):
    """Explicit route preference without a hidden boolean default."""

    ALLOW = "allow"
    AVOID = "avoid"


@dataclass(frozen=True, slots=True)
class ProfileRouteConfig:
    """Provider-neutral route choices owned by one config entry.

    The provider credential is operational private configuration. It is excluded
    from representations and must never be copied into diagnostics or logs.
    """

    provider: RouteProviderKind
    api_key: str = field(repr=False)
    tolls: RoutePreference
    highways: RoutePreference

    def __post_init__(self) -> None:
        _validate_api_key(self.api_key)

    @classmethod
    def from_entry_data(cls, data: Mapping[str, object]) -> ProfileRouteConfig:
        """Decode every required field without guessing provider or preferences."""

        return cls(
            provider=_required_enum(data, CONF_ROUTE_PROVIDER, RouteProviderKind),
            api_key=_required_api_key(data),
            tolls=_required_enum(data, CONF_TOLL_POLICY, RoutePreference),
            highways=_required_enum(data, CONF_HIGHWAY_POLICY, RoutePreference),
        )

    def as_entry_data(self) -> dict[str, str]:
        """Return the exact JSON-safe config-entry representation."""

        return {
            CONF_ROUTE_PROVIDER: self.provider.value,
            CONF_ROUTE_PROVIDER_API_KEY: self.api_key,
            CONF_TOLL_POLICY: self.tolls.value,
            CONF_HIGHWAY_POLICY: self.highways.value,
        }

    @property
    def route_options(self) -> RouteOptions:
        """Project explicit profile choices into the provider-neutral domain."""

        return RouteOptions(
            avoid_tolls=self.tolls is RoutePreference.AVOID,
            avoid_highways=self.highways is RoutePreference.AVOID,
        )


def _required_api_key(data: Mapping[str, object]) -> str:
    value = data.get(CONF_ROUTE_PROVIDER_API_KEY)
    if not isinstance(value, str):
        raise ValueError("route provider credential is unavailable")
    _validate_api_key(value)
    return value


def _validate_api_key(value: str) -> None:
    if not value or value != value.strip():
        raise ValueError("route provider credential is unavailable")


def _required_enum[EnumType: StrEnum](
    data: Mapping[str, object],
    key: str,
    enum_type: type[EnumType],
) -> EnumType:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} is unavailable")
    try:
        return enum_type(value)
    except ValueError:
        raise ValueError(f"{key} is unavailable") from None
