# coding=utf-8
"""
DataRadar 数据采集器

流程: RSS 全量采集 → Playwright 网页采集(可选) → 全文提取 → AI 摘要 → PostgreSQL 直写 → 后处理
"""

import asyncio
import logging
from typing import Dict, List, Optional

from dataradar.context import AppContext
from dataradar.storage.base import RSSItem, RSSData
from dataradar.utils.time import DEFAULT_TIMEZONE

logger = logging.getLogger(__name__)

logging.getLogger("trafilatura").setLevel(logging.ERROR)
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)


class DataCollector:
    """数据采集器：RSS + 网页 → 全文提取 → AI 摘要 → PostgreSQL"""

    def __init__(self, config: Dict):
        self.config = config
        self.ctx = AppContext(config)
        self.storage_manager = self.ctx.get_storage_manager()
        self.debug = config.get("DEBUG", False)

        kb_cfg = config.get("KNOWLEDGE_BASE", {})
        enrich_cfg = kb_cfg.get("ENRICHER", {})
        rss_cfg = config.get("RSS", {})
        proxy_url = rss_cfg.get("PROXY_URL", "") if rss_cfg.get("USE_PROXY", False) else ""
        from dataradar.enricher.extractor import ArticleExtractor
        self.extractor = ArticleExtractor(
            jina_api_key=enrich_cfg.get("JINA_API_KEY", ""),
            rate_limit_per_min=int(enrich_cfg.get("RATE_LIMIT_PER_MIN", 10)),
            use_playwright=enrich_cfg.get("USE_PLAYWRIGHT", True),
            proxy_url=proxy_url,
        )

        summarizer_cfg = kb_cfg.get("SUMMARIZER", {})
        self.summarizer = None
        if summarizer_cfg.get("ENABLED", False):
            from dataradar.ai.summarizer import ContentSummarizer
            self.summarizer = ContentSummarizer(config)

        webhook_cfg = config.get("WEBHOOK", {})
        self.webhook_url = webhook_cfg.get("URL", "")
        self.webhook_enabled = webhook_cfg.get("ENABLED", False) and bool(self.webhook_url)

    async def run(self):
        """运行完整采集管道，并确保任何异常都释放存储资源。"""
        logger.info("=" * 50)
        logger.info("DataRadar 数据采集")
        logger.info("=" * 50)
        await self.storage_manager.init()
        try:
            rss_data = await self._fetch_rss()
            web_items = await self._fetch_web_pages()
            if web_items:
                if rss_data is None:
                    from dataradar.utils.time import get_configured_time
                    now = get_configured_time(self.ctx.timezone)
                    rss_data = RSSData(now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), {}, {})
                for item in web_items:
                    rss_data.items.setdefault(item.feed_id, []).append(item)
                    rss_data.id_to_name.setdefault(item.feed_id, item.feed_name)
            if not rss_data or rss_data.get_total_count() == 0:
                logger.info("[采集] 未获取到任何数据")
                return
            total = rss_data.get_total_count()
            logger.info("[采集] 共获取 %d 条内容", total)
            enrich_cfg = self.config.get("KNOWLEDGE_BASE", {}).get("ENRICHER", {})
            if enrich_cfg.get("ENABLED", False):
                rss_data = await self._enrich_full_text(rss_data)
            if self.summarizer:
                rss_data = await self._generate_summaries(rss_data)
            await self.storage_manager.save_rss_data(rss_data)
            if self.config.get("KNOWLEDGE_BASE", {}).get("EMBEDDING", {}).get("ENABLED", False):
                await self._run_post_processing()
            if self.webhook_enabled:
                await self._notify_webhook("collection_complete", {"total": total})
            logger.info("[完成] 采集管道执行完毕")
        finally:
            await self.storage_manager.close()

    async def _fetch_rss(self) -> Optional[RSSData]:
        if not self.ctx.rss_enabled:
            logger.info("[RSS] 未启用")
            return None

        rss_feeds = self.ctx.rss_feeds
        if not rss_feeds:
            logger.info("[RSS] 未配置任何 RSS 源")
            return None

        from dataradar.crawler.rss import RSSFetcher, RSSFeedConfig

        feeds = []
        for feed_config in rss_feeds:
            feed = RSSFeedConfig(
                id=feed_config.get("id", ""),
                name=feed_config.get("name", ""),
                url=feed_config.get("url", ""),
                max_items=feed_config.get("max_items", 50),
                enabled=feed_config.get("enabled", True),
                max_age_days=0,
            )
            if feed.id and feed.url and feed.enabled:
                feeds.append(feed)

        if not feeds:
            logger.info("[RSS] 没有启用的 RSS 源")
            return None

        logger.info("[RSS] 开始采集 %d 个 RSS 源...", len(feeds))
        rss_config = self.ctx.rss_config
        rss_proxy_url = rss_config.get("PROXY_URL", "") or ""
        timezone = self.config.get("TIMEZONE", DEFAULT_TIMEZONE)

        fetcher = RSSFetcher(
            feeds=feeds,
            request_interval=rss_config.get("REQUEST_INTERVAL", 2000),
            timeout=rss_config.get("TIMEOUT", 15),
            use_proxy=rss_config.get("USE_PROXY", False),
            proxy_url=rss_proxy_url,
            timezone=timezone,
            freshness_enabled=False,
            default_max_age_days=0,
        )

        rss_data = await fetcher.fetch_all()
        total = rss_data.get_total_count() if rss_data else 0
        logger.info("[RSS] 采集完成: %d 条", total)
        return rss_data

    async def _fetch_web_pages(self) -> List[RSSItem]:
        scraper_cfg = self.config.get("WEB_SCRAPER", {})
        if not scraper_cfg.get("ENABLED", False):
            return []

        targets = scraper_cfg.get("TARGETS", [])
        if not targets:
            logger.info("[Web] 未配置采集目标，跳过")
            return []

        from dataradar.crawler.web.scraper import PlaywrightScraper

        ai_client = None
        ai_config = self.config.get("AI", {})
        if ai_config.get("API_KEY"):
            from dataradar.ai.client import AIClient
            ai_client = AIClient(ai_config)

        scraper = PlaywrightScraper(
            scraper_config=scraper_cfg,
            proxy_url=scraper_cfg.get("PROXY_URL", ""),
            ai_client=ai_client,
        )

        crawl_time = self.ctx.format_time()
        logger.info("[Web] 开始 Playwright 网页采集 %d 个目标...", len(targets))
        items = await scraper.fetch_all(crawl_time=crawl_time)
        logger.info("[Web] 采集完成: %d 条", len(items))
        return items

    async def _enrich_full_text(self, rss_data: RSSData) -> RSSData:
        all_items = []
        for feed_id, items in rss_data.items.items():
            for item in items:
                if item.url and not item.full_text:
                    all_items.append(item)

        if not all_items:
            return rss_data

        logger.info("[全文] 开始提取 %d 篇文章全文...", len(all_items))

        def on_progress(done: int, total: int, method: str):
            logger.info("[全文] 进度: %d/%d (%s)", done, total, method)

        url_to_items = {}
        for item in all_items:
            url_to_items.setdefault(item.url, []).append(item)

        results = await self.extractor.extract_many(
            list(url_to_items.keys()),
            progress_callback=on_progress,
        )

        count = 0
        for url, result in results.items():
            if result.text:
                for item in url_to_items.get(url, []):
                    item.full_text = result.text
                count += 1

        methods = {}
        for r in results.values():
            methods[r.method] = methods.get(r.method, 0) + 1
        stats = ", ".join(f"{m}: {c}" for m, c in sorted(methods.items()))
        logger.info("[全文] 提取完成: %d/%d 篇成功 (%s)", count, len(results), stats)
        return rss_data

    async def _generate_summaries(self, rss_data: RSSData) -> RSSData:
        all_items = []
        for items in rss_data.items.values():
            all_items.extend(items)

        items_to_summarize = [i for i in all_items if not i.ai_summary]
        if not items_to_summarize:
            return rss_data

        logger.info("[摘要] 开始生成 %d 条 AI 摘要...", len(items_to_summarize))
        await self.summarizer.summarize_items(items_to_summarize)
        summarized = sum(1 for i in items_to_summarize if i.ai_summary)
        logger.info("[摘要] 生成完成: %d/%d 条", summarized, len(items_to_summarize))
        return rss_data

    async def _run_post_processing(self):
        """后处理：embedding 生成 + 知识聚合。"""
        logger.info("[后处理] 开始 embedding + 聚合...")
        try:
            from knowledge_base.etl.pipeline import ETLPipeline

            pipeline = ETLPipeline.from_config(self.config)
            date_str = self.ctx.format_date()
            stats = await pipeline.run(date_str)
            logger.info("[后处理] 完成: %s", stats)
        except ImportError as e:
            logger.warning("[后处理] 缺少依赖: %s", e)
        except Exception as e:
            logger.error("[后处理] 失败: %s", e, exc_info=True)

    async def _notify_webhook(self, event: str, data: dict):
        """采集完成 Webhook 通知。"""
        if not self.webhook_enabled:
            return
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                payload = {"event": event, "data": data}
                resp = await client.post(self.webhook_url, json=payload)
                logger.info("[Webhook] POST %s → %d", self.webhook_url, resp.status_code)
        except Exception as e:
            logger.warning("[Webhook] 通知失败: %s", e)

    def show_status(self):
        logger.info("=" * 50)
        logger.info("DataRadar 状态")
        logger.info("=" * 50)
        logger.info("时区: %s", self.ctx.timezone)
        logger.info("当前时间: %s", self.ctx.get_time_display())
        logger.info("RSS 启用: %s", self.ctx.rss_enabled)
        logger.info("RSS 源数: %d", len(self.ctx.rss_feeds))

        kb_cfg = self.config.get("KNOWLEDGE_BASE", {})
        logger.info("知识库启用: %s", kb_cfg.get('ENABLED', False))
        logger.info("全文提取启用: %s", kb_cfg.get('ENRICHER', {}).get('ENABLED', False))
        logger.info("AI 摘要启用: %s", kb_cfg.get('SUMMARIZER', {}).get('ENABLED', False))

        scraper_cfg = self.config.get("WEB_SCRAPER", {})
        logger.info("Playwright 网页采集: %s", scraper_cfg.get('ENABLED', False))

        logger.info("存储后端: %s", self.storage_manager.backend_name)
