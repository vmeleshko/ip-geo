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
      - Uses an `IpLookupProviderFactory` (via dependency injection) to select and construct the concrete upstream IP lookup client based on the `provider` query parameter (defaulting to ipapi.co).
    - [`src/errors.py`](src/errors.py:1) – domain-specific exception types:
      - `InvalidIpError`, `ReservedIpError`, `IpNotFoundError`, `UpstreamServiceError`.
      - Used by the client layer to describe provider failures in a structured way.
    - [`src/exception_handlers.py`](src/exception_handlers.py:1) – shared FastAPI exception handlers:
      - Maps Pydantic validation errors to consistent 400 responses.
      - Adds a catch‑all 500 JSON error payload for truly unhandled exceptions.
    - [`src/clients/`](src/clients/__init__.py:1) – external integration layer:
      - [`src/clients/base.py`](src/clients/base.py:1) – abstract base client defining the interface for IP lookup providers (`lookup_ip`, `lookup_client_ip`).
      - [`src/clients/ip_api_co_client.py`](src/clients/ip_api_co_client.py:1) – concrete async client for **ipapi.co**:
        - Uses `httpx.AsyncClient`.
        - Normalizes responses into [`IPGeolocationData`](src/models/common.py:1).
        - Translates provider HTTP / JSON errors into the domain errors in [`src/errors.py`](src/errors.py:1).
      - [`src/clients/ip_api_com_client.py`](src/clients/ip_api_com_client.py:1) – concrete async client for **ip-api.com**:
        - Uses `httpx.AsyncClient`.
        - Maps the `status` / `message` semantics of ip-api.com into the same domain errors (`InvalidIpError`, `ReservedIpError`, `IpNotFoundError`, `UpstreamServiceError`).
        - Normalizes fields like `query`, `countryCode`, `regionName`, `lat`/`lon` into [`IPGeolocationData`](src/models/common.py:1).
      - [`src/clients/__init__.py`](src/clients/__init__.py:1) – package marker for `src.clients`.
    - [`src/models/`](src/models/common.py:1) – Pydantic v2 models:
      - [`src/models/request_models.py`](src/models/request_models.py:1) – request-side models:
        - `IPLookupRequest` with validation for the optional `ip` query parameter, including IPv4/IPv6 validation and normalization of blank strings to `None`.
        - A `provider` enum field (`Provider`) that allows selecting `"ipapi-co"` or `"ip-api-com"` and rejects any other value at validation time (e.g. a dummy provider string).
      - [`src/models/response_models.py`](src/models/response_models.py:1) – outward-facing response models:
        - `IPLookupResponse` which represents the API response for `/v1/ip/lookup`.
      - [`src/models/common.py`](src/models/common.py:1) – internal, provider‑agnostic model:
        - `IPGeolocationData` used internally by clients to represent normalized geo data, including lat/lon coercion.
  
  - Tests (`tests/`):
    - [`tests/test_ip_lookup_request.py`](tests/test_ip_lookup_request.py:1) – unit tests for `IPLookupRequest`:
      - Valid IPv4/IPv6, handling of blank/None, and invalid IP validation behavior.
    - [`tests/test_ipapi_client.py`](tests/test_ipapi_client.py:1) – unit tests for [`IpApiCo`](src/clients/ip_api_co_client.py:1):
      - Happy-path lookups for explicit IP and client IP against the ipapi.co provider.
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
  - Commits are rejected if linting or tests/coverage fail, keeping the main branch green.

### Viewing the OpenAPI specification

- The **hand-written spec-first definition** lives in [`openapi/openapi.yaml`](openapi/openapi.yaml:1).
  - Open this file directly in your editor to review the endpoint contract, models, examples, and error shapes.
- To compare the implementation with the spec:
  - Start the app (see “Running the application” above).
  - Run the helper script:

    ```bash
    uv run python export_openapi.py
    ```

  - This exports the FastAPI-generated OpenAPI document to [`openapi/openapi.generated.json`](openapi/openapi.generated.json:1).
  - You can then diff `openapi.yaml` vs `openapi.generated.json` to spot any drift between the spec-first design and the actual implementation.
