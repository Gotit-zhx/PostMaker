"""
asyncpg 连接池管理器。

在应用启动时初始化一次，在所有异步工作线程间共享。

用法::

    # 应用启动时（FastAPI lifespan / main）
    await init_pool(dsn="postgresql://user:pass@host/db")

    # 在请求处理器中
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM content_items LIMIT 10")

    # 应用关闭时
    await close_pool()
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_pool = None  # asyncpg.Pool


async def init_pool(
    dsn: str,
    min_size: int = 10,
    max_size: int = 200,
    command_timeout: float = 30.0,
    statement_cache_size: int = 100,
) -> None:
    """
    初始化全局 asyncpg 连接池。

    在执行任何数据库操作前，于应用启动时调用一次。
    """
    global _pool
    if _pool is not None:
        return  # 已初始化

    try:
        import asyncpg  # type: ignore
    except ImportError:
        raise ImportError(
            "asyncpg is required for the knowledge base. "
            "Install with: pip install asyncpg"
        )

    logger.info(
        "Initializing PostgreSQL pool: min=%d max=%d dsn=%s",
        min_size,
        max_size,
        _redact_dsn(dsn),
    )
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
        statement_cache_size=statement_cache_size,
        # 注册向量编解码器，使 pgvector 列以列表形式返回
        init=_register_vector_codec,
    )
    logger.info("PostgreSQL pool ready")


async def _register_vector_codec(conn) -> None:
    """为 pgvector 的 'vector' 类型注册文本编解码器。"""
    try:
        await conn.execute("SET search_path TO public")
        # pgvector 列默认以字符串形式返回；在此解析
        await conn.set_type_codec(
            "vector",
            encoder=_encode_vector,
            decoder=_decode_vector,
            schema="public",
            format="text",
        )
    except Exception as exc:
        logger.warning("pgvector codec 注册失败（扩展可能未安装）: %s", exc)


def _encode_vector(value) -> str:
    """将 Python list/tuple 编码为 pgvector 字符串 '[1.0,2.0,...]'。"""
    if value is None:
        return None
    return "[" + ",".join(str(float(v)) for v in value) + "]"


def _decode_vector(value: str):
    """将 pgvector 字符串 '[1.0,2.0,...]' 解码为 Python 列表。"""
    if value is None:
        return None
    return [float(x) for x in value.strip("[]").split(",")]


def get_pool():
    """返回已初始化的连接池。若未初始化则抛出 RuntimeError。"""
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized. Call await init_pool(dsn=...) first."
        )
    return _pool


async def close_pool() -> None:
    """关闭连接池并释放所有连接。"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed")


def _redact_dsn(dsn: str) -> str:
    """在 DSN 中隐藏密码，用于安全日志输出。"""
    import re
    return re.sub(r":[^:@]+@", ":***@", dsn)
