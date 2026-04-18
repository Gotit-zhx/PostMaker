# coding=utf-8
"""源管理 CLI 命令: list, add, remove, enable, disable, test"""

import json

from dataradar.source_manager import SourceManager


def handle_source(args):
    mgr = SourceManager()
    cmd = args.source_command

    if cmd == "list":
        _list_sources(mgr)
    elif cmd == "add":
        _add_source(mgr, args)
    elif cmd == "remove":
        _remove_source(mgr, args)
    elif cmd == "enable":
        _enable_source(mgr, args)
    elif cmd == "disable":
        _disable_source(mgr, args)
    elif cmd == "test":
        _test_source(mgr, args)


def _list_sources(mgr: SourceManager):
    feeds = mgr.list_feeds()
    targets = mgr.list_targets()

    print("=" * 60)
    print(f"  RSS 源 ({len(feeds)})")
    print("=" * 60)
    for f in feeds:
        status = "ON" if f["enabled"] else "OFF"
        print(f"  [{status:3s}] {f['id']:<25s} {f['name']}")
        print(f"        {f['url']}")

    if targets:
        print()
        print("=" * 60)
        print(f"  Web 采集目标 ({len(targets)})")
        print("=" * 60)
        for t in targets:
            status = "ON" if t["enabled"] else "OFF"
            print(f"  [{status:3s}] {t['id']:<25s} {t['name']}")
            print(f"        {t['url']}")


def _add_source(mgr: SourceManager, args):
    source_type = args.source_type

    if source_type == "rss":
        result = mgr.add_feed(
            url=args.url,
            id=args.id,
            name=args.name or "",
            max_age_days=args.max_age_days,
        )
        print(f"RSS 源已添加: {result['id']} ({result['url']})")
    elif source_type == "web":
        result = mgr.add_target(
            url=args.url,
            id=args.id,
            name=args.name or "",
            list_selector=args.list_selector or "",
            title_selector=args.title_selector or "",
            link_selector=args.link_selector or "",
        )
        print(f"Web 采集目标已添加: {result['id']} ({result['url']})")
    else:
        print(f"未知源类型: {source_type}，支持: rss, web")


def _remove_source(mgr: SourceManager, args):
    if mgr.remove_source(args.id):
        print(f"已删除: {args.id}")
    else:
        print(f"未找到: {args.id}")


def _enable_source(mgr: SourceManager, args):
    if mgr.enable_source(args.id):
        print(f"已启用: {args.id}")
    else:
        print(f"未找到: {args.id}")


def _disable_source(mgr: SourceManager, args):
    if mgr.disable_source(args.id):
        print(f"已禁用: {args.id}")
    else:
        print(f"未找到: {args.id}")


def _test_source(mgr: SourceManager, args):
    id_or_url = args.id_or_url

    if id_or_url.startswith(("http://", "https://")):
        result = mgr.test_feed(id_or_url)
    else:
        # Try RSS first, then Web
        result = mgr.test_feed(id_or_url)
        if not result.get("success") and "未找到 RSS 源" in result.get("error", ""):
            result = mgr.test_target(id_or_url)

    if result.get("success"):
        name = result.get("feed_name") or result.get("target_name", "")
        print(f"测试成功: {name}")
        print(f"URL: {result.get('url', '')}")
        print(f"获取条目: {result.get('item_count', 0)}")
        print()
        for item in result.get("items", []):
            print(f"  - {item.get('title', '')}")
            if item.get("url"):
                print(f"    {item['url']}")
    else:
        print(f"测试失败: {result.get('error', '未知错误')}")
