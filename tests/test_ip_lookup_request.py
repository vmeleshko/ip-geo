from typing import Any

import pytest
from pydantic import ValidationError

from src.main import IPLookupRequest


def _build_request(ip: Any) -> IPLookupRequest:
    """Helper to construct IPLookupRequest, used to keep tests small."""
    return IPLookupRequest(ip=ip)


def test_ip_lookup_request_allows_valid_ipv4() -> None:
    """Explicit valid IPv4 address is accepted as-is."""
    req = _build_request("8.8.8.8")
    assert req.ip == "8.8.8.8"


def test_ip_lookup_request_allows_valid_ipv6() -> None:
    """Explicit valid IPv6 address is accepted as-is."""
    req = _build_request("2001:4860:4860::8888")
    assert req.ip == "2001:4860:4860::8888"


def test_ip_lookup_request_normalizes_blank_to_none() -> None:
    """Blank string is treated as None (client IP lookup, no validation error)."""
    req = _build_request("   ")
    assert req.ip is None


def test_ip_lookup_request_allows_none() -> None:
    """None is allowed and used to trigger client IP lookup."""
    req = _build_request(None)
    assert req.ip is None


def test_ip_lookup_request_rejects_invalid_ip() -> None:
    """Non-empty, non-IP strings are rejected by validation."""
    with pytest.raises(ValidationError):
        _build_request("qwerty")