- For interactive documentation backed by the implementation, use the Swagger UI at `http://127.0.0.1:8000/docs`.

## Time Spent

- Day 1: ~2 hours — initial project setup, first pass at the IP lookup client and basic tests.
- Day 2: ~4 hours — adding the second provider, refining error handling and tests, and iterating on the OpenAPI spec and documentation.
- I intentionally stopped around the 6‑hour mark to stay within the expected time window for the exercise.

## Tooling and automation

- Environment and commands are managed via [`uv`](pyproject.toml:1) (e.g. `uv sync`, `uv run ...`).
- Linting and formatting are enforced by Ruff, configured in [`ruff.toml`](ruff.toml:1) and wired into pre-commit.
- A local pre-commit hook runs unit tests **with coverage** on every commit, configured in [`.pre-commit-config.yaml`](.pre-commit-config.yaml:1):
  - `uv run coverage run -m pytest && uv run coverage report -m`
- This means a commit will fail fast if either linting or tests/coverage fail, keeping the main branch green.

## Challenges & Solutions

- **AI-generated duplication and drift**
  - *Challenge:* The AI model sometimes duplicated logic across files (e.g. repeated mock helpers and overlapping client logic), or reintroduced patterns I had just refactored away.
  - *Solution:* I treated the AI output as a first draft and then iterated: extracting shared helpers into `tests/common.py`, pushing common behavior into base abstractions, and giving the model precise instructions about what to reuse vs. what to centralize.

- **Overly monolithic suggestions from AI**
  - *Challenge:* The model often proposed dropping large chunks of code into a single file (e.g. mixing routers, clients, and models together), which conflicts with my preference for a layered, modular structure.
  - *Solution:* I steered the structure explicitly: separating `src/clients`, `src/models`, `src/errors`, and `src/exception_handlers`, and asking the model to refactor into those modules rather than extending a single file.

- **OpenAPI vs. implementation alignment**
  - *Challenge:* The model was good at generating an initial `openapi/openapi.yaml`, but the first versions did not fully reflect the evolving implementation (e.g. missing the `provider` query parameter, incomplete examples, or not describing all error cases).
  - *Solution:* I iterated on the spec after the code was stable: reviewing the actual FastAPI endpoint and tests, then asking the model to enrich the YAML with more detailed descriptions and examples while making sure it matches the real behavior.

- **AI leaving diff/artifact markers in code and YAML**
  - *Challenge:* While iterating on both Python code and `openapi.yaml`, the AI occasionally left behind artifact blocks that looked like partial diff markers or duplicated sections (e.g. leftover “SEARCH/REPLACE” style chunks that were not valid YAML or Python).
  - *Solution:* I manually reviewed the generated changes, removed any diff-style artifacts, and re-ran tooling (linters, tests, and YAML validation via the editor) to ensure the files were syntactically correct. This reinforced the rule that AI edits must always be treated as proposals that still require a human pass before committing.

## GenAI Usage

- I used GenAI heavily throughout this exercise, primarily via the `gpt-5.1-latest` model (KiloCode) directly in the editor.
- **Where AI helped:**
  - Drafting the initial structure of the FastAPI app and clients, based on the provider documentation.
  - Generating and iterating on unit tests and integration-style tests, including good naming and coverage of edge cases.
  - Producing the initial `openapi/openapi.yaml` and then enriching it with descriptions and examples.
  - Assisting with refactors (e.g. extracting common test helpers, improving error mapping, tightening type hints).
- **How I kept control:**
  - I treated all AI output as suggestions, not ground truth.
  - I enforced my own structure (modules, layering) and asked the model to adapt to that.
  - I reviewed and adjusted the OpenAPI spec and tests to ensure they matched the actual implementation and the take‑home requirements.

## API Design Decisions

