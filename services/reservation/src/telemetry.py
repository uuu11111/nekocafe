"""OpenTelemetry 初始化。

设计取舍：otel 全套 SDK 是「可选依赖」。只有当 OTEL_EXPORTER_OTLP_ENDPOINT 配置了
（即真的有 collector 在收数据）才初始化；否则安全降级成 no-op。这样：
  - 本地 `docker compose up`（不带 observability profile）也能跑，不报错；
  - 单元测试不需要拉起一整套可观测性后端。
采样策略用 ParentBased(TraceIdRatio)：尊重上游传下来的采样决定，根 span 才按比例采。
"""
from __future__ import annotations

import logging

from .config import settings

log = logging.getLogger(__name__)


def init_tracing(app=None) -> bool:
    if not settings.otlp_endpoint:
        log.info("未配置 OTLP 端点，跳过链路追踪初始化（本地/测试模式）")
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

        resource = Resource.create(
            {
                "service.name": settings.service_name,
                "service.version": settings.version,
                "deployment.environment": settings.env,
            }
        )
        provider = TracerProvider(
            resource=resource,
            sampler=ParentBased(root=TraceIdRatioBased(settings.trace_sample_ratio)),
        )
        # OTLP/HTTP 导出器要的是完整 traces 路径；只给了 base 时补上 /v1/traces
        endpoint = settings.otlp_endpoint.rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        trace.set_tracer_provider(provider)

        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
        # 让出站的 httpx 调用自动注入 W3C traceparent，实现跨服务串联
        HTTPXClientInstrumentor().instrument()

        log.info(
            "链路追踪已启用 endpoint=%s 采样率=%s",
            settings.otlp_endpoint,
            settings.trace_sample_ratio,
        )
        return True
    except Exception:  # noqa: BLE001
        log.exception("链路追踪初始化失败，降级为无追踪模式（不影响业务）")
        return False
