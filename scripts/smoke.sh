#!/usr/bin/env bash
# 冒烟 + 跨服务集成检查。
#   无参数  -> 打本地 compose（reservation:8081 / member:8082）
#   带 BASE -> 打 Ingress（约定 /reservation 与 /member 两个路径前缀）
set -euo pipefail

BASE="${1:-}"
if [[ -n "$BASE" ]]; then
  RES="${BASE%/}/reservation"
  MEM="${BASE%/}/member"
else
  RES="http://localhost:8081"
  MEM="http://localhost:8082"
fi

echo "▶ reservation=$RES  member=$MEM"

wait_ready() {
  local name="$1" url="$2"
  for i in $(seq 1 30); do
    if curl -fsS "$url/healthz" >/dev/null 2>&1; then
      echo "  ✓ $name 就绪"; return 0
    fi
    sleep 2
  done
  echo "  ✗ $name 在 60s 内未就绪"; return 1
}

wait_ready reservation "$RES"
wait_ready member "$MEM"

echo "▶ 探针与指标"
curl -fsS "$RES/readyz" >/dev/null && echo "  ✓ reservation /readyz"
curl -fsS "$MEM/readyz" >/dev/null && echo "  ✓ member /readyz"
curl -fsS "$RES/metrics" | grep -q http_requests_total && echo "  ✓ reservation /metrics"
curl -fsS "$MEM/metrics" | grep -q http_requests_total && echo "  ✓ member /metrics"

echo "▶ 建一个会员（会员服务）"
MEMBER_ID=$(curl -fsS -X POST "$MEM/api/v1/members" \
  -H 'content-type: application/json' \
  -d '{"name":"冒烟猫","tier":"GOLD","phone":"13800000009"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "  ✓ member_id=$MEMBER_ID"

echo "▶ 用该会员下一笔预约（预约服务会回调会员服务做校验 → 跨服务链路）"
KEY="smoke-$(date +%s)"
RID=$(curl -fsS -X POST "$RES/api/v1/reservations" \
  -H 'content-type: application/json' -H "Idempotency-Key: $KEY" \
  -d "{\"member_id\":\"$MEMBER_ID\",\"store_id\":\"bjfu-01\",\"seat_type\":\"cat-room\",\"party_size\":2,\"reserved_at\":\"2026-06-20T18:30:00Z\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "  ✓ reservation_id=$RID"

echo "▶ 幂等校验：同 key 重放应返回同一条"
RID2=$(curl -fsS -X POST "$RES/api/v1/reservations" \
  -H 'content-type: application/json' -H "Idempotency-Key: $KEY" \
  -d "{\"member_id\":\"$MEMBER_ID\",\"store_id\":\"bjfu-01\",\"seat_type\":\"cat-room\",\"party_size\":2,\"reserved_at\":\"2026-06-20T18:30:00Z\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
[[ "$RID" == "$RID2" ]] && echo "  ✓ 幂等生效（$RID）" || { echo "  ✗ 幂等失效：$RID != $RID2"; exit 1; }

echo "▶ 回读预约"
curl -fsS "$RES/api/v1/reservations/$RID" >/dev/null && echo "  ✓ 可回读"

echo "✅ 冒烟与跨服务集成全部通过"
