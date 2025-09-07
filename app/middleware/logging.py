import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.lib.logger import configure_logger

logger = configure_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses in a clean, readable format."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Process the request
        response: Response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Create clean request info (only essential data)
        request_info = {
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown",
        }

        # Add query params if they exist
        if request.query_params:
            request_info["query_params"] = dict(request.query_params)

        # Create clean response info
        response_info = {
            "status_code": response.status_code,
            "process_time_ms": round(process_time * 1000, 2),
        }

        # Log with a clean message format
        status_emoji = "✓" if response.status_code < 400 else "✗"
        logger.info(
            f"{status_emoji} {request.method} {request.url.path}",
            extra={
                "request": request_info,
                "response": response_info,
                "event_type": "http_request",
            },
        )

        return response