- **Single primary endpoint**
  - I expose a single public endpoint: `GET /v1/ip/lookup`. This keeps the surface area small and focuses the service on its core responsibility: resolving IP geolocation.
  - The endpoint supports two modes:
    - Explicit lookup via the optional `ip` query parameter.
    - Implicit client IP lookup when `ip` is omitted or null.

- **Query parameters instead of request bodies for lookups**
  - Because this is a read‑only lookup operation, I use query parameters (`ip`, `provider`) on a GET endpoint rather than a JSON body.
  - The `IPLookupRequest` Pydantic model is still used internally for validation and normalization, but the external API feels natural for typical HTTP clients and tools (curl, browser, etc.).

- **Provider selection via an enum**
  - The `provider` query parameter is validated via an enum (`Provider`) in [`IPLookupRequest`](src/models/request_models.py:1).
  - Default behavior is to use **ipapi.co**, with **ip-api.com** as an explicit alternative.
  - Invalid provider values are rejected at validation time (422), so the endpoint implementation only sees valid, typed providers.

- **Normalized, provider‑agnostic response model**
  - Both upstream providers are normalized into a single internal model `IPGeolocationData`, which is then mapped to the outward‑facing `IPLookupResponse`.
  - This decouples the public API from any individual provider’s schema (field names, optionality, coordinate formats, etc.), and makes it easier to swap providers or add new ones later.

- **Explicit domain error types and consistent error responses**
  - The client layer raises domain‑specific exceptions (`InvalidIpError`, `ReservedIpError`, `IpNotFoundError`, `UpstreamServiceError`) based on HTTP status codes and provider‑specific payloads.
  - Global exception handlers translate these into a small set of consistent error responses with structured `code` fields (e.g. `invalid_ip`, `reserved_ip`, `ip_not_found`, `upstream_error`), as reflected in the OpenAPI spec and tests.
  - This separation keeps provider quirks (status codes, error messages) out of the FastAPI route handler and out of the external API contract.

- **Spec‑first, but implementation‑aligned**
  - I maintain a hand‑written `openapi/openapi.yaml` as the primary description of the API, and I also export an implementation‑generated spec for comparison.
  - When the design evolved (e.g. adding the `provider` parameter), I updated the OpenAPI spec to match the actual FastAPI implementation and tests, keeping it as the single source of truth for documentation and review.

## Third-party API / Database Selection

I chose **ipapi.co** as the primary external IP geolocation provider, and later added **ip-api.com** as an alternative to demonstrate a pluggable provider architecture.

**Reasons:**

- **Generous free tier for a take-home**: up to **30,000 free lookups per month**, with a hard cap of **1,000 requests per 24 hours** for ipapi.co. This is more than enough for local development and reviewer testing.
- **No mandatory API key for basic usage**: the public `/json/` endpoints work without authentication, which keeps the initial setup simple. An API key can be added later if needed.
- **Straightforward JSON schema**: the response includes most of the fields we care about (IP, country, region, city, coordinates, timezone, organisation/ISP) so the normalization logic in [`IPGeolocationData`](src/models/common.py:1) is relatively small.
- **Mature hosted APIs**: avoids the overhead of managing and periodically updating a local GeoIP database for the purposes of this exercise. In a production system, we could still swap this out for a local database-backed provider behind the same interface.

The dedicated clients [`IpApiCo`](src/clients/ip_api_co_client.py:1) and [`IpApiCom`](src/clients/ip_api_com_client.py:1) both use `httpx.AsyncClient` and return a normalized Pydantic v2 model [`IPGeolocationData`](src/models/common.py:1). Error conditions (invalid IP, reserved/private IP, not found, upstream failures, quota/limit exceeded) are mapped to explicit exceptions (`InvalidIpError`, `ReservedIpError`, `IpNotFoundError`, `UpstreamServiceError`), so the FastAPI layer can translate them into consistent HTTP responses regardless of the upstream provider.

**Organisation / ISP field**

