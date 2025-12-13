# DEVELOPMENT_NOTES

## Implementation Walkthrough

- TODO: Describe initial setup (tooling, project structure, dependencies).
- TODO: Describe how you implemented the IP lookup endpoints.
- TODO: Describe how you integrated the external IP geolocation provider.

## Time Spent

- First try: ~2 hours

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