"""API routes for the Hello API."""

import structlog
from fastapi import APIRouter, Depends, Request

from hello_api.schemas import HealthResponse, HelloResponse
from hello_api.settings import Settings

ROUTER = APIRouter()
logger = structlog.get_logger()


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
    logger.info("health_check", app_name=settings.app_name)
    return HealthResponse(status="healthy", app_name=settings.app_name)


@ROUTER.get(
    "/greetings",
    tags=["Greetings"],
    summary="Get a greeting",
)
async def get_greeting() -> HelloResponse:
    """Return a hello world greeting."""
    logger.info("greeting_requested", personalized=False)
    return HelloResponse(message="Hello, World!")


@ROUTER.get(
    "/greetings/{name}",
    tags=["Greetings"],
    summary="Get a personalized greeting",
)
async def get_personalized_greeting(name: str) -> HelloResponse:
    """Return a personalized greeting for the given name."""
    logger.info("greeting_requested", personalized=True, name=name)
    return HelloResponse(message=f"Hello, {name}!")
