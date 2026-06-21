# NekoCafé 常用命令入口。`make help` 看全部。
COMPOSE       := docker compose
COMPOSE_OBS   := docker compose -f docker-compose.yml -f docker-compose.observability.yml

.DEFAULT_GOAL := help
.PHONY: help up up-obs down logs ps smoke test test-reservation test-member lint scan sbom rollback

help: ## 列出所有可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	 awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: ## 启动基础栈（预约+会员+Redis）
	$(COMPOSE) up -d --build

up-obs: ## 启动基础栈 + 可观测性后端（Prometheus/Grafana/Tempo/Loki）
	$(COMPOSE_OBS) up -d --build

down: ## 停止并清理所有容器与卷
	$(COMPOSE_OBS) down -v

logs: ## 跟随查看业务服务日志（JSON）
	$(COMPOSE) logs -f reservation member

ps: ## 查看容器状态
	$(COMPOSE) ps

smoke: ## 对运行中的栈跑冒烟+跨服务集成检查
	bash scripts/smoke.sh

test: test-reservation test-member ## 跑两个服务的单元测试

test-reservation: ## 预约服务单测 + 覆盖率（门槛 80%）
	cd services/reservation && python -m pytest --cov=src --cov-fail-under=80

test-member: ## 会员服务单测 + 覆盖率
	cd services/member && npm test

lint: ## 本地一键跑全部 linter（等价 pre-commit）
	pre-commit run --all-files

scan: ## 用 Trivy 扫描两个镜像（需先 make up 构建出镜像）
	trivy image --severity HIGH,CRITICAL --exit-code 1 ghcr.io/uuu11111/nekocafe-reservation:0.1.0
	trivy image --severity HIGH,CRITICAL --exit-code 1 ghcr.io/uuu11111/nekocafe-member:0.1.0

sbom: ## 生成两个镜像的 SBOM（CycloneDX）
	trivy image --format cyclonedx --output reservation-sbom.json ghcr.io/uuu11111/nekocafe-reservation:0.1.0
	trivy image --format cyclonedx --output member-sbom.json ghcr.io/uuu11111/nekocafe-member:0.1.0

rollback: ## 一键回滚生产环境到上一个稳定版本（见 docs/rollback.md）
	bash scripts/rollback.sh $(SVC)
