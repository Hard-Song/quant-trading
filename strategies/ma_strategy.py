# -*- coding: utf-8 -*-
"""
双均线策略模块
实现经典的移动平均线交叉策略
"""

import backtrader as bt
from .base_strategy import BaseStrategy
from utils.logger import logger


class DualMovingAverage(BaseStrategy):
    """
    双均线交叉策略

    策略原理：
        1. 计算两条移动平均线：快线（短期）和慢线（长期）
        2. 当快线从下向上穿过慢线时（金叉），买入信号
        3. 当快线从上向下穿过慢线时（死叉），卖出信号

    策略参数：
        - fast_period: 快线周期（默认5天）
        - slow_period: 慢线周期（默认20天）
        - stake: 每次交易数量（默认100股=1手）

    适用场景：
        - 趋势明显的市场
        - 价格波动较大的股票
        - 不适合震荡市场（会产生频繁交易）

    优点：
        - 逻辑简单，容易理解
        - 能捕捉中期趋势
        - 在趋势行情中效果较好

    缺点：
        - 在震荡市场容易产生频繁交易（亏损）
        - 存在滞后性（MA是滞后指标）
        - 无法卖空（A股T+1限制）

    使用示例：
        strategy = DualMovingAverage(
            fast_period=5,
            slow_period=20,
            stake=100
        )
    """

    # 策略参数
    params = (
        ('fast_period', 5),      # 快线周期
        ('slow_period', 20),     # 慢线周期
        ('stake', 100),          # 每次交易股数
    )

    def __init__(self):
        """
        策略初始化

        说明：
            1. 调用父类初始化
            2. 计算移动平均线
            3. 计算交叉信号
        """
        # 调用父类初始化
        super().__init__()

        # 计算快线（短期移动平均）
        # bt.indicators.SMA: 简单移动平均线
        self.ma_fast = bt.indicators.SMA(
            self.data.close,
            period=self.p.fast_period
        )

        # 计算慢线（长期移动平均）
        self.ma_slow = bt.indicators.SMA(
            self.data.close,
            period=self.p.slow_period
        )

        # 计算交叉信号
        # bt.indicators.CrossOver: 交叉指标
        # - > 0: 快线向上穿过慢线（金叉）
        # - < 0: 快线向下穿过慢线（死叉）
        # - = 0: 无交叉
        self.crossover = bt.indicators.CrossOver(
            self.ma_fast,
            self.ma_slow
        )

        # 添加指标到图表（可选）
        # 这样在可视化时会显示这些指标
        bt.indicators.SMA(self.data.close, period=self.p.fast_period, subplot=False)
        bt.indicators.SMA(self.data.close, period=self.p.slow_period, subplot=False)

        logger.info(f"双均线策略初始化完成")
        logger.info(f"快线周期: {self.p.fast_period}, 慢线周期: {self.p.slow_period}")

    def next(self):
        """
        核心交易逻辑

        说明：
            每个bar都会调用此方法，在这里实现买卖逻辑
        """
        # 如果有未完成的订单，等待执行
        if self.order:
            return

        # === 买入逻辑 ===
        if not self.position:  # 当前没有持仓
            if self.crossover[0] > 0:  # 金叉：快线从下向上穿过慢线
                self.log(
                    f"金叉出现 | "
                    f"收盘价: {self.data.close[0]:.2f} | "
                    f"快线(MA{self.p.fast_period}): {self.ma_fast[0]:.2f} | "
                    f"慢线(MA{self.p.slow_period}): {self.ma_slow[0]:.2f}"
                )

                # 执行买入
                # size: 买入数量
                self.order = self.buy(size=self.p.stake)

        # === 卖出逻辑 ===
        else:  # 当前有持仓
            if self.crossover[0] < 0:  # 死叉：快线从上向下穿过慢线
                self.log(
                    f"死叉出现 | "
                    f"收盘价: {self.data.close[0]:.2f} | "
                    f"快线(MA{self.p.fast_period}): {self.ma_fast[0]:.2f} | "
                    f"慢线(MA{self.p.slow_period}): {self.ma_slow[0]:.2f}"
                )

                # 执行卖出
                # size: 卖出数量（卖出全部持仓）
                self.order = self.sell(size=self.position.size)


# ==================== 策略变体 ====================
class DualMovingAverageWithVolatility(BaseStrategy):
    """
    带波动率过滤的双均线策略

    策略改进：
        1. 增加ATR（平均真实波幅）指标作为市场波动率衡量
        2. 只有当波动率低于某个阈值时才交易
        3. 避免在剧烈波动的市场中交易

    适用场景：
        - 想要避免高波动风险
        - 更稳健的交易风格
    """

    params = (
        ('fast_period', 5),
        ('slow_period', 20),
        ('atr_period', 14),       # ATR周期
        ('atr_threshold', 0.05),  # ATR阈值（相对于价格的百分比）
        ('stake', 100),
    )

    def __init__(self):
        super().__init__()

        # 计算均线
        self.ma_fast = bt.indicators.SMA(self.data.close, period=self.p.fast_period)
        self.ma_slow = bt.indicators.SMA(self.data.close, period=self.p.slow_period)
        self.crossover = bt.indicators.CrossOver(self.ma_fast, self.ma_slow)

        # 计算ATR（平均真实波幅）
        # ATR衡量市场波动性，值越大表示波动越剧烈
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)

    def next(self):
        if self.order:
            return

        # 计算当前波动率（ATR相对于价格的百分比）
        current_volatility = self.atr[0] / self.data.close[0]

        # 买入逻辑
        if not self.position:
            if self.crossover[0] > 0 and current_volatility < self.p.atr_threshold:
                self.log(
                    f"金叉+低波动 | "
                    f"收盘价: {self.data.close[0]:.2f} | "
                    f"波动率: {current_volatility:.4f}"
                )
                self.order = self.buy(size=self.p.stake)

        # 卖出逻辑
        else:
            if self.crossover[0] < 0:
                self.log(f"死叉 | 卖出全部持仓")
                self.order = self.sell(size=self.position.size)
