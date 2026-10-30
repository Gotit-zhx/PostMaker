# coding=utf-8
"""RSS 数据查询 CLI 命令"""

import json
import asyncio

from dataradar.services.data_service import DataService


def handle_rss(args):
    svc = DataService()

    if args.status:
        result = asyncio.run(svc.get_rss_feeds_status())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.search:
        results = asyncio.run(svc.search_rss(
            keyword=args.search,
            feeds=args.feeds.split(",") if args.feeds else None,
            days=args.days,
            limit=args.limit,
            include_summary=args.summary,
        ))
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    results = asyncio.run(svc.get_latest_rss(
        feeds=args.feeds.split(",") if args.feeds else None,
        days=args.days,
        limit=args.limit,
        include_summary=args.summary,
    ))
    print(json.dumps(results, ensure_ascii=False, indent=2))
