from typing import Any

from pydantic import BaseModel, field_validator


class IPGeolocationData(BaseModel):
    """Normalized geolocation data returned by an IP provider.

    This shape is aligned with the IpGeolocationResponse schema in the OpenAPI spec
    and is used as the internal normalized representation before mapping to
    outward-facing response models.
    """

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

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _coerce_lat_lon(cls, value: Any) -> float | None:
        """Allow latitude/longitude to be provided as strings, numbers, or null.

        Providers may return these fields as strings; this validator normalizes them
        into floats while gracefully handling missing or invalid values.
        """
        if value is None:
            return None
        try:
            # For general GPS and mapping, 5-6 decimal places (e.g., 34.052235)
            return round(float(value), 6)
        except (TypeError, ValueError):
            return None
