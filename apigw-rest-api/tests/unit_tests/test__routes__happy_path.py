"""Happy path tests for API routes."""

from fastapi import status
from fastapi.testclient import TestClient


def test__get_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "Test Hello API"


def test__get_greeting(client: TestClient):
    response = client.get("/greetings")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Hello, World!"}


def test__get_personalized_greeting(client: TestClient):
    response = client.get("/greetings/Alice")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Hello, Alice!"}


def test__openapi_docs_available(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    assert schema["info"]["title"] == "Test Hello API"
    assert "/greetings" in schema["paths"]
    assert "/greetings/{name}" in schema["paths"]
    assert "/health" in schema["paths"]
