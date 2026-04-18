"""postmaker materials 命令"""

from postmaker.core.config import load_config
from postmaker.integrations.dataradar_client import DataRadarClient


async def cmd_materials(args):
    cfg = load_config()
    dr_cfg = cfg.get("dataradar", {})
    client = DataRadarClient(
        api_base=dr_cfg.get("api_base", "http://localhost:8000"),
        timeout=dr_cfg.get("timeout", 15),
    )

    try:
        if args.detail:
            m = await client.get_content_detail(args.detail)
            print(f"ID: {m.id}")
            print(f"标题: {m.title}")
            print(f"来源: {m.source_platform}")
            print(f"URL: {m.source_url}")
            print(f"分类: {m.category or '-'}")
            print(f"标签: {', '.join(m.tags) if m.tags else '-'}")
            print(f"重要性: {m.importance_score}")
            print(f"摘要: {m.ai_summary or m.summary or '-'}")
            return

        if args.search:
            materials = await client.search(args.search)
        elif args.trending:
            materials = await client.get_trending(limit=50)
        else:
            materials = await client.list_content(limit=50)

        if not materials:
            print("未找到素材。")
            return

        print(f"共 {len(materials)} 条素材：\n")
        for m in materials:
            cat = f"[{m.category}]" if m.category else ""
            score = f"★{m.importance_score:.0f}" if m.importance_score else ""
            print(f"  {m.id:>5}  {score:>3} {cat:<8} {m.title[:60]}")
    finally:
        await client.close()
