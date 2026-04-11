"""Functional tests that run against a live server.

These tests expect the API to be running at the URL specified by the
HELLO_API_BASE_URL environment variable (default: http://localhost:3000).

Run with:
    HELLO_API_BASE_URL=http://localhost:3000 pytest tests/functional_tests/
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("HELLO_API_BASE_URL", "http://localhost:3000")


@pytest.fixture
def http_client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL) as client:
        yield client


def test__health_check(http_client: httpx.Client):
    response = http_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test__greeting(http_client: httpx.Client):
    response = http_client.get("/greetings")
    assert response.status_code == 200
    assert response.json()["message"] == "Hello, World!"


def test__personalized_greeting(http_client: httpx.Client):
    response = http_client.get("/greetings/Bob")
    assert response.status_code == 200
    assert response.json()["message"] == "Hello, Bob!"
