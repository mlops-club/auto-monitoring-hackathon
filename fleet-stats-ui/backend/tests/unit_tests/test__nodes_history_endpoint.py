"""Unit tests for GET /api/nodes/{node}/history."""

from fastapi.testclient import TestClient


def test__get_history__returns_samples(client_with_mimir: TestClient):
    resp = client_with_mimir.get("/api/nodes/node-1/history", params={
        "metric": "cpu", "start": 1712345600, "end": 1712345720,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["node"] == "node-1"
    assert data["metric"] == "cpu"
    assert len(data["samples"]) == 3
    assert data["samples"][0]["value"] == 32.1


def test__get_history__400_unknown_metric(client_with_mimir: TestClient):
    resp = client_with_mimir.get("/api/nodes/node-1/history", params={
        "metric": "bogus", "start": 0, "end": 1,
    })
    assert resp.status_code == 400
    assert "bogus" in resp.json()["detail"]


def test__get_history__defaults_start_end(client_with_mimir: TestClient):
    """start and end are optional — omitting them should still return 200."""
    resp = client_with_mimir.get("/api/nodes/node-1/history", params={"metric": "cpu"})
    assert resp.status_code == 200
