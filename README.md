# NekoCafé 🐈 — DevOps PoC

> 猫咪主题餐饮预约平台的 DevOps 流水线试点。本仓库取实验二架构里的两个核心服务
> （**预约 reservation** + **会员 member**）做端到端落地：容器化 → CI → CD 渐进发布 → 可观测性。
>
> 设计目标对齐运维总监三条硬规则：① PR 10 分钟内可在测试环境看到效果；
> ② 一行配置灰度到 5%；③ 出问题 3 分钟内定位到服务/节点/接口。

—— 计算机23-3 · 230205423 · 刘璐

## 仓库取舍：为什么是 Monorepo

两个服务高度协同（预约要回调会员校验），且只有我一个人维护，**Monorepo** 能做到一次 PR 原子地改两个服务、共用一套 CI/CD 与 lint 规则、依赖与版本统一治理；代价是后期若服务数量暴涨、团队拆分，发布耦合与权限粒度会成为瓶颈，届时再按服务拆成 Polyrepo。对当前 PoC，收益 > 代价。

## 技术栈

| 服务 | 语言/框架 | 端口（本地） | 关键能力 |
|---|---|---|---|
| reservation | Python 3.12 / FastAPI | 8081 → 8080 | 预约 CRUD、幂等、跨服务校验会员 |
| member | Node 20 / Express | 8082 → 8080 | 会员 CRUD、PII 脱敏 |
| redis | redis:7-alpine | — | 预约幂等键存储 |

可观测：OpenTelemetry（trace）+ Prometheus（metrics）+ Loki（logs）+ Tempo + Grafana。

## 前置依赖

- Docker Desktop 24+（含 Compose v2）
- 跑单测/本地开发（可选）：Python 3.12、Node 20
- 跑 K8s/CD（可选）：kubectl、Helm 3.16+、一个 K8s 集群（minikube/kind/Docker Desktop）

## 一键启动（基础栈）

```bash
make up          # = docker compose up -d --build，几十秒起好
```

### 验证（应全部成功）

```bash
curl -s localhost:8081/healthz                       # {"status":"ok",...}
curl -s localhost:8082/healthz
# 建会员 → 用该会员下单（会触发预约→会员的跨服务调用）
make smoke       # 自动跑完整冒烟 + 跨服务 + 幂等校验
```

## 启动可观测性（按需，较重）

```bash
make up-obs      # 基础栈 + Prometheus/Grafana/Tempo/Loki/Promtail/Alertmanager
```

| 控制台 | 地址 |
|---|---|
| Grafana（匿名 Admin，看 RED 概览） | http://localhost:3000 |
| Prometheus | http://localhost:9090 |

> 可观测性后端刻意从 `make up` 里拆出来，保证「clone 后 30 分钟内可运行」的核心路径轻快。

## 本地测试

```bash
make test                 # 两个服务的单测 + 覆盖率门槛
# 单独跑：
make test-reservation     # ruff + pytest（≥80%）
make test-member          # eslint + node --test
```

## 目录结构

```
nekocafe/
├── README.md                 一键启动与验证（本文件）
├── Makefile                  常用命令入口（make help）
├── docker-compose.yml        基础栈：reservation + member + redis
├── docker-compose.observability.yml  可观测性叠加层
├── .editorconfig .pre-commit-config.yaml .yamllint.yml .hadolint.yaml .kube-linter.yaml
├── services/
│   ├── reservation/  src + tests + Dockerfile（多阶段，非 root）
│   └── member/       src + test + Dockerfile（多阶段，非 root）
├── infra/
│   ├── helm/         Helm Chart（dev/staging/prod 三套 values）= 交付物 D3-5
│   ├── observability/ otel-collector / prometheus / grafana / loki / tempo / promtail / alertmanager
│   ├── argocd/       ApplicationSet（GitOps 加分项）
│   └── chaos/        Chaos Mesh 实验（混沌演练加分项）
├── scripts/          smoke.sh / canary-analysis.sh / rollback.sh
├── .github/workflows/ ci.yml + cd.yml
└── docs/             runbook.md + rollback.md
```

## CI / CD 一览

- **CI**（`ci.yml`，PR 与 push 触发）：Lint(IaC) ∥ 单测+覆盖率 ∥ SAST(CodeQL+gitleaks) → 构建 → Trivy 扫描+SBOM → 集成测试；并把覆盖率/镜像大小/漏洞数回写 PR 评论。靠并行 + GHA 缓存把总时长压到 10 分钟内。
- **CD**（`cd.yml`，push main 触发）：推镜像到 GHCR → dev（自动）→ staging（自动）→ **prod（人工审批）** → 金丝雀 5→25→50→100，每档 Prometheus 分析，**越线自动回滚**。

## 安全基线

- Secret 一律不入库：K8s 用 Secret/External Secrets，CI 用 GitHub Secrets（`KUBE_CONFIG_*`、`PROM_URL`）；`detect-private-key` + `gitleaks` 双重兜底。
- 镜像非 root、只读根文件系统、丢弃全部 capabilities；Trivy 拦截 HIGH/CRITICAL。
- `GITHUB_TOKEN` 默认最小权限，按 job 显式放开。

## 停止 / 清理 / 回滚

```bash
make down                       # 停并清理容器与卷
make rollback SVC=reservation   # 生产一键回滚（详见 docs/rollback.md）
```
