"""DataRadar API 客户端"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from postmaker.core.models import Material


class DataRadarClient:
    def __init__(self, api_base: str = "http://localhost:8000", timeout: int = 15):
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_base, timeout=self.timeout
            )
        return self._client

    async def list_content(
        self, date: Optional[str] = None, limit: int = 50
    ) -> List[Material]:
        client = await self._get_client()
        params: Dict[str, Any] = {"limit": limit}
        if date:
            params["date"] = date
        resp = await client.get("/api/v1/content", params=params)
        resp.raise_for_status()
        return [_parse_material(item) for item in resp.json().get("items", [])]

    async def get_content_detail(self, content_id: int) -> Material:
        client = await self._get_client()
        resp = await client.get(f"/api/v1/content/{content_id}")
        resp.raise_for_status()
        return _parse_material(resp.json())

    async def search(self, query: str, limit: int = 20) -> List[Material]:
        client = await self._get_client()
        resp = await client.get(
            "/api/v1/content/search", params={"q": query, "limit": limit}
        )
        resp.raise_for_status()
        return [_parse_material(item) for item in resp.json().get("items", [])]

    async def get_trending(
        self, date: Optional[str] = None, limit: int = 50
    ) -> List[Material]:
        client = await self._get_client()
        params: Dict[str, Any] = {"limit": limit}
        if date:
            params["date"] = date
        resp = await client.get("/api/v1/content/trending", params=params)
        resp.raise_for_status()
        return [_parse_material(item) for item in resp.json().get("items", [])]

    async def get_trending_topics(
        self, date: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        client = await self._get_client()
        params: Dict[str, Any] = {"limit": limit}
        if date:
            params["date"] = date
        resp = await client.get("/api/v1/content/topics/trending", params=params)
        resp.raise_for_status()
        return resp.json().get("topics", [])

    async def get_bundle(
        self, category: str, date: Optional[str] = None, limit: int = 20
    ) -> List[Material]:
        client = await self._get_client()
        params: Dict[str, Any] = {"category": category, "limit": limit}
        if date:
            params["date"] = date
        resp = await client.get("/api/v1/content/bundle", params=params)
        resp.raise_for_status()
        return [_parse_material(item) for item in resp.json().get("items", [])]

    async def mark_used(self, content_id: int, persona_id: str) -> None:
        client = await self._get_client()
        resp = await client.post(
            f"/api/v1/content/{content_id}/mark_used",
            json={"persona_id": persona_id},
        )
        resp.raise_for_status()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


def _parse_material(data: Dict[str, Any]) -> Material:
    return Material(
        id=data.get("id", 0),
        title=data.get("title", ""),
        source_platform=data.get("source_platform", ""),
        source_url=data.get("source_url", ""),
        published_at=data.get("published_at"),
        summary=data.get("summary"),
        full_text=data.get("full_text"),
        importance_score=data.get("importance_score", 0.0),
        tags=data.get("tags", []),
        category=data.get("category"),
        ai_summary=data.get("ai_summary"),
    )
