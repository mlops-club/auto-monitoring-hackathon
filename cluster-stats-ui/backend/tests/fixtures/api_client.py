"""Pytest fixture for the FastAPI test client."""

import pytest
from fastapi.testclient import TestClient

from cs_backend.main import create_app
from cs_backend.settings import Settings


@pytest.fixture
def client() -> TestClient:
    settings = Settings(app_name="Test Cluster Stats API")
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client
