# coding=utf-8
"""
DataRadar CLI 入口

用法:
  python -m dataradar fetch                     # 运行采集管道
  python -m dataradar status                    # 系统状态
  python -m dataradar rss [--days N]            # 查询 RSS 数据
  python -m dataradar source list               # 列出所有源
  python -m dataradar source add rss <url>      # 添加 RSS 源
  python -m dataradar source test <id|url>      # 测试源
  python -m dataradar kb search <query>         # 知识库搜索
  python -m dataradar read <url>                # 读取文章
  python -m dataradar config [section]          # 查看配置
"""

import argparse
import json
import logging
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="dataradar",
        description="DataRadar - 数据采集与知识库系统",
    )
    parser.add_argument("--debug", action="store_true", help="调试模式")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ── fetch ──
    p_fetch = subparsers.add_parser("fetch", help="运行数据采集管道")

    # ── status ──
    p_status = subparsers.add_parser("status", help="查看系统状态")

    # ── rss ──
    p_rss = subparsers.add_parser("rss", help="查询 RSS 数据")
    p_rss.add_argument("--feeds", type=str, default=None, help="RSS 源 ID（逗号分隔）")
    p_rss.add_argument("--days", type=int, default=1, help="查询最近 N 天（默认 1）")
    p_rss.add_argument("--limit", type=int, default=50, help="返回条数（默认 50）")
    p_rss.add_argument("--search", type=str, default=None, help="搜索关键词")
    p_rss.add_argument("--status", action="store_true", help="显示 RSS 源数据统计")
    p_rss.add_argument("--summary", action="store_true", help="包含摘要")

    # ── source ──
    p_source = subparsers.add_parser("source", help="管理数据源")
    source_sub = p_source.add_subparsers(dest="source_command", help="源管理操作")

    source_sub.add_parser("list", help="列出所有源")

    p_add = source_sub.add_parser("add", help="添加源")
    p_add.add_argument("source_type", choices=["rss", "web"], help="源类型")
    p_add.add_argument("url", help="源 URL")
    p_add.add_argument("--id", type=str, default=None, help="源 ID（不指定则自动生成）")
    p_add.add_argument("--name", type=str, default=None, help="源名称")
    p_add.add_argument("--max-age-days", type=int, default=3, help="RSS: 最大保留天数")
    p_add.add_argument("--list-selector", type=str, default=None, help="Web: 列表选择器")
    p_add.add_argument("--title-selector", type=str, default=None, help="Web: 标题选择器")
    p_add.add_argument("--link-selector", type=str, default=None, help="Web: 链接选择器")

    p_remove = source_sub.add_parser("remove", help="删除源")
    p_remove.add_argument("id", help="源 ID")

    p_enable = source_sub.add_parser("enable", help="启用源")
    p_enable.add_argument("id", help="源 ID")

    p_disable = source_sub.add_parser("disable", help="禁用源")
    p_disable.add_argument("id", help="源 ID")

    p_test = source_sub.add_parser("test", help="测试源")
    p_test.add_argument("id_or_url", help="源 ID 或 URL")

    # ── kb ──
    p_kb = subparsers.add_parser("kb", help="知识库操作")
    kb_sub = p_kb.add_subparsers(dest="kb_command", help="知识库子命令")

    p_kb_search = kb_sub.add_parser("search", help="全文搜索")
    p_kb_search.add_argument("query", help="搜索词")
    p_kb_search.add_argument("--type", type=str, default=None, help="内容类型")
    p_kb_search.add_argument("--limit", type=int, default=20, help="返回条数")

    p_kb_semantic = kb_sub.add_parser("semantic", help="语义搜索")
    p_kb_semantic.add_argument("query", help="搜索词")
    p_kb_semantic.add_argument("--type", type=str, default=None, help="内容类型")
    p_kb_semantic.add_argument("--date-from", type=str, default=None, help="起始日期")
    p_kb_semantic.add_argument("--limit", type=int, default=10, help="返回条数")

    p_kb_list = kb_sub.add_parser("list", help="内容列表")
    p_kb_list.add_argument("--date", type=str, default=None, help="日期 YYYY-MM-DD")
    p_kb_list.add_argument("--type", type=str, default=None, help="内容类型")
    p_kb_list.add_argument("--platform", type=str, default=None, help="平台")
    p_kb_list.add_argument("--limit", type=int, default=50, help="返回条数")
    p_kb_list.add_argument("--cursor", type=int, default=None, help="分页游标")

    p_kb_trending = kb_sub.add_parser("trending", help="热门内容")
    p_kb_trending.add_argument("--date", type=str, default=None, help="日期")
    p_kb_trending.add_argument("--type", type=str, default=None, help="内容类型")
    p_kb_trending.add_argument("--limit", type=int, default=50, help="返回条数")

    kb_sub.add_parser("stats", help="统计信息")

    p_kb_get = kb_sub.add_parser("get", help="内容详情")
    p_kb_get.add_argument("id", help="内容 ID")

    p_kb_entry = kb_sub.add_parser("entry", help="知识条目")
    p_kb_entry.add_argument("id", help="条目 ID")

    p_kb_related = kb_sub.add_parser("related", help="相关条目")
    p_kb_related.add_argument("id", help="条目 ID")
    p_kb_related.add_argument("--limit", type=int, default=5, help="返回条数")

    # ── read ──
    p_read = subparsers.add_parser("read", help="读取文章内容")
    p_read.add_argument("url", nargs="?", help="文章 URL")
    p_read.add_argument("--batch", nargs="+", help="批量读取多个 URL")

    # ── config ──
    p_config = subparsers.add_parser("config", help="查看配置")
    p_config.add_argument("section", nargs="?", default="all", help="配置节: all/rss/ai/storage")

    # ── schedule ──
    p_schedule = subparsers.add_parser("schedule", help="定时运行采集任务")
    p_schedule.add_argument(
        "--interval", type=int, default=60,
        help="采集间隔（分钟，默认 60）",
    )

    # ── 解析参数 ──
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

    if not args.command:
        parser.print_help()
        return

    if args.command == "fetch":
        from dataradar.cli.collect import handle_fetch
        handle_fetch(args)

    elif args.command == "status":
        from dataradar.cli.collect import handle_status
        handle_status(args)

    elif args.command == "rss":
        from dataradar.cli.rss import handle_rss
        handle_rss(args)

    elif args.command == "source":
        if not args.source_command:
            p_source.print_help()
            return
        from dataradar.cli.source import handle_source
        handle_source(args)

    elif args.command == "kb":
        if not args.kb_command:
            p_kb.print_help()
            return
        from dataradar.cli.kb import handle_kb
        handle_kb(args)

    elif args.command == "read":
        if not args.url and not args.batch:
            p_read.print_help()
            return
        from dataradar.cli.read import handle_read
        handle_read(args)

    elif args.command == "schedule":
        from dataradar.cli.collect import handle_schedule
        handle_schedule(args)

    elif args.command == "config":
        _handle_config(args)


def _handle_config(args):
    from dataradar.core.loader import load_config
    config = load_config()

    section = args.section
    if section == "all":
        for key in ["TIMEZONE", "RSS_ENABLED"]:
            if key in config:
                print(f"{key}: {config[key]}")
        if "AI" in config:
            ai = config["AI"]
            print(f"AI Model: {ai.get('MODEL', 'N/A')}")
            print(f"AI API Base: {ai.get('API_BASE', 'N/A')}")
        if "KNOWLEDGE_BASE" in config:
            kb = config["KNOWLEDGE_BASE"]
            print(f"Knowledge Base: {'enabled' if kb.get('ENABLED') else 'disabled'}")
    elif section == "rss":
        rss = config.get("RSS", {})
        print(json.dumps(rss, ensure_ascii=False, indent=2))
    elif section == "ai":
        ai = config.get("AI", {})
        safe_ai = {k: v for k, v in ai.items() if k != "API_KEY"}
        print(json.dumps(safe_ai, ensure_ascii=False, indent=2))
    elif section == "storage":
        storage = config.get("STORAGE", {})
        print(json.dumps(storage, ensure_ascii=False, indent=2))
    else:
        print(f"未知配置节: {section}")


if __name__ == "__main__":
    main()
