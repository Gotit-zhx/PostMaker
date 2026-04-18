"""
轻量级定时调度器，基于 asyncio 原生实现。

用法:
    dataradar schedule --interval 60   # 每 60 分钟运行一次采集
"""

import asyncio
import logging
import signal
from datetime import datetime
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class SimpleScheduler:
    """基于 asyncio 的轻量级定时调度器。"""

    def __init__(self, interval_minutes: int = 60):
        self.interval = interval_minutes * 60
        self._running = False
        self._run_count = 0

    async def start(self, task_fn: Callable[[], Awaitable]):
        """循环执行异步任务，间隔 self.interval 秒。"""
        self._running = True
        logger.info(
            "调度器启动，每 %d 分钟执行一次采集任务",
            self.interval // 60,
        )

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop)
            except NotImplementedError:
                pass

        while self._running:
            self._run_count += 1
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                "调度器: 第 %d 次执行开始 (%s)", self._run_count, now,
            )
            try:
                await task_fn()
            except Exception as e:
                logger.error("调度任务失败: %s", e)

            if not self._running:
                break

            next_time = datetime.now().strftime("%H:%M")
            logger.info(
                "调度器: 下次执行在 %d 分钟后",
                self.interval // 60,
            )
            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break

        logger.info("调度器已停止，共执行 %d 次", self._run_count)

    def stop(self):
        """停止调度器。"""
        self._running = False
        logger.info("调度器收到停止信号")
