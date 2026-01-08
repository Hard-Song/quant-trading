# -*- coding: utf-8 -*-
"""
策略模块初始化文件
"""

from .base_strategy import BaseStrategy
from .ma_strategy import DualMovingAverage

__all__ = ['BaseStrategy', 'DualMovingAverage']
