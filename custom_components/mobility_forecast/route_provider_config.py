"""Explicit provider selection, disclosure and safety policy per profile."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Final, TypeVar
from urllib.parse import urlsplit

from .domain.routing import RouteCachePolicy, RouteOptions
from .provider_guardrails import (
    GeocodeCachePolicy,
    ProviderRequestPolicy,
)

CONF_ROUTE_PROVIDER = "route_provider"
CONF_ROUTE_PROVIDER_API_KEY = "route_provider_api_key"
CONF_ROUTING_BASE_URL = "routing_base_url"
CONF_GEOCODER_PROVIDER = "geocoder_provider"
CONF_GEOCODER_BASE_URL = "geocoder_base_url"
CONF_LOCATION_DATA_CONSENT = "location_data_consent"
CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH = "max_geocode_requests_per_refresh"
CONF_MAX_ROUTE_REQUESTS_PER_REFRESH = "max_route_requests_per_refresh"
CONF_MAX_REQUEST_ATTEMPTS = "max_request_attempts"
CONF_REQUEST_TIMEOUT_SECONDS = "request_timeout_seconds"
CONF_GEOCODE_CACHE_RETENTION_HOURS = "geocode_cache_retention_hours"
CONF_ROUTE_CACHE_FRESH_HOURS = "route_cache_fresh_hours"
CONF_ROUTE_CACHE_STALE_HOURS = "route_cache_stale_hours"
CONF_TOLL_POLICY = "toll_policy"
CONF_HIGHWAY_POLICY = "highway_policy"

MAX_ROUTE_CACHE_FRESH_HOURS: Final = 24
MAX_ROUTE_CACHE_STALE_HOURS: Final = 720

ORS_HOSTED_GEOCODING_ENDPOINT: Final = "https://api.openrouteservice.org/geocode/search"
ORS_HOSTED_ROUTING_ENDPOINT: Final = (
    "https://api.openrouteservice.org/v2/directions/driving-car"
)
GEOAPIFY_GEOCODING_ENDPOINT: Final = "https://api.geoapify.com/v1/geocode/search"
GEOAPIFY_ROUTING_ENDPOINT: Final = "https://api.geoapify.com/v1/routing"
GOOGLE_GEOCODING_ENDPOINT: Final = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_ROUTING_ENDPOINT: Final = (
    "https://routes.googleapis.com/directions/v2:computeRoutes"
)


class RouteProviderKind(StrEnum):
    """Explicit provider families available to a profile, with no automatic mode."""

    OPENROUTESERVICE_HOSTED = "openrouteservice_hosted"
    OPENROUTESERVICE_SELF_HOSTED = "openrouteservice_self_hosted"
    GEOAPIFY = "geoapify"
    GOOGLE = "google"


class GeocoderKind(StrEnum):
    """Supported separately operated self-hosted geocoder families."""

    PELIAS = "pelias"
    PHOTON = "photon"
    NOMINATIM = "nominatim"


class LocationDataConsent(StrEnum):
    """Affirmative consent value; absence and every other value fail closed."""

    ACCEPTED = "accepted"


class RoutePreference(StrEnum):
    """Explicit route preference without a hidden boolean default."""

    ALLOW = "allow"
    AVOID = "avoid"


@dataclass(frozen=True, slots=True)
class LocationDataRecipient:
    """One disclosed receiver of private text or coordinates."""

    provider: str
    endpoint: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ProfileRouteConfig:
    """Provider-neutral, consented route choices owned by one config entry.

    Credentials and configured self-hosted endpoints are operational private
    configuration. They are excluded from representations and must never enter
    diagnostics or logs. This contract selects exactly one provider family and
    contains no fallback provider.
    """

    provider: RouteProviderKind
    api_key: str | None = field(repr=False)
    routing_base_url: str | None = field(repr=False)
    geocoder: GeocoderKind | None
    geocoder_base_url: str | None = field(repr=False)
    consent: LocationDataConsent
    maximum_geocode_requests: int
    maximum_route_requests: int
    maximum_attempts: int
    request_timeout_seconds: int
    geocode_cache_retention_hours: int
    route_cache_fresh_hours: int
    route_cache_stale_hours: int
    tolls: RoutePreference
    highways: RoutePreference

    def __post_init__(self) -> None:
        _validated_policies = (
            self.request_policy,
            self.geocode_cache_policy,
            self.route_cache_policy,
        )
        if self.consent is not LocationDataConsent.ACCEPTED:
            raise ValueError("location-data consent is unavailable")
        if self.provider is RouteProviderKind.OPENROUTESERVICE_SELF_HOSTED:
            if self.api_key is not None:
                raise ValueError("self-hosted provider must not contain a hosted key")
            if self.geocoder is None:
                raise ValueError("self-hosted geocoder selection is unavailable")
            _validate_base_url(self.routing_base_url, "routing base URL")
            _validate_base_url(self.geocoder_base_url, "geocoder base URL")
        else:
            _validate_api_key(self.api_key)
            if any(
                value is not None
                for value in (
                    self.routing_base_url,
                    self.geocoder,
                    self.geocoder_base_url,
                )
            ):
                raise ValueError("hosted provider contains self-hosted configuration")

    @classmethod
    def from_entry_data(cls, data: Mapping[str, object]) -> ProfileRouteConfig:
        """Decode every required choice without provider or policy defaults."""

        provider = _required_enum(data, CONF_ROUTE_PROVIDER, RouteProviderKind)
        if provider is RouteProviderKind.OPENROUTESERVICE_SELF_HOSTED:
            api_key = _absent(data, CONF_ROUTE_PROVIDER_API_KEY)
            routing_base_url = _required_string(data, CONF_ROUTING_BASE_URL)
            geocoder = _required_enum(data, CONF_GEOCODER_PROVIDER, GeocoderKind)
            geocoder_base_url = _required_string(data, CONF_GEOCODER_BASE_URL)
        else:
            api_key = _required_string(data, CONF_ROUTE_PROVIDER_API_KEY)
            routing_base_url = _absent(data, CONF_ROUTING_BASE_URL)
            geocoder = _absent(data, CONF_GEOCODER_PROVIDER)
            geocoder_base_url = _absent(data, CONF_GEOCODER_BASE_URL)
        return cls(
            provider=provider,
            api_key=api_key,
            routing_base_url=routing_base_url,
            geocoder=geocoder,
            geocoder_base_url=geocoder_base_url,
            consent=_required_enum(
                data, CONF_LOCATION_DATA_CONSENT, LocationDataConsent
            ),
            maximum_geocode_requests=_required_int(
                data, CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH
            ),
            maximum_route_requests=_required_int(
                data, CONF_MAX_ROUTE_REQUESTS_PER_REFRESH
            ),
            maximum_attempts=_required_int(data, CONF_MAX_REQUEST_ATTEMPTS),
            request_timeout_seconds=_required_int(data, CONF_REQUEST_TIMEOUT_SECONDS),
            geocode_cache_retention_hours=_required_int(
                data, CONF_GEOCODE_CACHE_RETENTION_HOURS
            ),
            route_cache_fresh_hours=_required_int(data, CONF_ROUTE_CACHE_FRESH_HOURS),
            route_cache_stale_hours=_required_int(data, CONF_ROUTE_CACHE_STALE_HOURS),
            tolls=_required_enum(data, CONF_TOLL_POLICY, RoutePreference),
            highways=_required_enum(data, CONF_HIGHWAY_POLICY, RoutePreference),
        )

    def as_entry_data(self) -> dict[str, str | int]:
        """Return the exact JSON-safe config-entry representation."""

        data: dict[str, str | int] = {
            CONF_ROUTE_PROVIDER: self.provider.value,
            CONF_LOCATION_DATA_CONSENT: self.consent.value,
            CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH: self.maximum_geocode_requests,
            CONF_MAX_ROUTE_REQUESTS_PER_REFRESH: self.maximum_route_requests,
            CONF_MAX_REQUEST_ATTEMPTS: self.maximum_attempts,
            CONF_REQUEST_TIMEOUT_SECONDS: self.request_timeout_seconds,
            CONF_GEOCODE_CACHE_RETENTION_HOURS: self.geocode_cache_retention_hours,
            CONF_ROUTE_CACHE_FRESH_HOURS: self.route_cache_fresh_hours,
            CONF_ROUTE_CACHE_STALE_HOURS: self.route_cache_stale_hours,
            CONF_TOLL_POLICY: self.tolls.value,
            CONF_HIGHWAY_POLICY: self.highways.value,
        }
        if self.provider is RouteProviderKind.OPENROUTESERVICE_SELF_HOSTED:
            if (
                self.routing_base_url is None
                or self.geocoder is None
                or self.geocoder_base_url is None
            ):
                raise ValueError("self-hosted provider configuration is incomplete")
            data.update(
                {
                    CONF_ROUTING_BASE_URL: self.routing_base_url,
                    CONF_GEOCODER_PROVIDER: self.geocoder.value,
                    CONF_GEOCODER_BASE_URL: self.geocoder_base_url,
                }
            )
        else:
            if self.api_key is None:
                raise ValueError("hosted provider credential is unavailable")
            data[CONF_ROUTE_PROVIDER_API_KEY] = self.api_key
        return data

    @property
    def route_options(self) -> RouteOptions:
        """Project explicit choices into provider-neutral route options."""

        return RouteOptions(
            avoid_tolls=self.tolls is RoutePreference.AVOID,
            avoid_highways=self.highways is RoutePreference.AVOID,
        )

    @property
    def request_policy(self) -> ProviderRequestPolicy:
        """Project hard request, retry and timeout bounds."""

        return ProviderRequestPolicy(
            maximum_geocode_requests=self.maximum_geocode_requests,
            maximum_route_requests=self.maximum_route_requests,
            maximum_attempts=self.maximum_attempts,
            timeout=timedelta(seconds=self.request_timeout_seconds),
        )

    @property
    def geocode_cache_policy(self) -> GeocodeCachePolicy:
        """Project explicit privacy-cache retention."""

        return GeocodeCachePolicy(
            maximum_age=timedelta(hours=self.geocode_cache_retention_hours)
        )

    @property
    def route_cache_policy(self) -> RouteCachePolicy:
        """Project explicit fresh and stale route-cache retention."""

        fresh = self.route_cache_fresh_hours
        stale = self.route_cache_stale_hours
        if not 1 <= fresh <= MAX_ROUTE_CACHE_FRESH_HOURS:
            raise ValueError(
                "route fresh cache retention must be between 1 and 24 hours"
            )
        if not fresh <= stale <= MAX_ROUTE_CACHE_STALE_HOURS:
            raise ValueError(
                "route stale cache retention must be between fresh age and 720 hours"
            )
        return RouteCachePolicy(
            maximum_fresh_age=timedelta(hours=fresh),
            maximum_stale_age=timedelta(hours=stale),
        )

    @property
    def location_recipients(
        self,
    ) -> tuple[LocationDataRecipient, LocationDataRecipient]:
        """Disclose the exact geocoding and routing recipients, without fallback."""

        if self.provider is RouteProviderKind.OPENROUTESERVICE_HOSTED:
            return (
                LocationDataRecipient(
                    "OpenRouteService hosted Pelias geocoder",
                    ORS_HOSTED_GEOCODING_ENDPOINT,
                ),
                LocationDataRecipient(
                    "OpenRouteService hosted routing", ORS_HOSTED_ROUTING_ENDPOINT
                ),
            )
        if self.provider is RouteProviderKind.GEOAPIFY:
            return (
                LocationDataRecipient(
                    "Geoapify geocoding", GEOAPIFY_GEOCODING_ENDPOINT
                ),
                LocationDataRecipient("Geoapify routing", GEOAPIFY_ROUTING_ENDPOINT),
            )
        if self.provider is RouteProviderKind.GOOGLE:
            return (
                LocationDataRecipient(
                    "Google Geocoding API", GOOGLE_GEOCODING_ENDPOINT
                ),
                LocationDataRecipient("Google Routes API", GOOGLE_ROUTING_ENDPOINT),
            )
        if (
            self.geocoder is None
            or self.geocoder_base_url is None
            or self.routing_base_url is None
        ):
            raise ValueError("self-hosted provider configuration is incomplete")
        return (
            LocationDataRecipient(
                f"Self-hosted {self.geocoder.value.title()} geocoder",
                self.geocoder_base_url,
            ),
            LocationDataRecipient(
                "Self-hosted OpenRouteService routing", self.routing_base_url
            ),
        )


def _required_string(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{key} is unavailable")
    return value


def _validate_api_key(value: str | None) -> None:
    if value is None or not value or value != value.strip():
        raise ValueError("route provider credential is unavailable")


def _validate_base_url(value: str | None, field_name: str) -> None:
    if value is None:
        raise ValueError(f"{field_name} is unavailable")
    parsed = urlsplit(value)
    try:
        _port = parsed.port
    except ValueError as error:
        raise ValueError(f"{field_name} is unavailable") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{field_name} is unavailable")


def _absent(data: Mapping[str, object], key: str) -> None:
    if key in data:
        raise ValueError(f"{key} is not valid for the selected provider")
    return None


def _required_int(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool):
        raise ValueError(f"{key} is unavailable")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"{key} is unavailable")


EnumType = TypeVar("EnumType", bound=StrEnum)


def _required_enum(  # noqa: UP047
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
