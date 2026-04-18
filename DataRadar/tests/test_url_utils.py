"""Tests for URL normalization utilities."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataradar.utils.url import normalize_url


class TestNormalizeUrl:
    def test_no_params(self):
        url = "https://example.com/article/123"
        assert normalize_url(url) == url

    def test_remove_utm_params(self):
        url = "https://example.com/page?id=1&utm_source=twitter&utm_medium=social"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=1" in result

    def test_remove_weibo_params(self):
        url = "https://s.weibo.com/weibo?q=test&band_rank=6&Refer=top"
        result = normalize_url(url, "weibo")
        assert "q=test" in result
        assert "band_rank" not in result
        assert "Refer" not in result

    def test_preserve_essential_params(self):
        url = "https://example.com/search?q=python&page=2"
        result = normalize_url(url)
        assert "q=python" in result
        assert "page=2" in result

    def test_empty_url(self):
        assert normalize_url("") == ""

    def test_sorted_params(self):
        url = "https://example.com/page?z=1&a=2&m=3"
        result = normalize_url(url)
        assert result == "https://example.com/page?a=2&m=3&z=1"

    def test_remove_fragment(self):
        url = "https://example.com/page?id=1#section"
        result = normalize_url(url)
        assert "#" not in result

    def test_all_params_removed(self):
        url = "https://example.com/page?utm_source=x&ref=y"
        result = normalize_url(url)
        assert result == "https://example.com/page"

    def test_unknown_platform(self):
        url = "https://example.com/page?q=test&ref=home"
        result = normalize_url(url, "unknown_platform")
        assert "q=test" in result
        assert "ref" not in result
