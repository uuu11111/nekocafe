"""集中配置。

约定：所有可调项一律来自环境变量，代码里不出现任何密钥/连接串字面量。
本地默认值只保证「能跑起来」，真正的连接信息由 docker-compose / K8s ConfigMap / Secret 注入。
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("OTEL_SERVICE_NAME", "reservation")
    env: str = os.getenv("APP_ENV", "dev")
    version: str = os.getenv("APP_VERSION", "0.1.0")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8080"))

    # 会员服务地址，留空表示「不做跨服务校验」（本地起单服务或跑单测时用）
    member_base_url: str = os.getenv("MEMBER_SERVICE_URL", "")
    member_timeout_s: float = float(os.getenv("MEMBER_TIMEOUT_S", "1.5"))

    # 幂等存储，留空则退化为进程内字典
    redis_url: str = os.getenv("REDIS_URL", "")

    # OTLP collector 端点，留空则关闭链路追踪
    otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    trace_sample_ratio: float = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0"))

    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def member_check_enabled(self) -> bool:
        return bool(self.member_base_url)


settings = Settings()
