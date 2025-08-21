import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.lib.logger import configure_logger

logger = configure_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses in structured JSON format."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Get request information
        request_info = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client": request.client.host if request.client else None,
        }

        # Process the request
        response: Response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Get response information
        response_info = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "process_time_ms": round(process_time * 1000, 2),
        }

        # Log the request/response
        logger.info(
            "HTTP Request",
            extra={
                "req": request_info,
                "res": response_info,
            },
        )

        return response
