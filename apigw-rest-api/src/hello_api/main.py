"""Entrypoint for the Hello API."""

from fastapi import FastAPI

from hello_api.errors import handle_errors_globally
from hello_api.routes import ROUTER
from hello_api.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    app = FastAPI(
        docs_url="/",
        title=settings.app_name,
        version="v1",
        summary="A Hello World API with OpenTelemetry instrumentation.",
    )

    app.state.settings = settings

    app.include_router(ROUTER)

    app.add_exception_handler(
        exc_class_or_status_code=Exception,
        handler=handle_errors_globally,
    )

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=3000)
