# -*- coding: utf-8 -*-
"""
选股器模块
提供插件式选股策略框架
"""

from .base_screener import BaseScreener, ScreeningResult, register_screener
from .screener_manager import ScreenerManager

__all__ = [
    'BaseScreener',
    'ScreeningResult',
    'ScreenerManager',
    'register_screener',
]
