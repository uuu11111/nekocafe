"""预约领域：模型、内存存储、幂等守卫。

PoC 范围内预约数据放进程内存里就够了（重启即清空，文档里说清楚）。要落库时只需把
ReservationStore 换成 Postgres 实现，接口不变。幂等键则优先用 Redis（多副本共享），
Redis 不可用时自动退化到进程内字典——保证「没装 Redis 也能跑」。
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

from .config import settings

log = logging.getLogger(__name__)

VALID_SEATS = {"window", "sofa", "cat-room", "bar"}


class ReservationCreate(BaseModel):
    member_id: str = Field(min_length=1, max_length=64)
    store_id: str = Field(min_length=1, max_length=32)
    seat_type: str = Field(default="window")
    party_size: int = Field(ge=1, le=12)
    reserved_at: datetime

    @field_validator("seat_type")
    @classmethod
    def _check_seat(cls, value: str) -> str:
        if value not in VALID_SEATS:
            raise ValueError(f"seat_type 必须是 {sorted(VALID_SEATS)} 之一")
        return value


class Reservation(ReservationCreate):
    id: str
    status: str = "CONFIRMED"
    created_at: datetime


class ReservationStore:
    def __init__(self) -> None:
        self._data: dict[str, Reservation] = {}
        self._lock = threading.Lock()

    def create(self, payload: ReservationCreate) -> Reservation:
        now = datetime.now(UTC)
        reservation = Reservation(
            id=uuid.uuid4().hex,
            created_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._data[reservation.id] = reservation
        return reservation

    def get(self, reservation_id: str) -> Reservation | None:
        return self._data.get(reservation_id)

    def list(self) -> list[Reservation]:
        with self._lock:
            return sorted(self._data.values(), key=lambda r: r.created_at, reverse=True)


class IdempotencyGuard:
    """记住 Idempotency-Key -> reservation_id 的映射，让重复提交不会建出两条预约。"""

    _TTL_SECONDS = 24 * 3600

    def __init__(self) -> None:
        self._mem: dict[str, str] = {}
        self._lock = threading.Lock()
        self._redis = self._connect_redis()

    def _connect_redis(self):
        if not settings.redis_url:
            return None
        try:
            import redis

            client = redis.Redis.from_url(
                settings.redis_url, socket_timeout=0.5, decode_responses=True
            )
            client.ping()
            log.info("幂等存储使用 Redis")
            return client
        except Exception:  # noqa: BLE001
            log.warning("Redis 不可用，幂等键退化为进程内存储", exc_info=False)
            return None

    def lookup(self, key: str) -> str | None:
        if self._redis is not None:
            try:
                return self._redis.get(f"idem:{key}")
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            return self._mem.get(key)

    def remember(self, key: str, reservation_id: str) -> None:
        if self._redis is not None:
            try:
                self._redis.set(f"idem:{key}", reservation_id, ex=self._TTL_SECONDS)
                return
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            self._mem[key] = reservation_id
