from http import HTTPStatus
from typing import Any

import httpx

from src.clients.base import BaseIPLookupClient
from src.errors import InvalidIpError, IpNotFoundError, ReservedIpError, UpstreamServiceError
from src.models.common import IPGeolocationData


class IpApiCom(BaseIPLookupClient):
    """Client for the http://ip-api.com JSON API.

    This client is intentionally minimal and focused on the subset of fields
    we expose via our own API, providing a normalized shape that decouples
    the rest of the application from the third-party response format.
    """

    def __init__(self, base_url: str = "http://ip-api.com", timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def lookup_ip(self, ip: str) -> IPGeolocationData:
        """Look up geolocation information for an explicit IP address."""
        url = f"{self._base_url}/json/{ip}"
        return await self._request(url)

    async def lookup_client_ip(self) -> IPGeolocationData:
        """Look up geolocation information for the calling client IP."""
        url = f"{self._base_url}/json/"
        return await self._request(url)

    async def _request(self, url: str) -> IPGeolocationData:
        """Perform the HTTP request and normalize the response.

        The ip-api.com API returns a JSON payload with a `status` field that can
        be "success" or "fail". We normalize that into typed exceptions and a
        stable response shape.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(url)
        except httpx.RequestError as exc:
            raise UpstreamServiceError(f"Request to IP provider failed: {repr(exc)}") from exc

        self._handle_http_errors(response)

        data = self._parse_json(response)
        self._handle_provider_status(data)

        return self._normalize_payload(data)

    def _handle_http_errors(self, response: httpx.Response) -> None:
        """Map HTTP status codes from the provider to domain-specific errors."""
        status_code = response.status_code

        if status_code == HTTPStatus.NOT_FOUND:
            raise IpNotFoundError("No geolocation information found for this IP address.")

        if status_code == HTTPStatus.TOO_MANY_REQUESTS:
            # 429 Quota exceeded / rate limit hit.
            raise UpstreamServiceError("IP provider rate limit or quota exceeded (HTTP 429).")

        if HTTPStatus.BAD_REQUEST <= status_code < HTTPStatus.INTERNAL_SERVER_ERROR:
            # 4xx responses (except 404/429) are treated as upstream errors.
            raise UpstreamServiceError(f"IP provider returned HTTP {status_code}: {response.text}")

        if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            # 5xx – upstream service failure.
            raise UpstreamServiceError(f"IP provider returned HTTP {status_code}: {response.text}")

    def _handle_provider_status(self, data: dict[str, Any]) -> None:
        """Normalize ip-api.com status/message into domain exceptions."""
        status_value = str(data.get("status") or "").lower()

        if status_value == "success":
            return

        # status is "fail" or unknown
        message = str(data.get("message") or "Unknown error from ip-api.com")
        lower_msg = message.lower()

        if "invalid query" in lower_msg or "invalid" in lower_msg:
            raise InvalidIpError(message)

        if "private range" in lower_msg or "reserved range" in lower_msg:
            raise ReservedIpError(message)

        if "quota" in lower_msg or "limit" in lower_msg:
            raise UpstreamServiceError(f"IP provider rate limit or quota exceeded: {message}")

        if "not found" in lower_msg:
            raise IpNotFoundError(message)

        raise UpstreamServiceError(message)

    @staticmethod
    def _parse_json(response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamServiceError(f"Failed to decode IP provider response as JSON: {exc}") from exc

    @staticmethod
    def _normalize_payload(data: dict[str, Any]) -> IPGeolocationData:
        """Map ip-api.com's response into our normalized schema."""
        region_name = data.get("regionName") or data.get("region") or ""
        region = str(region_name) or None

        postal = str(data.get("zip") or "")
        postal_code = postal or None

        return IPGeolocationData(
            ip=str(data.get("query") or ""),
            country=str(data.get("countryCode") or ""),
            country_name=str(data.get("country") or ""),
            region=region,
            city=data.get("city"),
            postal_code=postal_code,
            latitude=data.get("lat"),
            longitude=data.get("lon"),
            timezone=data.get("timezone"),
            isp=data.get("isp") or data.get("org"),
        )
