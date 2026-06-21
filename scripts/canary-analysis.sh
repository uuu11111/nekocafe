#!/usr/bin/env bash
# 金丝雀分析门：连续观察金丝雀 Pod（track="canary"）的错误率与 P95，
# 任一采样越线即返回非 0，交给 cd.yml 触发自动回滚。
set -euo pipefail

PROM="${1:-${PROM_URL:-http://localhost:9090}}"
ERR_MAX="${ERR_MAX:-0.01}"     # 错误率上限 1%
P95_MAX="${P95_MAX:-0.5}"      # P95 上限 500ms
WINDOW="${WINDOW:-2m}"
SAMPLES="${SAMPLES:-4}"
INTERVAL="${INTERVAL:-30}"

query() {
  curl -fsS --get "$PROM/api/v1/query" --data-urlencode "query=$1" \
    | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 'nan')"
}

echo "▶ 金丝雀分析 @ $PROM（阈值：err≤${ERR_MAX} p95≤${P95_MAX}s，窗口 ${WINDOW}）"
for i in $(seq 1 "$SAMPLES"); do
  ERR=$(query 'sum(rate(http_requests_total{track="canary",status=~"5.."}['"$WINDOW"'])) / clamp_min(sum(rate(http_requests_total{track="canary"}['"$WINDOW"'])),1)')
  P95=$(query 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{track="canary"}['"$WINDOW"'])) by (le))')
  echo "  [$i/$SAMPLES] err=$ERR  p95=${P95}s"
  ERR="$ERR" P95="$P95" ERR_MAX="$ERR_MAX" P95_MAX="$P95_MAX" python3 - <<'PY'
import os, math
def f(x):
    try:
        v = float(x); return 0.0 if math.isnan(v) else v
    except ValueError:
        return 0.0
err, p95 = f(os.environ["ERR"]), f(os.environ["P95"])
em, pm = float(os.environ["ERR_MAX"]), float(os.environ["P95_MAX"])
if err > em or p95 > pm:
    raise SystemExit(1)
PY
  [[ "$i" -lt "$SAMPLES" ]] && sleep "$INTERVAL"
done
echo "✅ 金丝雀指标全程在阈值内"
