"""Custom exception handlers for the FastAPI app."""

from fastapi import Request, status
from fastapi.responses import JSONResponse


async def handle_errors_globally(request: Request, exc: Exception) -> JSONResponse:
    """Handle any raised exceptions not handled by a more specific handler."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": "error",
            "error_type": "500 Internal Server Error",
            "errors": str(exc),
        },
    )
