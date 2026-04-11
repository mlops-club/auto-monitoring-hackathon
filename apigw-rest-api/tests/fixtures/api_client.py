"""Pytest fixture for the FastAPI test client."""

import pytest
from fastapi.testclient import TestClient

from hello_api.main import create_app
from hello_api.settings import Settings


@pytest.fixture
def client() -> TestClient:
    settings = Settings(app_name="Test Hello API")
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client
