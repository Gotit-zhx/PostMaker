"""asyncpg 连接池"""

from __future__ import annotations

from typing import Optional

_pool = None


async def init_pool(dsn: str) -> None:
    global _pool
    if _pool is not None:
        return
    import asyncpg
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)


def get_pool():
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
