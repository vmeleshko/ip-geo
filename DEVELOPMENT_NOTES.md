# DEVELOPMENT_NOTES

## Implementation Walkthrough

### Initial setup (tooling, project structure, dependencies)

- **Python & uv**
  - Target Python version is **3.12.7**, constrained via [`pyproject.toml`](pyproject.toml:1) with `requires-python = ">=3.12,<3.13"`.
  - I use [`uv`](pyproject.toml:1) as the environment and dependency manager.
  - Initial setup steps for a fresh clone:
    - Install `uv` (if not already present), e.g.:
      - `curl -LsSf https://astral.sh/uv/install.sh | sh`
    - From the project root run:
      - `uv sync` – creates the virtualenv and installs both runtime and dev dependencies as defined in [`pyproject.toml`](pyproject.toml:1) and `uv.lock`.

- **Dependencies**
  - Core runtime dependencies (FastAPI stack and HTTP client) are declared in [`pyproject.toml`](pyproject.toml:1):
    - `fastapi`, `uvicorn[standard]`, `httpx`, `pydantic`, `pydantic-settings`.
  - Dev and quality tools are in the `dev` dependency group:
    - `pytest`, `pytest-asyncio`, `mypy`, `ruff`, `coverage`.

- **Project layout**
  - Top-level:
    - [`Backend_Take_Home_Test.md`](Backend_Take_Home_Test.md:1) – original take‑home specification.
    - [`README.md`](README.md:1) – setup, run, tests, tooling and how to access docs.
    - [`DEVELOPMENT_NOTES.md`](DEVELOPMENT_NOTES.md:1) – this file; implementation walkthrough and reflection.
    - [`pyproject.toml`](pyproject.toml:1) – project metadata, dependencies, and dev tools configuration (including mypy, ruff).
    - [`ruff.toml`](ruff.toml:1) – Ruff configuration for linting and formatting.
    - [`.pre-commit-config.yaml`](.pre-commit-config.yaml:1) – pre-commit hooks wiring Ruff and tests with coverage.
    - [`uv.lock`](uv.lock:1) – uv’s lock file to make dependency resolution reproducible.
    - [`run_app.py`](run_app.py:1) – small helper entrypoint to run the FastAPI app directly from an IDE like PyCharm without using `uv` on the command line.
    - [`export_openapi.py`](export_openapi.py:1) – helper script to export the FastAPI-generated OpenAPI schema to `openapi/openapi.generated.json` for comparison with the spec-first YAML.

  - API specification:
    - [`openapi/openapi.yaml`](openapi/openapi.yaml:1) – hand-written, spec‑first OpenAPI definition that serves as the source of truth for endpoints, request/response models, and error codes.
    - [`openapi/openapi.generated.json`](openapi/openapi.generated.json:1) – machine-generated OpenAPI document exported from the running FastAPI app via [`export_openapi.py`](export_openapi.py:1); used to validate that implementation and spec stay in sync.

  - Application package (`src/`):
    - [`src/__init__.py`](src/__init__.py:1) – marks `src` as a package.
    - [`src/main.py`](src/main.py:1) – FastAPI application factory:
      - Creates the `FastAPI` app instance.
      - Registers global exception handlers from [`src/exception_handlers.py`](src/exception_handlers.py:1).
      - Wires the IP lookup endpoint `/v1/ip/lookup`.
      - Provides the `get_ipapi_client` dependency for injecting [`IpapiClient`](src/clients/ipapi_client.py:1).
    - [`src/errors.py`](src/errors.py:1) – domain-specific exception types:
      - `InvalidIpError`, `ReservedIpError`, `IpNotFoundError`, `UpstreamServiceError`.
      - Used by the client layer to describe provider failures in a structured way.
    - [`src/exception_handlers.py`](src/exception_handlers.py:1) – shared FastAPI exception handlers:
      - Maps Pydantic validation errors to consistent 400 responses.
      - Adds a catch‑all 500 JSON error payload for truly unhandled exceptions.
    - [`src/clients/`](src/clients/__init__.py:1) – external integration layer:
      - [`src/clients/base.py`](src/clients/base.py:1) – abstract base client defining the interface for IP lookup providers (`lookup_ip`, `lookup_client_ip`).
      - [`src/clients/ipapi_client.py`](src/clients/ipapi_client.py:1) – concrete async client for `ipapi.co`:
        - Uses `httpx.AsyncClient`.
        - Normalizes responses into [`IPGeolocationData`](src/models/common.py:1).
        - Translates provider HTTP / JSON errors into the domain errors in [`src/errors.py`](src/errors.py:1).
      - [`src/clients/__init__.py`](src/clients/__init__.py:1) – package marker for `src.clients`.
    - [`src/models/`](src/models/common.py:1) – Pydantic v2 models:
      - [`src/models/request_models.py`](src/models/request_models.py:1) – request-side models:
        - `IPLookupRequest` with validation for the optional `ip` query parameter, including IPv4/IPv6 validation and normalization of blank strings to `None`.
      - [`src/models/response_models.py`](src/models/response_models.py:1) – outward-facing response models:
        - `IPLookupResponse` which represents the API response for `/v1/ip/lookup`.
      - [`src/models/common.py`](src/models/common.py:1) – internal, provider‑agnostic model:
        - `IPGeolocationData` used internally by clients to represent normalized geo data, including lat/lon coercion.
  
  - Tests (`tests/`):
    - [`tests/test_ip_lookup_request.py`](tests/test_ip_lookup_request.py:1) – unit tests for `IPLookupRequest`:
      - Valid IPv4/IPv6, handling of blank/None, and invalid IP validation behavior.
    - [`tests/test_ipapi_client.py`](tests/test_ipapi_client.py:1) – unit tests for [`IpapiClient`](src/clients/ipapi_client.py:1):
      - Happy-path lookups for explicit IP and client IP.
      - Error mapping for invalid IP, reserved IP, not found (404), upstream failures (400/403/405/429/5xx, rate‑limit/quota, network errors).
    - [`tests/test_main_api.py`](tests/test_main_api.py:1) – endpoint‑level tests using `TestClient`:
      - Verifies that each domain error maps to the expected HTTP status and error `code` (`invalid_ip`, `reserved_ip`, `ip_not_found`, `upstream_error`).

