from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import httpx
import pytest

from src.clients.ip_api_com_client import IpApiCom, IPGeolocationData
from src.errors import InvalidIpError, IpNotFoundError, ReservedIpError, UpstreamServiceError
from tests.common import FailingAsyncClient, MockAsyncClient, MockResponse


def make_fake_async_client(response: MockResponse) -> Callable[..., MockAsyncClient]:
    """Factory for a fake httpx.AsyncClient returning a fixed response."""

    def _fake_client(*args: Any, **kwargs: Any) -> MockAsyncClient:
        return MockAsyncClient(response)

    return _fake_client


@pytest.mark.asyncio
async def test_lookup_ip_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: successful lookup with normalized fields."""
    payload = {
        "status": "success",
        "query": "8.8.8.8",
        "countryCode": "US",
        "country": "United States",
        "regionName": "California",
        "city": "Mountain View",
        "zip": "94043",
        "lat": 37.386,
        "lon": -122.0838,
        "timezone": "America/Los_Angeles",
        "isp": "Google LLC",
    }
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    result = await client.lookup_ip("8.8.8.8")

    assert isinstance(result, IPGeolocationData)
    assert result.ip == "8.8.8.8"
    assert result.country == "US"
    assert result.country_name == "United States"
    assert result.region == "California"
    assert result.city == "Mountain View"
    assert result.postal_code == "94043"
    assert result.latitude == pytest.approx(37.386)
    assert result.longitude == pytest.approx(-122.0838)
    assert result.timezone == "America/Los_Angeles"
    assert result.isp == "Google LLC"


@pytest.mark.asyncio
async def test_lookup_client_ip_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client IP lookup uses the /json/ endpoint and normalizes payload."""
    payload = {
        "status": "success",
        "query": "198.51.100.42",
        "countryCode": "DE",
        "country": "Germany",
        "lat": 52.52,
        "lon": 13.405,
    }
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    result = await client.lookup_client_ip()

    assert result.ip == "198.51.100.42"
    assert result.country == "DE"
    assert result.country_name == "Germany"
    assert result.latitude == pytest.approx(52.52)
    assert result.longitude == pytest.approx(13.405)


@pytest.mark.asyncio
async def test_lookup_ip_invalid_ip_error_from_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """ip-api.com indicates an invalid IP via status/message in JSON payload."""
    payload = {"status": "fail", "message": "invalid query"}
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    with pytest.raises(InvalidIpError):
        await client.lookup_ip("999.999.999.999")


@pytest.mark.asyncio
async def test_lookup_ip_reserved_ip_error_from_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """ip-api.com indicates a reserved/private IP via status/message."""
    payload = {"status": "fail", "message": "private range"}
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    with pytest.raises(ReservedIpError):
        await client.lookup_ip("192.168.0.1")


@pytest.mark.asyncio
async def test_lookup_ip_not_found_http_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 404 is translated to IpNotFoundError."""
    response = MockResponse(status_code=HTTPStatus.NOT_FOUND, payload={}, text="Not Found")

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    with pytest.raises(IpNotFoundError):
        await client.lookup_ip("203.0.113.10")


@pytest.mark.asyncio
async def test_lookup_ip_not_found_from_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider status 'fail' with 'not found' message maps to IpNotFoundError."""
    payload = {"status": "fail", "message": "not found"}
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    with pytest.raises(IpNotFoundError):
        await client.lookup_ip("203.0.113.10")


@pytest.mark.asyncio
async def test_lookup_ip_quota_exceeded_from_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quota/limit messages are mapped to UpstreamServiceError."""
    payload = {"status": "fail", "message": "quota exceeded for this key"}
    response = MockResponse(status_code=HTTPStatus.OK, payload=payload)

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")


@pytest.mark.asyncio
async def test_lookup_ip_http_429_raises_upstream_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 429 responses are mapped to UpstreamServiceError."""
    response = MockResponse(status_code=HTTPStatus.TOO_MANY_REQUESTS, payload={}, text="Too Many Requests")

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code",
    [
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.METHOD_NOT_ALLOWED,
    ],
)
async def test_lookup_ip_http_4xx_statuses_raise_upstream_service_error(
    monkeypatch: pytest.MonkeyPatch,
    status_code: HTTPStatus,
) -> None:
    """HTTP 4xx responses (except 404/429) are mapped to UpstreamServiceError."""
    response = MockResponse(status_code=status_code, payload={}, text="Some error")

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")


@pytest.mark.asyncio
async def test_lookup_ip_http_5xx_statuses_raise_upstream_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 5xx responses are mapped to UpstreamServiceError."""
    response = MockResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        payload={},
        text="Internal Server Error",
    )

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.4.4")


@pytest.mark.asyncio
async def test_lookup_ip_network_failure_raises_upstream_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Network failures from httpx.AsyncClient are mapped to UpstreamServiceError."""

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: FailingAsyncClient("http://ip-api.com", *args, **kwargs),
    )

    client = IpApiCom()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")


@pytest.mark.asyncio
async def test_lookup_ip_invalid_json_raises_upstream_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-JSON responses are mapped to UpstreamServiceError via JSON decode failure."""

    class BadJsonResponse(MockResponse):
        def json(self) -> dict[str, Any]:
            raise ValueError("not json")

    response = BadJsonResponse(status_code=HTTPStatus.OK, payload={})

    monkeypatch.setattr(httpx, "AsyncClient", make_fake_async_client(response))

    client = IpApiCom()
    with pytest.raises(UpstreamServiceError):
        await client.lookup_ip("8.8.8.8")
