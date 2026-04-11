"""API routes for the Cluster Stats backend."""

from fastapi import APIRouter, Depends, Request

from cs_backend.schemas import HealthResponse
from cs_backend.settings import Settings

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
