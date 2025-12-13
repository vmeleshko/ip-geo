from fastapi import FastAPI

app = FastAPI(
    title="IP Geolocation Service",
    version="0.1.0",
    description="IP geolocation microservice for the take-home test.",
)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}
