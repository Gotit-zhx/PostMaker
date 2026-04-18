"""
数据访问服务 — PostgreSQL 后端

提供 RSS 数据查询接口。
"""

from datetime import datetime
from typing import Dict, List, Optional

from .cache_service import get_cache


class DataService:
    """RSS 数据访问服务（PostgreSQL）"""

    def __init__(self, project_root: str = None):
        self.cache = get_cache()
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            from knowledge_base.db import get_pool
            self._pool = get_pool()
        return self._pool

    async def get_latest_rss(
        self,
        feeds: Optional[List[str]] = None,
        days: int = 1,
        limit: int = 50,
        include_summary: bool = False,
    ) -> List[Dict]:
        days = min(max(days, 1), 30)
        cache_key = f"latest_rss:{','.join(feeds or [])}:{days}:{limit}:{include_summary}"
        cached = self.cache.get(cache_key, ttl=900)
        if cached:
            return cached

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if feeds:
                platforms = [f"rss-{fid}" for fid in feeds]
                rows = await conn.fetch(
                    """SELECT id, title, source_platform, source_url, published_at,
                              summary, author, feed_id, feed_name, date_partition,
                              ai_summary, importance_score, tags, category, crawled_at
                       FROM content_items
                       WHERE date_partition >= CURRENT_DATE - $1 * INTERVAL '1 day'
                         AND source_platform = ANY($2)
                       ORDER BY published_at DESC NULLS LAST
                       LIMIT $3""",
                    days, platforms, limit,
                )
            else:
                rows = await conn.fetch(
                    """SELECT id, title, source_platform, source_url, published_at,
                              summary, author, feed_id, feed_name, date_partition,
                              ai_summary, importance_score, tags, category, crawled_at
                       FROM content_items
                       WHERE date_partition >= CURRENT_DATE - $1 * INTERVAL '1 day'
                       ORDER BY published_at DESC NULLS LAST
                       LIMIT $2""",
                    days, limit,
                )

        rss_list = []
        for row in rows:
            pub_at = row["published_at"]
            item = {
                "title": row["title"],
                "feed_id": row["feed_id"] or "",
                "feed_name": row["feed_name"] or row["source_platform"],
                "url": row["source_url"] or "",
                "published_at": pub_at.isoformat() if pub_at else "",
                "author": row["author"] or "",
                "date": str(row["date_partition"]),
                "fetch_time": row["crawled_at"].strftime("%Y-%m-%d %H:%M:%S") if row["crawled_at"] else "",
            }
            if include_summary:
                item["summary"] = row["ai_summary"] or row["summary"] or ""
            rss_list.append(item)

        self.cache.set(cache_key, rss_list)
        return rss_list

    async def search_rss(
        self,
        keyword: str,
        feeds: Optional[List[str]] = None,
        days: int = 7,
        limit: int = 50,
        include_summary: bool = False,
    ) -> List[Dict]:
        cache_key = f"search_rss:{keyword}:{','.join(feeds or [])}:{days}:{limit}:{include_summary}"
        cached = self.cache.get(cache_key, ttl=900)
        if cached:
            return cached

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if feeds:
                platforms = [f"rss-{fid}" for fid in feeds]
                rows = await conn.fetch(
                    """SELECT id, title, source_platform, source_url, published_at,
                              summary, author, feed_id, feed_name, date_partition,
                              ai_summary, crawled_at
                       FROM content_items
                       WHERE date_partition >= CURRENT_DATE - $1 * INTERVAL '1 day'
                         AND source_platform = ANY($2)
                         AND (title ILIKE '%' || $3 || '%' OR summary ILIKE '%' || $3 || '%')
                       ORDER BY published_at DESC NULLS LAST
                       LIMIT $4""",
                    days, platforms, keyword, limit,
                )
            else:
                rows = await conn.fetch(
                    """SELECT id, title, source_platform, source_url, published_at,
                              summary, author, feed_id, feed_name, date_partition,
                              ai_summary, crawled_at
                       FROM content_items
                       WHERE date_partition >= CURRENT_DATE - $1 * INTERVAL '1 day'
                         AND (title ILIKE '%' || $2 || '%' OR summary ILIKE '%' || $2 || '%')
                       ORDER BY published_at DESC NULLS LAST
                       LIMIT $3""",
                    days, keyword, limit,
                )

        results = []
        for row in rows:
            pub_at = row["published_at"]
            item = {
                "title": row["title"],
                "feed_id": row["feed_id"] or "",
                "feed_name": row["feed_name"] or row["source_platform"],
                "url": row["source_url"] or "",
                "published_at": pub_at.isoformat() if pub_at else "",
                "author": row["author"] or "",
                "date": str(row["date_partition"]),
            }
            if include_summary:
                item["summary"] = row["ai_summary"] or row["summary"] or ""
            results.append(item)

        self.cache.set(cache_key, results)
        return results

    async def get_rss_feeds_status(self) -> Dict:
        cache_key = "rss_feeds_status"
        cached = self.cache.get(cache_key, ttl=900)
        if cached:
            return cached

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            feed_rows = await conn.fetch(
                """SELECT feed_id, feed_name, COUNT(*) as item_count
                   FROM content_items
                   WHERE date_partition = CURRENT_DATE AND feed_id IS NOT NULL
                   GROUP BY feed_id, feed_name"""
            )
            date_rows = await conn.fetch(
                """SELECT DISTINCT date_partition
                   FROM content_items
                   ORDER BY date_partition DESC
                   LIMIT 10"""
            )

        today_feeds = {}
        for row in feed_rows:
            today_feeds[row["feed_id"]] = {
                "name": row["feed_name"] or row["feed_id"],
                "item_count": row["item_count"],
            }

        result = {
            "available_dates": [str(r["date_partition"]) for r in date_rows],
            "total_dates": len(date_rows),
            "today_feeds": today_feeds,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.cache.set(cache_key, result)
        return result