The `isp` field in [`IpGeolocationData`](src/ipapi_client.py:10) represents the **Internet Service Provider** or organisation that owns and operates the IP address (e.g. "Google LLC", "Comcast Cable Communications, LLC", major cloud providers, hosting/VPN networks). ipapi.co exposes this as the `org` field, which I map directly to `isp`. This is useful for:

- Distinguishing between residential, corporate, and data-centre/cloud traffic.
- Supporting fraud detection and risk scoring based on network type.
- Applying access policies (e.g. blocking known VPN/hosting ranges).

**IP validation (IPv4 + IPv6) and provider selection**

For the public `/v1/ip/lookup` endpoint I validate the optional `ip` query parameter using
Python's standard library `ipaddress` module, via a Pydantic field validator on
[`IPLookupRequest`](src/models/request_models.py:6):

- If `ip` is **missing**, `null`, or a blank string → it is normalized to `None` and the
  service performs a **client IP lookup**, relying on ipapi.co's automatic detection.
- If `ip` is non-empty → it must be a valid **IPv4 or IPv6** literal; otherwise the
  validator raises an error and FastAPI returns a 422 validation response. In that case
  the handler is never invoked and **no call is made** to the external geolocation
  provider.

This keeps the upstream integration clean (no unnecessary traffic for obviously bad
inputs) and makes the API contract explicit: only syntactically valid IP addresses are
accepted for explicit lookup.

Additionally, `IPLookupRequest` includes a `provider` enum field that allows callers to select
which upstream provider to use:

- If `provider` is **omitted** or `null` → Pydantic applies the default and the service uses
  **ipapi.co** as the **default lookup IP provider**.
- If `provider` is `"ip-api-com"` → the factory uses the **ip-api.com** client.
- If `provider` is any other string → Pydantic raises a validation error before the handler
  runs, so invalid/dummy providers are rejected cleanly as 422s.

Provider selection is implemented in [`IpLookupProviderFactory`](src/main.py:24), which is
injected into the endpoint via FastAPI's dependency system. The factory maintains a mapping
from `Provider` enum values (e.g. `"ipapi-co"`, `"ip-api-com"`) to concrete client classes
(e.g. [`IpApiCo`](src/clients/ip_api_co_client.py:1), [`IpApiCom`](src/clients/ip_api_com_client.py:1)) and,
when called, returns a configured `BaseIPLookupClient` instance. This keeps the endpoint thin and
decoupled from the construction and configuration details of individual providers.

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

Below is a non-exhaustive list of possible next steps I would consider for making this
service production-ready. Many of these require alignment with a Product Owner / Architect
(first on requirements, budget, and expected traffic patterns) before implementation.

1. **Observability and error monitoring (Sentry or similar)**
   - Integrate Sentry (or an equivalent tool) to capture unhandled exceptions, structured
     logs, and basic performance profiling (slow endpoints, external calls).
   - Standardize log structure (JSON logs with correlation IDs / request IDs) so logs can be
     aggregated and queried across instances.
   - Ensure that sensitive data (e.g. IPs from specific tenants, auth data) is either
     masked or excluded from logs and error reports where required.

2. **Metrics and basic tracing**
   - Expose Prometheus-style metrics (or use another metrics backend) for:
     - Request rate, latency, and error rate per endpoint and per provider.
     - Upstream provider metrics (success vs. failure by error type).
   - Add minimal tracing (e.g. OpenTelemetry) for the HTTP request path and upstream
     calls, so issues can be traced end-to-end across services.

3. **Retries and backoff policy (after product discussion)**
   - Currently the idea is to avoid automatic retries and simply return upstream failures
     as they are mapped today.
   - Before adding retries, I would clarify with the Product Owner:
     - Acceptable impact on latency.
     - Error budget and tolerance for duplicate upstream requests.
     - Cost implications for third-party API quotas.
   - Depending on that discussion, selectively introduce retries with exponential backoff
     only for clearly transient upstream failures (e.g. timeouts, 5xx), and keep the
     policy configurable.

