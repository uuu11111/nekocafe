"""NekoCafé 预约服务入口（FastAPI）。

对外暴露：
  GET  /healthz                 存活探针
  GET  /readyz                  就绪探针（含依赖自检）
  GET  /metrics                 Prometheus 指标
  POST /api/v1/reservations     创建预约（支持 Idempotency-Key 幂等）
  GET  /api/v1/reservations     列表
  GET  /api/v1/reservations/{id}单条
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from .config import settings
from .domain import IdempotencyGuard, Reservation, ReservationCreate, ReservationStore
from .logging_setup import configure_logging
from .member_client import MemberClient, MemberUnavailableError
from .metrics import MetricsMiddleware, metrics_response
from .telemetry import init_tracing

configure_logging()
log = logging.getLogger("reservation")

store = ReservationStore()
idempotency = IdempotencyGuard()


def get_member_client() -> MemberClient | None:
    """没配会员服务地址时返回 None，表示「跳过跨服务校验」。

    用 FastAPI 依赖而不是模块级单例，是为了单测里能 dependency_overrides 注入假对象。
    """
    if settings.member_check_enabled:
        return MemberClient(settings.member_base_url, settings.member_timeout_s)
    return None


app = FastAPI(title="NekoCafé 预约服务", version=settings.version)
app.add_middleware(MetricsMiddleware)
init_tracing(app)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.get("/readyz")
def readyz() -> dict:
    return {
        "status": "ready",
        "env": settings.env,
        "version": settings.version,
        "deps": {
            "member_check": settings.member_check_enabled,
            "redis": bool(settings.redis_url),
        },
    }


@app.get("/metrics")
def metrics():
    return metrics_response()


@app.post("/api/v1/reservations", response_model=Reservation, status_code=201)
async def create_reservation(
    payload: ReservationCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    member_client: Annotated[MemberClient | None, Depends(get_member_client)] = None,
) -> Reservation:
    # 1) 幂等：同一个 key 命中，直接回放上次结果，绝不重复下单
    if idempotency_key:
        existing_id = idempotency.lookup(idempotency_key)
        if existing_id and (existing := store.get(existing_id)):
            log.info(
                "幂等命中，回放已有预约",
                extra={"reservation_id": existing.id, "idempotency_key": idempotency_key},
            )
            return existing

    # 2) 跨服务校验会员有效性（这一跳会被串进同一条 trace）
    if member_client is not None:
        try:
            active = await member_client.is_active(payload.member_id)
        except MemberUnavailableError as exc:
            # 会员服务挂了，宁可拒绝也不放进脏数据，返回 503 让客户端重试
            raise HTTPException(status_code=503, detail="会员服务暂时不可用，请稍后重试") from exc
        if not active:
            raise HTTPException(status_code=422, detail="会员不存在或已停用")

    reservation = store.create(payload)
    if idempotency_key:
        idempotency.remember(idempotency_key, reservation.id)
    log.info(
        "预约创建成功",
        extra={
            "reservation_id": reservation.id,
            "member_id": reservation.member_id,
            "store_id": reservation.store_id,
            "party_size": reservation.party_size,
        },
    )
    return reservation


@app.get("/api/v1/reservations", response_model=list[Reservation])
def list_reservations() -> list[Reservation]:
    return store.list()


@app.get("/api/v1/reservations/{reservation_id}", response_model=Reservation)
def get_reservation(reservation_id: str) -> Reservation:
    reservation = store.get(reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="预约不存在")
    return reservation


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # noqa: ANN001
    # 兜底：任何未捕获异常都记成结构化日志，返回统一错误体（同时被计入 5xx 指标）
    log.exception("未处理异常 path=%s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "内部错误"})


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)
