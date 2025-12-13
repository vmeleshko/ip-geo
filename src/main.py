from ipaddress import AddressValueError, ip_address
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from src.ipapi_client import (
    InvalidIpError,
    IpapiClient,
    IpGeolocationData,
    IpNotFoundError,
    UpstreamServiceError,
)

app = FastAPI(
    title="IP Geolocation Service",
    version="0.1.0",
    description="IP geolocation microservice for the take-home test.",
)


class IPLookupRequest(BaseModel):
    """Request model for IP geolocation lookup via query parameters.

    If `ip` is provided, the service will look up that explicit IP address.
    If `ip` is omitted or null, the service will use the calling client's IP address.
    """

    ip: str | None = Field(
        default=None,
        description="IPv4 or IPv6 address to look up. If omitted, the client's IP is used.",
        examples=["8.8.8.8", "2001:4860:4860::8888"],
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


class IPLookupResponse(BaseModel):
    """Response model for IP geolocation lookup."""

    ip: str
    country: str
    country_name: str
    region: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    isp: str | None = None


def get_ipapi_client() -> IpapiClient:
    """Dependency to provide an IpapiClient instance.

    Kept simple for this exercise; in a larger app this could be wired via settings.
    """
    return IpapiClient()


def _normalize_pydantic_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Make sure Pydantic error dicts are JSON-serializable."""
    normalized: list[dict[str, Any]] = []
    for error in errors:
        e = dict(error)
        ctx = e.get("ctx")
        if isinstance(ctx, dict):
            # Convert any non-serializable ctx values (e.g. exceptions) to strings.
            e["ctx"] = {k: str(v) for k, v in ctx.items()}
        normalized.append(e)
    return normalized


def _build_validation_error_payload(exc: ValidationError) -> dict:
    """Normalize validation errors into a consistent error payload."""
    code = "invalid_request"
    message = "Invalid request parameters"

    errors = _normalize_pydantic_errors(exc.errors())

    for error in errors:
        loc = error.get("loc", ())
        # Handle both request-level ("query", "ip") and model-level ("ip") locations.
        if len(loc) >= 1 and loc[-1] == "ip":
            code = "invalid_ip"
            # Use a stable, API-level message instead of the raw Pydantic text.
            message = "The supplied IP address is not a valid IPv4 or IPv6 address."
            break

    return {
        "code": code,
        "message": message,
    }


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI request validation errors (e.g. invalid query/body params)."""
    payload = _build_validation_error_payload(exc)
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=payload)


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors raised during dependency resolution."""
    payload = _build_validation_error_payload(exc)
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected errors to return a structured 500 response."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "internal_error",
            "message": "An unexpected error occurred while processing the request.",
        },
    )


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}


@app.get(
    "/v1/ip/lookup",
    response_model=IPLookupResponse,
    status_code=status.HTTP_200_OK,
    tags=["ip"],
    summary="Look up geolocation information for an IP address.",
)
async def ip_lookup(
    request: Request,
    query: Annotated[IPLookupRequest, Depends()],
    client: Annotated[IpapiClient, Depends(get_ipapi_client)],
) -> IPLookupResponse:
    """Look up geolocation information for either a specific IP or the caller's IP.

    - If `query.ip` is provided, that IP is used.
    - Otherwise, the client's IP is inferred from the request (e.g. `request.client.host`).
    """
    ip = query.ip
    try:
        if ip:
            data: IpGeolocationData = await client.get_geolocation_for_ip(ip)
        else:
            # For simplicity, rely on ipapi.co's automatic client IP detection.
            # In a real deployment behind a proxy/load balancer you would typically
            # also inspect X-Forwarded-For or similar headers.
            data = await client.get_geolocation_for_client_ip()
    except InvalidIpError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_ip", "message": str(exc)},
        ) from exc
    except IpNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ip_not_found", "message": str(exc)},
        ) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "upstream_error", "message": str(exc)},
        ) from exc

    # Map IpGeolocationData to the outward-facing response model.
    return IPLookupResponse(
        ip=data.ip,
        country=data.country,
        country_name=data.country_name,
        region=data.region,
        city=data.city,
        postal_code=data.postal_code,
        latitude=data.latitude,
        longitude=data.longitude,
        timezone=data.timezone,
        isp=data.isp,
    )
