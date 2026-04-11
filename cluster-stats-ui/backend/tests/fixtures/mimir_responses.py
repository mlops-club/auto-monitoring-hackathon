"""Canned Prometheus API responses for Mimir endpoint tests."""

import httpx
import pytest
import respx

from cs_backend.mimir import MimirClient

MIMIR_BASE = "http://mimir-test:8080"

# -- Instant query responses --

CPU_UTIL = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100"}, "value": [1712345678.0, "35.2"]},
            {"metric": {"instance": "10.0.0.2:9100"}, "value": [1712345678.0, "82.1"]},
        ],
    },
}

RAM_USED_PCT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100"}, "value": [1712345678.0, "20.5"]},
            {"metric": {"instance": "10.0.0.2:9100"}, "value": [1712345678.0, "71.3"]},
        ],
    },
}

RAM_TOTAL = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100"}, "value": [1712345678.0, "2147483648"]},
            {"metric": {"instance": "10.0.0.2:9100"}, "value": [1712345678.0, "2147483648"]},
        ],
    },
}

SWAP_USED_PCT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100"}, "value": [1712345678.0, "0"]},
            {"metric": {"instance": "10.0.0.2:9100"}, "value": [1712345678.0, "12.4"]},
        ],
    },
}

DISK_FREE = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100", "device": "nvme0n1"}, "value": [1712345678.0, "78.0"]},
            {"metric": {"instance": "10.0.0.1:9100", "device": "nvme1n1"}, "value": [1712345678.0, "12.0"]},
            {"metric": {"instance": "10.0.0.2:9100", "device": "nvme0n1"}, "value": [1712345678.0, "8.0"]},
        ],
    },
}

DISK_IOPS = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100", "device": "nvme0n1"}, "value": [1712345678.0, "120"]},
            {"metric": {"instance": "10.0.0.1:9100", "device": "nvme1n1"}, "value": [1712345678.0, "380"]},
            {"metric": {"instance": "10.0.0.2:9100", "device": "nvme0n1"}, "value": [1712345678.0, "480"]},
        ],
    },
}

DISK_TPUT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100", "device": "nvme0n1"}, "value": [1712345678.0, "2100000"]},
            {"metric": {"instance": "10.0.0.1:9100", "device": "nvme1n1"}, "value": [1712345678.0, "5800000"]},
            {"metric": {"instance": "10.0.0.2:9100", "device": "nvme0n1"}, "value": [1712345678.0, "6800000"]},
        ],
    },
}

NET_BW = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100", "device": "eth0"}, "value": [1712345678.0, "30000000"]},
            {"metric": {"instance": "10.0.0.2:9100", "device": "eth0"}, "value": [1712345678.0, "88000000"]},
        ],
    },
}

NET_SPEED = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100", "device": "eth0"}, "value": [1712345678.0, "12500000000"]},
            {"metric": {"instance": "10.0.0.2:9100", "device": "eth0"}, "value": [1712345678.0, "12500000000"]},
        ],
    },
}

NET_DROPS = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"instance": "10.0.0.1:9100", "device": "eth0"}, "value": [1712345678.0, "0"]},
            {"metric": {"instance": "10.0.0.2:9100", "device": "eth0"}, "value": [1712345678.0, "1247"]},
        ],
    },
}

# Ordered to match _INSTANT_QUERIES key order
ALL_INSTANT_RESPONSES = [
    CPU_UTIL,
    RAM_USED_PCT,
    RAM_TOTAL,
    SWAP_USED_PCT,
    DISK_FREE,
    DISK_IOPS,
    DISK_TPUT,
    NET_BW,
    NET_SPEED,
    NET_DROPS,
]

# -- Range query response --

CPU_RANGE = {
    "status": "success",
    "data": {
        "resultType": "matrix",
        "result": [
            {
                "metric": {"node": "node-1"},
                "values": [
                    [1712345600.0, "32.1"],
                    [1712345660.0, "34.8"],
                    [1712345720.0, "36.2"],
                ],
            }
        ],
    },
}

EMPTY_RESPONSE = {
    "status": "success",
    "data": {"resultType": "vector", "result": []},
}

ERROR_RESPONSE = {
    "status": "error",
    "errorType": "bad_data",
    "error": "invalid parameter 'query'",
}


@pytest.fixture
def mimir_router():
    """respx router with all instant queries mocked. Returns the router for customization."""
    with respx.mock(base_url=MIMIR_BASE, assert_all_called=False) as router:
        # Mock all instant queries to return their canned responses
        # respx matches by URL pattern; all go to /prometheus/api/v1/query
        router.get("/prometheus/api/v1/query").mock(
            side_effect=_instant_query_side_effect,
        )
        router.get("/prometheus/api/v1/query_range").mock(
            return_value=httpx.Response(200, json=CPU_RANGE),
        )
        yield router


def _instant_query_side_effect(request: httpx.Request) -> httpx.Response:
    """Route instant queries to the right canned response based on the query param."""
    from cs_backend.routes import _INSTANT_QUERIES

    query = str(request.url.params.get("query", ""))
    queries_list = list(_INSTANT_QUERIES.values())
    for i, q in enumerate(queries_list):
        if q == query:
            return httpx.Response(200, json=ALL_INSTANT_RESPONSES[i])
    # Unknown query — return empty
    return httpx.Response(200, json=EMPTY_RESPONSE)


@pytest.fixture
def mock_mimir_client(mimir_router):
    """A MimirClient backed by the respx mock transport."""
    client = MimirClient(base_url=MIMIR_BASE, tenant_id="test")
    yield client
