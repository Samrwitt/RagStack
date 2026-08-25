"""HTTP middleware for request correlation."""

import uuid
from collections.abc import Awaitable, Callable

from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.rate_limit import FixedWindowRateLimiter
from app.observability.metrics import RATE_LIMIT_REJECTIONS, increment

try:
    import structlog
except ModuleNotFoundError:  # pragma: no cover - minimal unit-test environments
    structlog = None  # type: ignore[assignment]
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
_rate_limiter: FixedWindowRateLimiter | None = None


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a request_id to every request and bind it to structured logs."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming.strip() if incoming else str(uuid.uuid4())
        request.state.request_id = request_id
        if structlog is not None:
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window API rate limiter for local and single-process deployments."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)
        global _rate_limiter
        if _rate_limiter is None:
            _rate_limiter = FixedWindowRateLimiter(
                limit=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window_seconds,
            )
        client_host = request.client.host if request.client else "unknown"
        key = request.headers.get("Authorization") or client_host
        allowed, remaining = _rate_limiter.allow(str(key))
        if not allowed:
            increment(RATE_LIMIT_REJECTIONS, labels={"path": request.url.path})
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={"X-RateLimit-Remaining": "0"},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
