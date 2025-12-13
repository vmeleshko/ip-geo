from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import httpx
import pytest

from src.ipapi_client import (
    InvalidIpError,
    IpapiClient,
    IpGeolocationData,
    IpNotFoundError,
    UpstreamServiceError,
)


class MockResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._payload


class MockAsyncClient:
    """Minimal async context-manager mock for httpx.AsyncClient."""

    def __init__(self, response: MockResponse) -> None:
        self._response = response

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    async def get(self, url: str) -> MockResponse:
        return self._response


def make_fake_async_client(response: MockResponse) -> Callable[..., MockAsyncClient]:
    """Factory for a fake httpx.AsyncClient returning a fixed response.

    This avoids repeating the same stub definition in every test.
    """

    def _fake_client(*args: Any, **kwargs: Any) -> MockAsyncClient:  # type: ignore[override]
        return MockAsyncClient(response)

    return _fake_client


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: successful lookup with string lat/lon coerced to float."""
    payload = {
        "ip": "8.8.8.8",
        "country": "US",
        "country_name": "United States",
        "region": "California",
        "city": "Mountain View",
        "latitude": "37.386",
        "longitude": "-122.0838",
        "timezone": "America/Los_Angeles",
        "org": "Google LLC",
    }
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpapiClient()
    result = await client.get_geolocation_for_ip("8.8.8.8")

    assert isinstance(result, IpGeolocationData)
    assert result.ip == "8.8.8.8"
    assert result.country == "US"
    assert result.country_name == "United States"
    assert result.region == "California"
    assert result.city == "Mountain View"
    # Use pytest.approx to allow for minor floating-point representation differences.
    assert result.latitude == pytest.approx(37.386)
    assert result.longitude == pytest.approx(-122.0838)
    assert result.timezone == "America/Los_Angeles"
    assert result.isp == "Google LLC"


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_invalid_ip_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """ipapi.co indicates an invalid IP via an error flag in the JSON payload."""
    payload = {"error": True, "reason": "Invalid IP address"}
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpapiClient()
    with pytest.raises(InvalidIpError):
        await client.get_geolocation_for_ip("999.999.999.999")


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """404 from ipapi.co is translated to IpNotFoundError."""
    response = MockResponse(status_code=HTTPStatus.NOT_FOUND, payload={}, text="Not Found")

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpapiClient()
    with pytest.raises(IpNotFoundError):
        await client.get_geolocation_for_ip("203.0.113.10")


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_upstream_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """5xx from ipapi.co is translated to UpstreamServiceError."""
    response = MockResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        payload={},
        text="Internal Server Error",
    )

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpapiClient()
    with pytest.raises(UpstreamServiceError):
        await client.get_geolocation_for_ip("8.8.4.4")


@pytest.mark.asyncio
async def test_get_geolocation_for_client_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client IP lookup uses the /json/ endpoint and normalizes the payload."""
    payload = {
        "ip": "198.51.100.42",
        "country": "DE",
        "country_name": "Germany",
        "latitude": 52.52,
        "longitude": 13.405,
    }
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpapiClient()
    result = await client.get_geolocation_for_client_ip()

    assert result.ip == "198.51.100.42"
    assert result.country == "DE"
    assert result.country_name == "Germany"
    # Use pytest.approx to allow for minor floating-point representation differences.
    assert result.latitude == pytest.approx(52.52)
    assert result.longitude == pytest.approx(13.405)
