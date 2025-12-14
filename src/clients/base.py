from abc import ABC, abstractmethod

from src.models.common import IPGeolocationData


class BaseIPLookupClient(ABC):
    """Abstract base for all IP geolocation clients.

    Concrete implementations (e.g. ipapi.co, MaxMind, ipstack) should implement
    these methods and map provider-specific responses into a normalized
    geolocation shape (e.g. IpGeolocationData).
    """

    @abstractmethod
    async def lookup_ip(self, ip: str) -> IPGeolocationData:
        """Look up geolocation information for an explicit IP address."""
        raise NotImplementedError

    @abstractmethod
    async def lookup_client_ip(self) -> IPGeolocationData:
        """Look up geolocation information for the calling client's IP address."""
        raise NotImplementedError
