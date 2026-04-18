"""Pytest fixtures for DataRadar tests."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def tmp_config():
    """Provide a minimal config dict for testing."""
    return {
        "TIMEZONE": "Asia/Shanghai",
        "RSS_ENABLED": True,
        "AI": {
            "MODEL": "openai/gpt-4o",
            "API_KEY": "test-key",
            "API_BASE": "",
            "TIMEOUT": 30,
            "TEMPERATURE": 1.0,
            "MAX_TOKENS": 500,
        },
        "STORAGE": {
            "BACKEND": "local",
            "LOCAL": {"DATA_DIR": tempfile.mkdtemp()},
        },
        "KNOWLEDGE_BASE": {
            "ENABLED": False,
        },
    }


@pytest.fixture
def tmp_sqlite_db():
    """Create a temporary SQLite database with RSS schema."""
    import sqlite3

    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    conn = sqlite3.connect(db_path)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            feed_url TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            last_fetch_time TEXT,
            last_fetch_status TEXT,
            item_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS rss_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            feed_id TEXT NOT NULL,
            url TEXT NOT NULL,
            published_at TEXT,
            summary TEXT,
            author TEXT,
            full_text TEXT,
            ai_summary TEXT,
            first_crawl_time TEXT NOT NULL,
            last_crawl_time TEXT NOT NULL,
            crawl_count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (feed_id) REFERENCES rss_feeds(id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_rss_url_feed
            ON rss_items(url, feed_id);
    """)

    conn.execute(
        "INSERT INTO rss_feeds (id, name) VALUES (?, ?)",
        ("test-feed", "Test Feed"),
    )
    conn.commit()
    conn.close()
    yield db_path
    os.unlink(db_path)
