"""Tests for the title similarity algorithm used in ETL aggregation."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from knowledge_base.etl.pipeline import _title_similar


class TestTitleSimilarityEnglish:
    def test_identical_titles(self):
        assert _title_similar("OpenAI releases GPT-5", "OpenAI releases GPT-5")

    def test_similar_english_titles(self):
        assert _title_similar(
            "OpenAI Launches GPT-5 with Major Improvements Today",
            "OpenAI Launches GPT-5 with Major New Features Today",
        )

    def test_dissimilar_english_titles(self):
        assert not _title_similar(
            "Apple announces new iPhone",
            "Google releases Android update",
        )

    def test_empty_strings(self):
        assert not _title_similar("", "")
        assert not _title_similar("test", "")
        assert not _title_similar("", "test")

    def test_case_insensitive(self):
        assert _title_similar(
            "BREAKING: Major Tech Merger Announced",
            "breaking: major tech merger announced",
        )


class TestTitleSimilarityChinese:
    def test_similar_chinese_titles(self):
        assert _title_similar(
            "OpenAI 发布 GPT-5 模型，性能大幅提升",
            "OpenAI 发布 GPT-5，性能显著提升",
        )

    def test_dissimilar_chinese_titles(self):
        assert not _title_similar(
            "苹果发布新款 iPhone",
            "谷歌推出安卓更新",
        )

    def test_mixed_cjk_english(self):
        assert _title_similar(
            "特斯拉 Tesla 发布自动驾驶更新",
            "特斯拉 Tesla 发布自动驾驶新版本",
        )

    def test_pure_chinese_different_topics(self):
        assert not _title_similar(
            "今日股市大涨百点",
            "明天天气预报晴朗",
        )


class TestTitleSimilarityEdgeCases:
    def test_single_word(self):
        assert _title_similar("test", "test")

    def test_threshold_boundary(self):
        assert not _title_similar("a b c d e", "a f g h i")

    def test_very_long_titles(self):
        base = "This is a very long title about technology and innovation "
        assert _title_similar(base * 3, base * 3 + "extra words")
