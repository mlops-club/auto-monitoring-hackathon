"""Happy-path tests for API routes."""

from fastapi import status
from fastapi.testclient import TestClient


def test__get_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "Test Cluster Stats API"


def test__get_health__response_schema(client: TestClient):
    response = client.get("/health")
    data = response.json()
    assert set(data.keys()) == {"status", "app_name"}


def test__get_openapi_docs(client: TestClient):
    """Verify that the OpenAPI docs page (mounted at /) is reachable."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
