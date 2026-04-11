"""API routes for the Cluster Stats backend."""

import structlog
from fastapi import APIRouter, Depends, Request

from cs_backend.k8s import get_node_labels
from cs_backend.schemas import HealthResponse, NodeLabelsResponse, UiProbeResponse
from cs_backend.settings import Settings

LOGGER = structlog.get_logger(__name__)
ROUTER = APIRouter()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


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
