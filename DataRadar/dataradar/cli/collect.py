# coding=utf-8
"""采集相关 CLI 命令: fetch, status"""

import asyncio

from dataradar.core.loader import load_config


def handle_fetch(args):
    from dataradar.collector import DataCollector
    config = load_config()
    if args.debug:
        config["DEBUG"] = True
    collector = DataCollector(config)
    asyncio.run(collector.run())


def handle_status(args):
    from dataradar.collector import DataCollector
    config = load_config()
    collector = DataCollector(config)
    collector.show_status()


def handle_schedule(args):
    """定时运行采集任务。"""
    import asyncio
    from dataradar.core.scheduler import SimpleScheduler
    from dataradar.collector import DataCollector

    config = load_config()
    interval = args.interval

    async def run_task():
        collector = DataCollector(config)
        await collector.run()

    scheduler = SimpleScheduler(interval_minutes=interval)
    print(f"[调度] 启动定时采集，间隔 {interval} 分钟（Ctrl+C 停止）")
    try:
        asyncio.run(scheduler.start(run_task))
    except KeyboardInterrupt:
        print("\n[调度] 已停止")
