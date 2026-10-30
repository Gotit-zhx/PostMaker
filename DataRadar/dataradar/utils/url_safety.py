"""Public URL validation helpers for user-configured fetch targets.

These checks reduce SSRF exposure when a hosted instance fetches user supplied
RSS and article URLs. They deliberately reject private, loopback, link-local,
reserved and non-routable destinations.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urljoin, urlsplit


class UnsafeURL(ValueError):
    """Raised when a URL does not point to a public HTTP(S) destination."""


def _rsshub_base_urls() -> tuple[str, ...]:
    value = os.getenv("RSSHUB_BASE_URL", "").strip()
    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


def _is_trusted_rsshub_url(url: str, base_urls: tuple[str, ...]) -> bool:
    if not base_urls:
        return False
    try:
        candidate = urlsplit(url)
    except ValueError:
        return False
    if candidate.username or candidate.password or not candidate.hostname:
        return False
    candidate_base = f"{candidate.scheme.lower()}://{candidate.netloc.lower()}"
    for base in base_urls:
        parsed_base = urlsplit(base)
        if parsed_base.scheme.lower() != candidate.scheme.lower():
            continue
        if parsed_base.netloc.lower() != candidate_base.split("://", 1)[1]:
            continue
        base_path = parsed_base.path.rstrip("/")
        if not base_path or candidate.path == base_path or candidate.path.startswith(f"{base_path}/"):
            return True
    return False


def validate_public_url(
    url: str,
    *,
    resolver=socket.getaddrinfo,
) -> str:
    """Return a normalized URL only if its host resolves exclusively publicly."""
    value = (url or "").strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeURL("URL 格式无效") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURL("仅支持 http:// 或 https:// 地址")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeURL("URL 必须包含公开主机名，且不能包含用户名或密码")
    if port not in (None, 80, 443):
        raise UnsafeURL("为保护服务器安全，仅允许 HTTP/HTTPS 默认端口")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost"} or hostname.endswith((".localhost", ".local", ".internal")):
        raise UnsafeURL("不能使用本机或内部网络地址")

    try:
        literal = ipaddress.ip_address(hostname)
        addresses = [literal]
    except ValueError:
        try:
            records = resolver(hostname, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except (OSError, socket.gaierror) as exc:
            raise UnsafeURL("无法解析该主机名") from exc
        addresses = []
        for record in records:
            try:
                addresses.append(ipaddress.ip_address(record[4][0].split("%", 1)[0]))
            except (ValueError, IndexError, TypeError):
                continue

    if not addresses or any(not address.is_global for address in addresses):
        raise UnsafeURL("数据源必须指向可公开访问的互联网地址")
    return value


def validate_rss_url(
    url: str,
    *,
    resolver=socket.getaddrinfo,
) -> str:
    """Validate a feed URL, allowing only the explicitly configured RSSHub base."""
    value = (url or "").strip()
    if _is_trusted_rsshub_url(value, _rsshub_base_urls()):
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or parsed.username or parsed.password:
            raise UnsafeURL("RSSHub 地址格式无效")
        return value
    return validate_public_url(value, resolver=resolver)


def validate_redirect(
    base_url: str,
    location: str,
    *,
    resolver=socket.getaddrinfo,
) -> str:
    """Resolve relative redirects and apply the same public destination policy."""
    return validate_public_url(urljoin(base_url, location), resolver=resolver)


def validate_rss_redirect(
    base_url: str,
    location: str,
    *,
    resolver=socket.getaddrinfo,
) -> str:
    """Resolve a feed redirect while preserving the RSSHub allowlist."""
    return validate_rss_url(urljoin(base_url, location), resolver=resolver)
