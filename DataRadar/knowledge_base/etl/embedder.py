"""
基于 LiteLLM 的批量文本向量嵌入生成器。

复用 config.yaml 中 ai 配置节的同一 AI 供应商。
默认使用 text-embedding-3-small（OpenAI，1536 维，$0.02/百万 token）。

用法::

    embedder = BatchEmbedder(model="text-embedding-3-small", api_key="sk-...")
    vectors = await embedder.embed_batch(["hello world", "another text"])
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# text-embedding-3-small 的向量维度
DEFAULT_DIMENSIONS = 1536


class BatchEmbedder:
    """
    使用 LiteLLM 批量生成文本向量嵌入。

    参数：
        model:      LiteLLM 模型字符串，如 "text-embedding-3-small"
        api_key:    OpenAI 兼容的 API 密钥（或通过环境变量设置）
        api_base:   可选的自定义基础 URL（用于本地模型）
        batch_size: 每次 API 调用的最大文本数量
        dimensions: 向量嵌入维度（须与 pgvector 列匹配）
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        batch_size: int = 50,
        dimensions: int = DEFAULT_DIMENSIONS,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.batch_size = batch_size
        self.dimensions = dimensions

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        对文本列表进行向量嵌入。返回与输入等长的向量列表。
        单条失败的项返回 None。
        """
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)

        for start in range(0, len(texts), self.batch_size):
            chunk = texts[start: start + self.batch_size]
            vectors = await asyncio.to_thread(self._sync_embed, chunk)
            for i, vec in enumerate(vectors):
                results[start + i] = vec

        return results

    async def embed_single(self, text: str) -> Optional[List[float]]:
        """对单条文本进行向量嵌入。"""
        results = await self.embed_batch([text])
        return results[0] if results else None

    def _sync_embed(self, texts: List[str]) -> List[Optional[List[float]]]:
        """同步调用 LiteLLM 嵌入接口。"""
        try:
            import litellm  # type: ignore
            litellm.suppress_debug_info = True
        except ImportError:
            logger.error(
                "litellm not installed. Install with: pip install litellm"
            )
            return [None] * len(texts)

        valid_texts = [t.strip() for t in texts]
        valid_texts = [t[:8000] if t else "" for t in valid_texts]

        try:
            kwargs: dict = {"model": self.model, "input": valid_texts}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.api_base:
                kwargs["api_base"] = self.api_base

            response = litellm.embedding(**kwargs)
            vectors = [item["embedding"] for item in response.data]
            return vectors
        except Exception as exc:
            logger.debug("Embedding batch failed: %s", exc)
            return [None] * len(texts)
