"""
DataRadar 知识库 API 的 FastAPI 应用入口。

启动顺序：
  1. 初始化 asyncpg 连接池（PostgreSQL）
  2. 初始化 Redis 缓存
  3. 初始化 BatchEmbedder（如已配置）

关闭时：释放连接池 + 关闭 Redis 连接。

运行方式::

    uvicorn api_server.main:app --host 0.0.0.0 --port 8000 --workers 1
"""

from __future__ import annotations

import logging
import os
import hmac
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api_server.routers import content, knowledge, stats
from api_server.routers import sources
from dataradar.workspace import reset_workspace, set_workspace_id, workspace_signature

logger = logging.getLogger(__name__)

# 模块级别的 Embedder 单例（在单个 uvicorn worker 进程内共享）
_embedder: Optional[object] = None  # BatchEmbedder | None


def get_embedder():
    """返回模块级别的 BatchEmbedder 实例，若未配置则返回 None。"""
    return _embedder


@asynccontextmanager
async def lifespan(app: FastAPI):
    """初始化和销毁共享资源。"""
    global _embedder

    # ── PostgreSQL ─────────────────────────────────────────────────
    postgres_dsn = os.getenv("POSTGRES_DSN")
    if postgres_dsn:
        from knowledge_base.db import init_pool
        await init_pool(postgres_dsn)
        logger.info("PostgreSQL pool initialised.")
    else:
        # Local SQLite is the default development/runtime backend.
        from knowledge_base.local_repository import LocalContentRepository
        LocalContentRepository()._connect().close()
        logger.info("POSTGRES_DSN not set — using local SQLite content store.")

    # ── Redis ──────────────────────────────────────────────────────
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        from knowledge_base.cache import init_cache
        init_cache(redis_url)
        logger.info("Redis cache initialised.")
    else:
        logger.info("REDIS_URL not set — cache will be no-op (cold reads only).")

    # ── Embedder ───────────────────────────────────────────────────
    embed_model = os.getenv("EMBED_MODEL", "")
    embed_api_key = os.getenv("EMBED_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    embed_api_base = os.getenv("EMBED_API_BASE", "")

    if embed_model and embed_api_key:
        from knowledge_base.etl.embedder import BatchEmbedder
        _embedder = BatchEmbedder(
            model=embed_model,
            api_key=embed_api_key,
            api_base=embed_api_base or None,
        )
        logger.info("BatchEmbedder ready (model=%s).", embed_model)
    else:
        logger.info(
            "EMBED_MODEL / EMBED_API_KEY not set — semantic search disabled."
        )

    yield

    # ── 资源清理 ───────────────────────────────────────────────────
    try:
        from knowledge_base.db import get_pool
        pool = get_pool()
        await pool.close()
        logger.info("PostgreSQL pool closed.")
    except Exception:
        pass

    try:
        from knowledge_base.cache import get_cache
        cache = get_cache()
        if hasattr(cache, "_client") and cache._client:
            await cache._client.aclose()
    except Exception:
        pass


# ── 应用实例 ────────────────────────────────────────────────────

app = FastAPI(
    title="DataRadar Knowledge Base API",
    description=(
        "High-performance multimodal content knowledge base. "
        "Supports text, video, audio, and image content from "
        "Hacker News, Reddit, YouTube, RSS feeds, and more."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


def _auth_required() -> bool:
    return os.getenv("DATARADAR_AUTH_REQUIRED", "0").lower() in {"1", "true", "yes"}


@app.middleware("http")
async def workspace_auth(request: Request, call_next):
    if not _auth_required() or request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}:
        return await call_next(request)
    if not request.url.path.startswith("/api/v1/"):
        return await call_next(request)
    if os.getenv("POSTGRES_DSN"):
        return JSONResponse(
            {"detail": "当前 PostgreSQL 存储尚未支持 workspace 隔离，请使用 SQLite 多用户模式"},
            status_code=503,
        )
    workspace = request.headers.get("x-workspace-id", "")
    signature = request.headers.get("x-workspace-signature", "")
    if not workspace or not signature or not hmac.compare_digest(signature, workspace_signature(workspace)):
        return JSONResponse({"detail": "工作区身份无效"}, status_code=401)
    try:
        token = set_workspace_id(workspace)
    except ValueError:
        return JSONResponse({"detail": "工作区身份无效"}, status_code=401)
    try:
        return await call_next(request)
    finally:
        reset_workspace(token)

# 默认允许所有来源；生产环境可通过 ALLOWED_ORIGINS 环境变量收紧
_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ────────────────────────────────────────────────────
app.include_router(content.router)
app.include_router(knowledge.router)
app.include_router(stats.router)
app.include_router(sources.router)


@app.get("/health", tags=["meta"])
async def health():
    """就绪探针：检查 PostgreSQL 和 Redis 连接状态。"""
    from fastapi.responses import JSONResponse
    checks = {"status": "ok", "postgres": "not_configured", "sqlite": "ok", "redis": "ok"}

    if os.getenv("POSTGRES_DSN"):
        try:
            from knowledge_base.db import get_pool
            pool = get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["postgres"] = "ok"
        except Exception:
            checks["postgres"] = "unavailable"
            checks["status"] = "degraded"
    else:
        try:
            from knowledge_base.local_repository import LocalContentRepository
            conn = LocalContentRepository()._connect(); conn.execute("SELECT 1"); conn.close()
        except Exception:
            checks["sqlite"] = "unavailable"
            checks["status"] = "degraded"

    try:
        from knowledge_base.cache import get_cache
        cache = get_cache()
        if not await cache.is_available():
            checks["redis"] = "unavailable"
    except Exception:
        checks["redis"] = "unavailable"

    status_code = 200 if checks["status"] == "ok" else 503
    return JSONResponse(content=checks, status_code=status_code)


@app.get("/", tags=["meta"])
async def root():
    return {
        "name": "DataRadar Knowledge Base API",
        "docs": "/docs",
        "health": "/health",
    }
