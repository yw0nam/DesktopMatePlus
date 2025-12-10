"""FastAPI middleware for Request ID tracking."""

import uuid
from contextvars import ContextVar

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable to store request ID across async calls
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and inject Request IDs for HTTP requests.

    Automatically generates a unique Request ID for each incoming HTTP request
    and binds it to the logger context for tracing throughout the request lifecycle.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with Request ID tracking.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response with Request ID tracking
        """
        # Generate unique request ID
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        request_id_var.set(request_id)

        # Bind request ID to logger context for this request
        with logger.contextualize(request_id=request_id):
            # Log incoming request
            logger.info(f"➡️ {request.method} {request.url.path}")

            # Process request
            response = await call_next(request)

            # Log outgoing response
            logger.info(
                f"⬅️ {request.method} {request.url.path} ({response.status_code})"
            )

        return response


def get_request_id() -> str:
    """Get current request ID from context.

    Returns:
        Current request ID or "-" if not in request context
    """
    return request_id_var.get()
