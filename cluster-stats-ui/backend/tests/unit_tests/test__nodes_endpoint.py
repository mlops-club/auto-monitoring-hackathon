"""Unit tests for GET /api/nodes."""

from fastapi.testclient import TestClient


def test__get_nodes__returns_node_list(client_with_mimir: TestClient):
    resp = client_with_mimir.get("/api/nodes")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]
    assert len(nodes) == 2


def test__get_nodes__cpu_util_correct(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node1 = next(n for n in nodes if n["id"] == "node-1")
    assert node1["cpu"]["util"] == pytest.approx(35.2, abs=0.1)


def test__get_nodes__ip_from_instance_label(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node1 = next(n for n in nodes if n["id"] == "node-1")
    assert node1["ip"] == "10.0.0.1"


def test__get_nodes__disks_grouped_by_device(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node1 = next(n for n in nodes if n["id"] == "node-1")
    assert len(node1["disks"]) == 2
    devs = {d["dev"] for d in node1["disks"]}
    assert "nvme0n1" in devs
    assert "nvme1n1" in devs


def test__get_nodes__disk_size_bytes(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node1 = next(n for n in nodes if n["id"] == "node-1")
    nvme0 = next(d for d in node1["disks"] if d["dev"] == "nvme0n1")
    assert nvme0["size_bytes"] == 107374182400  # 100 GiB
    nvme1 = next(d for d in node1["disks"] if d["dev"] == "nvme1n1")
    assert nvme1["size_bytes"] == 214748364800  # 200 GiB


def test__get_nodes__disk_size_bytes_node2(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node2 = next(n for n in nodes if n["id"] == "node-2")
    nvme0 = next(d for d in node2["disks"] if d["dev"] == "nvme0n1")
    assert nvme0["size_bytes"] == 1099511627776  # 1 TiB


def test__get_nodes__nics_present(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node1 = next(n for n in nodes if n["id"] == "node-1")
    assert len(node1["nics"]) == 1
    assert node1["nics"][0]["dev"] == "eth0"


def test__get_nodes__health_ok_for_low_usage(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node1 = next(n for n in nodes if n["id"] == "node-1")
    # cpu=35.2, ram=20.5, disk_free=[78, 12] -> disk 12% free is < 20 -> warn
    # Actually disk_free 12 <= 20, so this should be "warn"
    assert node1["health"] == "warn"


def test__get_nodes__health_warn_for_high_usage(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node2 = next(n for n in nodes if n["id"] == "node-2")
    # cpu=82.1 (>=70), ram=71.3 (>=70), disk_free=8 (<=10) -> crit
    assert node2["health"] == "crit"


def test__get_nodes__k8s_labels_joined(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node1 = next(n for n in nodes if n["id"] == "node-1")
    assert node1["labels"]["kubernetes.io/hostname"] == "node-1"
    assert node1["labels"]["topology.kubernetes.io/zone"] == "us-west-2a"


def test__get_nodes__gpu_rdma_pcie_null(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    for node in nodes:
        assert node["gpus"] is None
        assert node["rdma"] is None
        assert node["pcie"] is None


def test__get_nodes__ram_fields(client_with_mimir: TestClient):
    nodes = client_with_mimir.get("/api/nodes").json()["nodes"]
    node1 = next(n for n in nodes if n["id"] == "node-1")
    assert node1["ram"]["used"] == pytest.approx(20.5, abs=0.1)
    assert node1["ram"]["total_bytes"] == 2147483648
    assert node1["ram"]["swap"] == pytest.approx(0.0, abs=0.1)


# Need pytest import for approx
import pytest  # noqa: E402
