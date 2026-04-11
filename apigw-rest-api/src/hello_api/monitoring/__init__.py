"""OpenTelemetry instrumentation for the Hello API."""

from hello_api.monitoring.logging import configure_structlog
from hello_api.monitoring.metrics import configure_metrics, REQUEST_COUNTER, REQUEST_DURATION
from hello_api.monitoring.tracing import configure_tracing

__all__ = [
    "configure_structlog",
    "configure_metrics",
    "configure_tracing",
    "setup_telemetry",
    "REQUEST_COUNTER",
    "REQUEST_DURATION",
]


def setup_telemetry(
    service_name: str,
    otlp_endpoint: str | None = None,
    enabled: bool = True,
) -> None:
    """Initialize all OTel telemetry: traces, metrics, and structured logging."""
    if not enabled:
        configure_structlog()
        return

    configure_tracing(service_name=service_name, otlp_endpoint=otlp_endpoint)
    configure_metrics(service_name=service_name, otlp_endpoint=otlp_endpoint)
    configure_structlog()
