# coding=utf-8
"""
DataRadar - 数据采集与知识库系统

使用方式:
  python -m dataradar fetch   # 运行采集管道
  python -m dataradar status  # 查看状态
"""

from dataradar.context import AppContext

__version__ = "1.0.0"
__all__ = ["AppContext", "__version__"]
