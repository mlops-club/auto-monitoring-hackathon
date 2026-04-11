"""Pydantic models for request/response schemas and OpenAPI documentation."""

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status of the API")
    app_name: str = Field(..., description="Name of the application")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "healthy",
                    "app_name": "Hello API",
                }
            ]
        },
    )


class HelloResponse(BaseModel):
    message: str = Field(..., description="Greeting message")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "Hello, World!",
                }
            ]
        },
    )


class ErrorResponse(BaseModel):
    message: str
    error_type: str
    errors: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "error",
                    "error_type": "500 Internal Server Error",
                    "errors": "Something went wrong",
                }
            ]
        },
    )
