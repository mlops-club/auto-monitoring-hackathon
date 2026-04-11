"""AWS Lambda handler using Mangum as an ASGI adapter for the FastAPI application."""

from mangum import Mangum
from opentelemetry import metrics, trace

from hello_api.main import create_app

APP = create_app()

_mangum = Mangum(APP)


def handler(event, context):
    response = _mangum(event, context)

    # Force-flush telemetry before Lambda freezes the execution environment.
    tp = trace.get_tracer_provider()
    if hasattr(tp, "force_flush"):
        tp.force_flush(timeout_millis=5_000)

    mp = metrics.get_meter_provider()
    if hasattr(mp, "force_flush"):
        mp.force_flush(timeout_millis=5_000)

    return response
