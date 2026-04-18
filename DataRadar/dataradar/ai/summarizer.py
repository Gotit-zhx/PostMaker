# coding=utf-8
"""
AI 内容摘要 + 结构化分析生成器

使用 LLM 为 RSS 内容生成结构化 JSON：summary、category、tags、importance。
"""

import asyncio
import logging
from typing import Any, Dict, List

import json_repair

from dataradar.ai.client import AIClient
from dataradar.ai.prompt_loader import load_prompt_template
from dataradar.storage.base import RSSItem

logger = logging.getLogger(__name__)

_SUMMARY_CONCURRENCY = 10

_VALID_CATEGORIES = {
    "AI", "云计算", "开源", "网络安全", "商业", "硬件", "开发工具", "其他",
}


class ContentSummarizer:
    """使用 LLM 为内容生成结构化摘要（summary + category + tags + importance）。"""

    def __init__(self, config: Dict[str, Any]):
        ai_config = config.get("AI", {})
        summarizer_config = config.get("KNOWLEDGE_BASE", {}).get("SUMMARIZER", {})
        self.client = AIClient(ai_config)
        self.batch_size = summarizer_config.get("BATCH_SIZE", 20)
        self.max_tokens = summarizer_config.get("MAX_TOKENS", 500)
        self.skip_if_exists = summarizer_config.get("SKIP_IF_EXISTS", True)
        self.system_prompt, self.user_prompt_template = load_prompt_template(
            "summarize_prompt.txt", config_subdir="etl", label="摘要"
        )

    def _should_skip(self, item: RSSItem) -> bool:
        if len(item.title or "") < 10:
            if item.summary:
                item.ai_summary = item.summary
            return True
        if item.summary and len(item.summary) > 200 and not item.full_text:
            item.ai_summary = item.summary
            return True
        return False

    def _prepare_content(self, item: RSSItem) -> str:
        text = item.full_text or item.summary or ""
        if len(text) <= 1500:
            return text
        paragraphs = text.split("\n\n")
        if len(paragraphs) <= 3:
            return text[:1500]
        head = "\n\n".join(paragraphs[:2])
        tail = paragraphs[-1]
        budget = 1500 - len(head) - len(tail)
        mid = "\n\n".join(paragraphs[2:-1])[:max(budget, 0)]
        return f"{head}\n\n{mid}\n\n{tail}"

    def _summarize_one(self, item: RSSItem) -> bool:
        content = self._prepare_content(item)
        if not content and not item.title:
            return False

        prompt = self.user_prompt_template.format(
            title=item.title or "",
            source=item.feed_id or "",
            content=content,
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            result = self.client.chat(messages, max_tokens=self.max_tokens)
            return self._parse_result(item, result)
        except (ValueError, TypeError, ConnectionError, TimeoutError) as exc:
            logger.warning("生成摘要失败 [%s]: %s", item.title[:30] if item.title else "?", exc)
            return False
        except Exception as exc:
            logger.warning("生成摘要未知错误 [%s]: %s", item.title[:30] if item.title else "?", exc)
            return False

    def _parse_result(self, item: RSSItem, raw: str) -> bool:
        parsed = json_repair.loads(raw)
        if not isinstance(parsed, dict):
            item.ai_summary = raw.strip()
            return bool(item.ai_summary)

        item.ai_summary = parsed.get("summary", "").strip()

        category = parsed.get("category", "")
        if category in _VALID_CATEGORIES:
            item.category = category
        else:
            item.category = "其他"

        tags = parsed.get("tags", [])
        if isinstance(tags, list):
            item.tags = [str(t).strip() for t in tags if t][:10]

        importance = parsed.get("importance", 0)
        try:
            score = int(importance)
            item.importance_score = float(max(1, min(5, score)))
        except (ValueError, TypeError):
            item.importance_score = 0.0

        return bool(item.ai_summary)

    async def summarize_items(self, items: List[RSSItem]) -> List[RSSItem]:
        if not self.system_prompt and not self.user_prompt_template:
            logger.warning("摘要提示词文件未找到，跳过摘要生成")
            return items

        valid, err = self.client.validate_config()
        if not valid:
            logger.warning("AI 配置无效，跳过摘要生成: %s", err)
            return items

        to_process = []
        skipped = 0
        for i in items:
            if self.skip_if_exists and i.ai_summary:
                continue
            if self._should_skip(i):
                skipped += 1
                continue
            to_process.append(i)

        if skipped:
            logger.info("[摘要] 规则跳过 %d 条低价值内容", skipped)

        if not to_process:
            return items

        count = 0
        total = len(to_process)
        sem = asyncio.Semaphore(_SUMMARY_CONCURRENCY)

        async def _do_one(item: RSSItem) -> bool:
            async with sem:
                return await asyncio.to_thread(self._summarize_one, item)

        tasks = [_do_one(item) for item in to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if result is True:
                count += 1
            elif isinstance(result, Exception):
                logger.warning("摘要任务异常: %s", result)
            if (i + 1) % 20 == 0 and (i + 1) < total:
                logger.info("[摘要] 进度: %d/%d", i + 1, total)

        logger.info("AI 摘要生成完成: %d 条", count)
        return items
