from fastapi.testclient import TestClient

from src.errors import InvalidIpError, IpNotFoundError, ReservedIpError, UpstreamServiceError
from src.main import app, get_ipapi_co_client


class _ErrorRaisingClient:
    """Test double for IpapiClient that always raises a configured exception."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def lookup_ip(self, ip: str) -> None:
        raise self._exc

    async def lookup_client_ip(self) -> None:
        raise self._exc


def _call_lookup_with_error(exc: Exception) -> tuple[int, dict]:
    """Helper that wires a failing client and calls the /v1/ip/lookup endpoint."""
    app.dependency_overrides[get_ipapi_co_client] = lambda: _ErrorRaisingClient(exc)
    client = TestClient(app)
    try:
        response = client.get("/v1/ip/lookup?ip=8.8.8.8")
        return response.status_code, response.json()
    finally:
        app.dependency_overrides.clear()


def test_ip_lookup_maps_invalid_ip_error_to_400() -> None:
    status_code, body = _call_lookup_with_error(InvalidIpError("Invalid IP Address"))

    assert status_code == 400
    assert body["detail"]["code"] == "invalid_ip"
    assert "Invalid IP Address" in body["detail"]["message"]


def test_ip_lookup_maps_reserved_ip_error_to_400() -> None:
    status_code, body = _call_lookup_with_error(ReservedIpError("Reserved IP Address"))

    assert status_code == 400
    assert body["detail"]["code"] == "reserved_ip"
    assert "Reserved IP Address" in body["detail"]["message"]


def test_ip_lookup_maps_ip_not_found_error_to_404() -> None:
    status_code, body = _call_lookup_with_error(
        IpNotFoundError("No geolocation information found for this IP address.")
    )

    assert status_code == 404
    assert body["detail"]["code"] == "ip_not_found"


def test_ip_lookup_maps_upstream_service_error_to_502() -> None:
    status_code, body = _call_lookup_with_error(UpstreamServiceError("Upstream failure"))

    assert status_code == 502
    assert body["detail"]["code"] == "upstream_error"
    assert "Upstream failure" in body["detail"]["message"]
