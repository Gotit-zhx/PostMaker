# coding=utf-8
"""文章阅读 CLI 命令"""

import json

from dataradar.tools.article_reader import ArticleReaderTools


def handle_read(args):
    reader = ArticleReaderTools()

    if args.batch:
        urls = args.batch
        result = reader.read_articles_batch(urls)
        if result.get("success"):
            summary = result["summary"]
            print(f"批量读取: {summary['succeeded']}/{summary['processed']} 成功")
            print()
            for article in result.get("articles", []):
                if article.get("success"):
                    data = article["data"]
                    print(f"--- [{article['index']}] {data['url']} ({data['content_length']} chars) ---")
                    print(data["content"][:500])
                    print("...")
                else:
                    print(f"--- [{article['index']}] 失败: {article['error'].get('message', '')} ---")
        else:
            print(f"批量读取失败: {result.get('error', {}).get('message', '')}")
        return

    url = args.url
    result = reader.read_article(url)

    if result.get("success"):
        data = result["data"]
        print(data["content"])
    else:
        error = result.get("error", {})
        print(f"读取失败: {error.get('message', '未知错误')}")
        if error.get("suggestion"):
            print(f"建议: {error['suggestion']}")
