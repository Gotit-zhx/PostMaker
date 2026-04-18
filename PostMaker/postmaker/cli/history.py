"""postmaker history 命令"""

from postmaker.core.config import load_config


async def cmd_history(args):
    cfg = load_config()
    db_cfg = cfg.get("database", {})

    if not db_cfg.get("postgres_dsn"):
        print("未配置数据库，无法查看历史。")
        return

    try:
        from postmaker.storage.db import init_pool, get_pool, close_pool
        from postmaker.storage.repository import PostMakerRepository
        await init_pool(db_cfg["postgres_dsn"])
        repo = PostMakerRepository(get_pool())
        drafts = await repo.list_drafts(persona_id=args.persona)
        await close_pool()
    except Exception as e:
        print(f"查询失败: {e}")
        return

    if not drafts:
        print("暂无生成记录。")
        return

    print(f"共 {len(drafts)} 条记录：\n")
    for d in drafts:
        ts = d.get("created_at", "")
        if ts:
            ts = str(ts)[:16]
        print(f"  [{d['persona_id']}] {d['title'][:50]}  ({ts})")
