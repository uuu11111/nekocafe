#!/usr/bin/env bash
# 一键回滚。用法：
#   scripts/rollback.sh [service] [namespace] [revision]
#   service   默认 reservation
#   namespace 默认 nekocafe-prod
#   revision  默认 0（= 回到上一个稳定 revision）
set -euo pipefail

SVC="${1:-reservation}"
NS="${2:-nekocafe-prod}"
REV="${3:-0}"

echo "▶ $SVC @ $NS 最近发布历史："
helm history "$SVC" -n "$NS" --max 5 || true

echo "▶ 执行回滚……"
if [[ "$REV" == "0" ]]; then
  helm rollback "$SVC" -n "$NS"          # 不带 revision = 回上一个
else
  helm rollback "$SVC" "$REV" -n "$NS"
fi

kubectl -n "$NS" rollout status "deploy/$SVC" --timeout=120s
echo "✅ $SVC 已回滚并恢复就绪（$NS）"
