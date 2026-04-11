"""Functional tests that run against a live server.

These tests require a running instance of the Cluster Stats backend.
Set the CS_BACKEND_BASE_URL environment variable to the server URL.

Run with:
    CS_BACKEND_BASE_URL=http://localhost:3000 uv run pytest tests/functional_tests/
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("CS_BACKEND_BASE_URL", "http://localhost:3000")

pytestmark = pytest.mark.slow


@pytest.fixture
def http_client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL) as client:
        yield client


def test__health_check(http_client: httpx.Client):
    response = http_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
