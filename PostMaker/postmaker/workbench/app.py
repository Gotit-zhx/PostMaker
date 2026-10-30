"""FastAPI application for the local PostMaker workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from postmaker.core.config import get_persona_dir, load_config
from postmaker.core.models import GenerationTask
from postmaker.integrations.dataradar_client import DataRadarClient
from postmaker.persona.loader import load_all_personas
from postmaker.workbench.store import WorkbenchStore
from postmaker.content.generator import ContentGenerator

_STATIC = Path(__file__).parent / "static"
app = FastAPI(title="PostMaker Workbench", version="0.1.0")
app.mount("/static", StaticFiles(directory=_STATIC), name="static")
store = WorkbenchStore()


class GenerateRequest(BaseModel):
    material_id: int = Field(gt=0)
    persona_id: str = Field(min_length=1, max_length=100)


class DraftUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=200_000)
    status: Literal["pending_review", "approved", "archived"] | None = None


class RestoreRequest(BaseModel):
    revision_id: int = Field(gt=0)


def _personas():
    cfg = load_config()
    return cfg, load_all_personas(get_persona_dir(cfg))


@app.get("/")
async def index():
    return FileResponse(_STATIC / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "storage": "sqlite", "database": str(store.path)}


@app.get("/api/personas")
async def personas():
    _, entries = _personas()
    return [{"id": p.id, "name": p.name, "description": p.description,
             "topics": p.interests.topics} for p in entries]


@app.get("/api/materials")
async def materials(mode: Literal["trending", "recent"] = "trending",
                    limit: int = Query(default=30, ge=1, le=100)):
    cfg, _ = _personas()
    client_cfg = cfg.get("dataradar", {})
    client = DataRadarClient(client_cfg.get("api_base", "http://localhost:8000"),
                             client_cfg.get("timeout", 15))
    try:
        items = (await client.get_trending(limit=limit) if mode == "trending"
                 else await client.list_content(limit=limit))
        return {"items": [item.model_dump(mode="json") for item in items], "mode": mode}
    except Exception as exc:
        raise HTTPException(status_code=502,
                            detail=f"无法连接 DataRadar ({client.api_base})：{exc}") from exc
    finally:
        await client.close()


@app.get("/api/materials/{material_id}")
async def material_detail(material_id: int):
    cfg, _ = _personas()
    client_cfg = cfg.get("dataradar", {})
    client = DataRadarClient(client_cfg.get("api_base", "http://localhost:8000"),
                             client_cfg.get("timeout", 15))
    try:
        item = await client.get_content_detail(material_id)
        return item.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"读取素材详情失败：{exc}") from exc
    finally:
        await client.close()


@app.get("/api/drafts")
async def list_drafts(status: str = "all", limit: int = Query(default=100, ge=1, le=300)):
    return {"items": store.list_drafts(status=status, limit=limit)}


@app.get("/api/drafts/{draft_id}")
async def get_draft(draft_id: int):
    draft = store.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="找不到这篇草稿")
    return draft


@app.post("/api/drafts/generate")
async def generate_draft(request: GenerateRequest):
    cfg, persona_list = _personas()
    persona = next((p for p in persona_list if p.id == request.persona_id), None)
    if not persona:
        raise HTTPException(status_code=404, detail="找不到指定 persona")
    ai_cfg = cfg.get("ai", {})
    if not ai_cfg.get("api_key") or not ai_cfg.get("model"):
        raise HTTPException(status_code=503, detail="请先配置 AI_API_KEY 和 AI_MODEL")
    client_cfg = cfg.get("dataradar", {})
    client = DataRadarClient(client_cfg.get("api_base", "http://localhost:8000"),
                             client_cfg.get("timeout", 15))
    try:
        material = await client.get_content_detail(request.material_id)
        generator = ContentGenerator(ai_cfg, refine_enabled=ai_cfg.get("refine_enabled", False))
        draft = await generator.generate_batch([GenerationTask(material=material, persona=persona)])
    except Exception as exc:
        detail = "获取素材详情失败" if "material" not in locals() else "生成失败"
        raise HTTPException(status_code=502, detail=f"{detail}：{exc}") from exc
    finally:
        await client.close()

    if not draft or not draft[0].body:
        raise HTTPException(status_code=502, detail="模型没有返回有效正文，请稍后重试")
    title = draft[0].title or material.title
    created = store.create_draft(material.model_dump(mode="json"), persona.id, persona.name,
                                 title, draft[0].body, draft[0].model_used)

    # 草稿已经可靠落库后再标记素材，标记失败不影响用户继续审核草稿。
    mark_client = DataRadarClient(client_cfg.get("api_base", "http://localhost:8000"),
                                  client_cfg.get("timeout", 15))
    try:
        await mark_client.mark_used(material.id, persona.id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("标记素材已使用失败 material=%s persona=%s: %s",
                                            material.id, persona.id, exc)
    finally:
        await mark_client.close()
    return created


@app.put("/api/drafts/{draft_id}")
async def update_draft(draft_id: int, update: DraftUpdate):
    draft = store.update_draft(draft_id, update.title, update.body, update.status)
    if not draft:
        raise HTTPException(status_code=404, detail="找不到这篇草稿")
    return draft


@app.get("/api/drafts/{draft_id}/revisions")
async def revisions(draft_id: int):
    if not store.get_draft(draft_id):
        raise HTTPException(status_code=404, detail="找不到这篇草稿")
    return {"items": store.list_revisions(draft_id)}


@app.post("/api/drafts/{draft_id}/restore")
async def restore_revision(draft_id: int, request: RestoreRequest):
    draft = store.restore_revision(draft_id, request.revision_id)
    if not draft:
        raise HTTPException(status_code=404, detail="找不到草稿或修订版本")
    return draft


@app.get("/api/drafts/{draft_id}/export.md", response_class=PlainTextResponse)
async def export_markdown(draft_id: int):
    draft = store.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="找不到这篇草稿")
    if draft["status"] != "approved":
        raise HTTPException(status_code=409, detail="只有已批准的草稿可以导出")
    material = draft["material"]
    safe_title = draft["title"].replace('"', '\\"')
    source = material.get("source_url") or ""
    content = (f"---\ntitle: \"{safe_title}\"\npersona: \"{draft['persona_name']}\"\n"
               f"status: {draft['status']}\nsource: \"{source}\"\n"
               f"generated_at: \"{draft['created_at']}\"\nmodel: \"{draft['model_used']}\"\n---\n\n"
               f"{draft['body']}\n")
    return PlainTextResponse(content, headers={
        "Content-Disposition": f'attachment; filename="draft-{draft_id}.md"'
    })
