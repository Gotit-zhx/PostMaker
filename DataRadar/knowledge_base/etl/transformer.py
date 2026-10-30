"""Legacy SQLite export transformer.

Keeps the older file based RSS store usable by the PostgreSQL ETL pipeline and
provides a small compatibility layer for existing scripts.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List

from knowledge_base.repository import ContentItemInput


class SQLiteTransformer:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def _db(self, kind: str, date_str: str):
        candidates = [
            self.output_dir / kind / f"{date_str}.db",
            self.output_dir / f"{date_str}.db",
            self.output_dir / kind / date_str / "data.db",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def transform_rss(self, date_str: str) -> List[ContentItemInput]:
        path = self._db("rss", date_str)
        if not path:
            return []
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM rss_items").fetchall()
        except sqlite3.Error:
            return []
        finally:
            conn.close()
        return [self._rss_row(row, date_str) for row in rows]

    def transform_news(self, date_str: str) -> List[ContentItemInput]:
        path = self._db("news", date_str)
        if not path:
            return []
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM news_items").fetchall()
        except sqlite3.Error:
            return []
        finally:
            conn.close()
        return [ContentItemInput(content_type="text", title=row["title"], source_platform=f"news-{row['source_id']}", source_url=row["url"] or row["title"], date_partition=date_str, summary=row.get("summary") if hasattr(row, "get") else None) for row in rows]

    @staticmethod
    def _rss_row(row, date_str: str) -> ContentItemInput:
        published = row["published_at"] if "published_at" in row.keys() else None
        return ContentItemInput(
            content_type="text",
            title=row["title"] or "(untitled)",
            source_platform=f"rss-{row['feed_id']}",
            source_url=row["url"] or row["title"],
            date_partition=date_str,
            published_at=published,
            summary=row["summary"] if "summary" in row.keys() else None,
            full_text=row["full_text"] if "full_text" in row.keys() else None,
        )
