"""Entrypoint for the Hello API."""

import time

import structlog
from fastapi import FastAPI, Request, Response
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from hello_api.errors import handle_errors_globally
from hello_api.monitoring import REQUEST_COUNTER, REQUEST_DURATION, setup_telemetry
from hello_api.routes import ROUTER
from hello_api.settings import Settings

logger = structlog.get_logger()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    setup_telemetry(
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
        enabled=settings.otel_enabled,
    )

    app = FastAPI(
        docs_url="/",
        title=settings.app_name,
        version="v1",
        summary="A Hello World API with OpenTelemetry instrumentation.",
        root_path="/prod",
    )

    app.state.settings = settings

    app.include_router(ROUTER)

    app.add_exception_handler(
        exc_class_or_status_code=Exception,
        handler=handle_errors_globally,
    )

    @app.middleware("http")
    async def telemetry_middleware(request: Request, call_next) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        attrs = {
            "http.method": request.method,
            "http.route": request.url.path,
            "http.status_code": response.status_code,
        }
        REQUEST_COUNTER.add(1, attrs)
        REQUEST_DURATION.record(duration_ms, attrs)

        logger.info(
            "request_handled",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=3000)
