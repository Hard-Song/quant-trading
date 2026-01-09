# -*- coding: utf-8 -*-
"""
MACD策略模块
实现MACD指标交叉策略
"""

import backtrader as bt
from .base_strategy import BaseStrategy
from utils.logger import logger


class MACDStrategy(BaseStrategy):
    """
    MACD交叉策略

    策略原理：
        1. MACD由快线(DIF)、慢线(DEA)和柱状图(MACD)组成
        2. DIF上穿DEA（金叉）→ 买入信号
        3. DIF下穿DEA（死叉）→ 卖出信号
        4. 可选：MACD柱状图由负转正作为买入确认

    策略参数：
        - fast_period: 快线EMA周期（默认12天）
        - slow_period: 慢线EMA周期（默认26天）
        - signal_period: 信号线EMA周期（默认9天）
        - stake: 每次交易数量（默认100股）

    适用场景：
        - 趋势明显的市场
        - 中短期波段操作
        - 比双均线更灵敏，能更早捕捉趋势变化

    优点：
        - 比双均线反应更快，减少滞后
        - MACD是经典指标，信号可靠性较高
        - 能够捕捉趋势的转折点

    缺点：
        - 在震荡市容易产生假信号
        - 需要合理调整参数
        - 无法卖空（A股T+1限制）

    使用示例：
        strategy = MACDStrategy(
            fast_period=12,
            slow_period=26,
            signal_period=9
        )
    """

    params = (
        ('fast_period', 12),      # 快线EMA周期
        ('slow_period', 26),      # 慢线EMA周期
        ('signal_period', 9),     # 信号线周期
        ('stake', 100),           # 每次交易股数
    )

    def __init__(self):
        """
        策略初始化
        """
        super().__init__()

        # 计算MACD指标
        # bt.indicators.MACD: MACD指标
        # period_me1: 快线周期
        # period_me2: 慢线周期
        # period_signal: 信号线周期
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.fast_period,
            period_me2=self.p.slow_period,
            period_signal=self.p.signal_period
        )

        # MACD由三部分组成：
        # 1. macd - DIF线（快线）
        # 2. signal - DEA线（慢线/信号线）
        # 需要手动计算柱状图
        self.macd_hist = self.macd.macd - self.macd.signal

        # 计算交叉信号
        self.crossover = bt.indicators.CrossOver(
            self.macd.macd,
            self.macd.signal
        )

        logger.info(f"MACD策略初始化完成")
        logger.info(f"快线周期: {self.p.fast_period}, 慢线周期: {self.p.slow_period}, 信号线: {self.p.signal_period}")

    def next(self):
        """
        核心交易逻辑
        """
        if self.order:
            return

        # 如果数据不足（MACD需要足够的历史数据），等待
        if len(self.data) < self.p.slow_period + self.p.signal_period:
            return

        # === 买入逻辑 ===
        if not self.position:  # 当前没有持仓
            if self.crossover[0] > 0:  # 金叉：DIF上穿DEA
                # 可选：确认MACD柱状图为正（增强信号）
                if self.macd_hist[0] > 0:
                    self.log(
                        f"MACD金叉 | "
                        f"收盘价: {self.data.close[0]:.2f} | "
                        f"DIF: {self.macd.macd[0]:.4f} | "
                        f"DEA: {self.macd.signal[0]:.4f} | "
                        f"MACD柱: {self.macd_hist[0]:.4f}"
                    )
                    self.order = self.buy(size=self.p.stake)

        # === 卖出逻辑 ===
        else:  # 当前有持仓
            if self.crossover[0] < 0:  # 死叉：DIF下穿DEA
                self.log(
                    f"MACD死叉 | "
                    f"收盘价: {self.data.close[0]:.2f} | "
                    f"DIF: {self.macd.macd[0]:.4f} | "
                    f"DEA: {self.macd.signal[0]:.4f}"
                )
                self.order = self.sell(size=self.position.size)


