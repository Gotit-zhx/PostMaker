# coding=utf-8
"""
Playwright 网页采集器

抓取配置中的自定义网页列表，用于采集无 RSS 的站点。

风控策略：
- 默认关闭，需在 config.yaml 显式启用
- 每域名最小间隔 10s
- playwright-stealth 隐藏自动化特征
- 随机化 viewport 尺寸和页面停留时间
- 支持代理配置
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from dataradar.storage.base import RSSItem
from dataradar.utils.url_safety import UnsafeURL, validate_public_url

logger = logging.getLogger(__name__)


class PlaywrightScraper:
    """Playwright 网页采集器，抓取配置中的自定义网页列表。"""

    def __init__(
        self,
        scraper_config: Dict[str, Any],
        proxy_url: Optional[str] = None,
        ai_client=None,
    ):
        self.targets = scraper_config.get("TARGETS", [])
        self.proxy_url = proxy_url
        self.timeout = scraper_config.get("TIMEOUT", 30000)
        self.min_domain_interval = scraper_config.get("MIN_DOMAIN_INTERVAL", 10.0)
        self._last_domain_access: Dict[str, float] = {}
        self._ai_client = ai_client

        try:
            from dataradar.ai.prompt_loader import load_prompt_template
            self._system_prompt, self._user_prompt = load_prompt_template(
                "extract_list_prompt.txt", config_subdir="web_scraper", label="网页提取"
            )
        except Exception:
            self._system_prompt, self._user_prompt = "", ""

    async def fetch_all(self, crawl_time: str = "") -> List[RSSItem]:
        """抓取所有配置的目标网页，返回统一的 RSSItem 格式。"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright 未安装，跳过网页采集")
            return []

        if not self.targets:
            return []

        all_items: List[RSSItem] = []
        async with async_playwright() as p:
            launch_args: Dict[str, Any] = {"headless": True}
            if self.proxy_url:
                launch_args["proxy"] = {"server": self.proxy_url}
            browser = await p.chromium.launch(**launch_args)

            for target in self.targets:
                if not target.get("enabled", True):
                    continue
                try:
                    items = await self._fetch_target(browser, target, crawl_time)
                    all_items.extend(items)
                except Exception as exc:
                    logger.warning("采集 %s 失败: %s", target.get("name", "?"), exc)

            await browser.close()

        logger.info("Playwright 网页采集完成: %d 条", len(all_items))
        return all_items

    async def _fetch_target(self, browser, target: Dict, crawl_time: str) -> List[RSSItem]:
        """抓取单个目标网页。"""
        from urllib.parse import urlparse
        try:
            from playwright_stealth import stealth_async
        except ImportError:
            stealth_async = None

        url = target["url"]
        try:
            url = validate_public_url(url)
        except UnsafeURL as exc:
            raise ValueError(f"不安全的网页采集地址：{exc}") from exc
        domain = urlparse(url).netloc

        # 域名限速
        now = time.monotonic()
        last = self._last_domain_access.get(domain, 0)
        wait = self.min_domain_interval - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)

        # 随机 viewport
        width = random.randint(1280, 1920)
        height = random.randint(800, 1080)
        page = await browser.new_page(viewport={"width": width, "height": height})

        if stealth_async:
            await stealth_async(page)
        await page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
        await asyncio.sleep(random.uniform(2.0, 4.0))

        self._last_domain_access[domain] = time.monotonic()

        items: List[RSSItem] = []
        list_sel = target.get("list_selector", "")
        title_sel = target.get("title_selector", "")
        link_sel = target.get("link_selector", "")
        max_items = target.get("max_items", 30)

        if list_sel and title_sel:
            entries = await page.query_selector_all(list_sel)
            for entry in entries[:max_items]:
                try:
                    title_el = await entry.query_selector(title_sel)
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    link_el = await entry.query_selector(link_sel) if link_sel else title_el
                    href = await link_el.get_attribute("href") if link_el else ""
                    full_url = urljoin(url, href) if href else ""
                    if full_url:
                        try:
                            full_url = validate_public_url(full_url)
                        except UnsafeURL:
                            full_url = ""
                    if title:
                        items.append(RSSItem(
                            title=title,
                            feed_id=f"web-{target['id']}",
                            feed_name=target.get("name", target["id"]),
                            url=full_url,
                            crawl_time=crawl_time,
                        ))
                except Exception:
                    continue
        elif self._ai_client and self._system_prompt:
            html = await page.content()
            truncated = html[:15000]
            prompt = self._user_prompt.format(
                base_url=url,
                page_type=target.get("name", "unknown"),
                html_content=truncated,
            )
            try:
                result = self._ai_client.chat(
                    [{"role": "system", "content": self._system_prompt},
                     {"role": "user", "content": prompt}],
                    max_tokens=2000,
                )
                parsed = json.loads(result)
                for entry in parsed[:max_items]:
                    if entry.get("title"):
                        items.append(RSSItem(
                            title=entry["title"],
                            feed_id=f"web-{target['id']}",
                            feed_name=target.get("name", target["id"]),
                            url=(validate_public_url(urljoin(url, entry.get("url", "")))
                                 if entry.get("url") else url),
                            summary=entry.get("summary", ""),
                            published_at=entry.get("published_date", ""),
                            crawl_time=crawl_time,
                        ))
            except Exception as exc:
                logger.debug("AI 提取失败 %s: %s", target.get("name"), exc)

        await page.close()
        return items
