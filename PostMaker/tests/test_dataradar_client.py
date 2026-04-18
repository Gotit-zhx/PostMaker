"""DataRadar API 客户端测试"""

import pytest
import httpx
import respx

from postmaker.integrations.dataradar_client import DataRadarClient
from tests.conftest import (
    MOCK_CONTENT_ITEM_AI,
    MOCK_CONTENT_ITEM_OPENSOURCE,
    MOCK_CONTENT_ITEMS,
)

BASE = "http://testserver"


@pytest.fixture
def client():
    return DataRadarClient(api_base=BASE, timeout=5)


@respx.mock
@pytest.mark.asyncio
async def test_list_content(client):
    respx.get(f"{BASE}/api/v1/content").mock(
        return_value=httpx.Response(200, json={
            "items": MOCK_CONTENT_ITEMS,
            "meta": {"limit": 50, "next_cursor": None},
        })
    )
    materials = await client.list_content(limit=50)
    await client.close()
    assert len(materials) == 3
    assert materials[0].title == "OpenAI 发布 GPT-5"
    assert materials[0].id == 42
    assert materials[0].importance_score == 4.5


@respx.mock
@pytest.mark.asyncio
async def test_list_content_with_date(client):
    route = respx.get(f"{BASE}/api/v1/content").mock(
        return_value=httpx.Response(200, json={
            "items": [MOCK_CONTENT_ITEM_AI],
            "meta": {"limit": 50, "next_cursor": None},
        })
    )
    await client.list_content(date="2026-04-18", limit=10)
    await client.close()
    assert route.called
    assert "date=2026-04-18" in str(route.calls[0].request.url)


@respx.mock
@pytest.mark.asyncio
async def test_get_content_detail(client):
    respx.get(f"{BASE}/api/v1/content/42").mock(
        return_value=httpx.Response(200, json=MOCK_CONTENT_ITEM_AI)
    )
    material = await client.get_content_detail(42)
    await client.close()
    assert material.id == 42
    assert material.category == "AI"
    assert "GPT" in material.tags


@respx.mock
@pytest.mark.asyncio
async def test_search(client):
    respx.get(f"{BASE}/api/v1/content/search").mock(
        return_value=httpx.Response(200, json={
            "items": [MOCK_CONTENT_ITEM_AI],
            "query": "GPT",
            "total": 1,
        })
    )
    results = await client.search("GPT", limit=10)
    await client.close()
    assert len(results) == 1
    assert results[0].title == "OpenAI 发布 GPT-5"


@respx.mock
@pytest.mark.asyncio
async def test_get_trending(client):
    respx.get(f"{BASE}/api/v1/content/trending").mock(
        return_value=httpx.Response(200, json={
            "items": MOCK_CONTENT_ITEMS[:2],
            "meta": {"limit": 50, "next_cursor": None},
        })
    )
    materials = await client.get_trending(limit=10)
    await client.close()
    assert len(materials) == 2
    assert materials[0].importance_score >= materials[1].importance_score


@respx.mock
@pytest.mark.asyncio
async def test_get_trending_topics(client):
    respx.get(f"{BASE}/api/v1/content/topics/trending").mock(
        return_value=httpx.Response(200, json={
            "date": "2026-04-18",
            "topics": [
                {"category": "AI", "count": 15, "sources": 5,
                 "avg_importance": 3.8, "top_tags": ["AI", "GPT"]},
            ],
        })
    )
    topics = await client.get_trending_topics()
    await client.close()
    assert len(topics) == 1
    assert topics[0]["category"] == "AI"
    assert topics[0]["count"] == 15


@respx.mock
@pytest.mark.asyncio
async def test_get_bundle(client):
    respx.get(f"{BASE}/api/v1/content/bundle").mock(
        return_value=httpx.Response(200, json={
            "category": "AI",
            "items": [MOCK_CONTENT_ITEM_AI],
            "total": 1,
        })
    )
    materials = await client.get_bundle("AI", limit=20)
    await client.close()
    assert len(materials) == 1
    assert materials[0].category == "AI"


@respx.mock
@pytest.mark.asyncio
async def test_mark_used(client):
    respx.post(f"{BASE}/api/v1/content/42/mark_used").mock(
        return_value=httpx.Response(200, json={
            "ok": True, "content_id": 42, "persona_id": "tech-reviewer",
        })
    )
    await client.mark_used(42, "tech-reviewer")
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_parse_material_nullable_fields(client):
    item = {
        "id": 99,
        "title": "Minimal Item",
        "source_platform": "rss-test",
        "importance_score": 0.0,
    }
    respx.get(f"{BASE}/api/v1/content/99").mock(
        return_value=httpx.Response(200, json=item)
    )
    m = await client.get_content_detail(99)
    await client.close()
    assert m.id == 99
    assert m.published_at is None
    assert m.summary is None
    assert m.full_text is None
    assert m.category is None
    assert m.tags == []


@respx.mock
@pytest.mark.asyncio
async def test_http_error_404(client):
    respx.get(f"{BASE}/api/v1/content/999").mock(
        return_value=httpx.Response(404, json={"detail": "Not found"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_content_detail(999)
    await client.close()
