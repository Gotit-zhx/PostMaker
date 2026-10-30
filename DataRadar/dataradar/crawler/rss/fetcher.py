# coding=utf-8
"""
RSS 抓取器

负责从配置的 RSS 源抓取数据并转换为标准格式
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import httpx

from .parser import RSSParser
from dataradar.storage.base import RSSItem, RSSData
from dataradar.utils.time import get_configured_time, is_within_days, DEFAULT_TIMEZONE
from dataradar.utils.url_safety import UnsafeURL, validate_public_url, validate_redirect

logger = logging.getLogger(__name__)


@dataclass
class RSSFeedConfig:
    """RSS 源配置"""
    id: str                     # 源 ID
    name: str                   # 显示名称
    url: str                    # RSS URL
    max_items: int = 0          # 最大条目数（0=不限制）
    enabled: bool = True        # 是否启用
    max_age_days: Optional[int] = None  # 文章最大年龄（天），覆盖全局设置；None=使用全局，0=禁用过滤


class RSSFetcher:
    """RSS 抓取器"""

    def __init__(
        self,
        feeds: List[RSSFeedConfig],
        request_interval: int = 2000,
        timeout: int = 15,
        use_proxy: bool = False,
        proxy_url: str = "",
        timezone: str = DEFAULT_TIMEZONE,
        freshness_enabled: bool = True,
        default_max_age_days: int = 3,
    ):
        """
        初始化抓取器

        Args:
            feeds: RSS 源配置列表
            request_interval: 请求间隔（毫秒）
            timeout: 请求超时（秒）
            use_proxy: 是否使用代理
            proxy_url: 代理 URL
            timezone: 时区配置（如 'Asia/Shanghai'）
            freshness_enabled: 是否启用新鲜度过滤
            default_max_age_days: 默认最大文章年龄（天）
        """
        self.feeds = [f for f in feeds if f.enabled]
        self.request_interval = request_interval
        self.timeout = timeout
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        self.timezone = timezone
        self.freshness_enabled = freshness_enabled
        self.default_max_age_days = default_max_age_days

        self.parser = RSSParser()

        # httpx client config
        self._headers = {
            "User-Agent": "DataRadar/1.0 RSS Reader",
            "Accept": "application/feed+json, application/json, application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def _filter_by_freshness(
        self,
        items: List[RSSItem],
        feed: RSSFeedConfig,
    ) -> Tuple[List[RSSItem], int]:
        """
        根据新鲜度过滤文章

        Args:
            items: 待过滤的文章列表
            feed: RSS 源配置

        Returns:
            (过滤后的文章列表, 被过滤的文章数)
        """
        # 如果全局禁用，直接返回
        if not self.freshness_enabled:
            return items, 0

        # 确定此 feed 的 max_age_days
        max_days = feed.max_age_days
        if max_days is None:
            max_days = self.default_max_age_days

        # 如果设为 0，禁用此 feed 的过滤
        if max_days == 0:
            return items, 0

        # 过滤逻辑：无发布时间的文章保留
        filtered = []
        for item in items:
            if not item.published_at:
                # 无发布时间，保留
                filtered.append(item)
            elif is_within_days(item.published_at, max_days, self.timezone):
                # 在指定天数内，保留
                filtered.append(item)
            # 否则过滤掉

        filtered_count = len(items) - len(filtered)
        return filtered, filtered_count

    async def fetch_feed(self, feed: RSSFeedConfig) -> Tuple[List[RSSItem], Optional[str]]:
        """
        抓取单个 RSS 源

        Args:
            feed: RSS 源配置

        Returns:
            (条目列表, 错误信息) 元组
        """
        try:
            proxy_config = {}
            if self.use_proxy and self.proxy_url:
                proxy_config = {"proxy": self.proxy_url}

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                verify=False if (self.use_proxy and self.proxy_url) else True,
                headers=self._headers,
                follow_redirects=False,
                **proxy_config,
            ) as client:
                current_url = feed.url
                for redirect_count in range(6):
                    current_url = await asyncio.to_thread(validate_public_url, current_url)
                    response = await client.get(current_url)
                    if response.status_code not in {301, 302, 303, 307, 308}:
                        break
                    location = response.headers.get("location")
                    if not location:
                        response.raise_for_status()
                    if redirect_count == 5:
                        raise ValueError("RSS 地址重定向次数过多")
                    current_url = await asyncio.to_thread(validate_redirect, current_url, location)
                response.raise_for_status()

            parsed_items = await asyncio.to_thread(self.parser.parse, response.text, current_url)

            # 限制条目数量（0=不限制）
            if feed.max_items > 0:
                parsed_items = parsed_items[:feed.max_items]

            # 转换为 RSSItem（使用配置的时区）
            now = get_configured_time(self.timezone)
            crawl_time = now.strftime("%H:%M")
            items = []

            for parsed in parsed_items:
                item = RSSItem(
                    title=parsed.title,
                    feed_id=feed.id,
                    feed_name=feed.name,
                    url=parsed.url,
                    published_at=parsed.published_at or "",
                    summary=parsed.summary or "",
                    author=parsed.author or "",
                    content_type=parsed.content_type or "text",
                    enclosure_url=parsed.enclosure_url or "",
                    enclosure_type=parsed.enclosure_type or "",
                    enclosure_length=parsed.enclosure_length or 0,
                    thumbnail_url=parsed.thumbnail_url or "",
                    duration_sec=parsed.duration_sec or 0,
                    crawl_time=crawl_time,
                    first_time=crawl_time,
                    last_time=crawl_time,
                    count=1,
                )
                items.append(item)

            # 注意：新鲜度过滤已移至推送阶段（_convert_rss_items_to_list）
            # 这样所有文章都会存入数据库，但旧文章不会推送
            logger.info("[RSS] %s: 获取 %d 条", feed.name, len(items))
            return items, None

        except httpx.TimeoutException:
            error = f"请求超时 ({self.timeout}s)"
            logger.warning("[RSS] %s: %s", feed.name, error)
            return [], error

        except httpx.HTTPError as e:
            error = f"请求失败: {e}"
            logger.warning("[RSS] %s: %s", feed.name, error)
            return [], error

        except UnsafeURL as e:
            error = f"不安全的 RSS 地址: {e}"
            logger.warning("[RSS] %s: %s", feed.name, error)
            return [], error

        except ValueError as e:
            error = f"解析失败: {e}"
            logger.warning("[RSS] %s: %s", feed.name, error)
            return [], error

        except Exception as e:
            error = f"未知错误: {e}"
            logger.warning("[RSS] %s: %s", feed.name, error)
            return [], error

    async def fetch_all(self) -> RSSData:
        """
        抓取所有 RSS 源

        Returns:
            RSSData 对象
        """
        all_items: Dict[str, List[RSSItem]] = {}
        id_to_name: Dict[str, str] = {}
        failed_ids: List[str] = []

        # 使用配置的时区
        now = get_configured_time(self.timezone)
        crawl_time = now.strftime("%H:%M")
        crawl_date = now.strftime("%Y-%m-%d")

        logger.info("[RSS] 开始抓取 %d 个 RSS 源...", len(self.feeds))

        sem = asyncio.Semaphore(5)

        async def _fetch_one(feed: RSSFeedConfig):
            async with sem:
                if all_items or failed_ids:  # throttle between requests
                    interval = self.request_interval / 1000
                    jitter = random.uniform(-0.2, 0.2) * interval
                    await asyncio.sleep(interval + jitter)
                return await self.fetch_feed(feed)

        tasks = [_fetch_one(feed) for feed in self.feeds]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        for feed, result in zip(self.feeds, raw_results):
            id_to_name[feed.id] = feed.name

            if isinstance(result, Exception):
                logger.warning("[RSS] %s: 未知错误: %s", feed.name, result)
                failed_ids.append(feed.id)
            else:
                items, error = result
                if error:
                    failed_ids.append(feed.id)
                else:
                    all_items[feed.id] = items

        total_items = sum(len(items) for items in all_items.values())
        logger.info("[RSS] 抓取完成: %d 个源成功, %d 个失败, 共 %d 条", len(all_items), len(failed_ids), total_items)

        return RSSData(
            date=crawl_date,
            crawl_time=crawl_time,
            items=all_items,
            id_to_name=id_to_name,
            failed_ids=failed_ids,
        )

    @classmethod
    def from_config(cls, config: Dict) -> "RSSFetcher":
        """
        从配置字典创建抓取器

        Args:
            config: 配置字典，格式如下：
                {
                    "enabled": true,
                    "request_interval": 2000,
                    "freshness_filter": {
                        "enabled": true,
                        "max_age_days": 3
                    },
                    "feeds": [
                        {"id": "hacker-news", "name": "Hacker News", "url": "...", "max_age_days": 1}
                    ]
                }

        Returns:
            RSSFetcher 实例
        """
        # 读取新鲜度过滤配置
        freshness_config = config.get("freshness_filter", {})
        freshness_enabled = freshness_config.get("enabled", True)  # 默认启用
        default_max_age_days = freshness_config.get("max_age_days", 3)  # 默认3天

        feeds = []
        for feed_config in config.get("feeds", []):
            # 读取并验证单个 feed 的 max_age_days（可选）
            max_age_days_raw = feed_config.get("max_age_days")
            max_age_days = None
            if max_age_days_raw is not None:
                try:
                    max_age_days = int(max_age_days_raw)
                    if max_age_days < 0:
                        feed_id = feed_config.get("id", "unknown")
                        logger.warning("RSS feed '%s' 的 max_age_days 为负数，将使用全局默认值", feed_id)
                        max_age_days = None
                except (ValueError, TypeError):
                    feed_id = feed_config.get("id", "unknown")
                    logger.warning("RSS feed '%s' 的 max_age_days 格式错误：%s", feed_id, max_age_days_raw)
                    max_age_days = None

            feed = RSSFeedConfig(
                id=feed_config.get("id", ""),
                name=feed_config.get("name", ""),
                url=feed_config.get("url", ""),
                max_items=feed_config.get("max_items", 0),  # 0=不限制
                enabled=feed_config.get("enabled", True),
                max_age_days=max_age_days,  # None=使用全局，0=禁用，>0=覆盖
            )
            if feed.id and feed.url:
                feeds.append(feed)

        return cls(
            feeds=feeds,
            request_interval=config.get("request_interval", 2000),
            timeout=config.get("timeout", 15),
            use_proxy=config.get("use_proxy", False),
            proxy_url=config.get("proxy_url", ""),
            timezone=config.get("timezone", DEFAULT_TIMEZONE),
            freshness_enabled=freshness_enabled,
            default_max_age_days=default_max_age_days,
        )
