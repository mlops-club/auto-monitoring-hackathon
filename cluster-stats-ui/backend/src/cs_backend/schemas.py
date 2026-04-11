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


class UiProbeResponse(BaseModel):
    message: str = Field(..., description="Confirmation that the UI reached the backend")
    request_path: str = Field(..., description="Path received by the backend")


class NodeLabelsResponse(BaseModel):
    nodes: dict[str, dict[str, str]] = Field(
        ...,
        description="Mapping of node name to its K8s labels",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nodes": {
                        "ip-10-0-1-45.us-west-2.compute.internal": {
                            "kubernetes.io/os": "linux",
                            "node.kubernetes.io/instance-type": "m5.xlarge",
                            "topology.kubernetes.io/zone": "us-west-2a",
                        }
                    }
                }
            ]
        },
    )
