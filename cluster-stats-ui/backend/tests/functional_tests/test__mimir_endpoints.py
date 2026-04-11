"""Functional tests for Mimir-backed endpoints.

Run against a live backend + Mimir (port-forwarded):
    CS_BACKEND_BASE_URL=http://localhost:8000 uv run pytest tests/functional_tests/ -m slow
"""

import os
import time

import httpx
import pytest

BASE_URL = os.environ.get("CS_BACKEND_BASE_URL", "http://localhost:8000")

pytestmark = pytest.mark.slow


@pytest.fixture
def http_client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL) as client:
        yield client


def _get_nodes_or_skip(http_client: httpx.Client) -> list[dict]:
    resp = http_client.get("/api/nodes")
    if resp.status_code == 503:
        pytest.skip("Mimir unavailable")
    assert resp.status_code == 200
    return resp.json()["nodes"]


def test__get_nodes__at_least_one_node(http_client: httpx.Client):
    nodes = _get_nodes_or_skip(http_client)
    assert len(nodes) >= 1


def test__get_nodes__has_cpu_and_ram(http_client: httpx.Client):
    nodes = _get_nodes_or_skip(http_client)
    assert nodes[0]["cpu"]["util"] is not None
    assert nodes[0]["ram"]["used"] is not None


def test__get_nodes__has_disks_and_nics(http_client: httpx.Client):
    nodes = _get_nodes_or_skip(http_client)
    assert len(nodes[0]["disks"]) >= 1
    assert len(nodes[0]["nics"]) >= 1


def test__get_nodes__gpu_rdma_pcie_null(http_client: httpx.Client):
    nodes = _get_nodes_or_skip(http_client)
    for node in nodes:
        assert node["gpus"] is None
        assert node["rdma"] is None
        assert node["pcie"] is None


def test__get_history__cpu_returns_samples(http_client: httpx.Client):
    nodes = _get_nodes_or_skip(http_client)
    node_id = nodes[0]["id"]
    end = time.time()
    start = end - 3600
    resp = http_client.get(f"/api/nodes/{node_id}/history", params={
        "metric": "cpu", "start": start, "end": end,
    })
    assert resp.status_code == 200
    assert len(resp.json()["samples"]) > 0
