from http import HTTPStatus
from typing import Any

import httpx

from src.clients.base import BaseIPLookupClient
from src.errors import InvalidIpError, IpNotFoundError, ReservedIpError, UpstreamServiceError
from src.models.common import IPGeolocationData


class IpApiCo(BaseIPLookupClient):
    """Client for the https://ipapi.co/ IP geolocation API.

    This client is intentionally minimal and focused on the subset of fields
    we expose via our own API, providing a normalized shape that decouples
    the rest of the application from the third-party response format.
    """

    def __init__(self, base_url: str = "https://ipapi.co", timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def lookup_ip(self, ip: str) -> IPGeolocationData:
        """Look up geolocation information for an explicit IP address."""
        url = f"{self._base_url}/{ip}/json/"
        return await self._request(url)

    async def lookup_client_ip(self) -> IPGeolocationData:
        """Look up geolocation information for the calling client IP."""
        url = f"{self._base_url}/json/"
        return await self._request(url)

    async def _request(self, url: str) -> IPGeolocationData:
        """Perform the HTTP request and normalize the response.

        The ipapi.co API returns a JSON payload that may contain an "error" flag
        even when using HTTP 200. We normalize that into typed exceptions and
        a stable response shape, following the documented error semantics:
        https://ipapi.co/api/#specific-location-field6
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(url)
        except httpx.RequestError as exc:
            raise UpstreamServiceError(f"Request to IP provider failed: {repr(exc)}") from exc

        self._handle_http_errors(response)

        data = self._parse_json(response)
        self._handle_provider_error(data)

        return self._normalize_payload(data)

    def _handle_http_errors(self, response: httpx.Response) -> None:
        """Map HTTP status codes from the provider to domain-specific errors."""
        status_code = response.status_code

        # Handle documented HTTP error codes.
        if status_code == HTTPStatus.BAD_REQUEST:
            # 400 Bad Request – something is wrong with our request to the provider.
            raise UpstreamServiceError(f"IP provider returned HTTP 400 Bad Request: {response.text}")
        if status_code == HTTPStatus.FORBIDDEN:
            # 403 Authentication Failed.
            raise UpstreamServiceError("Authentication with IP provider failed (HTTP 403).")
        if status_code == HTTPStatus.METHOD_NOT_ALLOWED:
            # 405 Method Not Allowed – should not happen for GET, but handle defensively.
            raise UpstreamServiceError("HTTP method not allowed when calling IP provider (HTTP 405).")
        if status_code == HTTPStatus.TOO_MANY_REQUESTS:
            # 429 Quota exceeded / rate limit hit.
            raise UpstreamServiceError("IP provider rate limit or quota exceeded (HTTP 429).")
        if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            # 5xx – upstream service failure.
            raise UpstreamServiceError(f"IP provider returned HTTP {status_code}: {response.text}")

        if status_code == HTTPStatus.NOT_FOUND:
            # 404 URL Not Found (e.g. malformed endpoint).
            raise IpNotFoundError("No geolocation information found for this IP address.")

    def _handle_provider_error(self, data: dict[str, Any]) -> None:
        """Normalize provider-specific error payloads into domain exceptions.

        ipapi.co embeds error information in the JSON body, sometimes with HTTP 200.
        Examples:
            { "error": true, "reason": "Invalid IP Address", "ip": "..." }
            { "error": true, "reason": "Reserved IP Address", "ip": "127.0.0.1", "reserved": true }
            { "error": true, "reason": "RateLimited", "message": "..." }
            { "error": true, "reason": "Quota exceeded", "message": "..." }
        """
        if not data.get("error"):
            return

        reason = str(data.get("reason") or data.get("message") or "Unknown error from ipapi.co")
        lower_reason = reason.lower()

        # Syntactically invalid IP.
        if "invalid ip address" in lower_reason or "invalid" in lower_reason:
            raise InvalidIpError(reason)

        # Reserved / private address, e.g. 127.0.0.1, 192.168.x.x.
        if "reserved ip address" in lower_reason or "reserved" in lower_reason or data.get("reserved") is True:
            raise ReservedIpError(reason)

        # Rate limiting / quota exceeded signalled via reason or 200 with error.
        if "ratelimited" in lower_reason or "quota" in lower_reason:
            raise UpstreamServiceError(f"IP provider rate limit or quota exceeded: {reason}")

        # Any other provider-level error is treated as an upstream failure.
        raise UpstreamServiceError(reason)

    @staticmethod
    def _parse_json(response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamServiceError(f"Failed to decode IP provider response as JSON: {exc}") from exc

    @staticmethod
    def _normalize_payload(data: dict[str, Any]) -> IPGeolocationData:
        """Map ipapi.co's response into our normalized schema.

        Latitude/longitude are passed through as-is; the IpGeolocationData
        model is responsible for coercing them into floats via field validators.
        """
        return IPGeolocationData(
            ip=str(data.get("ip") or ""),
            country=str(data.get("country") or ""),
            country_name=str(data.get("country_name") or ""),
            region=data.get("region"),
            city=data.get("city"),
            postal_code=data.get("postal"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            timezone=data.get("timezone"),
            # ipapi.co exposes organisation/ISP information via the "org" field.
            isp=data.get("org"),
        )