### Running the application

- During development, I typically run the app via `uv`:

  ```bash
  uv run uvicorn src.main:app --reload
  ```

  - This uses the virtualenv managed by `uv`.
  - The app is then available at `http://127.0.0.1:8000`.
  - Swagger UI for interactive docs: `http://127.0.0.1:8000/docs`.

- For IDE usage (e.g. PyCharm) without having to configure `uv` as the interpreter, I added [`run_app.py`](run_app.py:1):

  - This script imports the FastAPI app from [`src/main.py`](src/main.py:1) and starts `uvicorn` directly.
  - In PyCharm you can:
    - Set `run_app.py` as a Run/Debug configuration.
    - Use your configured Python 3.12.7 interpreter / virtualenv.
    - Run/debug the service without typing `uv` commands manually.

### Running tests and coverage

- To run the unit tests manually:

  ```bash
  uv run pytest
  ```

- To run tests **with coverage** manually:

  ```bash
  uv run coverage run -m pytest && uv run coverage report -m
  ```

- I also enforce tests with coverage automatically on each commit via pre-commit (see “Tooling and automation” below):
  - A local hook in [`.pre-commit-config.yaml`](.pre-commit-config.yaml:1) runs:
    - `uv run coverage run -m pytest && uv run coverage report -m`
  - Commits are rejected if linting or tests/coverage fail.

## Time Spent

- First try: ~2 hours

## Tooling and automation

- Environment and commands are managed via [`uv`](pyproject.toml:1) (e.g. `uv sync`, `uv run ...`).
- Linting and formatting are enforced by Ruff, configured in [`ruff.toml`](ruff.toml:1) and wired into pre-commit.
- A local pre-commit hook runs unit tests **with coverage** on every commit, configured in [`.pre-commit-config.yaml`](.pre-commit-config.yaml:1):
  - `uv run coverage run -m pytest && uv run coverage report -m`
