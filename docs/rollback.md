# Rollback · 回滚手册

NekoCafé 的回滚有两条线：**自动**（金丝雀阶段越线）与**手动**（一键脚本）。

## 1. 自动回滚（首选，无需人介入）

CD 流水线在 prod 金丝雀放量（5%→25%→50%→100%）的每一档之间，都会运行
`scripts/canary-analysis.sh` 观察金丝雀 Pod 2 分钟：

- 错误率 > **1%**，或
- P95 延迟 > **500ms**

任一越线，流水线立即把 `canary.enabled` 置回 `false`（流量 100% 收回稳定版），
并以非 0 退出，本次发布判定失败。整个过程通常在 **1–2 分钟** 内完成。

## 2. 手动一键回滚

```bash
# 回滚预约服务到上一个稳定版本（默认 namespace: nekocafe-prod）
make rollback SVC=reservation
# 等价于：
bash scripts/rollback.sh reservation nekocafe-prod
# 回滚到指定 revision（先看历史）：
helm history reservation -n nekocafe-prod
bash scripts/rollback.sh reservation nekocafe-prod 7
```

脚本做三件事：打印最近 5 次发布历史 → `helm rollback` → `kubectl rollout status` 确认就绪。

## 3. 本地（docker compose）回滚

```bash
# 改回上一个镜像 tag 重新拉起即可
APP_VERSION=0.0.9 docker compose up -d
```

## 4. 回滚后必做
1. 确认 Grafana 上错误率/延迟回落；
2. 在 PR/issue 记录失败原因（写进 DORA 报告的「变更失败」与 MTTR）；
3. 修复后重新走 CI/CD，不要直接热修生产。
