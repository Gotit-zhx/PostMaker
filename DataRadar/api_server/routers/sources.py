"""数据源管理与采集任务路由。

这些接口给 PostMaker 工作台和其他前端提供一个不需要编辑 YAML 的入口。
当前仍是单实例管理：配置写回 DataRadar 的 config.yaml，采集任务在当前 API
进程的后台任务中运行。
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from dataradar.collector import DataCollector
from dataradar.core.loader import load_config
from dataradar.source_manager import SourceManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["sources"])

_SOURCE_LOCK = threading.RLock()
_collection_task: Optional[asyncio.Task] = None
_collection_state: dict[str, Any] = {
    "job_id": None,
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "error": None,
}


class RSSSourceCreate(BaseModel):
    """用户通过网页添加 RSS 源时提交的字段。"""

    id: Optional[str] = Field(default=None, min_length=1, max_length=80)
    name: str = Field(default="", max_length=200)
    url: str = Field(min_length=8, max_length=2_000)
    max_age_days: int = Field(default=3, ge=0, le=3_650)
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: Optional[str]) -> Optional[str]:
        if value and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
            raise ValueError("源 ID 只能包含字母、数字、下划线和短横线")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("RSS URL 必须以 http:// 或 https:// 开头")
        return value


class RSSSourceTest(BaseModel):
    """测试尚未保存的 RSS 地址。"""

    url: str = Field(min_length=8, max_length=2_000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("RSS URL 必须以 http:// 或 https:// 开头")
        return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manager() -> SourceManager:
    return SourceManager()


def _source_items(manager: SourceManager) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for feed in manager.list_feeds():
        items.append({"kind": "rss", **feed})
    for target in manager.list_targets():
        items.append({"kind": "web", **target})
    return items


def _find_source(manager: SourceManager, source_id: str) -> Optional[dict[str, Any]]:
    return next((item for item in _source_items(manager) if item["id"] == source_id), None)


async def _source_call(callback, *args, **kwargs):
    """在线程中执行 YAML 读写或网络测试，避免阻塞 FastAPI 事件循环。"""
    def invoke():
        with _SOURCE_LOCK:
            return callback(*args, **kwargs)

    return await asyncio.to_thread(invoke)


@router.get("/sources")
async def list_sources():
    manager = _manager()
    items = await _source_call(_source_items, manager)
    return {"items": items, "count": len(items)}


@router.post("/sources/rss", status_code=status.HTTP_201_CREATED)
async def add_rss_source(request: RSSSourceCreate):
    manager = _manager()
    try:
        result = await _source_call(
            manager.add_feed,
            url=request.url,
            id=request.id,
            name=request.name.strip(),
            max_age_days=request.max_age_days,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, KeyError) as exc:
        logger.exception("添加 RSS 源失败")
        raise HTTPException(status_code=500, detail=f"保存数据源配置失败：{exc}") from exc
    return {"kind": "rss", **result}


@router.post("/sources/rss/test")
async def test_rss_url(request: RSSSourceTest):
    """先试读用户填写的 RSS 地址，成功后再保存配置。"""
    result = await _source_call(_manager().test_feed, request.url)
    if not result.get("success"):
        raise HTTPException(status_code=422, detail=result.get("error", "RSS 测试失败"))
    return result


@router.post("/sources/{source_id}/test")
async def test_source(source_id: str):
    manager = _manager()
    source = await _source_call(_find_source, manager, source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"找不到数据源：{source_id}")
    tester = manager.test_feed if source["kind"] == "rss" else manager.test_target
    result = await _source_call(tester, source_id)
    if not result.get("success"):
        raise HTTPException(status_code=422, detail=result.get("error", "数据源测试失败"))
    return result


@router.post("/sources/{source_id}/enable")
async def enable_source(source_id: str):
    manager = _manager()
    source = await _source_call(_find_source, manager, source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"找不到数据源：{source_id}")
    changed = await _source_call(manager.enable_source, source_id)
    return {"ok": changed, "source_id": source_id, "enabled": True}


@router.post("/sources/{source_id}/disable")
async def disable_source(source_id: str):
    manager = _manager()
    source = await _source_call(_find_source, manager, source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"找不到数据源：{source_id}")
    changed = await _source_call(manager.disable_source, source_id)
    return {"ok": changed, "source_id": source_id, "enabled": False}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    manager = _manager()
    source = await _source_call(_find_source, manager, source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"找不到数据源：{source_id}")
    deleted = await _source_call(manager.remove_source, source_id)
    return {"ok": deleted, "source_id": source_id}


async def _run_collection(job_id: str) -> None:
    global _collection_state
    try:
        config = load_config()
        await DataCollector(config).run()
        _collection_state = {
            **_collection_state,
            "job_id": job_id,
            "status": "completed",
            "finished_at": _now(),
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - exercised by integration tests
        logger.exception("后台采集任务失败 job_id=%s", job_id)
        _collection_state = {
            **_collection_state,
            "job_id": job_id,
            "status": "failed",
            "finished_at": _now(),
            "error": str(exc),
        }


@router.post("/collect", status_code=status.HTTP_202_ACCEPTED)
async def trigger_collection():
    global _collection_task, _collection_state
    if _collection_task and not _collection_task.done():
        raise HTTPException(status_code=409, detail="已有采集任务正在运行")

    job_id = uuid.uuid4().hex
    _collection_state = {
        "job_id": job_id,
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "error": None,
    }
    _collection_task = asyncio.create_task(_run_collection(job_id))
    return {**_collection_state}


@router.get("/collect/status")
async def collection_status():
    return {**_collection_state}
