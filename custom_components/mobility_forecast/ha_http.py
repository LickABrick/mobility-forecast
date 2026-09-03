"""Bounded Home Assistant HTTP sender for explicitly configured providers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from types import TracebackType
from typing import TYPE_CHECKING, Protocol, cast

from .openrouteservice_http import (
    InjectedHttpFailure,
    InjectedHttpFailureCategory,
    InjectedHttpRequest,
    InjectedHttpResponse,
    InjectedHttpResult,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

MAX_PROVIDER_RESPONSE_BYTES = 1_048_576
_READ_CHUNK_BYTES = 65_536


class HttpResponseContent(Protocol):
    """Small response-stream shape used by the production sender."""

    async def read(self, size: int) -> bytes:
        """Read at most size bytes, returning empty bytes at EOF."""
        ...


class HttpClientResponse(Protocol):
    """Response values used without retaining request or response details."""

    status: int
    content: HttpResponseContent


class HttpRequestContext(Protocol):
    """Async response context returned by Home Assistant's managed client."""

    async def __aenter__(self) -> HttpClientResponse: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class HomeAssistantHttpSession(Protocol):
    """Minimum aiohttp-compatible session boundary used by this integration."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        params: tuple[tuple[str, str], ...],
        json: object,
        allow_redirects: bool,
    ) -> HttpRequestContext: ...


class _ResponseUnavailableError(ValueError):
    """Internal marker for a response that cannot safely be decoded."""


class HomeAssistantHttpSender:
    """Send private provider requests through Home Assistant's shared client."""

    def __init__(
        self,
        session: HomeAssistantHttpSession,
        *,
        maximum_response_bytes: int,
    ) -> None:
        if (
            type(maximum_response_bytes) is not int
            or not 1 <= maximum_response_bytes <= 10_000_000
        ):
            raise ValueError("maximum_response_bytes must be between 1 and 10000000")
        self._session = session
        self._maximum_response_bytes = maximum_response_bytes

    async def send(self, request: InjectedHttpRequest) -> InjectedHttpResult:
        """Send one request without redirects and decode one bounded JSON response."""

        try:
            async with self._session.request(
                request.method,
                request.url,
                headers=dict(request.headers),
                params=request.query,
                json=request.json_body,
                allow_redirects=False,
            ) as response:
                status_code = response.status
                if status_code != 200:
                    return InjectedHttpResponse(status_code, None)
                body = await self._read_bounded(response.content)
        except _ResponseUnavailableError:
            return InjectedHttpFailure(InjectedHttpFailureCategory.UNAVAILABLE)
        except Exception:
            return InjectedHttpFailure(InjectedHttpFailureCategory.TRANSIENT)

        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return InjectedHttpFailure(InjectedHttpFailureCategory.UNAVAILABLE)
        return InjectedHttpResponse(status_code, decoded)

    async def _read_bounded(self, content: HttpResponseContent) -> bytes:
        body = bytearray()
        while True:
            remaining = self._maximum_response_bytes + 1 - len(body)
            if remaining <= 0:
                raise _ResponseUnavailableError
            chunk = await content.read(min(_READ_CHUNK_BYTES, remaining))
            if not chunk:
                return bytes(body)
            body.extend(chunk)
            if len(body) > self._maximum_response_bytes:
                raise _ResponseUnavailableError


def build_home_assistant_http_sender(hass: HomeAssistant) -> HomeAssistantHttpSender:
    """Build the production sender from Home Assistant's managed HTTP session."""

    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = cast(HomeAssistantHttpSession, async_get_clientsession(hass))
    return HomeAssistantHttpSender(
        session,
        maximum_response_bytes=MAX_PROVIDER_RESPONSE_BYTES,
    )
