"""Public-fetch URL validation and redirect policy tests."""

import socket

import pytest

from dataradar.utils.url_safety import UnsafeURL, validate_public_url, validate_redirect


def _public_dns(host, port, *, type):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def _private_dns(host, port, *, type):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port))]


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/feed.xml",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/feed.xml",
    "http://localhost/feed.xml",
    "http://user:pass@example.com/feed.xml",
    "http://example.com:8080/feed.xml",
    "file:///etc/passwd",
])
def test_rejects_non_public_or_unsupported_urls(url):
    with pytest.raises(UnsafeURL):
        validate_public_url(url, resolver=_public_dns)


def test_rejects_hostname_resolving_to_private_network():
    with pytest.raises(UnsafeURL, match="公开访问"):
        validate_public_url("https://feed.example/feed.xml", resolver=_private_dns)


def test_accepts_public_hostname():
    assert validate_public_url("https://feed.example/feed.xml", resolver=_public_dns) == "https://feed.example/feed.xml"


def test_redirect_cannot_escape_to_private_network():
    with pytest.raises(UnsafeURL):
        validate_redirect("https://feed.example/rss", "http://127.0.0.1/admin", resolver=_public_dns)


def test_relative_redirect_is_resolved_and_checked():
    assert validate_redirect("https://feed.example/rss", "/new-feed", resolver=_public_dns) == "https://feed.example/new-feed"
