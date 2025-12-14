from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import ValidationError

from src.clients.base import BaseIPLookupClient
from src.clients.ip_api_co_client import IpApiCo, IPGeolocationData
from src.clients.ip_api_com_client import IpApiCom
from src.errors import InvalidIpError, IpNotFoundError, ReservedIpError, UpstreamServiceError
from src.exception_handlers import (
    pydantic_validation_exception_handler,
    unhandled_exception_handler,
)
from src.logger import logger
from src.models.request_models import IPLookupRequest, Provider
from src.models.response_models import HealthResponse, IPLookupResponse

app = FastAPI(
    title="IP Geolocation Service",
    version="0.1.0",
    description="IP geolocation microservice for the take-home test.",
)
logger.info("Started IP Geolocation Service")


# TODO: move to the separate factory.py file
class IpLookupProviderFactory:
    """Factory for IP lookup provider clients.

    Given a Provider enum, returns a concrete client instance.
    """

    PROVIDERS_MAP: dict[Provider, type[BaseIPLookupClient]] = {
        Provider.ipapi_co: IpApiCo,
        Provider.ip_api_com: IpApiCom,
    }

    def __call__(self, provider: Provider) -> BaseIPLookupClient:
        client_cls = self.PROVIDERS_MAP[provider]
        return client_cls()


def get_ip_lookup_provider_factory() -> IpLookupProviderFactory:
    """Dependency to provide an IpLookupProviderFactory instance."""
    return IpLookupProviderFactory()


# Register global exception handlers using the shared handlers module.
app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get(
    "/health",
    tags=["health"],
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
)
async def health() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(status="ok")


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
    provider_factory: Annotated[IpLookupProviderFactory, Depends(get_ip_lookup_provider_factory)],
) -> IPLookupResponse:
    """Look up geolocation information for either a specific IP or the caller's IP.

    - If `query.ip` is provided, that IP is used.
    - Otherwise, the client's IP is inferred from the request (e.g. `request.client.host`).
    - If `query.provider` is provided, it selects which upstream provider to use.
      If omitted, ipapi.co is used by default.
    """
    ip = query.ip
    provider = query.provider
    ip_lookup_client = provider_factory(provider)

    try:
        if ip:
            logger.info(
                "Performing explicit IP lookup "
                f"path={request.url.path} method={request.method} ip={ip} "
                f"provider={provider}"
            )
            data: IPGeolocationData = await ip_lookup_client.lookup_ip(ip)
        else:
            # Automatically detect the client's IP address from the request.
            client_host = request.client.host if request.client else None
            x_forwarded_for = request.headers.get("x-forwarded-for")
            logger.info(
                "Performing client IP lookup "
                f"path={request.url.path} method={request.method} "
                f"client_ip={client_host} x_forwarded_for={x_forwarded_for} "
                f"provider={provider}"
            )
            # For simplicity, rely on the provider's automatic client IP detection.
            # In a real deployment behind a proxy/load balancer you would typically
            # also inspect X-Forwarded-For or similar headers more carefully.
            data = await ip_lookup_client.lookup_client_ip()
    except InvalidIpError as exc:
        logger.error(
            "Invalid IP error during lookup "
            f"path={request.url.path} method={request.method} ip={ip} provider={provider} error={exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_ip",
                "message": str(exc),
                "provider": provider,
            },
        ) from exc
    except ReservedIpError as exc:
        logger.error(
            "Reserved/private IP used for lookup "
            f"path={request.url.path} method={request.method} ip={ip} provider={provider} error={exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "reserved_ip",
                "message": str(exc),
                "provider": provider,
            },
        ) from exc
    except IpNotFoundError as exc:
        logger.error(
            "No geolocation information found for IP "
            f"path={request.url.path} method={request.method} ip={ip} provider={provider} error={exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ip_not_found",
                "message": str(exc),
                "provider": provider,
            },
        ) from exc
    except UpstreamServiceError as exc:
        logger.exception(
            "Upstream IP provider error during lookup "
            f"path={request.url.path} method={request.method} ip={ip} provider={provider} error={exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "upstream_error",
                "message": str(exc),
                "provider": provider,
            },
        ) from exc

    # Map IpGeolocationData to the outward-facing response model.
    return IPLookupResponse(
        provider=provider,
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