4. **Response caching for popular IPs (e.g. Redis), if justified**
   - Consider adding a short-lived cache (Redis or another in-memory store) for frequently
     looked up IPs to:
     - Reduce latency for repeated queries.
     - Decrease load and cost on upstream providers.
   - Because caching introduces operational cost and another moving part, it should be
     added only if there is a clear usage pattern and business value; this is something
     to validate with Product / Architecture first.

5. **Security: authentication and access control**
   - Introduce a simple authentication mechanism such as:
     - API keys for partners / internal clients, or
     - OAuth2 / Bearer tokens, depending on how the product will be sold and integrated.
   - Clarify with Product / Architecture how access control should work:
     - Per-tenant rate limits, quotas, or billing models.
     - Separation between internal and external consumers.
   - Harden input and headers handling (e.g. stricter parsing of `X-Forwarded-For` in
     real deployments behind proxies) as part of an overall security review.

6. **CI/CD pipeline and environments**
   - Set up a basic CI pipeline (GitHub Actions or Jenkins) that runs:
     - `ruff` for linting/formatting.
     - `mypy` for static type checking.
     - `pytest` + coverage.
   - Add at least two environments (testing/staging and production) and a deployment
     script or job that:
     - Accepts the target environment as a parameter.
     - Applies the correct configuration (e.g. provider timeouts, Sentry DSN, logging
       level, upstream URLs) for that environment.
   - The exact tooling (e.g. container registry, deployment workflow) should be aligned
     with the chosen cloud/platform.

7. **Deployment packaging and platform alignment**
   - Package the service as a container image with a minimal base (e.g. Python slim image)
     and clear health checks.
   - Whether this runs on plain VMs, Docker-only, or Kubernetes (with Helm charts, etc.)
     depends on the broader platform strategy; that decision should be made with the
     Product Owner / Architect.
   - Once the platform is chosen, add readiness/liveness probes and basic autoscaling
     rules (if applicable).

8. **Configuration and secrets management**
   - Centralize runtime configuration (timeouts, base URLs, feature flags, auth
     configuration, Sentry DSN, etc.) via environment variables or a config service.
   - Store secrets (API keys, tokens) in a secure secrets manager provided by the target
     platform rather than in code or plain configuration files.

9. **Load and capacity testing with Locust**
   - Introduce load testing with Locust to understand how many concurrent users and
     requests per second the service can realistically handle for `/v1/ip/lookup`.
   - Design scenarios that ramp up users and request rates until the system starts to
     degrade, and record:
     - Latency distributions (p50/p90/p99) under load.
     - Error rates and error types (e.g. timeouts, upstream provider failures, 5xx).
   - Use the results to:
     - Validate whether upstream provider limits or timeouts become an issue.
     - Inform decisions on autoscaling policies, caching strategy, and whether retries
       are worth the added complexity.
     - Provide concrete numbers during reviews (e.g. “on this hardware we sustain
       N requests/sec with <X ms p99 latency before errors rise above Y%”).

These items are intentionally framed as *possible improvements* rather than a fixed plan;
the exact roadmap would depend on stakeholder priorities, expected traffic, and hosting
constraints.

## Example IP addresses for manual testing

IPv4 examples (different countries)
8.8.8.8
1.1.1.1
5.9.164.112
51.158.0.0
51.140.0.0
37.48.0.0
24.114.0.0
133.130.0.0
1.40.0.0
177.128.0.0

IPv6 examples
2001:4860:4860::8888
2001:4860:4860::8844
2606:4700:4700::1111
2606:4700:4700::1001
2001:db8::1
2001:db8:abcd:0012::1
2001:0db8:85a3::8a2e:0370:7334
2404:6800:4001::200e
2a00:1450:4001::200e
2800:3f0:4001::200e

Local / reserved IP addresses
192.168.1.1
10.0.0.1
172.16.0.1
127.0.0.1
169.254.10.20
