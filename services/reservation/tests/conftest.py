"""单测公共装置。

用 dependency_overrides 把「会员服务客户端」换成假对象，这样单测既不依赖网络，
也能精确制造「会员有效 / 会员停用 / 会员服务挂了」三种分支。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app, get_member_client, idempotency, store
from src.member_client import MemberUnavailableError


class FakeMemberClient:
    """member_id 以 'ghost' 开头 -> 不存在；以 'down' 开头 -> 模拟服务不可用；其余有效。"""

    async def is_active(self, member_id: str) -> bool:
        if member_id.startswith("ghost"):
            return False
        if member_id.startswith("down"):
            raise MemberUnavailableError("simulated outage")
        return True


@pytest.fixture
def client():
    app.dependency_overrides[get_member_client] = lambda: FakeMemberClient()
    # 每个用例前清空内存状态，保证用例之间互不污染
    store._data.clear()
    idempotency._mem.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_payload() -> dict:
    return {
        "member_id": "m-1001",
        "store_id": "bjfu-01",
        "seat_type": "cat-room",
        "party_size": 2,
        "reserved_at": "2026-06-20T18:30:00Z",
    }
