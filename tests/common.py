from http import HTTPStatus
from typing import Any

import httpx


class MockResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._payload


class MockAsyncClient:
    """Minimal async context-manager mock for httpx.AsyncClient."""

    def __init__(self, response: MockResponse) -> None:
        self._response = response

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str) -> MockResponse:
        return self._response


class FailingAsyncClient:
    """Async client that raises a RequestError on enter to simulate network failure.

    The target URL is provided at construction time, so tests for different providers
    can reuse this implementation with different base URLs.
    """

    def __init__(self, url: str, *args: Any, **kwargs: Any) -> None:
        self._url = url

    async def __aenter__(self) -> "FailingAsyncClient":
        request = httpx.Request("GET", self._url)
        raise httpx.RequestError("Network failure", request=request)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str) -> MockResponse:
        return MockResponse(status_code=HTTPStatus.OK, payload={})
