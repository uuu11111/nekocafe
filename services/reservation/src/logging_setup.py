"""结构化日志：一行一条 JSON，自动带上 traceId / spanId，并对 PII 脱敏。

之所以自己写 Formatter 而不是直接上 structlog，是因为 PoC 只需要「JSON + trace 关联 +
脱敏」三件事，自带 logging 足够，少一个依赖也少一份镜像体积和扫描面。
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime

from .config import settings

# 链路追踪是可选依赖；没装 opentelemetry 时日志照常工作，只是不带 traceId
try:  # pragma: no cover - 取决于运行环境是否安装 otel
    from opentelemetry import trace as _otel_trace
except Exception:  # noqa: BLE001
    _otel_trace = None

# 待脱敏的三类敏感信息：手机号、邮箱、身份证
_PHONE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
_EMAIL = re.compile(r"([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
_IDCARD = re.compile(r"(?<!\d)(\d{4})\d{10}(\d{3}[\dXx])(?!\d)")


def mask_pii(text: str) -> str:
    """把日志正文里的手机号 / 邮箱 / 身份证替换成掩码，避免明文落盘。"""
    text = _PHONE.sub(r"\g<1>****\g<2>", text)
    text = _EMAIL.sub(r"\g<1>***\g<2>", text)
    text = _IDCARD.sub(r"\g<1>**********\g<2>", text)
    return text


# 标准 LogRecord 自带字段，不当作业务 extra 输出
_RESERVED = set(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"asctime", "message", "taskName", "otelTraceID", "otelSpanID",
     "otelServiceName", "otelTraceSampled"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC)
        payload: dict[str, object] = {
            "time": ts.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "service": settings.service_name,
            "env": settings.env,
            "logger": record.name,
            "msg": mask_pii(record.getMessage()),
        }
        # 优先从当前 span 取 trace 上下文，这样即便没启用 logging instrumentation 也能关联
        if _otel_trace is not None:
            ctx = _otel_trace.get_current_span().get_span_context()
            if getattr(ctx, "is_valid", False) and ctx.is_valid:
                payload["traceId"] = format(ctx.trace_id, "032x")
                payload["spanId"] = format(ctx.span_id, "016x")
        # 业务侧通过 logger.info(..., extra={...}) 传入的字段
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = mask_pii(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level.upper())
    # 访问日志统一由 MetricsMiddleware 产出，关掉 uvicorn 自带的免得重复刷屏
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).handlers[:] = []
        logging.getLogger(noisy).propagate = False
