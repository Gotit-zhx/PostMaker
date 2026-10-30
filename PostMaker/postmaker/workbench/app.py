"""FastAPI application for the local PostMaker workbench."""

from __future__ import annotations

import html
import io
import json
import os
from pathlib import Path
import zipfile
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from postmaker.core.config import get_persona_dir, load_config
from postmaker.core.models import GenerationTask
from postmaker.integrations.dataradar_client import DataRadarClient
from postmaker.persona.loader import load_all_personas
from postmaker.workbench.store import WorkbenchStore
from postmaker.workbench.auth import AuthStore, auth_required, workspace_signature
from postmaker.workbench.workspace import reset_workspace, set_workspace_id, workspace_id
from postmaker.content.generator import ContentGenerator
from postmaker.workbench.platforms import adapt_draft, list_platforms
from postmaker.workbench.source_presets import get_source_preset, list_source_presets
import httpx

_STATIC = Path(__file__).parent / "static"
app = FastAPI(title="PostMaker Workbench", version="0.1.0")
app.mount("/static", StaticFiles(directory=_STATIC), name="static")
store = WorkbenchStore()
auth_store = AuthStore()


def _store() -> WorkbenchStore:
    return store if workspace_id() == "default" else WorkbenchStore()


def _dataradar_headers() -> dict[str, str]:
    current = workspace_id()
    if current == "default":
        return {}
    return {
        "X-Workspace-ID": current,
        "X-Workspace-Signature": workspace_signature(current),
    }


def _cookie_secure() -> bool:
    return os.getenv("POSTMAKER_COOKIE_SECURE", "0").lower() in {"1", "true", "yes"}


def _client_key(request: Request) -> str:
    return request.client.host if request.client and request.client.host else "unknown"


def _auth_rate_limit(request: Request, action: str) -> JSONResponse | None:
    """Limit public auth endpoints before password work or account creation."""
    defaults = {"register": (5, 600), "login": (15, 300)}
    limit, window = defaults[action]
    try:
        limit = int(os.getenv(f"POSTMAKER_{action.upper()}_RATE_LIMIT", str(limit)))
        window = int(os.getenv("POSTMAKER_AUTH_RATE_WINDOW", str(window)))
    except ValueError:
        pass
    allowed, retry_after = auth_store.check_rate_limit(f"{action}:{_client_key(request)}", limit, window)
    if allowed:
        return None
    return JSONResponse(
        {"detail": "请求过于频繁，请稍后重试"},
        status_code=429,
        headers={"Retry-After": str(retry_after)},
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    token = None
    session = auth_store.get_session(request.cookies.get("pm_session")) if auth_required() else None
    public = request.url.path.startswith("/static") or request.url.path in {"/", "/api/health", "/api/auth/me", "/api/auth/register", "/api/auth/login", "/api/auth/logout"}
    if auth_required() and not public and not session:
        return JSONResponse({"detail": "请先登录"}, status_code=401) if request.url.path.startswith("/api/") else RedirectResponse("/")
    if session:
        user, csrf = session
        token = set_workspace_id(user["workspace_id"])
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path.startswith("/api/") and request.url.path not in {"/api/auth/register", "/api/auth/login", "/api/auth/logout"}:
            if request.headers.get("x-csrf-token") != csrf:
                return JSONResponse({"detail": "CSRF token 无效"}, status_code=403)
        request.state.user = user
        request.state.csrf_token = csrf
    try:
        return await call_next(request)
    finally:
        if token is not None:
            reset_workspace(token)


class GenerateRequest(BaseModel):
    material_id: int = Field(gt=0)
    persona_id: str = Field(min_length=1, max_length=100)


class DraftUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=200_000)
    status: Literal["pending_review", "approved", "archived"] | None = None


class RestoreRequest(BaseModel):
    revision_id: int = Field(gt=0)


class AdaptRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=40)


def _personas():
    cfg = load_config()
    return cfg, load_all_personas(get_persona_dir(cfg))


@app.get("/")
async def index():
    return FileResponse(_STATIC / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "storage": "sqlite", "database": str(_store().path), "auth_required": auth_required()}


@app.get("/api/auth/me")
async def auth_me(request: Request):
    user = getattr(request.state, "user", None)
    return {"authenticated": bool(user), "user": user}


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)


