from http import HTTPStatus
from typing import Any

import httpx
from pydantic import BaseModel, field_validator


class IpGeolocationData(BaseModel):
    """Normalized geolocation data returned by the IP provider.

    This shape is aligned with the IpGeolocationResponse schema in the OpenAPI spec.
    """

    ip: str
    country: str
    country_name: str
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    isp: str | None = None

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _coerce_lat_lon(cls, value: Any) -> float | None:
        """Allow latitude/longitude to be provided as strings, numbers, or null.

        ipapi.co may return these fields as strings; this validator normalizes them
        into floats while gracefully handling missing or invalid values.
        """
        if value is None:
            return None
        try:
            # For general GPS and mapping, 5-6 decimal places (e.g., 34.052235)
            return round(float(value), 6)
        except (TypeError, ValueError):
            return None


class IpProviderError(Exception):
    """Base error for IP geolocation provider failures."""


class InvalidIpError(IpProviderError):
    """Raised when the supplied IP address is invalid or reserved."""


class IpNotFoundError(IpProviderError):
    """Raised when no geolocation information is found for the IP."""


class UpstreamServiceError(IpProviderError):
    """Raised when the upstream IP provider fails."""


class IpapiClient:
    """Client for the https://ipapi.co/ IP geolocation API.

    This client is intentionally minimal and focused on the subset of fields
    we expose via our own API, providing a normalized shape that decouples
    the rest of the application from the third-party response format.
    """

    def __init__(self, base_url: str = "https://ipapi.co", timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def get_geolocation_for_ip(self, ip: str) -> IpGeolocationData:
        """Look up geolocation information for an explicit IP address."""
        url = f"{self._base_url}/{ip}/json/"
        return await self._request(url)

    async def get_geolocation_for_client_ip(self) -> IpGeolocationData:
        """Look up geolocation information for the calling client IP."""
        url = f"{self._base_url}/json/"
        return await self._request(url)

    async def _request(self, url: str) -> IpGeolocationData:
        """Perform the HTTP request and normalize the response.

        The ipapi.co API returns a JSON payload that may contain an "error" flag
        even when using HTTP 200. We normalize that into typed exceptions and
        a stable response shape.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(url)
        except httpx.RequestError as exc:
            raise UpstreamServiceError(f"Request to IP provider failed: {exc}") from exc

        # ipapi.co uses 200 for many cases, but we still handle obvious HTTP failures.
        if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise UpstreamServiceError(f"IP provider returned HTTP {response.status_code}: {response.text}")

        if response.status_code == HTTPStatus.NOT_FOUND:
            raise IpNotFoundError("No geolocation information found for this IP address.")

        data = self._parse_json(response)

        # ipapi.co embeds error information in the JSON body.
        if data.get("error"):
            reason = str(data.get("reason") or data.get("message") or "Unknown error from ipapi.co")
            lower_reason = reason.lower()
            if "invalid" in lower_reason or "reserved" in lower_reason or "private" in lower_reason:
                raise InvalidIpError(reason)
            raise UpstreamServiceError(reason)

        return self._normalize_payload(data)

    @staticmethod
    def _parse_json(response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamServiceError(f"Failed to decode IP provider response as JSON: {exc}") from exc

    @staticmethod
    def _normalize_payload(data: dict[str, Any]) -> IpGeolocationData:
        """Map ipapi.co's response into our normalized schema.

        Latitude/longitude are passed through as-is; the IpGeolocationData
        model is responsible for coercing them into floats via field validators.
        """
        return IpGeolocationData(
            ip=str(data.get("ip") or ""),
            country=str(data.get("country") or ""),
            country_name=str(data.get("country_name") or ""),
            region=data.get("region"),
            city=data.get("city"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            timezone=data.get("timezone"),
            # ipapi.co exposes organisation/ISP information via the "org" field.
            isp=data.get("org"),
        )
