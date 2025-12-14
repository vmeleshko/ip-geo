from enum import Enum
from ipaddress import AddressValueError, ip_address

from pydantic import BaseModel, Field, field_validator


class Provider(str, Enum):
    """Supported IP geolocation providers."""

    ipapi_co = "ipapi.co"
    ip_api_com = "ip-api.com"


class IPLookupRequest(BaseModel):
    """Request model for IP geolocation lookup via query parameters.

    If `ip` is provided, the service will look up that explicit IP address.
    If `ip` is omitted or null, the service will use the calling client's IP address.

    The optional `provider` parameter allows the caller to select the upstream
    geolocation provider. If omitted, the default is ipapi.co.
    """

    ip: str | None = Field(
        default=None,
        description="IPv4 or IPv6 address to look up. If omitted, the client's IP is used.",
        examples=["8.8.8.8", "2001:4860:4860::8888"],
    )
    provider: Provider = Field(
        default="ipapi.co",
        description="Upstream provider to use for the lookup. Defaults to ipapi.co.",
        examples=["ipapi.co", "ip-api.com"],
    )

    @field_validator("ip", mode="before")
    @classmethod
    def _validate_ip(cls, value: str | None) -> str | None:
        """Validate that ip is either empty/None or a valid IP address (IPv4 or IPv6).

        - None or blank string -> treated as None (client IP lookup, no error).
        - Non-blank -> must be a valid IP literal, otherwise a validation error
          is raised and the endpoint handler is never invoked.
        """
        if value is None:
            return None

        value_str = str(value).strip()
        if not value_str:
            return None

        try:
            ip_address(value_str)
        except AddressValueError as exc:
            raise ValueError("ip must be a valid IPv4 or IPv6 address") from exc

        return value_str
