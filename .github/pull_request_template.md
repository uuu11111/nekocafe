## 变更说明
<!-- 这个 PR 做了什么？为什么？关联 issue #xxx -->

## 变更类型
- [ ] 功能 feat
- [ ] 修复 fix
- [ ] 重构 refactor
- [ ] 文档 docs
- [ ] CI/CD / 基础设施 chore

## 自检清单
- [ ] 本地 `make test` 通过，覆盖率不低于 80%
- [ ] 本地 `pre-commit run --all-files` 通过
- [ ] 不含任何硬编码密钥（已交由 Secret/Vault 注入）
- [ ] 若改动接口，已更新对应的冒烟/集成用例
- [ ] 若改动 Helm/K8s，已 `helm lint` + `kube-linter` 通过

## 影响范围与回滚
<!-- 影响哪个服务？灰度计划？出问题如何回滚（一键 `make rollback SVC=xxx`）？ -->
