"""Platform-specific publishing adapters.

Adapters deliberately prepare content for manual publishing. They do not log in to,
or automate, third-party platforms.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

import markdown as markdown_lib


@dataclass(frozen=True)
class PlatformSpec:
    id: str
    name: str
    description: str
    max_title: int | None = None
    max_body: int | None = None
    needs_media: bool = False


PLATFORM_SPECS: tuple[PlatformSpec, ...] = (
    PlatformSpec("wechat", "微信公众号", "富文本稿，适合复制到公众号编辑器", max_title=64, needs_media=True),
    PlatformSpec("zhihu", "知乎", "Markdown 长文，保留标题、引用和代码块", needs_media=False),
    PlatformSpec("xiaohongshu", "小红书", "短段落、重点句、话题标签和配图清单", max_title=20, max_body=1000, needs_media=True),
    PlatformSpec("x", "X / Threads", "按字符长度拆分为可复制的线程", max_body=280),
    PlatformSpec("linkedin", "LinkedIn", "专业导语、正文和话题标签", max_body=3000),
    PlatformSpec("generic", "通用 Markdown", "适合归档、复制和二次编辑"),
)


def list_platforms() -> list[dict[str, Any]]:
    return [
        {
            "id": spec.id,
            "name": spec.name,
            "description": spec.description,
            "max_title": spec.max_title,
            "max_body": spec.max_body,
            "needs_media": spec.needs_media,
        }
        for spec in PLATFORM_SPECS
    ]


def _spec(platform: str) -> PlatformSpec:
    try:
        return next(item for item in PLATFORM_SPECS if item.id == platform)
    except StopIteration as exc:
        raise ValueError(f"不支持的平台：{platform}") from exc


def _plain_text(value: str) -> str:
    value = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", value or "")
    value = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1（\2）", value)
    value = re.sub(r"^#{1,6}\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*[-*+]\s+", "• ", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*\d+\.\s+", "", value, flags=re.MULTILINE)
    value = re.sub(r"[`*_~]", "", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def _hashtags(draft: dict[str, Any]) -> list[str]:
    material = draft.get("material") or {}
    raw = material.get("tags") or []
    tags: list[str] = []
    for tag in raw:
        text = re.sub(r"[^\w\u4e00-\u9fff-]", "", str(tag), flags=re.UNICODE).strip("-")
        if text and text.lower() not in {item.lower() for item in tags}:
            tags.append(text)
    category = str(material.get("category") or "").strip()
    if category:
        category = re.sub(r"[^\w\u4e00-\u9fff-]", "", category, flags=re.UNICODE).strip("-")
        if category and category.lower() not in {item.lower() for item in tags}:
            tags.insert(0, category)
    return tags[:8]


def _source_line(draft: dict[str, Any]) -> str:
    material = draft.get("material") or {}
    url = str(material.get("source_url") or "").strip()
    platform = str(material.get("source_platform") or "原始来源").strip()
    return f"来源：{platform} · {url}" if url else f"来源：{platform}"


def _media(draft: dict[str, Any]) -> list[dict[str, str]]:
    material = draft.get("material") or {}
    candidates = material.get("media") or material.get("images") or []
    candidates = list(candidates)
    for key, role in (("thumbnail_url", "cover"), ("media_url", "inline")):
        if material.get(key):
            candidates.append({"url": material[key], "role": role})
    candidates.extend({"url": url, "role": "inline"} for url in (material.get("image_urls") or []))
    result: list[dict[str, str]] = []
    for item in candidates:
        if isinstance(item, str):
            result.append({"url": item, "role": "inline"})
        elif isinstance(item, dict) and (item.get("url") or item.get("path")):
            result.append({"url": str(item.get("url") or item.get("path")), "role": str(item.get("role") or "inline")})
    return result


def _split_thread(text: str, limit: int = 260) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = [paragraph[i : i + limit] for i in range(0, len(paragraph), limit)] or [""]
        for piece in pieces:
            candidate = f"{current}\n\n{piece}".strip() if current else piece
            if current and len(candidate) > limit:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks or [""]


def adapt_draft(draft: dict[str, Any], platform: str) -> dict[str, Any]:
    """Return a normalized publish-preparation payload for one approved draft."""
    spec = _spec(platform)
    title = str(draft.get("title") or "未命名文章").strip()
    body = str(draft.get("body") or "").strip()
    tags = _hashtags(draft)
    media = _media(draft)
    warnings: list[str] = []
    output: dict[str, Any] = {
        "platform": spec.id,
        "platform_name": spec.name,
        "title": title,
        "body": body,
        "hashtags": tags,
        "media": media,
        "warnings": warnings,
        "source": _source_line(draft),
    }

    if platform == "wechat":
        output["body"] = markdown_lib.markdown(body, extensions=["fenced_code", "tables"])
        output["plain_body"] = _plain_text(body)
        output["html"] = f"<h1>{html.escape(title)}</h1>\n{output['body']}\n<p>{html.escape(_source_line(draft))}</p>"
        if not media:
            warnings.append("建议补充封面图或正文配图")
    elif platform == "zhihu":
        output["body"] = body
        output["markdown"] = f"# {title}\n\n{body}\n\n---\n{_source_line(draft)}"
        output["plain_body"] = _plain_text(body)
    elif platform == "xiaohongshu":
        compact = _plain_text(body)
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", compact) if p.strip()]
        short = "\n\n".join(paragraphs[:8])
        if len(short) > 1000:
            short = short[:997].rstrip() + "…"
            warnings.append("正文已截断到约 1000 字，请在发布前检查")
        output["body"] = short
        output["hashtags"] = tags or ["内容创作"]
        output["caption"] = f"{short}\n\n" + " ".join(f"#{tag}" for tag in output["hashtags"])
        if not media:
            warnings.append("小红书建议至少准备 1 张竖版配图")
        if len(title) > 20:
            output["title"] = title[:19].rstrip() + "…"
            warnings.append("标题已截断到 20 字以内")
    elif platform == "x":
        thread = _split_thread(_plain_text(body), 260)
        output["body"] = "\n\n".join(f"{index}/{len(thread)}\n{part}" for index, part in enumerate(thread, 1))
        output["thread"] = thread
        output["plain_body"] = _plain_text(body)
        if len(thread) > 1:
            warnings.append(f"正文已拆分为 {len(thread)} 条线程，请按顺序发布")
    elif platform == "linkedin":
        output["body"] = f"{title}\n\n{_plain_text(body)}\n\n{_source_line(draft)}"
        output["hashtags"] = tags[:5]
        if len(output["body"]) > 3000:
            warnings.append("正文超过 LinkedIn 建议长度，请发布前精简")
    else:
        output["body"] = body
        output["markdown"] = f"# {title}\n\n{body}\n\n---\n{_source_line(draft)}"
        output["plain_body"] = _plain_text(body)

    if spec.max_title and len(output["title"]) > spec.max_title:
        output["title"] = output["title"][: spec.max_title - 1].rstrip() + "…"
        warnings.append(f"标题超过 {spec.max_title} 字，已截断")
    if spec.max_body and platform not in {"xiaohongshu", "x"} and len(_plain_text(output["body"])) > spec.max_body:
        warnings.append(f"正文超过平台建议长度 {spec.max_body} 字")
    return output
