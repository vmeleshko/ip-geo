from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import httpx
import pytest

from src.clients.ip_api_co_client import IpApiCo, IPGeolocationData
from src.errors import InvalidIpError, IpNotFoundError, ReservedIpError, UpstreamServiceError
from tests.common import FailingAsyncClient, MockAsyncClient, MockResponse


def make_fake_async_client(response: MockResponse) -> Callable[..., MockAsyncClient]:
    """Factory for a fake httpx.AsyncClient returning a fixed response.

    This avoids repeating the same stub definition in every test.
    """

    def _fake_client(*args: Any, **kwargs: Any) -> MockAsyncClient:
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

    client = IpApiCo()
    result = await client.lookup_ip("8.8.8.8")

    assert isinstance(result, IPGeolocationData)
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

    client = IpApiCo()
    with pytest.raises(InvalidIpError):
        await client.lookup_ip("999.999.999.999")


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """404 from ipapi.co is translated to IpNotFoundError."""
    response = MockResponse(status_code=HTTPStatus.NOT_FOUND, payload={}, text="Not Found")

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCo()
    with pytest.raises(IpNotFoundError):
        await client.lookup_ip("203.0.113.10")


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_upstream_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """5xx from ipapi.co is translated to UpstreamServiceError."""
    response = MockResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        payload={},
        text="Internal Server Error",
    )

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCo()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.4.4")


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

    client = IpApiCo()
    result = await client.lookup_client_ip()

    assert result.ip == "198.51.100.42"
    assert result.country == "DE"
    assert result.country_name == "Germany"
    # Use pytest.approx to allow for minor floating-point representation differences.
    assert result.latitude == pytest.approx(52.52)
    assert result.longitude == pytest.approx(13.405)


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_reserved_ip_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """ipapi.co indicates a reserved/private IP via an error flag in the JSON payload."""
    payload = {"error": True, "reason": "Reserved IP Address", "reserved": True}
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCo()
    with pytest.raises(ReservedIpError):
        await client.lookup_ip("192.168.0.1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code",
    [
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.METHOD_NOT_ALLOWED,
    ],
)
async def test_get_geolocation_for_ip_http_error_statuses_raise_upstream_service_error(
    monkeypatch: pytest.MonkeyPatch,
    status_code: HTTPStatus,
) -> None:
    """HTTP 4xx responses (except 404/429) from ipapi.co are mapped to UpstreamServiceError."""
    response = MockResponse(status_code=status_code, payload={}, text="Some error")

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCo()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_http_429_raises_upstream_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 429 responses from ipapi.co are mapped to UpstreamServiceError."""
    response = MockResponse(status_code=HTTPStatus.TOO_MANY_REQUESTS, payload={}, text="Too Many Requests")

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCo()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_json_rate_limited_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON body with RateLimited reason is mapped to UpstreamServiceError."""
    payload = {"error": True, "reason": "RateLimited", "message": "Too many requests"}
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCo()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_json_quota_exceeded_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON body with quota exceeded reason is mapped to UpstreamServiceError."""
    payload = {"error": True, "reason": "Quota exceeded", "message": "Daily quota exceeded"}
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCo()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")


@pytest.mark.asyncio
async def test_get_geolocation_for_ip_network_failure_raises_upstream_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Network failures from httpx.AsyncClient are mapped to UpstreamServiceError."""

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *args, **kwargs: FailingAsyncClient("https://ipapi.co", *args, **kwargs)
    )

    client = IpApiCo()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")
