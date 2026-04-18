"""
数据解析服务 — 查询 PostgreSQL content_items
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import yaml

from ..utils.errors import FileParseError, DataNotFoundError
from .cache_service import get_cache


class ParserService:
    """数据解析服务（PostgreSQL 后端）"""

    def __init__(self, project_root: str = None):
        if project_root is None:
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent
        else:
            self.project_root = Path(project_root)

        self.cache = get_cache()
        self._pool = None
        self._freq_words_cache: Optional[List[Dict]] = None
        self._freq_words_mtime: float = 0.0

    async def _get_pool(self):
        if self._pool is None:
            from knowledge_base.db import get_pool
            self._pool = get_pool()
        return self._pool

    @staticmethod
    def clean_title(title: str) -> str:
        title = re.sub(r'\s+', ' ', title)
        return title.strip()

    def get_date_folder_name(self, date: datetime = None) -> str:
        if date is None:
            date = datetime.now()
        return date.strftime("%Y-%m-%d")

    async def read_all_titles_for_date(
        self,
        date: datetime = None,
        platform_ids: Optional[List[str]] = None,
        db_type: str = "rss"
    ) -> Tuple[Dict, Dict, Dict]:
        date_str = self.get_date_folder_name(date)
        platform_key = ','.join(sorted(platform_ids)) if platform_ids else 'all'
        cache_key = f"read_all:{db_type}:{date_str}:{platform_key}"

        cached = self.cache.get(cache_key, ttl=900)
        if cached:
            return cached

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if platform_ids:
                platforms = [f"rss-{fid}" for fid in platform_ids]
                rows = await conn.fetch(
                    """SELECT title, source_platform, source_url, published_at,
                              summary, author, feed_id, feed_name,
                              first_crawl_at, last_crawl_at, crawl_count, crawled_at
                       FROM content_items
                       WHERE date_partition = $1::date AND source_platform = ANY($2)
                       ORDER BY published_at DESC""",
                    date_str, platforms,
                )
            else:
                rows = await conn.fetch(
                    """SELECT title, source_platform, source_url, published_at,
                              summary, author, feed_id, feed_name,
                              first_crawl_at, last_crawl_at, crawl_count, crawled_at
                       FROM content_items
                       WHERE date_partition = $1::date
                       ORDER BY published_at DESC""",
                    date_str,
                )

        if not rows:
            raise DataNotFoundError(
                f"未找到 {date_str} 的 {db_type} 数据",
                suggestion="请先运行采集或检查日期是否正确"
            )

        all_items = {}
        id_to_name = {}
        all_timestamps = {}

        for row in rows:
            feed_id = row["feed_id"] or row["source_platform"]
            feed_name = row["feed_name"] or feed_id

            if feed_id not in id_to_name:
                id_to_name[feed_id] = feed_name
            if feed_id not in all_items:
                all_items[feed_id] = {}

            pub_at = row["published_at"]
            pub_str = pub_at.isoformat() if pub_at else ""

            all_items[feed_id][row["title"]] = {
                "url": row["source_url"] or "",
                "published_at": pub_str,
                "summary": row["summary"] or "",
                "author": row["author"] or "",
                "first_time": str(row["first_crawl_at"] or ""),
                "last_time": str(row["last_crawl_at"] or ""),
                "count": row["crawl_count"] or 1,
            }

            crawled = row["crawled_at"]
            if crawled:
                ts_key = crawled.strftime("%H:%M")
                all_timestamps[ts_key] = crawled.timestamp()

        result = (all_items, id_to_name, all_timestamps)
        self.cache.set(cache_key, result)
        return result

    async def get_available_dates(self, db_type: str = "rss") -> List[str]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT DISTINCT date_partition
                   FROM content_items
                   ORDER BY date_partition DESC
                   LIMIT 30"""
            )
        return [r["date_partition"].strftime("%Y-%m-%d") for r in rows]

    async def get_available_date_range(self, db_type: str = "rss") -> Tuple[Optional[datetime], Optional[datetime]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT MIN(date_partition) as earliest, MAX(date_partition) as latest FROM content_items"
            )
        if not row or not row["earliest"]:
            return (None, None)
        return (
            datetime.combine(row["earliest"], datetime.min.time()),
            datetime.combine(row["latest"], datetime.min.time()),
        )

    def parse_yaml_config(self, config_path: str = None) -> dict:
        if config_path is None:
            config_path = self.project_root / "config" / "config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileParseError(str(config_path), "配置文件不存在")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
            return config_data
        except Exception as e:
            raise FileParseError(str(config_path), str(e))

    def parse_frequency_words(self, words_file: str = None) -> List[Dict]:
        import os
        from dataradar.core.frequency import load_frequency_words

        if words_file is None:
            words_file = str(self.project_root / "config" / "frequency_words.txt")

        try:
            current_mtime = os.path.getmtime(words_file)
            if self._freq_words_cache is not None and current_mtime == self._freq_words_mtime:
                return self._freq_words_cache

            word_groups, filter_words, global_filters = load_frequency_words(words_file)
            self._freq_words_cache = word_groups
            self._freq_words_mtime = current_mtime
            return word_groups
        except FileNotFoundError:
            return []
        except Exception as e:
            raise FileParseError(words_file, str(e))
