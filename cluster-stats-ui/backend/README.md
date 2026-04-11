# Cluster Stats Backend

FastAPI backend for the Cluster Stats monitoring UI.

## Setup

```bash
uv sync --all-extras
```

## Run

```bash
uv run uvicorn cs_backend.main:create_app --factory --host 0.0.0.0 --port 3000 --reload
```

OpenAPI docs are served at `http://localhost:3000/`.

## Test

Run unit tests (fast, no external dependencies):

```bash
uv run pytest tests/unit_tests/ -v
```

Run all tests excluding slow/functional ones:

```bash
uv run pytest tests/ -v -m "not slow"
```

Run functional tests against a live server:

```bash
CS_BACKEND_BASE_URL=http://localhost:3000 uv run pytest tests/functional_tests/ -v
```
