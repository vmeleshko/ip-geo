# IP Geolocation Service

FastAPI microservice for IP address geolocation, implemented as a take‑home exercise.

## Overview

The service exposes endpoints to:

- Look up geolocation information for an explicit IPv4 address.
- Look up geolocation information for the calling client IP.

The API is designed **spec‑first**, with an OpenAPI definition stored at [`openapi/openapi.yaml`](openapi/openapi.yaml:1).

## Requirements

- Python **3.12.x** (developed and tested with 3.12.7).
- [`uv`](https://docs.astral.sh/uv/) for environment and dependency management.
- (Optional) [`pre-commit`](https://pre-commit.com/) if you want pre-commit hooks to run locally.

## Environment setup (uv)

1. **Install uv** (one-time per machine). For Linux/macOS, the recommended installer is:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   Or via pip/pipx if you prefer:

   ```bash
   pip install uv
   # or
   pipx install uv
   ```

2. **Create/sync the virtual environment** in the project root:

   ```bash
   uv sync
   ```

   This reads [`pyproject.toml`](pyproject.toml:1) and `uv.lock` and creates a virtual environment with all
   runtime and development dependencies.

## Running the API locally

Run the FastAPI app with uvicorn through uv:

```bash
uv run uvicorn src.main:app --reload
```

By default, the app listens on `http://127.0.0.1:8000`.

- Interactive docs (Swagger UI): `http://127.0.0.1:8000/docs`
- ReDoc docs: `http://127.0.0.1:8000/redoc`

## Tests

Run the test suite with:

```bash
uv run pytest
```

Run the test suite **with coverage**:

```bash
uv run coverage run -m pytest && uv run coverage report -m
```

## Code quality

This project uses [`ruff`](ruff.toml:1) for both linting and formatting.

- Lint the codebase:

  ```bash
  uv run ruff check .
  ```

- Format the codebase:

  ```bash
  uv run ruff format .
  ```

Static type checking is done with `mypy` (configured via [`pyproject.toml`](pyproject.toml:1)):

```bash
uv run mypy .
```

### pre-commit hooks

If you want ruff/ruff-format to run automatically on each commit, enable pre-commit hooks:

```bash
uv run pre-commit install
```

The hooks themselves are configured in [`.pre-commit-config.yaml`](.pre-commit-config.yaml:1).

## Development notes

Additional implementation details and reflection on the exercise are tracked in
[`DEVELOPMENT_NOTES.md`](DEVELOPMENT_NOTES.md:1).
