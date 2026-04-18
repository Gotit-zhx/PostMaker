"""
轻量级异步 HTTP 客户端，用于调用 DataRadar 知识库 API。

使用共享的 httpx.AsyncClient 实现连接复用（长连接）。

配置：
  设置环境变量 KB_API_BASE_URL（默认：http://localhost:8000）
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "http://localhost:8000"
_client: Optional["KnowledgeAPIClient"] = None


class KnowledgeAPIClient:
    """知识库 FastAPI 服务的异步 HTTP 客户端封装。"""

    def __init__(self, base_url: str = _DEFAULT_BASE, timeout: float = 10.0):
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=base_url.rstrip("/"),
                timeout=timeout,
                headers={"User-Agent": "DataRadar-CLI/1.0"},
            )
        except ImportError:
            self._client = None
            logger.error("httpx 未安装，请执行: pip install httpx")

        self.base_url = base_url

    async def get(self, path: str, params: Optional[Dict] = None) -> Any:
        if not self._client:
            return {"error": "httpx not available"}
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("知识库 API GET %s 失败: %s", path, exc)
            return {"error": str(exc)}

    async def post(self, path: str, json_body: Any) -> Any:
        if not self._client:
            return {"error": "httpx not available"}
        try:
            resp = await self._client.post(path, json=json_body)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("知识库 API POST %s 失败: %s", path, exc)
            return {"error": str(exc)}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def list_content(
        self,
        date: Optional[str] = None,
        content_type: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[int] = None,
    ) -> Dict:
        params = {"limit": limit}
        if date:
            params["date"] = date
        if content_type:
            params["content_type"] = content_type
        if platform:
            params["platform"] = platform
        if cursor:
            params["cursor"] = cursor
        return await self.get("/api/v1/content", params=params)

    async def get_content_detail(self, content_id: int) -> Dict:
        return await self.get(f"/api/v1/content/{content_id}")

    async def search_content(
        self,
        query: str,
        content_type: Optional[str] = None,
        limit: int = 20,
    ) -> Dict:
        params = {"q": query, "limit": limit}
        if content_type:
            params["content_type"] = content_type
        return await self.get("/api/v1/content/search", params=params)

    async def semantic_search_content(
        self,
        query: str,
        content_type: Optional[str] = None,
        date_from: Optional[str] = None,
        limit: int = 10,
    ) -> Dict:
        body: Dict[str, Any] = {"query": query, "limit": limit}
        if content_type:
            body["content_type"] = content_type
        if date_from:
            body["date_from"] = date_from
        return await self.post("/api/v1/content/semantic", body)

    async def get_trending(
        self,
        date: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 50,
    ) -> Dict:
        params: Dict[str, Any] = {"limit": limit}
        if date:
            params["date"] = date
        if content_type:
            params["content_type"] = content_type
        return await self.get("/api/v1/content/trending", params=params)

    async def list_knowledge(
        self,
        days: int = 7,
        category: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[int] = None,
    ) -> Dict:
        params: Dict[str, Any] = {"days": days, "limit": limit}
        if category:
            params["category"] = category
        if cursor:
            params["cursor"] = cursor
        return await self.get("/api/v1/knowledge", params=params)

    async def get_knowledge_entry(self, entry_id: int) -> Dict:
        return await self.get(f"/api/v1/knowledge/{entry_id}")

    async def semantic_search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> Dict:
        body: Dict[str, Any] = {"query": query, "limit": limit}
        if category:
            body["category"] = category
        return await self.post("/api/v1/knowledge/semantic", body)

    async def get_stats(self) -> Dict:
        return await self.get("/api/v1/stats/overview")


def get_api_client() -> KnowledgeAPIClient:
    """返回模块级单例 KnowledgeAPIClient。"""
    global _client
    if _client is None:
        base_url = os.getenv("KB_API_BASE_URL", _DEFAULT_BASE)
        _client = KnowledgeAPIClient(base_url=base_url)
        logger.info("KnowledgeAPIClient 已初始化 → %s", base_url)
    return _client
