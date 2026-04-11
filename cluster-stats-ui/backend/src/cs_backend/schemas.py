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
                    "app_name": "Cluster Stats API",
                }
            ]
        },
    )


class ErrorResponse(BaseModel):
    message: str = Field(..., description="Human-readable error summary")
    error_type: str = Field(..., description="Error classification")
    errors: str = Field(..., description="Detailed error information")

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
