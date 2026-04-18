"""
基于 Redis 的 FastAPI HTTP 响应缓存中间件。

提供 `cached_response` 装饰器，功能如下：
  - 将请求路径 + 查询字符串哈希为缓存键
  - 命中缓存时直接返回缓存的 JSON（跳过处理函数）
  - 未命中时将处理函数的响应存入 Redis
  - Redis 不可用时静默降级为无缓存模式
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def _make_cache_key(prefix: str, *parts: Any) -> str:
    raw = ":".join(str(p) for p in parts)
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"{prefix}:{h}"


def cached_response(ttl: int = 300, prefix: str = "api"):
    """
    用于 FastAPI 路由处理函数的缓存装饰器，将返回值缓存到 Redis。

    用法示例::

        @router.get("/trending")
        @cached_response(ttl=300, prefix="trending")
        async def get_trending(date: str = Query(...)):
            ...

    装饰器会检查所有位置参数和关键字参数来构建缓存键，
    因此相同处理函数但不同查询参数的请求会生成不同的缓存条目。
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from knowledge_base.cache import get_cache

            # 根据所有调用参数构建稳定的缓存键
            key_parts = [func.__name__] + [str(v) for v in args] + [
                f"{k}={v}" for k, v in sorted(kwargs.items())
            ]
            cache_key = _make_cache_key(prefix, *key_parts)

            try:
                cache = get_cache()
                cached = await cache.get_json(cache_key)
                if cached is not None:
                    return cached
            except Exception:
                pass  # 缓存不可用 — 继续执行处理函数

            result = await func(*args, **kwargs)

            try:
                cache = get_cache()
                # Pydantic 模型需要先调用 .model_dump() 再进行 JSON 序列化
                data = result
                if hasattr(result, "model_dump"):
                    data = result.model_dump(mode="json")
                await cache.set_json(cache_key, data, ttl=ttl)
            except Exception as exc:
                logger.debug("Cache set failed: %s", exc)

            return result

        return wrapper

    return decorator
