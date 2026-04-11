"""Pytest fixture for the FastAPI test client."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cs_backend.main import create_app
from cs_backend.settings import Settings


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    static_dir = tmp_path / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<!doctype html><html><body>cluster stats ui</body></html>")
    (assets_dir / "app.js").write_text('console.log("cluster stats ui");')

    settings = Settings(app_name="Test Cluster Stats API", static_dir=static_dir)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client
