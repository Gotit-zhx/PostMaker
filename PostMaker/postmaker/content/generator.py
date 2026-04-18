"""两阶段内容生成器"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List

from postmaker.ai.client import AIClient
from postmaker.content.prompt_builder import build_messages
from postmaker.core.models import Draft, DraftStatus, GenerationTask

logger = logging.getLogger(__name__)

_CONCURRENCY = 5


class ContentGenerator:
    def __init__(self, ai_config: Dict[str, Any], refine_enabled: bool = False):
        self.client = AIClient(ai_config)
        self.refine_enabled = refine_enabled

    async def generate_batch(self, tasks: List[GenerationTask]) -> List[Draft]:
        sem = asyncio.Semaphore(_CONCURRENCY)
        results: List[Draft] = []

        async def _do_one(task: GenerationTask) -> Draft:
            async with sem:
                return await asyncio.to_thread(self._generate_one, task)

        coros = [_do_one(t) for t in tasks]
        outcomes = await asyncio.gather(*coros, return_exceptions=True)

        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, Draft):
                results.append(outcome)
            elif isinstance(outcome, Exception):
                logger.warning("生成失败 [%s]: %s", tasks[i].material.title[:30], outcome)
                results.append(Draft(
                    material_id=tasks[i].material.id,
                    persona_id=tasks[i].persona.id,
                    status=DraftStatus.FAILED,
                ))
            if (i + 1) % 10 == 0:
                logger.info("[生成] 进度: %d/%d", i + 1, len(tasks))

        return results

    def _generate_one(self, task: GenerationTask) -> Draft:
        messages = build_messages(task)
        model = self.client.get_model_for_importance(task.material.importance_score)

        raw = self.client.chat(messages, model=model)
        title, body = _parse_output(raw)

        if self.refine_enabled and body:
            body = self._refine(task, body)

        return Draft(
            material_id=task.material.id,
            persona_id=task.persona.id,
            title=title or task.material.title,
            body=body,
            status=DraftStatus.COMPLETED if body else DraftStatus.FAILED,
            model_used=model,
        )

    def _refine(self, task: GenerationTask, body: str) -> str:
        messages = [
            {"role": "system", "content": (
                "你是一位文章编辑。请审查以下草稿，确保风格一致、逻辑通顺、"
                "没有事实错误。只做必要修改，保留原文风格。输出修改后的完整 Markdown 正文。"
            )},
            {"role": "user", "content": body},
        ]
        try:
            return self.client.chat(messages, max_tokens=self.client.max_tokens)
        except Exception as exc:
            logger.warning("Refine 失败: %s", exc)
            return body


def _parse_output(raw: str) -> tuple[str, str]:
    lines = raw.strip().split("\n", 1)
    if len(lines) < 2:
        return "", raw.strip()
    title = lines[0].strip().lstrip("#").strip()
    body = lines[1].strip()
    return title, body
