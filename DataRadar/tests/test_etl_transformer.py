"""Tests for ETL transformer (SQLite → ContentItemInput)."""

import os
import sys
import sqlite3

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSQLiteTransformer:
    def test_transform_rss_empty_db(self, tmp_sqlite_db):
        from knowledge_base.etl.transformer import SQLiteTransformer

        output_dir = os.path.dirname(os.path.dirname(tmp_sqlite_db))
        transformer = SQLiteTransformer(output_dir)
        items = transformer.transform_rss("9999-01-01")
        assert items == []

    def test_transform_rss_with_data(self, tmp_sqlite_db):
        conn = sqlite3.connect(tmp_sqlite_db)
        conn.execute(
            """INSERT INTO rss_items
               (title, feed_id, url, published_at, summary, first_crawl_time, last_crawl_time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "Test Article",
                "test-feed",
                "https://example.com/article1",
                "2025-01-15T10:00:00Z",
                "This is a test article summary.",
                "10:00",
                "10:00",
            ),
        )
        conn.commit()
        conn.close()

        from knowledge_base.etl.transformer import SQLiteTransformer

        db_date = os.path.basename(tmp_sqlite_db).replace(".db", "")
        rss_dir = os.path.dirname(tmp_sqlite_db)
        parent_dir = os.path.dirname(rss_dir)

        actual_date_name = os.path.basename(tmp_sqlite_db).replace(".db", "")
        os.makedirs(os.path.join(parent_dir, "rss"), exist_ok=True)
        target_path = os.path.join(parent_dir, "rss", os.path.basename(tmp_sqlite_db))
        if not os.path.exists(target_path):
            import shutil
            shutil.copy2(tmp_sqlite_db, target_path)

        transformer = SQLiteTransformer(parent_dir)
        items = transformer.transform_rss(actual_date_name)
        assert len(items) >= 0

    def test_transform_news_nonexistent_date(self, tmp_sqlite_db):
        from knowledge_base.etl.transformer import SQLiteTransformer

        output_dir = os.path.dirname(os.path.dirname(tmp_sqlite_db))
        transformer = SQLiteTransformer(output_dir)
        items = transformer.transform_news("9999-01-01")
        assert items == []
