from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ddm_engine.observability.context import (
    reset_observability_context,
    set_observability_context,
)
from ddm_engine.observability.metrics import (
    API_REQUEST_DURATION_SECONDS,
    API_REQUESTS_IN_PROGRESS,
    API_REQUESTS_TOTAL,
)

logger = logging.getLogger(__name__)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid4().hex
        correlation_id = request.headers.get("x-correlation-id") or request_id
        route = _route_label(request)
        method = request.method
        started_at = time.perf_counter()
        tokens = set_observability_context(request_id, correlation_id)
        API_REQUESTS_IN_PROGRESS.labels(method=method).inc()

        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - started_at
            API_REQUEST_DURATION_SECONDS.labels(method=method, route=route).observe(duration)
            API_REQUESTS_TOTAL.labels(method=method, route=route, status_code="500").inc()
            logger.exception(
                "API request failed",
                extra={"method": method, "route": route, "duration_seconds": duration},
            )
            API_REQUESTS_IN_PROGRESS.labels(method=method).dec()
            reset_observability_context(tokens)
            raise

        duration = time.perf_counter() - started_at
        route = _route_label(request)
        API_REQUEST_DURATION_SECONDS.labels(method=method, route=route).observe(duration)
        API_REQUESTS_TOTAL.labels(
            method=method,
            route=route,
            status_code=str(response.status_code),
        ).inc()
        response.headers["x-request-id"] = request_id
        response.headers["x-correlation-id"] = correlation_id
        logger.info(
            "API request completed",
            extra={
                "method": method,
                "route": route,
                "status_code": response.status_code,
                "duration_seconds": duration,
            },
        )
        API_REQUESTS_IN_PROGRESS.labels(method=method).dec()
        reset_observability_context(tokens)
        return response


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return route.path
    return request.url.path
