"""Pytest fixture for the FastAPI test client."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cs_backend.main import create_app
from cs_backend.mimir import MimirClient
from cs_backend.settings import Settings

_MIMIR_BASE = "http://mimir-test:8080"


def _make_test_settings(tmp_path: Path) -> Settings:
    static_dir = tmp_path / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<!doctype html><html><body>fleet stats ui</body></html>")
    (assets_dir / "app.js").write_text('console.log("fleet stats ui");')
    return Settings(app_name="Test Fleet Stats API", static_dir=static_dir, mimir_base_url=_MIMIR_BASE)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = _make_test_settings(tmp_path)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client_with_mimir(tmp_path: Path, mock_mimir_client: MimirClient, monkeypatch) -> TestClient:
    """TestClient with Mimir queries mocked via respx and K8s labels stubbed."""
    settings = _make_test_settings(tmp_path)
    app = create_app(settings=settings)

    # Stub K8s calls so tests don't need a real cluster
    monkeypatch.setattr(
        "cs_backend.routes.get_node_labels",
        lambda: {
            "node-1": {"kubernetes.io/hostname": "node-1", "topology.kubernetes.io/zone": "us-west-2a"},
            "node-2": {"kubernetes.io/hostname": "node-2", "topology.kubernetes.io/zone": "us-west-2b"},
        },
    )
    monkeypatch.setattr(
        "cs_backend.routes.get_node_ip_map",
        lambda: {"10.0.0.1": "node-1", "10.0.0.2": "node-2"},
    )

    with TestClient(app) as tc:
        # Replace the lifespan-created client with our mock
        app.state.mimir_client = mock_mimir_client
        yield tc
