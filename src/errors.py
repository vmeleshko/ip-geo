class AppError(Exception):
    """Base application error for the IP geolocation service."""


class IpProviderError(AppError):
    """Base error for IP geolocation provider failures."""


class InvalidIpError(IpProviderError):
    """Raised when the supplied IP address is syntactically invalid."""


class ReservedIpError(IpProviderError):
    """Raised when the supplied IP address is reserved/private (e.g. 127.0.0.1, 192.168.x.x)."""


class IpNotFoundError(IpProviderError):
    """Raised when no geolocation information is found for the IP."""


class UpstreamServiceError(IpProviderError):
    """Raised when the upstream IP provider fails."""
