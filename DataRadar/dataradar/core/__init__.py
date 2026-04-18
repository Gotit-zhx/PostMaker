# coding=utf-8
"""
核心模块 - 配置管理和核心工具
"""

from dataradar.core.loader import load_config
from dataradar.core.frequency import load_frequency_words, matches_word_groups
from dataradar.core.data import (
    read_all_today_titles_from_storage,
    read_all_today_titles,
    detect_latest_new_titles_from_storage,
    detect_latest_new_titles,
)
from dataradar.core.analyzer import (
    calculate_news_weight,
    format_time_display,
    count_word_frequency,
    count_rss_frequency,
)

__all__ = [
    "load_config",
    "load_frequency_words",
    "matches_word_groups",
    "read_all_today_titles_from_storage",
    "read_all_today_titles",
    "detect_latest_new_titles_from_storage",
    "detect_latest_new_titles",
    "calculate_news_weight",
    "format_time_display",
    "count_word_frequency",
    "count_rss_frequency",
]
