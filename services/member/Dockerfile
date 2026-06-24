# syntax=docker/dockerfile:1.7
# ============ deps 阶段：只装生产依赖，devDependencies 不进镜像 ============
FROM node:26-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# 装完顺手剔掉运行期用不到的类型声明/sourcemap/文档（otel 全家桶的这些占了大头，
# 单 @opentelemetry 一项就能从 79MB 砍到 28MB），纯 JS 一律保留，零运行风险
RUN npm ci --omit=dev && npm cache clean --force \
 && find node_modules -type f \( -name "*.d.ts" -o -name "*.map" -o -name "*.md" \) -delete

# ============ runtime 阶段：拷 node_modules + 源码，非 root 运行 ============
FROM node:26-alpine
# 升级 OS 包以拿到 openssl(libcrypto3/libssl3) 等的安全补丁，消除基线镜像滞后带来的 HIGH CVE
RUN apk upgrade --no-cache
ENV NODE_ENV=production \
    APP_VERSION=0.1.0
WORKDIR /app
# alpine 官方镜像自带非 root 的 node 用户(uid 1000)，直接复用
COPY --chown=node:node --from=deps /app/node_modules ./node_modules
COPY --chown=node:node package.json ./
COPY --chown=node:node src ./src
USER node
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:8080/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "src/index.js"]
