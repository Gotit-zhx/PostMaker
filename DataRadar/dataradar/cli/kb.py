# coding=utf-8
"""知识库 CLI 命令"""

import asyncio
import json

from dataradar.tools.knowledge import KnowledgeTools


def _run(coro):
    return asyncio.run(coro)


def handle_kb(args):
    tools = KnowledgeTools()
    cmd = args.kb_command

    if cmd == "search":
        result = _run(tools.kb_search_fulltext(
            query=args.query,
            content_type=args.type,
            limit=args.limit,
        ))
        print(result)

    elif cmd == "semantic":
        result = _run(tools.kb_search_semantic(
            query=args.query,
            content_type=args.type,
            date_from=args.date_from,
            limit=args.limit,
        ))
        print(result)

    elif cmd == "list":
        result = _run(tools.kb_list_content(
            date=args.date,
            content_type=args.type,
            platform=args.platform,
            limit=args.limit,
            cursor=args.cursor,
        ))
        print(result)

    elif cmd == "trending":
        result = _run(tools.kb_get_trending(
            date=args.date,
            content_type=args.type,
            limit=args.limit,
        ))
        print(result)

    elif cmd == "stats":
        result = _run(tools.kb_get_stats())
        print(result)

    elif cmd == "get":
        result = _run(tools.kb_get_content(int(args.id)))
        print(result)

    elif cmd == "entry":
        result = _run(tools.kb_get_knowledge_entry(int(args.id)))
        print(result)

    elif cmd == "related":
        result = _run(tools.kb_find_related(
            entry_id=int(args.id),
            n=args.limit,
        ))
        print(result)
