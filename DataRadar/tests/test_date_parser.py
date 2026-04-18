"""Tests for date parsing utilities."""

import sys
import os
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataradar.utils.date_parser import DateParser
from dataradar.utils.errors import InvalidParameterError


class TestParseDateQuery:
    def test_today_cn(self):
        result = DateParser.parse_date_query("今天")
        assert result.date() == datetime.now().date()

    def test_yesterday_cn(self):
        result = DateParser.parse_date_query("昨天")
        expected = (datetime.now() - timedelta(days=1)).date()
        assert result.date() == expected

    def test_today_en(self):
        result = DateParser.parse_date_query("today")
        assert result.date() == datetime.now().date()

    def test_yesterday_en(self):
        result = DateParser.parse_date_query("yesterday")
        expected = (datetime.now() - timedelta(days=1)).date()
        assert result.date() == expected

    def test_days_ago_cn(self):
        result = DateParser.parse_date_query("3天前")
        expected = (datetime.now() - timedelta(days=3)).date()
        assert result.date() == expected

    def test_days_ago_en(self):
        result = DateParser.parse_date_query("5 days ago")
        expected = (datetime.now() - timedelta(days=5)).date()
        assert result.date() == expected

    def test_iso_date(self):
        result = DateParser.parse_date_query("2025-06-15")
        assert result.date() == datetime(2025, 6, 15).date()

    def test_chinese_date(self):
        result = DateParser.parse_date_query("2025年6月15日")
        assert result.date() == datetime(2025, 6, 15).date()

    def test_slash_date(self):
        result = DateParser.parse_date_query("2025/6/15")
        assert result.date() == datetime(2025, 6, 15).date()

    def test_empty_raises(self):
        with pytest.raises(InvalidParameterError):
            DateParser.parse_date_query("")

    def test_invalid_format_raises(self):
        with pytest.raises(InvalidParameterError):
            DateParser.parse_date_query("not-a-date")

    def test_too_many_days_ago_raises(self):
        with pytest.raises(InvalidParameterError):
            DateParser.parse_date_query("500天前")

    def test_case_insensitive(self):
        result = DateParser.parse_date_query("TODAY")
        assert result.date() == datetime.now().date()


class TestDateRangeExpression:
    def test_today_range(self):
        result = DateParser.resolve_date_range_expression("今天")
        assert result["success"] is True
        today_str = datetime.now().strftime("%Y-%m-%d")
        assert result["date_range"]["start"] == today_str
        assert result["date_range"]["end"] == today_str

    def test_last_7_days(self):
        result = DateParser.resolve_date_range_expression("最近7天")
        assert result["success"] is True
        start = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        assert result["date_range"]["start"] == start

    def test_this_week_en(self):
        result = DateParser.resolve_date_range_expression("this week")
        assert result["success"] is True

    def test_invalid_expression_raises(self):
        with pytest.raises(InvalidParameterError):
            DateParser.resolve_date_range_expression("invalid expression")


class TestValidations:
    def test_future_date_raises(self):
        future = datetime.now() + timedelta(days=10)
        with pytest.raises(InvalidParameterError):
            DateParser.validate_date_not_future(future)

    def test_today_does_not_raise(self):
        DateParser.validate_date_not_future(datetime.now())

    def test_too_old_raises(self):
        old_date = datetime.now() - timedelta(days=400)
        with pytest.raises(InvalidParameterError):
            DateParser.validate_date_not_too_old(old_date)
