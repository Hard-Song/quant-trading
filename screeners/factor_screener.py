# -*- coding: utf-8 -*-
"""
因子选股器模块
基于基本面因子进行选股（PE、PB、ROE、市值等）
"""

from typing import List, Dict, Any, Tuple, Optional
import akshare as ak

from .base_screener import BaseScreener, ScreeningResult, register_screener
from utils.logger import logger


@register_screener('factor')
class FactorScreener(BaseScreener):
    """
    因子选股器

    基于基本面因子进行选股，包括：
        - 估值因子：PE、PB、PS、PCF等
        - 盈利因子：ROE、ROA、净利润率等
        - 成长因子：营收增长率、净利润增长率等
        - 规模因子：市值、流通股本等
        - 质量因子：负债率、流动比率等
        - 交易因子：换手率、振幅等

    使用示例:
        screener = FactorScreener()

        # 选股：低估值
        result = screener.screen(
            stock_list=['000001', '600000', ...],
            pe=(0, 20),      # PE 0-20
            pb=(0, 2),       # PB 0-2
            market_cap=(50, 1000)  # 市值50-1000亿
        )

        # 选股：高盈利
        result = screener.screen(
            stock_list=stock_list,
            roe=(15, 100),   # ROE > 15%
        )
    """

    name = "因子选股器"
    description = "基于基本面因子进行选股"
    category = "factor"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 因子数据缓存 {symbol: {factor: value}}
        self._factor_cache = {}

    def screen(
        self,
        stock_list: List[str],
        pe: Tuple[float, float] = None,
        pb: Tuple[float, float] = None,
        ps: Tuple[float, float] = None,
        roe: Tuple[float, float] = None,
        roa: Tuple[float, float] = None,
        market_cap: Tuple[float, float] = None,
        turnover: Tuple[float, float] = None,
        **kwargs
    ) -> ScreeningResult:
        """
        执行因子选股

        参数:
            stock_list: 股票代码列表
            pe: PE范围 (min, max)
            pb: PB范围 (min, max)
            ps: PS范围 (min, max)
            roe: ROE范围 (min, max) 单位：%
            roa: ROA范围 (min, max) 单位：%
            market_cap: 市值范围 (min, max) 单位：亿
            turnover: 换手率范围 (min, max) 单位：%
            **kwargs: 其他参数

        返回:
            ScreeningResult: 选股结果
        """
        logger.info("=" * 60)
        logger.info(f"因子选股: {self.name}")
        logger.info(f"股票数量: {len(stock_list)}")
        logger.info("=" * 60)

        # 验证股票列表
        stock_list = self.validate_stock_list(stock_list)

        # 构建筛选条件
        conditions = {
            'pe': pe,
            'pb': pb,
            'ps': ps,
            'roe': roe,
            'roa': roa,
            'market_cap': market_cap,
            'turnover': turnover,
        }

        # 过滤掉None的条件
        conditions = {k: v for k, v in conditions.items() if v is not None}

        if not conditions:
            raise ValueError("请至少指定一个筛选条件")

        logger.info(f"筛选条件: {list(conditions.keys())}")

        # 获取所有股票的因子数据
        all_factors = self._get_factors_batch(stock_list)

        # 筛选符合条件的股票
        selected = []
        details = {}

        for symbol in stock_list:
            if symbol not in all_factors:
                continue

            factors = all_factors[symbol]

            # 检查是否满足所有条件
            if self._check_conditions(factors, conditions):
                selected.append(symbol)
                details[symbol] = factors

        # 创建结果
        result = self.create_result(
            symbols=selected,
            total_count=len(stock_list),
            details=details
        )

        logger.info(f"选股完成: {len(selected)}/{len(stock_list)}")
        logger.info(f"选股率: {result.get_selection_rate():.2f}%")

        return result

    def _get_factors_batch(self, stock_list: List[str]) -> Dict[str, Dict[str, float]]:
        """
        批量获取股票因子数据

        参数:
            stock_list: 股票代码列表

        返回:
            Dict: {symbol: {factor: value}}
        """
        logger.info("获取股票因子数据...")

        all_factors = {}

        for i, symbol in enumerate(stock_list, 1):
            if i % 50 == 0:
                logger.info(f"进度: {i}/{len(stock_list)}")

            try:
                factors = self._get_stock_factors(symbol)
                if factors:
                    all_factors[symbol] = factors
            except Exception as e:
                logger.debug(f"获取 {symbol} 因子数据失败: {e}")
                continue

        logger.info(f"成功获取 {len(all_factors)}/{len(stock_list)} 只股票的因子数据")

        return all_factors

    def _get_stock_factors(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        获取单只股票的因子数据

        参数:
            symbol: 股票代码

        返回:
            Dict or None: 因子数据字典
        """
        # 检查缓存
        if symbol in self._factor_cache:
            return self._factor_cache[symbol]

        try:
            # 获取个股实时行情
            stock_zh_a_spot_df = ak.stock_zh_a_spot_em()

            # 查找目标股票
            stock_info = stock_zh_a_spot_df[stock_zh_a_spot_df['代码'] == symbol]

            if stock_info.empty:
                return None

            stock_info = stock_info.iloc[0]

            # 提取因子数据
            factors = {
                'pe': self._safe_float(stock_info.get('市盈率-动态', 0)),
                'pb': self._safe_float(stock_info.get('市净率', 0)),
                'ps': self._safe_float(stock_info.get('市销率', 0)),
                'market_cap': self._safe_float(stock_info.get('总市值', 0)) / 100000000,  # 转换为亿
                'turnover': self._safe_float(stock_info.get('换手率', 0)),
            }

            # ROE、ROA需要从财务数据获取（这里简化处理）
            # 实际应用中应该从ak.stock_financial_analysis获取
            factors['roe'] = 0  # 占位
            factors['roa'] = 0  # 占位

            # 缓存
            self._factor_cache[symbol] = factors

            return factors

        except Exception as e:
            logger.debug(f"获取 {symbol} 因子数据失败: {e}")
            return None

    def _check_conditions(
        self,
        factors: Dict[str, float],
        conditions: Dict[str, Tuple[float, float]]
    ) -> bool:
        """
        检查因子是否满足条件

        参数:
            factors: 因子数据
            conditions: 筛选条件

        返回:
            bool: 是否满足所有条件
        """
        for factor_name, (min_val, max_val) in conditions.items():
            factor_value = factors.get(factor_name)

            # 如果因子数据不存在，跳过该股票
            if factor_value is None or factor_value == 0:
                return False

            # 检查范围
            if not (min_val <= factor_value <= max_val):
                return False

        return True

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """
        安全转换为float

        参数:
            value: 原始值
            default: 默认值

        返回:
            float: 转换后的值
        """
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_realtime_data(self) -> Any:
        """
        获取实时行情数据（供外部调用）

        返回:
            DataFrame: 实时行情数据
        """
        try:
            return ak.stock_zh_a_spot_em()
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return None


@register_screener('low_pe')
class LowPEScreener(BaseScreener):
    """
    低PE选股器

    专门筛选低市盈率的股票（价值投资策略）

    使用示例:
        screener = LowPEScreener()
        result = screener.screen(
            stock_list=['000001', '600000', ...],
            max_pe=15  # PE < 15
        )
    """

    name = "低PE选股器"
    description = "筛选低市盈率股票"
    category = "factor"

    def screen(
        self,
        stock_list: List[str],
        max_pe: float = 15,
        min_pe: float = 0,
        **kwargs
    ) -> ScreeningResult:
        """执行选股"""
        # 复用FactorScreener
        factor_screener = FactorScreener(data_manager=self.data_manager)
        return factor_screener.screen(
            stock_list=stock_list,
            pe=(min_pe, max_pe),
            **kwargs
        )


@register_screener('high_market_cap')
class HighMarketCapScreener(BaseScreener):
    """
    大市值选股器

    筛选市值较大的股票（蓝筹股）

    使用示例:
        screener = HighMarketCapScreener()
        result = screener.screen(
            stock_list=['000001', '600000', ...],
            min_market_cap=500  # 市值 > 500亿
        )
    """

    name = "大市值选股器"
    description = "筛选大市值蓝筹股"
    category = "factor"

    def screen(
        self,
        stock_list: List[str],
        min_market_cap: float = 500,
        **kwargs
    ) -> ScreeningResult:
        """执行选股"""
        factor_screener = FactorScreener(data_manager=self.data_manager)
        return factor_screener.screen(
            stock_list=stock_list,
            market_cap=(min_market_cap, 100000),
            **kwargs
        )
