# -*- coding: utf-8 -*-
"""
选股器基类模块
定义所有选股器的基础接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd

from core.data_manager import DataManager
from utils.logger import logger


@dataclass
class ScreeningResult:
    """
    选股结果数据类

    属性:
        total_stocks: 总股票数
        selected_stocks: 选中的股票数
        symbols: 选中的股票代码列表
        details: 每只股票的详细信息 {代码: {指标: 值}}
        screening_time: 选股时间
        screener_name: 选股器名称
    """
    total_stocks: int
    selected_stocks: int
    symbols: List[str] = field(default_factory=list)
    details: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    screening_time: datetime = None
    screener_name: str = ""

    def __post_init__(self):
        if self.screening_time is None:
            self.screening_time = datetime.now()

    def get_selection_rate(self) -> float:
        """获取选股率"""
        if self.total_stocks == 0:
            return 0.0
        return (self.selected_stocks / self.total_stocks) * 100

    def to_dataframe(self) -> pd.DataFrame:
        """
        转换为DataFrame格式

        返回:
            DataFrame: 股票详情表格
        """
        if not self.details:
            # 如果没有详细信息，返回简单列表
            return pd.DataFrame({
                '股票代码': self.symbols
            })

        # 有详细信息，返回完整表格
        data = []
        for symbol in self.symbols:
            row = {'股票代码': symbol}
            if symbol in self.details:
                row.update(self.details[symbol])
            data.append(row)

        df = pd.DataFrame(data)
        return df

    def __str__(self):
        """格式化输出结果"""
        selection_rate = self.get_selection_rate()
        return f"""
========== 选股结果 ==========
选股器: {self.screener_name}
选股时间: {self.screening_time.strftime('%Y-%m-%d %H:%M:%S')}
------------------------------
总股票数: {self.total_stocks}
选中股票: {self.selected_stocks}
选股率: {selection_rate:.2f}%
==============================
"""


class BaseScreener(ABC):
    """
    选股器基类

    所有选股器都应该继承此类并实现screen方法

    生命周期：
        1. __init__(): 初始化选股器
        2. screen(): 执行选股
        3. get_details(): 获取股票详细信息（可选）

    使用示例:
        class MyScreener(BaseScreener):
            def screen(self, stock_list, **kwargs):
                selected = []
                for stock in stock_list:
                    if self.my_condition(stock):
                        selected.append(stock)
                return self.create_result(selected, len(stock_list))

            def my_condition(self, stock):
                # 自定义选股逻辑
                return True
    """

    # 选股器元信息
    name = ""  # 选股器名称
    description = ""  # 选股器描述
    category = ""  # 选股器类别 (factor/technical/pattern/custom)

    def __init__(self, data_manager: DataManager = None):
        """
        初始化选股器

        参数:
            data_manager: 数据管理器（可选，默认创建新实例）
        """
        self.data_manager = data_manager or DataManager()
        logger.info(f"初始化选股器: {self.name or self.__class__.__name__}")

    @abstractmethod
    def screen(
        self,
        stock_list: List[str],
        **kwargs
    ) -> ScreeningResult:
        """
        执行选股（抽象方法，子类必须实现）

        参数:
            stock_list: 股票代码列表
            **kwargs: 选股参数

        返回:
            ScreeningResult: 选股结果对象

        说明:
            1. 遍历stock_list中的每只股票
            2. 根据选股条件判断是否满足
            3. 返回满足条件的股票列表和详细信息
        """
        raise NotImplementedError("子类必须实现screen方法")

    def get_stock_data(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        获取股票数据

        参数:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        返回:
            DataFrame: 股票数据
        """
        # 默认获取最近1年数据
        if start_date is None:
            from datetime import timedelta
            end = datetime.now()
            start = end - timedelta(days=365)
            start_date = start.strftime('%Y-%m-%d')
            end_date = end.strftime('%Y-%m-%d')

        df = self.data_manager.get_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            **kwargs
        )

        return df

    def create_result(
        self,
        symbols: List[str],
        total_count: int,
        details: Dict[str, Dict[str, Any]] = None
    ) -> ScreeningResult:
        """
        创建选股结果对象

        参数:
            symbols: 选中的股票代码列表
            total_count: 总股票数
            details: 详细信息字典

        返回:
            ScreeningResult: 选股结果对象
        """
        result = ScreeningResult(
            total_stocks=total_count,
            selected_stocks=len(symbols),
            symbols=symbols,
            details=details or {},
            screener_name=self.name or self.__class__.__name__
        )
        return result

    def validate_stock_list(self, stock_list: List[str]) -> List[str]:
        """
        验证并清洗股票列表

        参数:
            stock_list: 原始股票列表

        返回:
            List[str]: 清洗后的股票列表
        """
        if not stock_list:
            raise ValueError("股票列表不能为空")

        # 去重
        stock_list = list(set(stock_list))

        # 过滤无效代码
        valid_stocks = [s for s in stock_list if s and len(str(s).strip()) == 6]

        if not valid_stocks:
            raise ValueError("没有有效的股票代码")

        logger.info(f"股票列表验证完成: {len(valid_stocks)} 只有效股票")

        return valid_stocks

    def get_info(self) -> Dict[str, str]:
        """
        获取选股器信息

        返回:
            Dict: 选股器元信息
        """
        return {
            'name': self.name or self.__class__.__name__,
            'description': self.description,
            'category': self.category,
        }

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<{self.__class__.__name__}: {self.name}>"


# ==================== 装饰器 ====================
_screener_registry = {}


def register_screener(name: str = None):
    """
    选股器注册装饰器

    用于自动注册选股器到管理器

    使用示例:
        @register_screener('my_screener')
        class MyScreener(BaseScreener):
            pass
    """
    def decorator(cls):
        screener_name = name or cls.__name__
        _screener_registry[screener_name] = cls
        cls.name = screener_name
        logger.info(f"注册选股器: {screener_name}")
        return cls

    return decorator


def get_registered_screeners() -> Dict[str, type]:
    """
    获取所有已注册的选股器

    返回:
        Dict: {选股器名称: 选股器类}
    """
    return _screener_registry.copy()
