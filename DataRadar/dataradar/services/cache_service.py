"""
缓存服务

实现TTL缓存机制，提升数据访问性能。
"""

import hashlib
import json
import time
from typing import Any, Optional
from threading import Lock


def make_cache_key(namespace: str, **params) -> str:
    """
    生成结构化缓存 key

    通过对参数排序和哈希，确保相同参数组合总是生成相同的 key。

    Args:
        namespace: 缓存命名空间，如 "latest_rss", "search_rss"
        **params: 缓存参数

    Returns:
        格式化的缓存 key，如 "latest_rss:a1b2c3d4"
    """
    if not params:
        return namespace

    normalized_params = {}
    for k, v in params.items():
        if v is None:
            continue
        elif isinstance(v, (list, tuple)):
            normalized_params[k] = json.dumps(sorted(v) if all(isinstance(i, str) for i in v) else list(v), ensure_ascii=False)
        elif isinstance(v, dict):
            normalized_params[k] = json.dumps(v, sort_keys=True, ensure_ascii=False)
        else:
            normalized_params[k] = str(v)

    sorted_params = sorted(normalized_params.items())
    param_str = "&".join(f"{k}={v}" for k, v in sorted_params)

    hash_value = hashlib.md5(param_str.encode('utf-8')).hexdigest()[:8]

    return f"{namespace}:{hash_value}"


class CacheService:
    """缓存服务类"""

    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        self._lock = Lock()

    def get(self, key: str, ttl: int = 900) -> Optional[Any]:
        """
        获取缓存数据

        Args:
            key: 缓存键
            ttl: 存活时间（秒），默认15分钟
        """
        with self._lock:
            if key in self._cache:
                if time.time() - self._timestamps[key] < ttl:
                    return self._cache[key]
                else:
                    del self._cache[key]
                    del self._timestamps[key]
        return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = time.time()

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]
                return True
        return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    def cleanup_expired(self, ttl: int = 900) -> int:
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, timestamp in self._timestamps.items()
                if current_time - timestamp >= ttl
            ]

            for key in expired_keys:
                del self._cache[key]
                del self._timestamps[key]

            return len(expired_keys)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_entries": len(self._cache),
                "oldest_entry_age": (
                    time.time() - min(self._timestamps.values())
                    if self._timestamps else 0
                ),
                "newest_entry_age": (
                    time.time() - max(self._timestamps.values())
                    if self._timestamps else 0
                )
            }


_global_cache = None


def get_cache() -> CacheService:
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheService()
    return _global_cache
