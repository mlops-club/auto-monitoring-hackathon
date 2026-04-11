"""Tests for serving built frontend assets."""

from fastapi import status
from fastapi.testclient import TestClient


def test__root_serves_index_html(client: TestClient):
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert "cluster stats ui" in response.text


def test__built_asset_is_served(client: TestClient):
    response = client.get("/assets/app.js")
    assert response.status_code == status.HTTP_200_OK
    assert 'console.log("cluster stats ui");' in response.text


def test__spa_route_falls_back_to_index_html(client: TestClient):
    response = client.get("/clusters/demo")
    assert response.status_code == status.HTTP_200_OK
    assert "cluster stats ui" in response.text
