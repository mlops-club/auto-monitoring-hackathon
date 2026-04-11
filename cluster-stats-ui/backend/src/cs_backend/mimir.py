"""Async client for querying Mimir's Prometheus-compatible API."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import structlog

LOGGER = structlog.get_logger(__name__)


class MimirQueryError(Exception):
    """Mimir returned an error response."""


class MimirUnavailableError(Exception):
    """Mimir is unreachable or timed out."""


@dataclass
class PrometheusResult:
    metric: dict[str, str]
    value: float | None


@dataclass
class PrometheusRangeResult:
    metric: dict[str, str]
    values: list[tuple[float, float]] = field(default_factory=list)


def _parse_float(s: str) -> float | None:
    if s == "NaN" or s == "+Inf" or s == "-Inf":
        return None
    return float(s)


class MimirClient:
    def __init__(
        self,
        base_url: str,
        tenant_id: str = "anonymous",
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Scope-OrgID": tenant_id},
            timeout=timeout,
        )

    async def instant_query(self, query: str) -> list[PrometheusResult]:
        data = await self._request("/prometheus/api/v1/query", {"query": query})
        return [
            PrometheusResult(
                metric=item["metric"],
                value=_parse_float(item["value"][1]),
            )
            for item in data.get("result", [])
        ]

    async def range_query(
        self, query: str, start: float, end: float, step: str = "60s"
    ) -> list[PrometheusRangeResult]:
        data = await self._request(
            "/prometheus/api/v1/query_range",
            {"query": query, "start": start, "end": end, "step": step},
        )
        results = []
        for item in data.get("result", []):
            vals = [(_parse_float(str(ts)), _parse_float(v)) for ts, v in item.get("values", [])]
            results.append(
                PrometheusRangeResult(
                    metric=item["metric"],
                    values=[(ts, v) for ts, v in vals if ts is not None and v is not None],
                )
            )
        return results

    async def _request(self, path: str, params: dict) -> dict:
        try:
            resp = await self._client.get(path, params=params)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise MimirUnavailableError(str(exc)) from exc

        if resp.status_code != 200:
            raise MimirQueryError(f"Mimir returned {resp.status_code}: {resp.text[:200]}")

        body = resp.json()
        if body.get("status") != "success":
            raise MimirQueryError(body.get("error", "unknown error"))

        return body.get("data", {})

    async def aclose(self) -> None:
        await self._client.aclose()
