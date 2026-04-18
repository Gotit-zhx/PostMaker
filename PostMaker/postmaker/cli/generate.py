"""postmaker generate 命令"""

from __future__ import annotations

import logging
from typing import List

from postmaker.core.config import get_persona_dir, load_config
from postmaker.core.models import Draft, DraftStatus, GenerationTask, Material
from postmaker.content.generator import ContentGenerator
from postmaker.integrations.dataradar_client import DataRadarClient
from postmaker.output.html import save_html
from postmaker.output.markdown import save_markdown
from postmaker.persona.loader import load_all_personas
from postmaker.persona.matcher import build_generation_tasks

logger = logging.getLogger(__name__)


async def cmd_generate(args):
    cfg = load_config()
    dr_cfg = cfg.get("dataradar", {})
    ai_cfg = cfg.get("ai", {})
    out_cfg = cfg.get("output", {})

    personas = load_all_personas(get_persona_dir(cfg))
    if args.persona:
        personas = [p for p in personas if p.id == args.persona]
    if not personas:
        print("未找到匹配的人设。")
        return

    client = DataRadarClient(
        api_base=dr_cfg.get("api_base", "http://localhost:8000"),
        timeout=dr_cfg.get("timeout", 15),
    )

    try:
        materials = await _fetch_materials(client, args)
    except Exception as e:
        print(f"获取素材失败: {e}")
        return
    finally:
        await client.close()

    if not materials:
        print("未找到素材。")
        return

    print(f"获取到 {len(materials)} 条素材，{len(personas)} 个人设")

    existing_pairs = set()
    db_cfg = cfg.get("database", {})
    repo = None
    if db_cfg.get("postgres_dsn"):
        try:
            from postmaker.storage.db import init_pool, get_pool
            from postmaker.storage.repository import PostMakerRepository
            await init_pool(db_cfg["postgres_dsn"])
            repo = PostMakerRepository(get_pool())
            await repo.ensure_schema()
            existing_pairs = await repo.get_existing_pairs()
        except Exception as e:
            logger.warning("数据库连接失败，跳过去重: %s", e)

    tasks = build_generation_tasks(materials, personas, existing_pairs)
    if not tasks:
        print("所有素材-人设组合已生成，无新任务。")
        return

    print(f"匹配到 {len(tasks)} 个生成任务")

    if args.dry_run:
        for t in tasks:
            print(f"  [{t.persona.id}] {t.material.title[:50]}")
        return

    refine = args.refine or ai_cfg.get("refine_enabled", False)
    generator = ContentGenerator(ai_cfg, refine_enabled=refine)
    drafts = await generator.generate_batch(tasks)

    base_dir = out_cfg.get("base_dir", "output")
    formats = out_cfg.get("formats", ["markdown", "html"])
    task_map = {(t.material.id, t.persona.id): t for t in tasks}

    ok = 0
    for draft in drafts:
        if draft.status != DraftStatus.COMPLETED:
            continue
        task = task_map.get((draft.material_id, draft.persona_id))
        if not task:
            continue

        paths = []
        if "markdown" in formats:
            p = save_markdown(draft, task.material, task.persona, base_dir)
            paths.append(p)
            draft.output_path = p
        if "html" in formats:
            p = save_html(draft, task.material, task.persona, base_dir)
            paths.append(p)

        if repo:
            try:
                mid = await repo.upsert_material(task.material)
                await repo.save_draft(draft, mid)
            except Exception as e:
                logger.warning("保存草稿记录失败: %s", e)

        ok += 1
        print(f"  [{task.persona.id}] {draft.title[:40]}  ->  {', '.join(paths)}")

    print(f"\n生成完成: {ok}/{len(drafts)} 篇成功")

    if db_cfg.get("postgres_dsn"):
        try:
            from postmaker.storage.db import close_pool
            await close_pool()
        except Exception:
            pass


async def _fetch_materials(
    client: DataRadarClient, args
) -> List[Material]:
    if args.material_id:
        m = await client.get_content_detail(args.material_id)
        return [m]
    if args.topic:
        return await client.get_bundle(args.topic, limit=args.limit)
    if args.trending:
        return await client.get_trending(limit=args.limit)
    return await client.list_content(limit=args.limit)
