from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str


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