@app.post("/api/auth/register", status_code=201)
async def auth_register(payload: AuthRequest, request: Request):
    limited = _auth_rate_limit(request, "register")
    if limited:
        return limited
    try:
        user = auth_store.create_user(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raw, csrf = auth_store.create_session(user["id"])
    response = JSONResponse({"authenticated": True, "user": user}, status_code=201)
    response.set_cookie("pm_session", raw, httponly=True, secure=_cookie_secure(), samesite="lax", max_age=7 * 24 * 3600, path="/")
    response.set_cookie("pm_csrf", csrf, httponly=False, secure=_cookie_secure(), samesite="lax", max_age=7 * 24 * 3600, path="/")
    return response


@app.post("/api/auth/login")
async def auth_login(payload: AuthRequest, request: Request):
    limited = _auth_rate_limit(request, "login")
    if limited:
        return limited
    client_key = _client_key(request)
    locked = auth_store.login_lockout_remaining(payload.email, client_key)
    if locked:
        return JSONResponse(
            {"detail": "登录失败次数过多，请稍后重试"},
            status_code=429,
            headers={"Retry-After": str(locked)},
        )
    user = auth_store.authenticate(payload.email, payload.password, client_key=client_key)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    raw, csrf = auth_store.create_session(user["id"])
    response = JSONResponse({"authenticated": True, "user": user})
    response.set_cookie("pm_session", raw, httponly=True, secure=_cookie_secure(), samesite="lax", max_age=7 * 24 * 3600, path="/")
    response.set_cookie("pm_csrf", csrf, httponly=False, secure=_cookie_secure(), samesite="lax", max_age=7 * 24 * 3600, path="/")
    return response


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    auth_store.delete_session(request.cookies.get("pm_session"))
    response = JSONResponse({"authenticated": False})
    response.delete_cookie("pm_session", path="/")
    response.delete_cookie("pm_csrf", path="/")
    return response


async def _dataradar_request(method: str, path: str, **kwargs):
    cfg = load_config()
    client_cfg = cfg.get("dataradar", {})
    api_base = client_cfg.get("api_base", "http://localhost:8000").rstrip("/")
    timeout = client_cfg.get("timeout", 15)
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.update({k: v for k, v in _dataradar_headers().items() if k not in headers})
    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=timeout) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except Exception:
            detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"无法连接 DataRadar ({api_base})：{exc}") from exc


@app.get("/api/platforms")
async def platforms():
    return {"items": list_platforms()}


@app.get("/api/source-presets")
async def source_presets():
    return {"items": list_source_presets()}


@app.post("/api/source-presets/{preset_id}/enable", status_code=201)
async def enable_source_preset(preset_id: str):
    preset = get_source_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="找不到来源预置")
    payload = {"id": preset["id"], "name": preset["name"], "url": preset["url"],
               "max_age_days": preset.get("max_age_days", 3), "enabled": True}
    return await _dataradar_request("POST", "/api/v1/sources/rss", json=payload)


@app.get("/api/sources")
async def sources():
    return await _dataradar_request("GET", "/api/v1/sources")


@app.post("/api/sources/rss", status_code=201)
async def add_rss_source(payload: dict):
    return await _dataradar_request("POST", "/api/v1/sources/rss", json=payload)


@app.put("/api/sources/rss/{source_id}")
async def update_rss_source(source_id: str, payload: dict):
    return await _dataradar_request("PUT", f"/api/v1/sources/rss/{source_id}", json=payload)


@app.post("/api/sources/rss/test")
async def test_rss_source(payload: dict):
    return await _dataradar_request("POST", "/api/v1/sources/rss/test", json=payload)


@app.post("/api/sources/{source_id}/test")
async def test_source(source_id: str):
    return await _dataradar_request("POST", f"/api/v1/sources/{source_id}/test")


@app.post("/api/sources/{source_id}/enable")
async def enable_source(source_id: str):
    return await _dataradar_request("POST", f"/api/v1/sources/{source_id}/enable")


@app.post("/api/sources/{source_id}/disable")
async def disable_source(source_id: str):
    return await _dataradar_request("POST", f"/api/v1/sources/{source_id}/disable")


@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: str):
    return await _dataradar_request("DELETE", f"/api/v1/sources/{source_id}")


