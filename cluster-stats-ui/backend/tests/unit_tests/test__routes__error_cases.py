"""Error-case tests for API routes."""

from fastapi import status
from fastapi.testclient import TestClient


def test__get_nonexistent_route(client: TestClient):
    response = client.get("/nonexistent")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test__post_to_health__method_not_allowed(client: TestClient):
    response = client.post("/health")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
