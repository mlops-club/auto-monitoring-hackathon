"""Entrypoint for the Fleet Stats backend."""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from cs_backend.errors import handle_errors_globally
from cs_backend.mimir import MimirClient
from cs_backend.routes import ROUTER
from cs_backend.settings import Settings

LOGGER = structlog.get_logger(__name__)

RESERVED_PATH_PREFIXES = {
    "api",
    "docs",
    "openapi.json",
    "redoc",
}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    app.state.mimir_client = MimirClient(
        base_url=settings.mimir_base_url,
        tenant_id=settings.mimir_tenant_id,
        timeout=settings.mimir_timeout_seconds,
    )
    try:
        yield
    finally:
        await app.state.mimir_client.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    app = FastAPI(
        docs_url="/docs",
        title=settings.app_name,
        version="v1",
        summary="Backend API for the Fleet Stats monitoring UI.",
        lifespan=_lifespan,
    )

    app.state.settings = settings

    app.include_router(ROUTER)

    app.add_exception_handler(
        exc_class_or_status_code=Exception,
        handler=handle_errors_globally,
    )

    @app.get("/{requested_path:path}", include_in_schema=False)
    async def serve_frontend(requested_path: str) -> FileResponse:
        static_dir = Path(app.state.settings.static_dir)
        index_file = static_dir / "index.html"

        if requested_path and requested_path.split("/", 1)[0] in RESERVED_PATH_PREFIXES:
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = static_dir / requested_path if requested_path else index_file
        if candidate.is_file():
            return FileResponse(candidate)

        if index_file.is_file():
            return FileResponse(index_file)

        LOGGER.warning("static_asset_missing", requested_path=requested_path)
        raise HTTPException(
            status_code=503,
            detail="Frontend assets are not built yet. Run the frontend build before serving the bundled app.",
        )

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app=app, host="0.0.0.0", port=3000)