@app.post("/api/collect", status_code=202)
async def trigger_collection():
    return await _dataradar_request("POST", "/api/v1/collect")


@app.get("/api/collect/status")
async def collect_status():
    return await _dataradar_request("GET", "/api/v1/collect/status")


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
                             client_cfg.get("timeout", 15), headers=_dataradar_headers())
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
                             client_cfg.get("timeout", 15), headers=_dataradar_headers())
    try:
        item = await client.get_content_detail(material_id)
        return item.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"读取素材详情失败：{exc}") from exc
    finally:
        await client.close()


@app.get("/api/drafts")
async def list_drafts(status: str = "all", limit: int = Query(default=100, ge=1, le=300)):
    return {"items": _store().list_drafts(status=status, limit=limit)}


@app.get("/api/drafts/{draft_id}")
async def get_draft(draft_id: int):
    draft = _store().get_draft(draft_id)
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
                             client_cfg.get("timeout", 15), headers=_dataradar_headers())
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
    created = _store().create_draft(material.model_dump(mode="json"), persona.id, persona.name,
                                 title, draft[0].body, draft[0].model_used)

    # 草稿已经可靠落库后再标记素材，标记失败不影响用户继续审核草稿。
    mark_client = DataRadarClient(client_cfg.get("api_base", "http://localhost:8000"),
                                  client_cfg.get("timeout", 15), headers=_dataradar_headers())
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
    draft = _store().update_draft(draft_id, update.title, update.body, update.status)
    if not draft:
        raise HTTPException(status_code=404, detail="找不到这篇草稿")
    return draft


@app.post("/api/drafts/{draft_id}/adapt")
async def adapt_draft_for_platform(draft_id: int, request: AdaptRequest):
    draft = _store().get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="找不到这篇草稿")
    if draft["status"] != "approved":
        raise HTTPException(status_code=409, detail="只有已批准的草稿可以适配平台")
    try:
        return adapt_draft(draft, request.platform)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/drafts/{draft_id}/revisions")
async def revisions(draft_id: int):
    if not _store().get_draft(draft_id):
        raise HTTPException(status_code=404, detail="找不到这篇草稿")
    return {"items": _store().list_revisions(draft_id)}


@app.post("/api/drafts/{draft_id}/restore")
async def restore_revision(draft_id: int, request: RestoreRequest):
    draft = _store().restore_revision(draft_id, request.revision_id)
    if not draft:
        raise HTTPException(status_code=404, detail="找不到草稿或修订版本")
    return draft


def _approved_draft(draft_id: int) -> dict:
    draft = _store().get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="找不到这篇草稿")
    if draft["status"] != "approved":
        raise HTTPException(status_code=409, detail="只有已批准的草稿可以导出")
    return draft


@app.get("/api/drafts/{draft_id}/export.html", response_class=PlainTextResponse)
async def export_html(draft_id: int):
    draft = _approved_draft(draft_id)
    adapted = adapt_draft(draft, "wechat")
    content = "<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>" + html.escape(draft["title"]) + "</title><body>" + adapted["html"] + "</body></html>"
    return PlainTextResponse(content, media_type="text/html", headers={"Content-Disposition": f'attachment; filename="draft-{draft_id}.html"'})


@app.get("/api/drafts/{draft_id}/export-package")
async def export_package(draft_id: int, platform: str = "generic"):
    draft = _approved_draft(draft_id)
    try:
        adapted = adapt_draft(draft, platform)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("draft.md", f"# {draft['title']}\n\n{draft['body']}\n")
        archive.writestr("publish.txt", adapted.get("caption") or adapted.get("plain_body") or adapted.get("body") or "")
        archive.writestr("publish.json", json.dumps(adapted, ensure_ascii=False, indent=2))
        archive.writestr("media-manifest.json", json.dumps({"items": adapted.get("media", []), "note": "图片保留原始 URL，未在服务器下载。"}, ensure_ascii=False, indent=2))
    memory.seek(0)
    return Response(memory.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="draft-{draft_id}-{platform}.zip"'})


@app.get("/api/drafts/{draft_id}/export.md", response_class=PlainTextResponse)
async def export_markdown(draft_id: int):
    draft = _approved_draft(draft_id)
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
