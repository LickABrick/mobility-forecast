"""Provider request limits and privacy-safe geocode cache contracts."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

MAX_GEOCODE_REQUESTS_PER_REFRESH: Final = 50
MAX_ROUTE_REQUESTS_PER_REFRESH: Final = 100
MAX_REQUEST_ATTEMPTS: Final = 3
MAX_REQUEST_TIMEOUT: Final = timedelta(seconds=30)
MAX_GEOCODE_CACHE_RETENTION: Final = timedelta(hours=720)


def _require_bounded_integer(value: int, maximum: int, field_name: str) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{field_name} must be between 1 and {maximum}")


@dataclass(frozen=True, slots=True)
class ProviderRequestPolicy:
    """Hard per-refresh budgets, attempt bound and per-attempt timeout."""

    maximum_geocode_requests: int
    maximum_route_requests: int
    maximum_attempts: int
    timeout: timedelta

    def __post_init__(self) -> None:
        _require_bounded_integer(
            self.maximum_geocode_requests,
            MAX_GEOCODE_REQUESTS_PER_REFRESH,
            "maximum_geocode_requests",
        )
        _require_bounded_integer(
            self.maximum_route_requests,
            MAX_ROUTE_REQUESTS_PER_REFRESH,
            "maximum_route_requests",
        )
        _require_bounded_integer(
            self.maximum_attempts,
            MAX_REQUEST_ATTEMPTS,
            "maximum_attempts",
        )
        if not timedelta(0) < self.timeout <= MAX_REQUEST_TIMEOUT:
            raise ValueError("timeout must be positive and no more than 30 seconds")

    def can_start_geocode(self, *, completed_requests: int) -> bool:
        """Return whether another geocode request fits this refresh budget."""

        _require_nonnegative_count(completed_requests)
        return completed_requests < self.maximum_geocode_requests

    def can_start_route(self, *, completed_requests: int) -> bool:
        """Return whether another route request fits this refresh budget."""

        _require_nonnegative_count(completed_requests)
        return completed_requests < self.maximum_route_requests

    def can_retry(self, *, failed_attempt: int, retryable: bool) -> bool:
        """Permit only typed retryable failures within the attempt bound."""

        _require_nonnegative_count(failed_attempt)
        if failed_attempt == 0:
            raise ValueError("failed_attempt must identify a completed attempt")
        return retryable and failed_attempt < self.maximum_attempts


def _require_nonnegative_count(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("request count must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class GeocodeCachePolicy:
    """Explicit retention for successful geocodes, with a hard upper bound."""

    maximum_age: timedelta

    def __post_init__(self) -> None:
        if not timedelta(0) < self.maximum_age <= MAX_GEOCODE_CACHE_RETENTION:
            raise ValueError("geocode cache age must be positive and at most 720 hours")


@dataclass(frozen=True, slots=True)
class GeocodeCacheKey:
    """Opaque profile-scoped digest that retains no raw location text."""

    digest: str

    def __post_init__(self) -> None:
        if len(self.digest) != hashlib.sha256().digest_size * 2:
            raise ValueError("digest must be a SHA-256 hexadecimal digest")
        try:
            bytes.fromhex(self.digest)
        except ValueError as error:
            raise ValueError("digest must be hexadecimal") from error


def build_geocode_cache_key(
    location_text: str,
    *,
    privacy_key: bytes,
    provider_namespace: str,
) -> GeocodeCacheKey:
    """HMAC private location text with profile-local key material and provider scope."""

    if not location_text.strip():
        raise ValueError("location_text must not be empty")
    if len(privacy_key) < 16:
        raise ValueError("privacy_key must contain at least 16 bytes")
    if not provider_namespace.strip():
        raise ValueError("provider_namespace must not be empty")
    canonical = b"\x01".join(
        (provider_namespace.encode("utf-8"), location_text.encode("utf-8"))
    )
    return GeocodeCacheKey(hmac.new(privacy_key, canonical, hashlib.sha256).hexdigest())