class MACDWithTrend(BaseStrategy):
    """
    MACD + 趋势过滤策略

    策略改进：
        1. 增加EMA(200)作为长期趋势判断
        2. 只在价格高于EMA200时买入（上升趋势）
        3. 避免在下跌趋势中抄底

    适用场景：
        - 强趋势市场
        - 想要避免逆势交易
    """

    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
        ('trend_period', 200),    # 趋势判断EMA周期
        ('stake', 100),
    )

    def __init__(self):
        super().__init__()

        # 计算MACD
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.fast_period,
            period_me2=self.p.slow_period,
            period_signal=self.p.signal_period
        )

        # 计算交叉信号
        self.crossover = bt.indicators.CrossOver(
            self.macd.macd,
            self.macd.signal
        )

        # 计算长期趋势线
        self.ema_trend = bt.indicators.EMA(
            self.data.close,
            period=self.p.trend_period
        )

        logger.info(f"MACD+趋势策略初始化完成")

    def next(self):
        if self.order:
            return

        # 数据不足时等待
        if len(self.data) < self.p.trend_period:
            return

        # === 买入逻辑 ===
        if not self.position:
            # 金叉 + 价格在趋势线上方
            if self.crossover[0] > 0 and self.data.close[0] > self.ema_trend[0]:
                self.log(
                    f"MACD金叉+上升趋势 | "
                    f"收盘价: {self.data.close[0]:.2f} | "
                    f"趋势线EMA{self.p.trend_period}: {self.ema_trend[0]:.2f}"
                )
                self.order = self.buy(size=self.p.stake)

        # === 卖出逻辑 ===
        else:
            # 死叉 或 跌破趋势线
            if self.crossover[0] < 0 or self.data.close[0] < self.ema_trend[0]:
                self.log(
                    f"卖出信号 | "
                    f"收盘价: {self.data.close[0]:.2f} | "
                    f"趋势线: {self.ema_trend[0]:.2f}"
                )
                self.order = self.sell(size=self.position.size)


class MACDWithRSI(BaseStrategy):
    """
    MACD + RSI组合策略

    策略改进：
        1. MACD判断趋势方向
        2. RSI判断超买超卖
        3. 买入：MACD金叉 + RSI不超买
        4. 卖出：MACD死叉 或 RSI超买

    适用场景：
        - 想要结合趋势和动量
        - 避免在超买时追高
    """

    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
        ('rsi_period', 14),
        ('rsi_overbought', 70),   # RSI超买阈值
        ('rsi_oversold', 30),     # RSI超卖阈值
        ('stake', 100),
    )

    def __init__(self):
        super().__init__()

        # 计算MACD
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.fast_period,
            period_me2=self.p.slow_period,
            period_signal=self.p.signal_period
        )

        # 计算交叉信号
        self.crossover = bt.indicators.CrossOver(
            self.macd.macd,
            self.macd.signal
        )

        # 计算RSI
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=self.p.rsi_period
        )

        logger.info(f"MACD+RSI策略初始化完成")

    def next(self):
        if self.order:
            return

        # 数据不足时等待
        if len(self.data) < max(self.p.slow_period, self.p.rsi_period) + self.p.signal_period:
            return

        # === 买入逻辑 ===
        if not self.position:
            # MACD金叉 + RSI未超买
            if self.crossover[0] > 0 and self.rsi[0] < self.p.rsi_overbought:
                self.log(
                    f"MACD金叉+RSI({self.rsi[0]:.1f}) | "
                    f"收盘价: {self.data.close[0]:.2f}"
                )
                self.order = self.buy(size=self.p.stake)

        # === 卖出逻辑 ===
        else:
            # MACD死叉 或 RSI超买
            if self.crossover[0] < 0 or self.rsi[0] > self.p.rsi_overbought:
                self.log(
                    f"卖出信号 | "
                    f"RSI: {self.rsi[0]:.1f} | "
                    f"收盘价: {self.data.close[0]:.2f}"
                )
                self.order = self.sell(size=self.position.size)
