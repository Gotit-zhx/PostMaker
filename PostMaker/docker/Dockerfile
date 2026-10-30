FROM node:22-alpine AS frontend-build

WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm ci --prefix frontend
COPY frontend/ ./frontend/
COPY PostMaker/postmaker/workbench/static/ ./PostMaker/postmaker/workbench/static/
RUN npm run build --prefix frontend

FROM python:3.12-slim

WORKDIR /app

# curl 用于容器健康检查；其余运行时依赖由 PostMaker 的 pyproject.toml 声明。
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY PostMaker/pyproject.toml ./
COPY PostMaker/postmaker/ ./postmaker/
COPY PostMaker/config/ ./config/
COPY PostMaker/templates/ ./templates/
COPY PostMaker/prompts/ ./prompts/
COPY --from=frontend-build /src/PostMaker/postmaker/workbench/static/ ./postmaker/workbench/static/

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8787

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD curl -fsS http://localhost:8787/api/health || exit 1

CMD ["uvicorn", "postmaker.workbench.app:app", "--host", "0.0.0.0", "--port", "8787", "--workers", "1"]
