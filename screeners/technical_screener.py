# -*- coding: utf-8 -*-
"""
技术指标选股器模块
基于技术指标进行选股（RSI、MACD、均线等）
"""

from typing import List, Dict, Tuple, Optional, Any
import pandas as pd
import numpy as np

from .base_screener import BaseScreener, ScreeningResult, register_screener
from utils.logger import logger


@register_screener('technical')
class TechnicalScreener(BaseScreener):
    """
    技术指标选股器

    基于技术指标进行选股，包括：
        - 趋势指标：MA、EMA、MACD
        - 动量指标：RSI、KDJ、CCI
        - 成交量指标：成交量、换手率、OBV
        - 波动率指标：ATR、布林带

    使用示例:
        screener = TechnicalScreener()

        # 选股：RSI超卖
        result = screener.screen(
            stock_list=['000001', '600000', ...],
            rsi=(0, 30),  # RSI < 30 (超卖)
        )

        # 选股：MACD金叉
        result = screener.screen(
            stock_list=stock_list,
            macd_cross='golden'  # MACD金叉
        )

        # 选股：均线多头排列
        result = screener.screen(
            stock_list=stock_list,
            ma_alignment='bullish',  # 多头排列
            ma_short=5,
            ma_long=20
        )
    """

    name = "技术指标选股器"
    description = "基于技术指标进行选股"
    category = "technical"

    def screen(
        self,
        stock_list: List[str],
        rsi: Tuple[float, float] = None,
        macd_cross: str = None,
        ma_alignment: str = None,
        ma_short: int = 5,
        ma_long: int = 20,
        price_above_ma: bool = None,
        ma_period: int = None,
        volume_surge: bool = False,
        volume_ratio: float = 2.0,
        days: int = 20,
        **kwargs
    ) -> ScreeningResult:
        """
        执行技术指标选股

        参数:
            stock_list: 股票代码列表
            rsi: RSI范围 (min, max)
            macd_cross: MACD交叉 ('golden'金叉, 'death'死叉)
            ma_alignment: 均线排列 ('bullish'多头, 'bearish'空头)
            ma_short: 短期均线周期
            ma_long: 长期均线周期
            price_above_ma: 价格是否在均线上方
            ma_period: 均线周期（用于price_above_ma）
            volume_surge: 是否放量
            volume_ratio: 放量倍数
            days: 查看最近N天数据
            **kwargs: 其他参数

        返回:
            ScreeningResult: 选股结果
        """
        logger.info("=" * 60)
        logger.info(f"技术指标选股: {self.name}")
        logger.info(f"股票数量: {len(stock_list)}")
        logger.info("=" * 60)

        # 验证股票列表
        stock_list = self.validate_stock_list(stock_list)

        # 构建筛选条件
        conditions = {
            'rsi': rsi,
            'macd_cross': macd_cross,
            'ma_alignment': ma_alignment,
            'price_above_ma': price_above_ma,
            'volume_surge': volume_surge,
        }
        conditions = {k: v for k, v in conditions.items() if v is not None}

        if not conditions:
            raise ValueError("请至少指定一个筛选条件")

        logger.info(f"筛选条件: {list(conditions.keys())}")

        # 筛选符合条件的股票
        selected = []
        details = {}

        for i, symbol in enumerate(stock_list, 1):
            if i % 50 == 0:
                logger.info(f"进度: {i}/{len(stock_list)}")

            try:
                # 获取数据
                df = self.get_stock_data(symbol)

                if df.empty or len(df) < days:
                    continue

                # 获取最近N天的数据
                recent_df = df.tail(days)

                # 计算技术指标
                indicators = self._calculate_indicators(recent_df, ma_short, ma_long, ma_period)

                # 检查是否满足条件
                if self._check_technical_conditions(indicators, conditions, volume_ratio):
                    selected.append(symbol)
                    details[symbol] = indicators

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

    def _calculate_indicators(
        self,
        df: pd.DataFrame,
        ma_short: int,
        ma_long: int,
        ma_period: int
    ) -> Dict[str, Any]:
        """
        计算技术指标

        参数:
            df: 价格数据
            ma_short: 短期均线周期
            ma_long: 长期均线周期
            ma_period: 均线周期

        返回:
            Dict: 技术指标字典
        """
        indicators = {}

        # RSI
        if len(df) >= 14:
            rsi = self._calculate_rsi(df['close'], 14)
            indicators['rsi'] = rsi.iloc[-1] if not rsi.empty else 50

        # MACD
        if len(df) >= 26:
            macd_data = self._calculate_macd(df['close'])
            indicators['macd'] = macd_data['macd'].iloc[-1] if not macd_data['macd'].empty else 0
            indicators['macd_signal'] = macd_data['signal'].iloc[-1] if not macd_data['signal'].empty else 0
            indicators['macd_hist'] = macd_data['hist'].iloc[-1] if not macd_data['hist'].empty else 0

            # 判断金叉死叉
            if len(macd_data['hist']) >= 2:
                hist_prev = macd_data['hist'].iloc[-2]
                hist_curr = macd_data['hist'].iloc[-1]
                if hist_prev <= 0 and hist_curr > 0:
                    indicators['macd_cross'] = 'golden'
                elif hist_prev >= 0 and hist_curr < 0:
                    indicators['macd_cross'] = 'death'

        # 均线
        if len(df) >= ma_long:
            ma_short_line = df['close'].rolling(window=ma_short).mean()
            ma_long_line = df['close'].rolling(window=ma_long).mean()

            indicators['ma_short'] = ma_short_line.iloc[-1]
            indicators['ma_long'] = ma_long_line.iloc[-1]
            indicators['close'] = df['close'].iloc[-1]

            # 判断均线排列
            if ma_short_line.iloc[-1] > ma_long_line.iloc[-1]:
                indicators['ma_alignment'] = 'bullish'  # 多头
            else:
                indicators['ma_alignment'] = 'bearish'  # 空头

        # 单条均线
        if ma_period and len(df) >= ma_period:
            ma = df['close'].rolling(window=ma_period).mean()
            indicators['ma'] = ma.iloc[-1]
            indicators['close'] = df['close'].iloc[-1]
            indicators['price_above_ma'] = indicators['close'] > indicators['ma']

        # 成交量
        if 'volume' in df.columns and len(df) >= 5:
            vol_avg = df['volume'].rolling(window=5).mean()
            vol_current = df['volume'].iloc[-1]
            indicators['volume'] = vol_current
            indicators['volume_avg'] = vol_avg.iloc[-1] if not vol_avg.empty else 0
            indicators['volume_ratio'] = vol_current / indicators['volume_avg'] if indicators['volume_avg'] > 0 else 0

        return indicators

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices: pd.Series, fast=12, slow=26, signal=9):
        """计算MACD指标"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_hist = macd - macd_signal

        return {
            'macd': macd,
            'signal': macd_signal,
            'hist': macd_hist
        }

    def _check_technical_conditions(
        self,
        indicators: Dict[str, Any],
        conditions: Dict[str, Any],
        volume_ratio: float
    ) -> bool:
        """
        检查技术指标是否满足条件

        参数:
            indicators: 技术指标数据
            conditions: 筛选条件
            volume_ratio: 放量倍数

        返回:
            bool: 是否满足所有条件
        """
        # RSI条件
        if 'rsi' in conditions:
            rsi_range = conditions['rsi']
            rsi_value = indicators.get('rsi', 50)
            if not (rsi_range[0] <= rsi_value <= rsi_range[1]):
                return False

        # MACD金叉死叉
        if 'macd_cross' in conditions:
            cross_type = conditions['macd_cross']
            actual_cross = indicators.get('macd_cross')
            if actual_cross != cross_type:
                return False

        # 均线排列
        if 'ma_alignment' in conditions:
            alignment = conditions['ma_alignment']
            actual_alignment = indicators.get('ma_alignment')
            if actual_alignment != alignment:
                return False

        # 价格在均线上方/下方
        if 'price_above_ma' in conditions:
            above = conditions['price_above_ma']
            actual_above = indicators.get('price_above_ma', False)
            if actual_above != above:
                return False

        # 放量
        if 'volume_surge' in conditions and conditions['volume_surge']:
            vol_ratio = indicators.get('volume_ratio', 0)
            if vol_ratio < volume_ratio:
                return False

        return True


@register_screener('oversold')
class OverSoldScreener(BaseScreener):
    """
    超卖选股器

    筛选RSI超卖的股票（可能反弹）

    使用示例:
        screener = OverSoldScreener()
        result = screener.screen(
            stock_list=['000001', '600000', ...],
            rsi_threshold=30  # RSI < 30
        )
    """

    name = "超卖选股器"
    description = "筛选RSI超卖股票"
    category = "technical"

    def screen(
        self,
        stock_list: List[str],
        rsi_threshold: float = 30,
        **kwargs
    ) -> ScreeningResult:
        """执行选股"""
        technical_screener = TechnicalScreener(data_manager=self.data_manager)
        return technical_screener.screen(
            stock_list=stock_list,
            rsi=(0, rsi_threshold),
            **kwargs
        )


@register_screener('golden_cross')
class GoldenCrossScreener(BaseScreener):
    """
    金叉选股器

    筛选MACD金叉或短期均线上穿长期均线的股票

    使用示例:
        screener = GoldenCrossScreener()
        result = screener.screen(
            stock_list=['000001', '600000', ...]
        )
    """

    name = "金叉选股器"
    description = "筛选金叉形态股票"
    category = "technical"

    def screen(
        self,
        stock_list: List[str],
        cross_type: str = 'macd',  # 'macd' or 'ma'
        ma_short: int = 5,
        ma_long: int = 20,
        **kwargs
    ) -> ScreeningResult:
        """执行选股"""
        if cross_type == 'macd':
            technical_screener = TechnicalScreener(data_manager=self.data_manager)
            return technical_screener.screen(
                stock_list=stock_list,
                macd_cross='golden',
                **kwargs
            )
        else:  # MA金叉
            # TODO: 实现MA金叉逻辑
            raise NotImplementedError("MA金叉暂未实现")
