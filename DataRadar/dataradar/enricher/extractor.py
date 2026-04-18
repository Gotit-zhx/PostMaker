"""
三引擎文章提取器。

引擎优先级：
1. Trafilatura（本地，免费，零风控风险，处理 ~80% 静态页面）
2. Playwright（JS 渲染回退，共享浏览器实例）
3. Jina Reader API（云端兜底，带频率限制）

三阶段并行架构：
- 阶段 1: 所有 URL 并发 Trafilatura 提取（10 并发）
- 阶段 2: 失败的 URL 用共享浏览器 Playwright 回退
- 阶段 3: 仍失败的 URL 并发 Jina API 兜底
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import requests as _requests
import urllib3

logger = logging.getLogger(__name__)

_MIN_TEXT_LENGTH = 200
_JINA_BASE = "https://r.jina.ai"
_TRAFILATURA_CONCURRENCY = 20
_JINA_CONCURRENCY = 5


@dataclass
class ExtractResult:
    url: str
    text: str
    images: List[str] = field(default_factory=list)
    method: str = "none"
    word_count: int = 0


def _extract_images_from_markdown(text: str) -> List[str]:
    pattern = r'!\[[^\]]*\]\((https?://[^)]+)\)'
    return re.findall(pattern, text)


def _sync_download_html(url: str, proxy_url: str = "", timeout: int = 20) -> Optional[str]:
    try:
        kwargs: Dict = {"timeout": timeout, "headers": {"User-Agent": "DataRadar/1.0"}}
        if proxy_url:
            kwargs["proxies"] = {"http": proxy_url, "https": proxy_url}
            kwargs["verify"] = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = _requests.get(url, **kwargs)
        if resp.status_code == 200:
            return resp.text
        return None
    except (_requests.RequestException, OSError, urllib3.exceptions.HTTPError) as exc:
        logger.debug("下载 %s 失败: %s", url, exc)
        return None


def _sync_trafilatura_extract(url: str, proxy_url: str = "") -> Optional[str]:
    try:
        import trafilatura
    except ImportError:
        return None

    try:
        html = _sync_download_html(url, proxy_url=proxy_url)
        if not html:
            return None
        text = trafilatura.extract(
            html,
            include_images=True,
            output_format="markdown",
            favor_precision=True,
        )
        return text if text and len(text) >= _MIN_TEXT_LENGTH else None
    except (ValueError, TypeError, OSError) as exc:
        logger.debug("Trafilatura 处理 %s 失败: %s", url, exc)
        return None


class ArticleExtractor:
    """三引擎文章提取器：Trafilatura → Playwright → Jina Reader"""

    def __init__(
        self,
        jina_api_key: Optional[str] = None,
        rate_limit_per_min: int = 10,
        use_playwright: bool = True,
        proxy_url: str = "",
    ):
        self._jina_key = jina_api_key or ""
        self._use_playwright = use_playwright
        self._proxy_url = proxy_url
        self._jina_semaphore = asyncio.Semaphore(_JINA_CONCURRENCY)
        self._jina_min_interval = 60.0 / max(rate_limit_per_min, 1)
        self._last_jina_call: float = 0.0

    async def extract(self, url: str) -> ExtractResult:
        """提取单个 URL（三引擎串行回退）。"""
        if not url or not url.startswith("http"):
            return ExtractResult(url=url, text="", method="failed")

        text = await asyncio.to_thread(_sync_trafilatura_extract, url, self._proxy_url)
        if text:
            return self._build_result(url, text, "trafilatura")

        if self._use_playwright:
            text = await self._playwright_extract_single(url)
            if text:
                return self._build_result(url, text, "playwright")

        return await self._jina_extract(url)

    async def extract_many(
        self,
        urls: List[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, ExtractResult]:
        """
        批量提取：三阶段并行架构。

        阶段 1: 并发 Trafilatura（10 并发线程）
        阶段 2: 失败 URL 用共享 Playwright 浏览器回退
        阶段 3: 剩余失败用并发 Jina API 兜底
        """
        results: Dict[str, ExtractResult] = {}
        if not urls:
            return results

        valid_urls = [u for u in urls if u and u.startswith("http")]
        done_count = 0
        total = len(valid_urls)

        def report(method: str):
            nonlocal done_count
            done_count += 1
            if progress_callback and done_count % 20 == 0:
                progress_callback(done_count, total, method)

        # ── 阶段 1: 并发 Trafilatura ──
        sem = asyncio.Semaphore(_TRAFILATURA_CONCURRENCY)

        async def phase1(url: str):
            async with sem:
                text = await asyncio.to_thread(_sync_trafilatura_extract, url, self._proxy_url)
            if text:
                results[url] = self._build_result(url, text, "trafilatura")
                report("trafilatura")

        await asyncio.gather(*[phase1(u) for u in valid_urls])

        failed_urls = [u for u in valid_urls if u not in results]
        if not failed_urls:
            if progress_callback:
                progress_callback(total, total, "trafilatura")
            return results

        # ── 阶段 2: 共享 Playwright 浏览器 ──
        if self._use_playwright and failed_urls:
            pw_results = await self._playwright_extract_batch(failed_urls)
            for url, text in pw_results.items():
                if text:
                    results[url] = self._build_result(url, text, "playwright")
                    report("playwright")
            failed_urls = [u for u in failed_urls if u not in results]

        # ── 阶段 3: 并发 Jina API ──
        if failed_urls:
            async def phase3(url: str):
                r = await self._jina_extract(url)
                results[url] = r
                report("jina" if r.text else "failed")

            await asyncio.gather(*[phase3(u) for u in failed_urls])

        if progress_callback:
            progress_callback(total, total, "done")
        return results

    def _build_result(self, url: str, text: str, method: str) -> ExtractResult:
        images = _extract_images_from_markdown(text)
        return ExtractResult(
            url=url, text=text, images=images,
            method=method, word_count=len(text.split()),
        )

    # ── Playwright ──

    async def _playwright_extract_single(self, url: str) -> Optional[str]:
        """单 URL Playwright 提取（用于 extract() 单条调用）。"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None
        try:
            async with async_playwright() as p:
                launch_args = {"headless": True}
                if self._proxy_url:
                    launch_args["proxy"] = {"server": self._proxy_url}
                browser = await p.chromium.launch(**launch_args)
                page = await browser.new_page()
                await page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                html = await page.content()
                await browser.close()
            return self._extract_from_html(html)
        except (TimeoutError, OSError, RuntimeError) as exc:
            logger.debug("Playwright 处理 %s 失败: %s", url, exc)
            return None
        except Exception as exc:
            logger.warning("Playwright 处理 %s 未知错误: %s", url, exc)
            return None

    async def _playwright_extract_batch(self, urls: List[str]) -> Dict[str, Optional[str]]:
        """共享浏览器实例批量 Playwright 提取。"""
        results: Dict[str, Optional[str]] = {}
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return results

        try:
            stealth_async = None
            try:
                from playwright_stealth import stealth_async
            except ImportError:
                pass

            async with async_playwright() as p:
                launch_args = {"headless": True}
                if self._proxy_url:
                    launch_args["proxy"] = {"server": self._proxy_url}
                browser = await p.chromium.launch(**launch_args)

                sem = asyncio.Semaphore(3)

                async def fetch_page(url: str):
                    async with sem:
                        try:
                            page = await browser.new_page()
                            if stealth_async:
                                await stealth_async(page)
                            await page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
                            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                            html = await page.content()
                            await page.close()
                            results[url] = self._extract_from_html(html)
                        except Exception as exc:
                            logger.debug("Playwright 处理 %s 失败: %s", url, exc)
                            results[url] = None

                await asyncio.gather(*[fetch_page(u) for u in urls])
                await browser.close()

        except Exception as exc:
            logger.debug("Playwright 批量处理失败: %s", exc)

        return results

    @staticmethod
    def _extract_from_html(html: str) -> Optional[str]:
        try:
            import trafilatura
            text = trafilatura.extract(
                html, output_format="markdown",
                include_images=True, favor_precision=True,
            )
            return text if text and len(text) >= _MIN_TEXT_LENGTH else None
        except Exception:
            return None

    # ── Jina Reader API ──

    async def _jina_extract(self, url: str) -> ExtractResult:
        import httpx

        async with self._jina_semaphore:
            now = time.monotonic()
            wait = self._jina_min_interval - (now - self._last_jina_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_jina_call = time.monotonic()

            jina_url = f"{_JINA_BASE}/{url}"
            headers = {
                "Accept": "application/json",
                "X-Return-Format": "markdown",
            }
            if self._jina_key:
                headers["Authorization"] = f"Bearer {self._jina_key}"

            try:
                client_kwargs: Dict = {"timeout": 30.0}
                if self._proxy_url:
                    client_kwargs["proxy"] = self._proxy_url
                    client_kwargs["verify"] = False
                async with httpx.AsyncClient(**client_kwargs) as client:
                    resp = await client.get(jina_url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()

                text: str = data.get("data", {}).get("content", "") or ""
                if not text:
                    return ExtractResult(url=url, text="", method="failed")

                return self._build_result(url, text, "jina")

            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as exc:
                logger.debug("Jina 处理 %s 失败: %s", url, exc)
                return ExtractResult(url=url, text="", method="failed")
            except Exception as exc:
                logger.warning("Jina 处理 %s 未知错误: %s", url, exc)
                return ExtractResult(url=url, text="", method="failed")
