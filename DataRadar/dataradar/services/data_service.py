"""
数据访问服务 — PostgreSQL / SQLite 后端

提供 RSS 数据查询接口。
"""

from datetime import datetime
from typing import Dict, List, Optional

from .cache_service import get_cache
import os


def _local_item(row: Dict) -> Dict:
    pub_at = row.get("published_at")
    return {
        "title": row.get("title", ""),
        "feed_id": row.get("feed_id") or "",
        "feed_name": row.get("feed_name") or row.get("source_platform", ""),
        "url": row.get("source_url") or "",
        "published_at": pub_at.isoformat() if hasattr(pub_at, "isoformat") else (pub_at or ""),
        "author": row.get("author") or "",
        "date": str(row.get("date_partition") or ""),
        "fetch_time": str(row.get("crawled_at") or ""),
    }


class DataService:
    """RSS 数据访问服务，按环境选择 PostgreSQL 或本地 SQLite。"""

    def __init__(self, project_root: str = None):
        self.cache = get_cache()
        self._pool = None
        self._local = None
        if not os.getenv("POSTGRES_DSN"):
            from knowledge_base.local_repository import LocalContentRepository
            self._local = LocalContentRepository()

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
        if self._local:
            date_str = await self._local.get_latest_date()
            rows = []
            for feed in feeds or [None]:
                rows.extend(await self._local.list_by_date(date_str, platform=f"rss-{feed}" if feed else None, limit=limit))
            rows.sort(key=lambda r: r.get("published_at") or "", reverse=True)
            result = [_local_item(r) for r in rows[:limit]]
            if include_summary:
                for item, row in zip(result, rows[:limit]):
                    item["summary"] = row.get("ai_summary") or row.get("summary") or ""
            return result
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
        if self._local:
            rows = await self._local.search_fulltext(keyword, limit=limit)
            if feeds:
                allowed = {f"rss-{feed}" for feed in feeds}
                rows = [r for r in rows if r.get("source_platform") in allowed]
            result = [_local_item(r) for r in rows[:limit]]
            if include_summary:
                for item, row in zip(result, rows[:limit]):
                    item["summary"] = row.get("ai_summary") or row.get("summary") or ""
            return result
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
        if self._local:
            result = await self._local.get_feed_status()
            result["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return result
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
