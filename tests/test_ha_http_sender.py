from __future__ import annotations

import asyncio
import json
import sys
import types
import unittest
from collections.abc import Mapping
from types import TracebackType

from custom_components.mobility_forecast.ha_http import (
    MAX_PROVIDER_RESPONSE_BYTES,
    HomeAssistantHttpSender,
    build_home_assistant_http_sender,
)
from custom_components.mobility_forecast.openrouteservice_http import (
    InjectedHttpFailure,
    InjectedHttpFailureCategory,
    InjectedHttpRequest,
    InjectedHttpResponse,
)

PRIVATE_URL = "https://provider.synthetic.invalid/private"
PRIVATE_KEY = "synthetic-private-key"
PRIVATE_TEXT = "Synthetic Private Destination 42"


class SyntheticContent:
    def __init__(self, body: bytes, *, chunk_size: int = 7) -> None:
        self._body = body
        self._chunk_size = chunk_size
        self.read_sizes: list[int] = []

    async def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        amount = min(size, self._chunk_size, len(self._body))
        chunk, self._body = self._body[:amount], self._body[amount:]
        return chunk


class SyntheticResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.content = SyntheticContent(body)


class SyntheticRequestContext:
    def __init__(self, response: SyntheticResponse) -> None:
        self.response = response
        self.exited = False

    async def __aenter__(self) -> SyntheticResponse:
        return self.response

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.exited = True


class SyntheticSession:
    def __init__(
        self,
        response: SyntheticResponse | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []
        self.context: SyntheticRequestContext | None = None

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        params: tuple[tuple[str, str], ...],
        json: object,
        allow_redirects: bool,
    ) -> SyntheticRequestContext:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "params": params,
                "json": json,
                "allow_redirects": allow_redirects,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.response is not None
        self.context = SyntheticRequestContext(self.response)
        return self.context


def private_request() -> InjectedHttpRequest:
    return InjectedHttpRequest(
        method="GET",
        url=PRIVATE_URL,
        headers=(("Authorization", PRIVATE_KEY),),
        query=(("text", PRIVATE_TEXT),),
        json_body=None,
    )


class HomeAssistantHttpSenderTests(unittest.TestCase):
    def test_sends_exact_private_values_with_redirects_disabled(self) -> None:
        body = {"features": []}
        session = SyntheticSession(
            SyntheticResponse(200, json.dumps(body).encode("utf-8"))
        )
        sender = HomeAssistantHttpSender(session, maximum_response_bytes=1024)

        result = asyncio.run(sender.send(private_request()))

        self.assertEqual(result, InjectedHttpResponse(200, body))
        self.assertEqual(
            session.calls,
            [
                {
                    "method": "GET",
                    "url": PRIVATE_URL,
                    "headers": {"Authorization": PRIVATE_KEY},
                    "params": (("text", PRIVATE_TEXT),),
                    "json": None,
                    "allow_redirects": False,
                }
            ],
        )
        self.assertTrue(session.context.exited)
        self.assertNotIn(PRIVATE_URL, repr(sender))
        self.assertNotIn(PRIVATE_KEY, repr(sender))

    def test_non_success_status_does_not_read_or_retain_response_body(self) -> None:
        response = SyntheticResponse(429, b'{"private":"provider echo"}')
        sender = HomeAssistantHttpSender(
            SyntheticSession(response), maximum_response_bytes=16
        )

        result = asyncio.run(sender.send(private_request()))

        self.assertEqual(result, InjectedHttpResponse(429, None))
        self.assertEqual(response.content.read_sizes, [])
        self.assertNotIn("provider echo", repr(result))

    def test_oversized_invalid_utf8_and_invalid_json_fail_closed(self) -> None:
        cases = (
            b"x" * 17,
            b"\xff",
            b"not-json",
        )
        for body in cases:
            with self.subTest(body=body):
                sender = HomeAssistantHttpSender(
                    SyntheticSession(SyntheticResponse(200, body)),
                    maximum_response_bytes=16,
                )

                result = asyncio.run(sender.send(private_request()))

                self.assertEqual(
                    result,
                    InjectedHttpFailure(InjectedHttpFailureCategory.UNAVAILABLE),
                )

    def test_transport_errors_are_sanitized_and_cancellation_propagates(self) -> None:
        for error in (TimeoutError(PRIVATE_TEXT), OSError(PRIVATE_TEXT)):
            with self.subTest(error=type(error).__name__):
                sender = HomeAssistantHttpSender(
                    SyntheticSession(error=error), maximum_response_bytes=16
                )
                result = asyncio.run(sender.send(private_request()))
                self.assertEqual(
                    result,
                    InjectedHttpFailure(InjectedHttpFailureCategory.TRANSIENT),
                )
                self.assertNotIn(PRIVATE_TEXT, repr(result))

        sender = HomeAssistantHttpSender(
            SyntheticSession(error=asyncio.CancelledError()),
            maximum_response_bytes=16,
        )
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(sender.send(private_request()))

    def test_response_limit_is_required_and_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "maximum_response_bytes"):
            HomeAssistantHttpSender(SyntheticSession(), maximum_response_bytes=0)
        with self.assertRaisesRegex(ValueError, "maximum_response_bytes"):
            HomeAssistantHttpSender(
                SyntheticSession(), maximum_response_bytes=10_000_001
            )

    def test_factory_uses_home_assistant_managed_session(self) -> None:
        hass = object()
        session = SyntheticSession(SyntheticResponse(200, b"{}"))
        aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
        calls: list[object] = []

        def async_get_clientsession(received_hass: object) -> SyntheticSession:
            calls.append(received_hass)
            return session

        aiohttp_client.async_get_clientsession = async_get_clientsession  # type: ignore[attr-defined]
        previous = sys.modules.get("homeassistant.helpers.aiohttp_client")
        sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
        try:
            sender = build_home_assistant_http_sender(hass)  # type: ignore[arg-type]
            result = asyncio.run(sender.send(private_request()))
        finally:
            if previous is None:
                sys.modules.pop("homeassistant.helpers.aiohttp_client", None)
            else:
                sys.modules["homeassistant.helpers.aiohttp_client"] = previous

        self.assertEqual(calls, [hass])
        self.assertEqual(result, InjectedHttpResponse(200, {}))
        self.assertEqual(MAX_PROVIDER_RESPONSE_BYTES, 1_048_576)


if __name__ == "__main__":
    unittest.main()
