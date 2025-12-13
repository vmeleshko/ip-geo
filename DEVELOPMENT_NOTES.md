# DEVELOPMENT_NOTES

## Implementation Walkthrough

- TODO: Describe initial setup (tooling, project structure, dependencies).
- TODO: Describe how you implemented the IP lookup endpoints.
- TODO: Describe how you integrated the external IP geolocation provider.

## Time Spent

- TODO: Track approximate time spent (e.g. 3.5h total).

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

## Production Readiness

- TODO: List 5–10 things you would do next for production readiness (
  e.g. observability, CI/CD, caching, retries, configuration hardening).