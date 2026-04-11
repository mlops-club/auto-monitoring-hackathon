"""AWS Lambda handler using Mangum as an ASGI adapter for the FastAPI application."""

from mangum import Mangum

from hello_api.main import create_app

APP = create_app()

_mangum = Mangum(APP)


def handler(event, context):
    return _mangum(event, context)
