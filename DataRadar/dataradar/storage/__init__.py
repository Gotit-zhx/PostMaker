# coding=utf-8
"""
存储模块 — PostgreSQL 直写
"""

from dataradar.storage.base import (
    StorageBackend,
    NewsItem,
    NewsData,
    RSSItem,
    RSSData,
    convert_crawl_results_to_news_data,
)
from dataradar.storage.manager import StorageManager, get_storage_manager

__all__ = [
    "StorageBackend",
    "NewsItem",
    "NewsData",
    "RSSItem",
    "RSSData",
    "convert_crawl_results_to_news_data",
    "StorageManager",
    "get_storage_manager",
]
