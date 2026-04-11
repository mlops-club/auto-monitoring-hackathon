"""Unit tests for the MimirClient."""

import httpx
import pytest
import respx

from cs_backend.mimir import MimirClient, MimirQueryError, MimirUnavailableError

pytestmark = pytest.mark.anyio

BASE = "http://mimir-test:8080"


async def test__instant_query__parses_vector():
    async with respx.mock(base_url=BASE, assert_all_called=False) as router:
        router.get("/prometheus/api/v1/query").mock(
            return_value=httpx.Response(200, json={
                "status": "success",
                "data": {"resultType": "vector", "result": [
                    {"metric": {"node": "n1"}, "value": [1.0, "42.5"]},
                ]},
            }),
        )
        client = MimirClient(base_url=BASE)
        results = await client.instant_query("up")
        assert len(results) == 1
        assert results[0].metric == {"node": "n1"}
        assert results[0].value == 42.5
        await client.aclose()


async def test__instant_query__converts_nan_to_none():
    async with respx.mock(base_url=BASE, assert_all_called=False) as router:
        router.get("/prometheus/api/v1/query").mock(
            return_value=httpx.Response(200, json={
                "status": "success",
                "data": {"resultType": "vector", "result": [
                    {"metric": {"node": "n1"}, "value": [1.0, "NaN"]},
                ]},
            }),
        )
        client = MimirClient(base_url=BASE)
        results = await client.instant_query("up")
        assert results[0].value is None
        await client.aclose()


async def test__instant_query__raises_on_error_status():
    async with respx.mock(base_url=BASE, assert_all_called=False) as router:
        router.get("/prometheus/api/v1/query").mock(
            return_value=httpx.Response(200, json={
                "status": "error",
                "error": "bad query",
            }),
        )
        client = MimirClient(base_url=BASE)
        with pytest.raises(MimirQueryError, match="bad query"):
            await client.instant_query("bad{")
        await client.aclose()


async def test__instant_query__raises_on_http_error():
    async with respx.mock(base_url=BASE, assert_all_called=False) as router:
        router.get("/prometheus/api/v1/query").mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )
        client = MimirClient(base_url=BASE)
        with pytest.raises(MimirQueryError, match="500"):
            await client.instant_query("up")
        await client.aclose()


async def test__instant_query__raises_on_timeout():
    async with respx.mock(base_url=BASE, assert_all_called=False) as router:
        router.get("/prometheus/api/v1/query").mock(side_effect=httpx.TimeoutException("timed out"))
        client = MimirClient(base_url=BASE)
        with pytest.raises(MimirUnavailableError):
            await client.instant_query("up")
        await client.aclose()


async def test__range_query__parses_matrix():
    async with respx.mock(base_url=BASE, assert_all_called=False) as router:
        router.get("/prometheus/api/v1/query_range").mock(
            return_value=httpx.Response(200, json={
                "status": "success",
                "data": {"resultType": "matrix", "result": [
                    {"metric": {"node": "n1"}, "values": [[100.0, "1.1"], [200.0, "2.2"]]},
                ]},
            }),
        )
        client = MimirClient(base_url=BASE)
        results = await client.range_query("up", start=100, end=200, step="60s")
        assert len(results) == 1
        assert len(results[0].values) == 2
        assert results[0].values[0] == (100.0, 1.1)
        await client.aclose()


async def test__instant_query__sends_org_id_header():
    async with respx.mock(base_url=BASE, assert_all_called=False) as router:
        route = router.get("/prometheus/api/v1/query").mock(
            return_value=httpx.Response(200, json={
                "status": "success",
                "data": {"resultType": "vector", "result": []},
            }),
        )
        client = MimirClient(base_url=BASE, tenant_id="my-tenant")
        await client.instant_query("up")
        assert route.calls[0].request.headers["X-Scope-OrgID"] == "my-tenant"
        await client.aclose()
