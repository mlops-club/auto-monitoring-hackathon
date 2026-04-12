"""API routes for the Cluster Stats backend."""

import asyncio
import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from cs_backend.k8s import get_node_ip_map, get_node_labels
from cs_backend.mimir import MimirClient, MimirQueryError, MimirUnavailableError
from cs_backend.schemas import (
    CpuMetrics,
    DiskMetrics,
    HealthResponse,
    MetricSample,
    NicMetrics,
    NodeHistoryResponse,
    NodeLabelsResponse,
    NodeMetrics,
    NodesResponse,
    RamMetrics,
    UiProbeResponse,
)
from cs_backend.settings import Settings

LOGGER = structlog.get_logger(__name__)
ROUTER = APIRouter()

# PromQL instant queries keyed by metric name.
# Group by "instance" (IP:port) — works whether or not the Alloy "node" relabel
# has been deployed. The backend maps instance IPs to K8s node names via the API.
_INSTANT_QUERIES = {
    "cpu_util": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
    "ram_used_pct": "avg by (instance) (100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))",
    "ram_total": "avg by (instance) (node_memory_MemTotal_bytes)",
    "swap_used_pct": "avg by (instance) (100 * (1 - node_memory_SwapFree_bytes / node_memory_SwapTotal_bytes))",
    "disk_free": 'avg by (instance, device) (100 * node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})',
    "disk_size": 'avg by (instance, device) (node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})',
    "disk_iops": "sum by (instance, device) (rate(node_disk_reads_completed_total[5m]) + rate(node_disk_writes_completed_total[5m]))",
    "disk_tput": "sum by (instance, device) (rate(node_disk_read_bytes_total[5m]) + rate(node_disk_written_bytes_total[5m]))",
    "net_bw": 'sum by (instance, device) (rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[5m]) + rate(node_network_transmit_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[5m]))',
    "net_speed": 'node_network_speed_bytes{device!~"lo|veth.*|docker.*|br-.*"}',
    "net_drops": "sum by (instance, device) (rate(node_network_receive_drop_total[5m]) + rate(node_network_transmit_drop_total[5m]))",
}

# PromQL range query templates — {instance} is interpolated (IP:port)
_HISTORY_QUERIES = {
    "cpu": '100 - (avg by (instance) (rate(node_cpu_seconds_total{{mode="idle",instance="{instance}"}}[5m])) * 100)',
    "ram": 'avg by (instance) (100 * (1 - node_memory_MemAvailable_bytes{{instance="{instance}"}} / node_memory_MemTotal_bytes{{instance="{instance}"}}))',
    "swap": 'avg by (instance) (100 * (1 - node_memory_SwapFree_bytes{{instance="{instance}"}} / node_memory_SwapTotal_bytes{{instance="{instance}"}}))',
    "disk_free": 'avg by (instance) (100 * node_filesystem_avail_bytes{{instance="{instance}",fstype!~"tmpfs|overlay"}} / node_filesystem_size_bytes{{instance="{instance}",fstype!~"tmpfs|overlay"}})',
    "disk_iops": 'sum by (instance) (rate(node_disk_reads_completed_total{{instance="{instance}"}}[5m]) + rate(node_disk_writes_completed_total{{instance="{instance}"}}[5m]))',
    "disk_tput": 'sum by (instance) (rate(node_disk_read_bytes_total{{instance="{instance}"}}[5m]) + rate(node_disk_written_bytes_total{{instance="{instance}"}}[5m]))',
    "net_bw": 'sum by (instance) (rate(node_network_receive_bytes_total{{instance="{instance}",device!~"lo|veth.*|docker.*|br-.*"}}[5m]) + rate(node_network_transmit_bytes_total{{instance="{instance}",device!~"lo|veth.*|docker.*|br-.*"}}[5m]))',
    "net_drops": 'sum by (instance) (rate(node_network_receive_drop_total{{instance="{instance}"}}[5m]) + rate(node_network_transmit_drop_total{{instance="{instance}"}}[5m]))',
}


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _get_mimir(request: Request) -> MimirClient:
    return request.app.state.mimir_client


