# coding=utf-8
"""
存储管理器 — 直写 PostgreSQL

RSSData/NewsData → asyncpg UPSERT → content_items
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dataradar.storage.base import RSSData, RSSItem

logger = logging.getLogger(__name__)

_storage_manager: Optional["StorageManager"] = None


class StorageManager:
    """直写 PostgreSQL 的存储管理器。"""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool = None

    async def init(self):
        if self._pool is not None:
            return
        from knowledge_base.db import init_pool, get_pool
        await init_pool(self.dsn)
        self._pool = get_pool()
        logger.info("[存储] PostgreSQL 连接池就绪")

    async def close(self):
        if self._pool is not None:
            from knowledge_base.db import close_pool
            await close_pool()
            self._pool = None

    @property
    def backend_name(self) -> str:
        return "postgresql"

    async def save_rss_data(self, rss_data: RSSData) -> bool:
        """将 RSSData 直接 UPSERT 到 content_items。"""
        if not self._pool:
            await self.init()

        now = datetime.now(timezone.utc)
        date_partition = rss_data.date or now.strftime("%Y-%m-%d")
        upserted = 0

        for feed_id, items in rss_data.items.items():
            feed_name = rss_data.id_to_name.get(feed_id, feed_id)
            for item in items:
                try:
                    await self._upsert_item(item, feed_id, feed_name, date_partition, now)
                    upserted += 1
                except Exception as e:
                    logger.warning("[存储] UPSERT 失败 (%s): %s", item.title[:30], e)

        logger.info("[存储] UPSERT 完成: %d/%d 条", upserted, rss_data.get_total_count())
        return upserted > 0

    async def _upsert_item(
        self, item: RSSItem, feed_id: str, feed_name: str,
        date_partition: str, now: datetime
    ):
        source_platform = f"rss-{feed_id}"
        source_url = item.url or ""
        content_hash = hashlib.md5(f"{source_platform}:{source_url}".encode()).hexdigest()

        published_at = None
        if item.published_at:
            try:
                published_at = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        tags = item.tags if item.tags else None
        importance = item.importance_score if item.importance_score else 0.0

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO content_items (
                    content_type, title, source_platform, source_url, canonical_url,
                    published_at, crawled_at, date_partition,
                    summary, full_text, author, ai_summary,
                    feed_id, feed_name, crawl_count, first_crawl_at, last_crawl_at,
                    importance_score, tags, category, content_hash
                ) VALUES (
                    'text', $1, $2, $3, $3,
                    $4, $5, $6::date,
                    $7, $8, $9, $10,
                    $11, $12, 1, $5, $5,
                    $13, $14, $15, $16
                )
                ON CONFLICT (source_platform, source_url) DO UPDATE SET
                    crawl_count = content_items.crawl_count + 1,
                    last_crawl_at = EXCLUDED.crawled_at,
                    full_text = COALESCE(NULLIF(EXCLUDED.full_text, ''), content_items.full_text),
                    ai_summary = COALESCE(NULLIF(EXCLUDED.ai_summary, ''), content_items.ai_summary),
                    importance_score = GREATEST(EXCLUDED.importance_score, content_items.importance_score),
                    tags = COALESCE(EXCLUDED.tags, content_items.tags),
                    category = COALESCE(NULLIF(EXCLUDED.category, ''), content_items.category)
                """,
                item.title,             # $1
                source_platform,        # $2
                source_url,             # $3
                published_at,           # $4
                now,                    # $5
                date_partition,         # $6
                item.summary or None,   # $7
                item.full_text or None, # $8
                item.author or None,    # $9
                item.ai_summary or None, # $10
                feed_id,                # $11
                feed_name,              # $12
                importance,             # $13
                tags,                   # $14
                item.category or None,  # $15
                content_hash,           # $16
            )

    async def detect_new_rss_items(self, rss_data: RSSData) -> List[RSSItem]:
        """检测 rss_data 中哪些是数据库没有的新条目。"""
        if not self._pool:
            await self.init()

        new_items = []
        for feed_id, items in rss_data.items.items():
            urls = [item.url for item in items if item.url]
            if not urls:
                continue

            source_platform = f"rss-{feed_id}"
            async with self._pool.acquire() as conn:
                existing = await conn.fetch(
                    "SELECT source_url FROM content_items WHERE source_platform = $1 AND source_url = ANY($2)",
                    source_platform, urls,
                )
                existing_urls = {r["source_url"] for r in existing}

            for item in items:
                if item.url and item.url not in existing_urls:
                    new_items.append(item)

        return new_items

    async def get_content_by_date(
        self, date: str, feed_ids: Optional[List[str]] = None, limit: int = 200
    ) -> List[dict]:
        """按日期查询内容。"""
        if not self._pool:
            await self.init()

        async with self._pool.acquire() as conn:
            if feed_ids:
                platforms = [f"rss-{fid}" for fid in feed_ids]
                rows = await conn.fetch(
                    """SELECT * FROM content_items
                       WHERE date_partition = $1::date AND source_platform = ANY($2)
                       ORDER BY importance_score DESC, published_at DESC
                       LIMIT $3""",
                    date, platforms, limit,
                )
            else:
                rows = await conn.fetch(
                    """SELECT * FROM content_items
                       WHERE date_partition = $1::date
                       ORDER BY importance_score DESC, published_at DESC
                       LIMIT $2""",
                    date, limit,
                )
        return [dict(r) for r in rows]

    async def search_content(
        self, keyword: str, days: int = 7, limit: int = 50
    ) -> List[dict]:
        """关键词搜索。"""
        if not self._pool:
            await self.init()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM content_items
                   WHERE date_partition >= CURRENT_DATE - $1 * INTERVAL '1 day'
                     AND (title ILIKE '%' || $2 || '%' OR summary ILIKE '%' || $2 || '%')
                   ORDER BY published_at DESC
                   LIMIT $3""",
                days, keyword, limit,
            )
        return [dict(r) for r in rows]

    async def get_feeds_status(self) -> Dict:
        """获取各 feed 统计。"""
        if not self._pool:
            await self.init()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT feed_id, feed_name, COUNT(*) as item_count,
                          MIN(date_partition) as first_date, MAX(date_partition) as last_date
                   FROM content_items
                   WHERE feed_id IS NOT NULL
                   GROUP BY feed_id, feed_name
                   ORDER BY item_count DESC"""
            )
        return {
            "feeds": [dict(r) for r in rows],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def cleanup(self):
        pass


def get_storage_manager(dsn: str = "", force_new: bool = False) -> StorageManager:
    """获取 StorageManager 单例。"""
    global _storage_manager
    if _storage_manager is None or force_new:
        _storage_manager = StorageManager(dsn=dsn)
    return _storage_manager