- This means a commit will fail fast if either linting or tests/coverage fail, keeping the main branch green.

## Challenges & Solutions

- TODO: List notable challenges and how you solved them.

## GenAI Usage

- TODO: Describe how you used AI tools during development.

## API Design Decisions

- TODO: Explain your endpoint structure, models, and error handling choices.

## Third-party API / Database Selection

I chose **ipapi.co** as the external IP geolocation provider.

**Reasons:**

- **Generous free tier for a take-home**: up to **30,000 free lookups per month**, with a hard cap of **1,000 requests per 24 hours**. This is more than enough for local development and reviewer testing.
- **No mandatory API key for basic usage**: the public `/json/` endpoints work without authentication, which keeps the initial setup simple. An API key can be added later if needed.
- **Straightforward JSON schema**: the response includes most of the fields we care about (IP, country, region, city, coordinates, timezone, organisation/ISP) so the normalization logic in [`IpGeolocationData`](src/ipapi_client.py:10) is relatively small.
- **Mature hosted API**: avoids the overhead of managing and periodically updating a local GeoIP database for the purposes of this exercise. In a production system, we could still swap this out for a local database-backed provider behind the same interface.

The dedicated client [`IpapiClient`](src/ipapi_client.py:43) wraps ipapi.co using `httpx.AsyncClient` and returns a normalized Pydantic v2 model [`IpGeolocationData`](src/ipapi_client.py:10). Error conditions (invalid IP, not found, upstream failures) are mapped to explicit exceptions (`InvalidIpError`, `IpNotFoundError`, `UpstreamServiceError`), so the FastAPI layer can translate them into consistent HTTP responses.

**Organisation / ISP field**

The `isp` field in [`IpGeolocationData`](src/ipapi_client.py:10) represents the **Internet Service Provider** or organisation that owns and operates the IP address (e.g. "Google LLC", "Comcast Cable Communications, LLC", major cloud providers, hosting/VPN networks). ipapi.co exposes this as the `org` field, which I map directly to `isp`. This is useful for:

- Distinguishing between residential, corporate, and data-centre/cloud traffic.
- Supporting fraud detection and risk scoring based on network type.
- Applying access policies (e.g. blocking known VPN/hosting ranges).

**IP validation (IPv4 + IPv6)**

For the public `/v1/ip/lookup` endpoint I validate the optional `ip` query parameter using
Python's standard library `ipaddress` module, via a Pydantic field validator on
[`IPLookupRequest`](src/main.py:21):

- If `ip` is **missing**, `null`, or a blank string → it is normalized to `None` and the
  service performs a **client IP lookup**, relying on ipapi.co's automatic detection.
- If `ip` is non-empty → it must be a valid **IPv4 or IPv6** literal; otherwise the
  validator raises an error and FastAPI returns a 422 validation response. In that case
  the handler is never invoked and **no call is made** to the external geolocation
  provider.

This keeps the upstream integration clean (no unnecessary traffic for obviously bad
inputs) and makes the API contract explicit: only syntactically valid IP addresses are
accepted for explicit lookup.

**TODO: Reserved / local IP handling**

A future improvement is to short-circuit lookups for **reserved/local IP ranges** (e.g.
`192.168.0.0/16`, `10.0.0.0/8`, `127.0.0.0/8`, link-local ranges, etc.) using the
standard library `ipaddress` module:

- If a client explicitly passes such an IP (e.g. `192.168.0.1`), the service can:
  - Detect that it is a private or otherwise non-routable address.
  - **Avoid calling** the external IP geolocation provider.
  - Return a deterministic response or error, for example an error code like
    `"reserved_ip"` with a message such as `"Reserved IP address"`.

This would reduce unnecessary upstream calls and make the behavior for non-public IPs
explicit and predictable.

## Production Readiness

- TODO: List 5–10 things you would do next for production readiness (
  e.g. observability, CI/CD, caching, retries, configuration hardening).