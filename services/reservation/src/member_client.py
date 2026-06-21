"""会员服务客户端。

预约落库前先问一句会员服务「这个会员还有效吗」。这一次出站 httpx 调用会被
HTTPXClientInstrumentor 自动注入 traceparent，从而把「预约」和「会员」两个 span 串到
同一条 trace 上——这正是答辩里演示「3 分钟定位到具体服务/接口」的关键链路。
"""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


class MemberUnavailableError(RuntimeError):
    """会员服务暂时不可达（超时 / 5xx），交给上层决定是放行还是拒绝。"""


class MemberClient:
    def __init__(self, base_url: str, timeout_s: float) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    async def is_active(self, member_id: str) -> bool:
        url = f"{self._base}/api/v1/members/{member_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
        except httpx.HTTPError as exc:
            log.warning("调用会员服务失败 member_id=%s err=%s", member_id, exc)
            raise MemberUnavailableError(str(exc)) from exc

        if resp.status_code == 404:
            return False
        if resp.status_code >= 500:
            raise MemberUnavailableError(f"member service {resp.status_code}")
        resp.raise_for_status()
        return bool(resp.json().get("active", True))
