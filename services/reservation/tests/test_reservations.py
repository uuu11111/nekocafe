"""预约接口的核心行为测试：创建 / 查询 / 列表 / 幂等 / 校验失败。"""
from __future__ import annotations


def test_create_and_get(client, sample_payload):
    created = client.post("/api/v1/reservations", json=sample_payload)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "CONFIRMED"
    assert body["member_id"] == "m-1001"

    fetched = client.get(f"/api/v1/reservations/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_list_returns_created(client, sample_payload):
    client.post("/api/v1/reservations", json=sample_payload)
    resp = client.get("/api/v1/reservations")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_missing_returns_404(client):
    assert client.get("/api/v1/reservations/does-not-exist").status_code == 404


def test_idempotency_replays_same_reservation(client, sample_payload):
    headers = {"Idempotency-Key": "order-abc-123"}
    first = client.post("/api/v1/reservations", json=sample_payload, headers=headers)
    second = client.post("/api/v1/reservations", json=sample_payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    # 只应落一条，幂等键挡住了重复下单
    assert len(client.get("/api/v1/reservations").json()) == 1


def test_invalid_seat_type_rejected(client, sample_payload):
    sample_payload["seat_type"] = "rooftop"
    assert client.post("/api/v1/reservations", json=sample_payload).status_code == 422


def test_invalid_party_size_rejected(client, sample_payload):
    sample_payload["party_size"] = 99
    assert client.post("/api/v1/reservations", json=sample_payload).status_code == 422


def test_inactive_member_rejected(client, sample_payload):
    sample_payload["member_id"] = "ghost-9"
    resp = client.post("/api/v1/reservations", json=sample_payload)
    assert resp.status_code == 422
    assert "会员" in resp.json()["detail"]


def test_member_service_down_returns_503(client, sample_payload):
    sample_payload["member_id"] = "down-7"
    assert client.post("/api/v1/reservations", json=sample_payload).status_code == 503
