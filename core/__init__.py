# -*- coding: utf-8 -*-
"""
核心模块初始化文件
"""

from .backtest_engine import BacktestEngine, BacktestResult
from .data_manager import DataManager
from .strategy_comparator import StrategyComparator, StrategyTestConfig, ComparisonResult
from .batch_backtest_engine import BatchBacktestEngine, BatchBacktestResult, run_batch_backtest

__all__ = [
    'BacktestEngine',
    'BacktestResult',
    'DataManager',
    'StrategyComparator',
    'StrategyTestConfig',
    'ComparisonResult',
    'BatchBacktestEngine',
    'BatchBacktestResult',
    'run_batch_backtest',
]
