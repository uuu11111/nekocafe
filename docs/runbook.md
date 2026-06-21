# Runbook · 值班手册

> 目标：任何一个收到告警的人，照着这份手册都能在 **3 分钟内定位到「具体服务 / 具体节点 / 具体接口」**。

## 0. 入口与约定

| 系统 | 地址（本地 compose） | 用途 |
|---|---|---|
| Grafana | http://localhost:3000 | Dashboard、告警 |
| Prometheus | http://localhost:9090 | 指标查询、告警规则 |
| Tempo | 经 Grafana Explore | 链路追踪 |
| Loki | 经 Grafana Explore | 结构化日志 |

所有日志都是 JSON，且带 `traceId`/`spanId`；所有指标都带 `service` 标签。

## 1. 收到告警后的标准动作（黄金 3 步）

### 第 1 步：定位「哪个服务」（约 30s）
打开 Grafana → **NekoCafé · RED 概览**：
- 看 **错误率** 面板哪个 `service` 飘红 → 锁定服务；
- 看 **P99/P95 延迟** 面板确认是延迟问题还是错误问题。

### 第 2 步：定位「哪个接口 / 哪个节点」（约 60s）
- 在 Prometheus 执行：
  `topk(5, sum(rate(http_requests_total{service="reservation",status=~"5.."}[5m])) by (route))`
  → 找出出错最多的 `route`（精确到接口）。
- `kube_pod_info` / `up` 看是哪个 Pod（节点）异常。

### 第 3 步：定位「根因」（约 90s）
- Grafana Explore → Loki：
  `{service="reservation"} | json | level="ERROR"` → 取一条出错日志里的 `traceId`；
- 点日志行里的 **「查看链路」** 直接跳到 Tempo，看这条 trace 卡在哪个 span（是 DB？是调用会员服务超时？），span 上有 `http.route`、耗时、异常栈。

> 跨服务问题（如「下单失败」）：预约服务的 span 会带出它调用会员服务的子 span，一条 trace 看穿两个服务，无需来回切日志。

## 2. 常见现象 → 处置

| 现象 | 可能原因 | 处置 |
|---|---|---|
| `HighErrorRate`（5xx>1%） | 新版本 bug / 下游不可用 | 若处于金丝雀阶段会**自动回滚**；否则手动 `make rollback SVC=reservation` |
| `HighLatencyP95`（>500ms） | 资源不足 / 慢查询 | 看 HPA 是否已扩容；必要时临时调高 `replicaCount` |
| `TargetDown` | Pod 崩溃 / OOM | `kubectl -n nekocafe-prod describe pod <pod>` 看 OOMKilled；调高内存 limit |
| 预约创建返回 503 | 会员服务不可达 | 查 member 服务健康与链路；预约侧已做「宁拒不脏」保护 |

## 3. 升级路径
P0（全站不可用）：自动回滚未生效 → 立即 `make rollback` → 群里 @负责人 → 拉电话会。
P1（单接口异常）：按上表处置，30 分钟未恢复升级为 P0。
