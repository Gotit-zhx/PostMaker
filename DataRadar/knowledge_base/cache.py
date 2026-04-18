"""
知识库 API 的 Redis 共享缓存。

与内存缓存 CacheService（dataradar/services/cache_service.py）不同，
此缓存存储在 Redis 中，因此在所有 FastAPI 工作进程间共享，
实现高并发场景下的真正共享缓存。

TTL 策略:
  搜索结果     →  5 分钟  （热门查询变化频繁）
  热点列表     →  5 分钟
  内容详情     →  30 分钟 （写入后稳定不变）
  知识条目     →  30 分钟
  统计概览     →  10 分钟
  平台列表     →  1 小时  （几乎不变）

用法::

    cache = KnowledgeCache(redis_url="redis://localhost:6379/0")
    await cache.set("trending:2025-01-15", json_str, ttl=300)
    val = await cache.get("trending:2025-01-15")
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 默认 TTL（秒）
TTL_SEARCH = 300        # 5 分钟
TTL_TRENDING = 300      # 5 分钟
TTL_CONTENT = 1800      # 30 分钟
TTL_KNOWLEDGE = 1800    # 30 分钟
TTL_STATS = 600         # 10 分钟
TTL_PLATFORM = 3600     # 1 小时


class KnowledgeCache:
    """
    基于 Redis 的知识库 API 共享缓存。

    若 Redis 不可用则降级为空操作（每次调用均缓存未命中），
    确保应用在无 Redis 情况下仍可正常运行。
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._redis = None
        self._url = redis_url or ""
        if self._url:
            self._connect()

    def _connect(self):
        try:
            import redis.asyncio as aioredis  # type: ignore
            self._redis = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            logger.info("Redis cache connected: %s", self._url)
        except ImportError:
            logger.warning(
                "redis[hiredis] not installed. Cache disabled. "
                "Install with: pip install redis[hiredis]"
            )
        except Exception as exc:
            logger.warning("Redis connection failed (%s), cache disabled", exc)

    # ------------------------------------------------------------------
    # 核心 get / set / delete 操作
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception as exc:
            logger.debug("Cache GET failed for %s: %s", key, exc)
            return None

    async def set(self, key: str, value: str, ttl: int = TTL_CONTENT) -> None:
        if not self._redis:
            return
        try:
            await self._redis.setex(key, ttl, value)
        except Exception as exc:
            logger.debug("Cache SET failed for %s: %s", key, exc)

    async def delete(self, key: str) -> None:
        if not self._redis:
            return
        try:
            await self._redis.delete(key)
        except Exception as exc:
            logger.debug("Cache DELETE failed for %s: %s", key, exc)

    async def delete_pattern(self, pattern: str) -> int:
        """删除所有匹配指定 glob 模式的键。返回删除数量。"""
        if not self._redis:
            return 0
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                return await self._redis.delete(*keys)
            return 0
        except Exception as exc:
            logger.debug("Cache DELETE PATTERN failed for %s: %s", pattern, exc)
            return 0

    # ------------------------------------------------------------------
    # 类型化辅助方法
    # ------------------------------------------------------------------

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_json(self, key: str, value: Any, ttl: int = TTL_CONTENT) -> None:
        await self.set(key, json.dumps(value, ensure_ascii=False), ttl)

    # ------------------------------------------------------------------
    # 便捷的缓存键构建方法
    # ------------------------------------------------------------------

    @staticmethod
    def search_key(query: str, content_type: str = "", limit: int = 0) -> str:
        h = hashlib.md5(f"{query}:{content_type}:{limit}".encode()).hexdigest()[:12]
        return f"search:{h}"

    @staticmethod
    def trending_key(date: str, content_type: str = "") -> str:
        return f"trending:{date}:{content_type}"

    @staticmethod
    def content_key(content_id: int) -> str:
        return f"content:{content_id}"

    @staticmethod
    def knowledge_key(entry_id: int) -> str:
        return f"knowledge:{entry_id}"

    @staticmethod
    def stats_key() -> str:
        return "stats:overview"

    @staticmethod
    def platform_list_key() -> str:
        return "platforms:list"

    async def is_available(self) -> bool:
        """检查 Redis 是否可达。"""
        if not self._redis:
            return False
        try:
            return await self._redis.ping()
        except Exception:
            return False


# 模块级单例（由 FastAPI lifespan 初始化）
_cache: Optional[KnowledgeCache] = None


def init_cache(redis_url: Optional[str] = None) -> KnowledgeCache:
    global _cache
    _cache = KnowledgeCache(redis_url)
    return _cache


def get_cache() -> KnowledgeCache:
    global _cache
    if _cache is None:
        _cache = KnowledgeCache()  # 空操作缓存
    return _cache
