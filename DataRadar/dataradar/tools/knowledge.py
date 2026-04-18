"""
知识库工具 — 通过 FastAPI 查询 PostgreSQL 知识库。

共 8 个工具：
  1. kb_search_semantic      - 语义向量搜索
  2. kb_search_fulltext      - 三元组关键词搜索
  3. kb_get_content          - 单条内容详情
  4. kb_list_content         - 按日期/类型/平台过滤，游标分页
  5. kb_get_trending         - 热门排行
  6. kb_get_knowledge_entry  - 聚合知识条目及关联来源
  7. kb_find_related         - 相关知识条目
  8. kb_get_stats            - 统计概览
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class KnowledgeTools:

    def __init__(self):
        from dataradar.services.api_client import get_api_client
        self._client = get_api_client()

    async def kb_search_semantic(
        self,
        query: str,
        content_type: Optional[str] = None,
        date_from: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        result = await self._client.semantic_search_content(
            query=query,
            content_type=content_type,
            date_from=date_from,
            limit=limit,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def kb_search_fulltext(
        self,
        query: str,
        content_type: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        result = await self._client.search_content(
            query=query,
            content_type=content_type,
            limit=limit,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def kb_get_content(self, content_id: int) -> str:
        result = await self._client.get_content_detail(content_id)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def kb_list_content(
        self,
        date: Optional[str] = None,
        content_type: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[int] = None,
    ) -> str:
        result = await self._client.list_content(
            date=date,
            content_type=content_type,
            platform=platform,
            limit=limit,
            cursor=cursor,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def kb_get_trending(
        self,
        date: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        result = await self._client.get_trending(
            date=date,
            content_type=content_type,
            limit=limit,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def kb_get_knowledge_entry(self, entry_id: int) -> str:
        result = await self._client.get_knowledge_entry(entry_id)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def kb_find_related(
        self,
        entry_id: int,
        n: int = 5,
        category: Optional[str] = None,
    ) -> str:
        source = await self._client.get_knowledge_entry(entry_id)
        if "error" in source:
            return json.dumps({"error": "Source entry not found."})

        title = source.get("canonical_title", "")
        result = await self._client.semantic_search_knowledge(
            query=title,
            category=category,
            limit=n + 1,
        )

        items = result.get("items", [])
        items = [it for it in items if it.get("id") != entry_id][:n]
        result["items"] = items
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def kb_get_stats(self) -> str:
        result = await self._client.get_stats()
        return json.dumps(result, ensure_ascii=False, indent=2)
