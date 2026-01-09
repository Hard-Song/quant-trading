# -*- coding: utf-8 -*-
"""
自定义选股器示例

这是一个示例文件，展示如何创建自己的选股器

使用方法：
    1. 在这个文件中定义你的选股器类
    2. 继承自 BaseScreener
    3. 使用 @register_screener 装饰器注册
    4. 实现 screen 方法
    5. ScreenerManager 会自动发现并加载它
"""

from typing import List, Dict, Tuple
import pandas as pd

from ..base_screener import BaseScreener, ScreeningResult, register_screener
from utils.logger import logger


@register_screener('my_custom')
class MyCustomScreener(BaseScreener):
    """
    自定义选股器示例

    这个示例展示了如何创建一个简单的选股器：
    1. 筛选同时满足以下条件的股票：
       - RSI < 30 (超卖)
       - 成交量 > 5日均量 (放量)
       - 最近3天上涨

    你可以修改这个模板来实现自己的选股逻辑
    """

    name = "自定义选股器"
    description = "自定义选股策略示例"
    category = "custom"

    def screen(
        self,
        stock_list: List[str],
        rsi_threshold: float = 30,
        volume_ratio: float = 1.5,
        up_days: int = 3,
        **kwargs
    ) -> ScreeningResult:
        """
        执行选股

        参数:
            stock_list: 股票代码列表
            rsi_threshold: RSI阈值（默认30）
            volume_ratio: 成交量倍数（默认1.5倍）
            up_days: 连续上涨天数（默认3天）
            **kwargs: 其他参数

        返回:
            ScreeningResult: 选股结果
        """
        logger.info("=" * 60)
        logger.info(f"自定义选股: {self.name}")
        logger.info(f"股票数量: {len(stock_list)}")
        logger.info(f"筛选条件: RSI<{rsi_threshold}, 放量>{volume_ratio}倍, 连续{up_days}天上涨")
        logger.info("=" * 60)

        # 验证股票列表
        stock_list = self.validate_stock_list(stock_list)

        # 筛选符合条件的股票
        selected = []
        details = {}

        for i, symbol in enumerate(stock_list, 1):
            if i % 50 == 0:
                logger.info(f"进度: {i}/{len(stock_list)}")

            try:
                # 获取股票数据
                df = self.get_stock_data(symbol)

                if df.empty or len(df) < 20:
                    continue

                # 检查是否满足条件
                if self._check_conditions(df, rsi_threshold, volume_ratio, up_days):
                    selected.append(symbol)

                    # 保存详细信息
                    details[symbol] = {
                        'rsi': self._calculate_rsi(df['close']).iloc[-1],
                        'volume_ratio': df['volume'].iloc[-1] / df['volume'].iloc[-5:-1].mean(),
                        'close': df['close'].iloc[-1],
                        'change_pct': ((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]) * 100
                    }

            except Exception as e:
                logger.debug(f"分析 {symbol} 失败: {e}")
                continue

        # 创建结果
        result = self.create_result(
            symbols=selected,
            total_count=len(stock_list),
            details=details
        )

        logger.info(f"选股完成: {len(selected)}/{len(stock_list)}")
        logger.info(f"选股率: {result.get_selection_rate():.2f}%")

        return result

    def _check_conditions(
        self,
        df: pd.DataFrame,
        rsi_threshold: float,
        volume_ratio: float,
        up_days: int
    ) -> bool:
        """
        检查是否满足选股条件

        参数:
            df: 股票数据
            rsi_threshold: RSI阈值
            volume_ratio: 成交量倍数
            up_days: 上涨天数

        返回:
            bool: 是否满足条件
        """
        # 1. 检查RSI是否超卖
        rsi = self._calculate_rsi(df['close'])
        if rsi.iloc[-1] >= rsi_threshold:
            return False

        # 2. 检查是否放量
        recent_vol = df['volume'].iloc[-1]
        avg_vol = df['volume'].iloc[-5:-1].mean()
        if recent_vol < avg_vol * volume_ratio:
            return False

        # 3. 检查是否连续上涨
        if len(df) < up_days:
            return False

        recent_prices = df['close'].iloc[-up_days:]
        for i in range(1, len(recent_prices)):
            if recent_prices.iloc[i] <= recent_prices.iloc[i-1]:
                return False

        return True

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi


@register_screener('momentum')
class MomentumScreener(BaseScreener):
    """
    动量选股器

    筛选最近N天涨幅最大的股票（动量策略）

    使用示例:
        screener = MomentumScreener()
        result = screener.screen(
            stock_list=['000001', '600000', ...],
            days=20,      # 最近20天
            top_n=50      # 前50只
        )
    """

    name = "动量选股器"
    description = "筛选涨幅最大的股票（动量策略）"
    category = "custom"

    def screen(
        self,
        stock_list: List[str],
        days: int = 20,
        top_n: int = 50,
        min_change_pct: float = 5.0,
        **kwargs
    ) -> ScreeningResult:
        """
        执行动量选股

        参数:
            stock_list: 股票代码列表
            days: 统计天数
            top_n: 返回前N只股票
            min_change_pct: 最小涨幅百分比
            **kwargs: 其他参数
        """
        logger.info(f"动量选股: 最近{days}天涨幅，前{top_n}只")

        stock_list = self.validate_stock_list(stock_list)

        # 计算每只股票的涨幅
        momentum_list = []

        for symbol in stock_list:
            try:
                df = self.get_stock_data(symbol)

                if df.empty or len(df) < days:
                    continue

                # 计算涨幅
                start_price = df['close'].iloc[-days]
                end_price = df['close'].iloc[-1]
                change_pct = ((end_price - start_price) / start_price) * 100

                if change_pct >= min_change_pct:
                    momentum_list.append({
                        'symbol': symbol,
                        'change_pct': change_pct,
                        'start_price': start_price,
                        'end_price': end_price
                    })

            except Exception as e:
                logger.debug(f"计算 {symbol} 涨幅失败: {e}")
                continue

        # 按涨幅排序，取前N只
        momentum_list.sort(key=lambda x: x['change_pct'], reverse=True)
        top_momentum = momentum_list[:top_n]

        # 提取结果
        selected = [item['symbol'] for item in top_momentum]
        details = {
            item['symbol']: {
                'change_pct': round(item['change_pct'], 2),
                'start_price': round(item['start_price'], 2),
                'end_price': round(item['end_price'], 2)
            }
            for item in top_momentum
        }

        result = self.create_result(
            symbols=selected,
            total_count=len(stock_list),
            details=details
        )

        logger.info(f"动量选股完成: {len(selected)}/{len(stock_list)}")

        return result
