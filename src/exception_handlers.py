from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.logger import logger


def _get_provider_from_request(request: Request) -> str | None:
    """Best-effort extraction of the provider value from the incoming request.

    Currently this looks at the `provider` query parameter used by /v1/ip/lookup.
    For other endpoints this will typically be None.
    """
    return request.query_params.get("provider")


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
    """Normalize validation errors into a consistent error payload.

    We intentionally keep the external shape minimal:
    - `code`: short machine-readable error code.
    - `message`: stable human-readable message.

    Internal validation details are not exposed to clients.
    """
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


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors raised during dependency resolution."""
    provider = _get_provider_from_request(request)
    logger.info(
        "Pydantic validation error during request handling "
        f"path={request.url.path} method={request.method} provider={provider} errors={exc.errors()}"
    )
    payload = _build_validation_error_payload(exc)
    payload["provider"] = provider
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=payload)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected errors to return a structured 500 response."""
    provider = _get_provider_from_request(request)
    logger.exception(
        "Unhandled exception while processing request: "
        f"{repr(exc)} path={request.url.path} method={request.method} provider={provider}"
    )
    content: dict[str, Any] = {
        "code": "internal_error",
        "message": "An unexpected error occurred while processing the request.",
        "provider": provider,
    }
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
    )
