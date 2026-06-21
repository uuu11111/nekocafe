# syntax=docker/dockerfile:1.7
# ============ build 阶段：把依赖装进独立 venv，编译/缓存产物留在这一层 ============
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
# 单独成层：requirements.txt 不变时这一层走缓存，改源码不会触发重装依赖
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
 && find /opt/venv -type d -name "__pycache__" -prune -exec rm -rf {} + \
 && find /opt/venv -type d -name "tests" -prune -exec rm -rf {} + \
 && find /opt/venv -name "*.pyc" -delete

# ============ runtime 阶段：只拷 venv + 源码，非 root 运行，体积最小 ============
FROM python:3.12-slim
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_VERSION=0.1.0
# 固定 uid 的非 root 用户，方便在 K8s securityContext 里 runAsUser: 10001
RUN groupadd -g 10001 app && useradd -u 10001 -g app -m app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=app:app src ./src
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
