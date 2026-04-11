"""OpenTelemetry tracing configuration."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

_TRACER_CONFIGURED = False


def configure_tracing(
    service_name: str,
    otlp_endpoint: str | None = None,
) -> None:
    global _TRACER_CONFIGURED  # noqa: PLW0603
    if _TRACER_CONFIGURED:
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=f"{otlp_endpoint}/v1/traces" if otlp_endpoint else None,
    )
    # SimpleSpanProcessor in Lambda to flush before the function freezes;
    # BatchSpanProcessor is fine when running behind the ADOT collector extension.
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _TRACER_CONFIGURED = True
