"""冒烟测试：探针与指标端点必须随时可用。"""
from __future__ import annotations


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz(client):
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_metrics_exposes_prometheus_format(client):
    # 先打一次业务请求，确保计数器里有数据
    client.get("/api/v1/reservations")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
    assert "http_request_duration_seconds" in resp.text