@ROUTER.get(
    "/health",
    tags=["Health"],
    summary="Health check",
)
async def get_health(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> HealthResponse:
    """Check the health of the API."""
    return HealthResponse(status="healthy", app_name=settings.app_name)


@ROUTER.get(
    "/api/labels",
    tags=["Cluster"],
    summary="K8s node labels",
)
async def get_labels() -> NodeLabelsResponse:
    """Return K8s labels for every node in the cluster (cached ~60 s)."""
    return NodeLabelsResponse(nodes=get_node_labels())


@ROUTER.get(
    "/api/ui-probe",
    tags=["UI"],
    summary="UI probe",
)
async def get_ui_probe(request: Request) -> UiProbeResponse:
    """Emit a log entry that can be triggered from the frontend."""
    LOGGER.info("ui_probe", path=request.url.path)
    return UiProbeResponse(message="Backend probe reached successfully.", request_path=request.url.path)


def _compute_health(cpu_util: float | None, ram_used: float | None, disks: list[DiskMetrics]) -> str:
    if cpu_util is None and ram_used is None and not disks:
        return "unknown"
    if (cpu_util is not None and cpu_util >= 90) or (ram_used is not None and ram_used >= 90) or any(d.free is not None and d.free <= 10 for d in disks):
        return "crit"
    if (cpu_util is not None and cpu_util >= 70) or (ram_used is not None and ram_used >= 70) or any(d.free is not None and d.free <= 20 for d in disks):
        return "warn"
    return "ok"


@ROUTER.get("/api/nodes", tags=["Cluster"], summary="List nodes with current metrics")
async def get_nodes(mimir: MimirClient = Depends(_get_mimir)) -> NodesResponse:  # noqa: B008
    """Query Mimir for current node-exporter metrics and return per-node data."""
    try:
        keys = list(_INSTANT_QUERIES.keys())
        results_list = await asyncio.gather(
            *(mimir.instant_query(q) for q in _INSTANT_QUERIES.values())
        )
    except MimirUnavailableError:
        raise HTTPException(status_code=503, detail="Mimir is unavailable")
    except MimirQueryError as e:
        raise HTTPException(status_code=502, detail=str(e))

    results_by_key = dict(zip(keys, results_list))

    # Build IP -> node name mapping from K8s API
    try:
        ip_to_node = get_node_ip_map()
    except Exception:
        LOGGER.warning("k8s_ip_map_unavailable")
        ip_to_node = {}

    # Get K8s labels (cached, sync call)
    try:
        k8s_labels = get_node_labels()
    except Exception:
        LOGGER.warning("k8s_labels_unavailable")
        k8s_labels = {}

    # Discover all instances from metric results and map to node names
    instance_to_node: dict[str, str] = {}
    for results in results_by_key.values():
        for r in results:
            inst = r.metric.get("instance", "")
            if inst and inst not in instance_to_node:
                ip = inst.rsplit(":", 1)[0]
                instance_to_node[inst] = ip_to_node.get(ip, ip)

    # Collect all node names (from metrics + K8s API)
    all_nodes: set[str] = set(instance_to_node.values())
    all_nodes.update(k8s_labels.keys())

    # Reverse map: node name -> instance string (for lookups)
    node_to_instance: dict[str, str] = {v: k for k, v in instance_to_node.items()}

    def _get_scalar(key: str, instance: str) -> float | None:
        for r in results_by_key.get(key, []):
            if r.metric.get("instance") == instance:
                return r.value
        return None

    def _get_by_device(key: str, instance: str) -> dict[str, float | None]:
        out: dict[str, float | None] = {}
        for r in results_by_key.get(key, []):
            if r.metric.get("instance") == instance:
                dev = r.metric.get("device", "unknown")
                out[dev] = r.value
        return out

    nodes = []
    for node_name in sorted(all_nodes):
        inst = node_to_instance.get(node_name, "")
        ip = inst.rsplit(":", 1)[0] if inst else None

        cpu_util = _get_scalar("cpu_util", inst)
        ram_used = _get_scalar("ram_used_pct", inst)
        ram_total = _get_scalar("ram_total", inst)

        disk_free = _get_by_device("disk_free", inst)
        disk_size = _get_by_device("disk_size", inst)
        disk_iops = _get_by_device("disk_iops", inst)
        disk_tput = _get_by_device("disk_tput", inst)
        all_devs = set(disk_free) | set(disk_size) | set(disk_iops) | set(disk_tput)
        disks = [
            DiskMetrics(
                dev=d,
                free=disk_free.get(d),
                size_bytes=int(disk_size[d]) if disk_size.get(d) is not None else None,
                iops=disk_iops.get(d),
                tput_bytes=disk_tput.get(d),
            )
            for d in sorted(all_devs)
        ]

        net_bw = _get_by_device("net_bw", inst)
        net_speed = _get_by_device("net_speed", inst)
        net_drops = _get_by_device("net_drops", inst)
        all_nics = set(net_bw) | set(net_speed) | set(net_drops)
        nics = [
            NicMetrics(dev=d, bw_bytes=net_bw.get(d), speed_bytes=net_speed.get(d), drops=net_drops.get(d))
            for d in sorted(all_nics)
        ]

        nodes.append(NodeMetrics(
            id=node_name,
            ip=ip,
            health=_compute_health(cpu_util, ram_used, disks),
            labels=k8s_labels.get(node_name, {}),
            cpu=CpuMetrics(util=cpu_util),
            ram=RamMetrics(
                used=ram_used,
                total_bytes=int(ram_total) if ram_total is not None else None,
                used_gb=round(ram_total * (ram_used / 100) / 1e9, 1) if ram_total is not None and ram_used is not None else None,
                swap=_get_scalar("swap_used_pct", inst),
            ),
            disks=disks,
            nics=nics,
        ))

    return NodesResponse(nodes=nodes)


@ROUTER.get("/api/nodes/{node}/history", tags=["Cluster"], summary="Node metric history")
async def get_node_history(
    node: str,
    metric: str = Query(..., description="Metric key: cpu|ram|swap|disk_free|disk_iops|disk_tput|net_bw|net_drops"),
    start: float | None = Query(default=None, description="Start epoch seconds (default: 15 min ago)"),
    end: float | None = Query(default=None, description="End epoch seconds (default: now)"),
    step: str = Query(default="60s", description="Step interval"),
    mimir: MimirClient = Depends(_get_mimir),  # noqa: B008
) -> NodeHistoryResponse:
    """Return time-series samples for a single node and metric."""
    template = _HISTORY_QUERIES.get(metric)
    if template is None:
        raise HTTPException(status_code=400, detail=f"Unknown metric '{metric}'. Valid: {list(_HISTORY_QUERIES)}")

    if end is None:
        end = time.time()
    if start is None:
        start = end - 900  # 15 minutes ago

    # Resolve node name to instance (IP:port) for PromQL filtering
    try:
        ip_to_node = get_node_ip_map()
    except Exception:
        ip_to_node = {}
    node_to_ip = {v: k for k, v in ip_to_node.items()}
    ip = node_to_ip.get(node, node)
    instance = f"{ip}:9100"

    query = template.format(instance=instance)
    try:
        results = await mimir.range_query(query, start=start, end=end, step=step)
    except MimirUnavailableError:
        raise HTTPException(status_code=503, detail="Mimir is unavailable")
    except MimirQueryError as e:
        raise HTTPException(status_code=502, detail=str(e))

    samples = []
    if results:
        samples = [MetricSample(timestamp=ts, value=v) for ts, v in results[0].values]

    return NodeHistoryResponse(node=node, metric=metric, samples=samples)
