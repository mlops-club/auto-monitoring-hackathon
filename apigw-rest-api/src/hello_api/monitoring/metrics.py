"""OpenTelemetry metrics configuration with custom counters and histograms."""

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

_METRICS_CONFIGURED = False

_meter = metrics.get_meter("hello_api")

REQUEST_COUNTER = _meter.create_counter(
    name="hello_api.requests",
    description="Total number of requests handled by the Hello API",
    unit="1",
)

REQUEST_DURATION = _meter.create_histogram(
    name="hello_api.request.duration",
    description="Duration of HTTP request handling",
    unit="ms",
)


def configure_metrics(
    service_name: str,
    otlp_endpoint: str | None = None,
) -> None:
    global _METRICS_CONFIGURED  # noqa: PLW0603
    if _METRICS_CONFIGURED:
        return

    resource = Resource.create({"service.name": service_name})
    exporter = OTLPMetricExporter(
        endpoint=f"{otlp_endpoint}/v1/metrics" if otlp_endpoint else None,
    )
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5_000)
    provider = MeterProvider(resource=resource, metric_readers=[reader])

    metrics.set_meter_provider(provider)
    _METRICS_CONFIGURED = True
