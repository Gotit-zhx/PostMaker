"""PostMaker CLI 入口"""

import argparse
import asyncio
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="postmaker",
        description="PostMaker - 矩阵运营内容生成系统",
    )
    sub = parser.add_subparsers(dest="command")

    # generate
    gen = sub.add_parser("generate", help="生成内容")
    gen.add_argument("--persona", help="指定人设 ID")
    gen.add_argument("--topic", help="指定主题分类")
    gen.add_argument("--material-id", type=int, help="指定素材 ID")
    gen.add_argument("--trending", action="store_true", help="使用热门素材")
    gen.add_argument("--limit", type=int, default=10, help="素材数量上限")
    gen.add_argument("--dry-run", action="store_true", help="预览匹配，不生成")
    gen.add_argument("--refine", action="store_true", help="启用二阶段优化")

    # personas
    sub.add_parser("personas", help="列出所有人设")

    # materials
    mat = sub.add_parser("materials", help="查看素材")
    mat.add_argument("--search", help="搜索关键词")
    mat.add_argument("--trending", action="store_true", help="热门素材")
    mat.add_argument("--detail", type=int, help="素材详情 ID")

    # history
    hist = sub.add_parser("history", help="生成历史")
    hist.add_argument("--persona", help="按人设过滤")

    # config
    cfg = sub.add_parser("config", help="查看配置")
    cfg.add_argument("section", nargs="?", help="配置段名")

    # workbench
    wb = sub.add_parser("workbench", help="启动本地内容审核工作台")
    wb.add_argument("--host", default="127.0.0.1", help="监听地址")
    wb.add_argument("--port", type=int, default=8787, help="监听端口")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "workbench":
        import uvicorn
        uvicorn.run("postmaker.workbench.app:app", host=args.host, port=args.port, reload=False)
        return

    asyncio.run(_dispatch(args))


async def _dispatch(args):
    if args.command == "generate":
        from postmaker.cli.generate import cmd_generate
        await cmd_generate(args)
    elif args.command == "personas":
        from postmaker.cli.personas import cmd_personas
        await cmd_personas(args)
    elif args.command == "materials":
        from postmaker.cli.materials import cmd_materials
        await cmd_materials(args)
    elif args.command == "history":
        from postmaker.cli.history import cmd_history
        await cmd_history(args)
    elif args.command == "config":
        from postmaker.cli.config_cmd import cmd_config
        await cmd_config(args)


if __name__ == "__main__":
    main()
