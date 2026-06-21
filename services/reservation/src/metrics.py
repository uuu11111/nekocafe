"""Prometheus 指标与请求级中间件。

埋点遵循 RED 方法：
  Rate     -> http_requests_total（按 method/route/status 计数）
  Errors   -> 上面这个 metric 里 status=~"5.." 的部分
  Duration -> http_request_duration_seconds（直方图，便于算 P95/P99）
route 标签取「路由模板」而非真实 URL，避免 /reservations/{id} 把基数打爆。
"""
from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUESTS = Counter(
    "http_requests_total",
    "HTTP 请求总数",
    ("method", "route", "status"),
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求耗时（秒）",
    ("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
INPROGRESS = Gauge(
    "http_requests_in_progress",
    "正在处理的 HTTP 请求数",
)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        INPROGRESS.inc()
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            route = _route_template(request)
            REQUESTS.labels(request.method, route, str(status)).inc()
            LATENCY.labels(request.method, route).observe(elapsed)
            INPROGRESS.dec()


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
