"""Fetch K8s node labels from the cluster API."""

import time

import structlog
from kubernetes import client, config

LOGGER = structlog.get_logger(__name__)

_cache: dict[str, dict[str, str]] | None = None
_cache_ts: float = 0.0
_CACHE_TTL_SECONDS = 60.0


def _load_k8s_config() -> None:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


def get_node_labels() -> dict[str, dict[str, str]]:
    """Return ``{node_name: {label_key: label_value, ...}}`` with a 60 s TTL cache."""
    global _cache, _cache_ts  # noqa: PLW0603

    now = time.monotonic()
    if _cache is not None and (now - _cache_ts) < _CACHE_TTL_SECONDS:
        return _cache

    _load_k8s_config()
    v1 = client.CoreV1Api()
    nodes = v1.list_node()

    result = {
        node.metadata.name: node.metadata.labels or {}
        for node in nodes.items
    }

    _cache = result
    _cache_ts = now
    LOGGER.info("k8s_node_labels_refreshed", node_count=len(result))
    return result


def get_node_ip_map() -> dict[str, str]:
    """Return ``{internal_ip: node_name}`` from K8s node status addresses."""
    _load_k8s_config()
    v1 = client.CoreV1Api()
    nodes = v1.list_node()
    ip_map: dict[str, str] = {}
    for node in nodes.items:
        for addr in node.status.addresses or []:
            if addr.type == "InternalIP":
                ip_map[addr.address] = node.metadata.name
    return ip_map
