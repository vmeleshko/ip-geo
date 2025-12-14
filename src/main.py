from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import ValidationError

from src.clients.ipapi_client import IpapiClient, IPGeolocationData
from src.errors import InvalidIpError, IpNotFoundError, ReservedIpError, UpstreamServiceError
from src.exception_handlers import (
    pydantic_validation_exception_handler,
    unhandled_exception_handler,
)
from src.models.request_models import IPLookupRequest
from src.models.response_models import IPLookupResponse

app = FastAPI(
    title="IP Geolocation Service",
    version="0.1.0",
    description="IP geolocation microservice for the take-home test.",
)


def get_ipapi_client() -> IpapiClient:
    """Dependency to provide an IpapiClient instance.

    Kept simple for this exercise; in a larger app this could be wired via settings.
    """
    return IpapiClient()


# Register global exception handlers using the shared handlers module.
app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


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
            data: IPGeolocationData = await client.lookup_ip(ip)
        else:
            # For simplicity, rely on ipapi.co's automatic client IP detection.
            # In a real deployment behind a proxy/load balancer you would typically
            # also inspect X-Forwarded-For or similar headers.
            data = await client.lookup_client_ip()
    except InvalidIpError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_ip", "message": str(exc)},
        ) from exc
    except ReservedIpError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "reserved_ip", "message": str(exc)},
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
