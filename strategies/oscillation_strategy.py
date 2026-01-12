# -*- coding: utf-8 -*-
"""
短期高频震荡策略模块
高风险策略，适合震荡市场，频繁交易
"""

import backtrader as bt
from .base_strategy import BaseStrategy
from utils.logger import logger


class HighFrequencyOscillation(BaseStrategy):
    """
    高频震荡策略

    策略特点：
        1. 短期操作，持仓周期3-10天
        2. 高风险高收益，允许20%止损
        3. 结合多个震荡指标：RSI、布林带、KDJ
        4. 强制交易频率：至少3天一次交易

    适用场景：
        - 横盘震荡市场
        - 波动率适中的股票
        - 不适合单边趋势市场

    风险提示：
        - 高频交易导致手续费累积
        - 震荡假信号可能造成频繁止损
        - 需要严格执行止损纪律
    """

    params = (
        # RSI参数（短期）
        ('rsi_period', 6),          # RSI周期（短期）
        ('rsi_oversold', 30),       # RSI超卖阈值
        ('rsi_overbought', 70),     # RSI超买阈值

        # 布林带参数
        ('bb_period', 10),          # 布林带周期
        ('bb_dev', 2.0),            # 布林带标准差倍数

        # KDJ参数
        ('kdj_period', 9),          # KDJ周期
        ('kdj_k_period', 3),        # K值平滑周期
        ('kdj_d_period', 3),        # D值平滑周期

        # 止损止盈
        ('stop_loss', 0.20),        # 止损：20%
        ('quick_profit', 0.05),     # 快速止盈：5%
        ('target_profit', 0.10),    # 目标止盈：10%

        # 交易频率控制
        ('min_trade_interval', 3),  # 最小交易间隔（天）
        ('max_hold_days', 10),      # 最大持仓天数

        # 交易数量
        ('stake', 200),             # 每次交易股数（增加到200股）
    )

    def __init__(self):
        """策略初始化"""
        super().__init__()

        # === 计算指标 ===

        # 1. RSI指标（短期，超买超卖）
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=self.p.rsi_period
        )

        # 2. 布林带（判断价格波动范围）
        self.bollinger = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.bb_period,
            devfactor=self.p.bb_dev
        )

        # 3. KDJ指标（Stochastic的变种）
        self.stoch = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_period,
            period_dfast=self.p.kdj_d_period
        )
        # KDJ的K线和D线
        self.kdj_k = self.stoch.percK
        self.kdj_d = self.stoch.percD

        # 4. 成交量移动平均
        self.volume_ma = bt.indicators.SMA(
            self.data.volume,
            period=5
        )

        # === 交易状态记录 ===
        self.buy_bar = 0  # 买入时的bar索引
        self.hold_days = 0  # 持仓天数
        self.last_trade_bar = 0  # 上次交易的bar索引

        logger.info(f"高频震荡策略初始化完成")
        logger.info(f"RSI({self.p.rsi_period}): {self.p.rsi_oversold}/{self.p.rsi_overbought}")
        logger.info(f"布林带({self.p.bb_period}, {self.p.bb_dev})")
        logger.info(f"止损: {self.p.stop_loss*100}%, 止盈: {self.p.quick_profit*100}%/{self.p.target_profit*100}%")

    def next(self):
        """核心交易逻辑"""
        # 如果有未完成的订单，等待执行
        if self.order:
            return

        # 检查最小交易间隔
        bars_since_last_trade = len(self.data) - self.last_trade_bar
        if bars_since_last_trade < self.p.min_trade_interval and self.position:
            # 如果有持仓且未达到最小间隔，继续持有
            pass

        # === 买入逻辑 ===
        if not self.position:
            # 当前没有持仓，寻找买入机会

            # 买入条件（需要同时满足）：
            # 1. RSI超卖（< 30）
            # 2. 价格触及布林带下轨
            # 3. KDJ金叉（K上穿D）
            # 4. 成交量放大

            rsi_oversold = self.rsi[0] < self.p.rsi_oversold
            price_at_lower = self.data.close[0] <= self.bollinger.lines.bot[0]
            kdj_golden_cross = self.kdj_k[0] > self.kdj_d[0] and self.kdj_k[-1] <= self.kdj_d[-1]
            volume_high = self.data.volume[0] > self.volume_ma[0]

            if rsi_oversold and price_at_lower and kdj_golden_cross and volume_high:
                self.log(
                    f"买入信号 | "
                    f"收盘价: {self.data.close[0]:.2f} | "
                    f"RSI: {self.rsi[0]:.1f} | "
                    f"布林下轨: {self.bollinger.lines.bot[0]:.2f} | "
                    f"KDJ: {self.kdj_k[0]:.1f}/{self.kdj_d[0]:.1f} | "
                    f"成交量: {self.data.volume[0]:.0f}"
                )

                self.order = self.buy(size=self.p.stake)
                self.buy_bar = len(self.data)
                self.hold_days = 0

        # === 卖出逻辑 ===
        else:
            # 当前有持仓，检查卖出条件

            # 检查T+1限制
            if not self.can_sell():
                return

            # 计算持仓天数
            self.hold_days = len(self.data) - self.buy_bar

            # 计算当前盈亏
            buy_price = self.buy_price if self.buy_price else self.data.close[0]
            profit_pct = (self.data.close[0] - buy_price) / buy_price

            # 卖出条件（满足任一即可）：
            # 1. 止损：亏损达到20%
            # 2. 快速止盈：盈利达到5%（震荡市场快速兑现）
            # 3. 目标止盈：盈利达到10%
            # 4. 技术卖出：RSI超买且价格触及布林带上轨
            # 5. 超过最大持仓天数

            hit_stop_loss = profit_pct <= -self.p.stop_loss
            hit_quick_profit = profit_pct >= self.p.quick_profit
            hit_target_profit = profit_pct >= self.p.target_profit

            rsi_overbought = self.rsi[0] > self.p.rsi_overbought
            price_at_upper = self.data.close[0] >= self.bollinger.lines.top[0]
            technical_sell = rsi_overbought and price_at_upper

            exceed_hold_days = self.hold_days >= self.p.max_hold_days

            sell_reason = None
            if hit_stop_loss:
                sell_reason = f"止损({profit_pct*100:.2f}%)"
            elif hit_target_profit:
                sell_reason = f"目标止盈({profit_pct*100:.2f}%)"
            elif hit_quick_profit:
                # 快速止盈需要额外确认：RSI不再极度超卖
                if self.rsi[0] > 40:
                    sell_reason = f"快速止盈({profit_pct*100:.2f}%)"
            elif technical_sell:
                sell_reason = f"技术卖出(RSI:{self.rsi[0]:.1f})"
            elif exceed_hold_days:
                sell_reason = f"超期({self.hold_days}天)"

            if sell_reason:
                self.log(
                    f"卖出信号: {sell_reason} | "
                    f"收盘价: {self.data.close[0]:.2f} | "
                    f"买入价: {buy_price:.2f} | "
                    f"持仓天数: {self.hold_days}"
                )

                self.order = self.sell(size=self.position.size)
                self.last_trade_bar = len(self.data)


class AggressiveOscillation(BaseStrategy):
    """
    超激进震荡策略

    相比HighFrequencyOscillation更加激进：
        1. 使用更短的指标周期
        2. 更宽松的入场条件
        3. 更高的交易频率
        4. 允许更大的亏损

    适合：
        - 经验丰富的交易者
        - 能承受高风险的投资者
        - 有时间密切监控市场的交易者
    """

    params = (
        # 更激进的RSI参数
        ('rsi_period', 5),          # 极短期RSI
        ('rsi_oversold', 35),       # 更宽松的超卖阈值
        ('rsi_overbought', 65),     # 更宽松的超买阈值

        # 更激进的布林带
        ('bb_period', 8),           # 更短周期
        ('bb_dev', 1.5),            # 更窄的带宽

        # 更大的止损空间
        ('stop_loss', 0.20),        # 20%止损
        ('quick_profit', 0.03),     # 3%快速止盈
        ('target_profit', 0.08),    # 8%目标止盈

        # 更短的交易间隔
        ('min_trade_interval', 2),  # 最小2天
        ('max_hold_days', 7),       # 最多持仓7天

        ('stake', 200),             # 交易股数
    )

    def __init__(self):
        """初始化"""
        super().__init__()

        # RSI
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=self.p.rsi_period
        )

        # 布林带
        self.bollinger = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.bb_period,
            devfactor=self.p.bb_dev
        )

        # KDJ
        self.stoch = bt.indicators.Stochastic(self.data, period=9, period_dfast=3)
        self.kdj_k = self.stoch.percK
        self.kdj_d = self.stoch.percD

        # 成交量
        self.volume_ma = bt.indicators.SMA(self.data.volume, period=5)

        # 状态记录
        self.buy_bar = 0
        self.hold_days = 0
        self.last_trade_bar = 0

        logger.info(f"超激进震荡策略初始化完成")
        logger.info(f"极短期RSI({self.p.rsi_period}), 布林带({self.p.bb_period})")

    def next(self):
        """交易逻辑"""
        if self.order:
            return

        # 买入条件（更宽松）
        if not self.position:
            # 只需满足两个条件即可买入
            conditions_met = 0

            # 条件1：RSI超卖
            if self.rsi[0] < self.p.rsi_oversold:
                conditions_met += 1

            # 条件2：价格接近布林带下轨
            if self.data.close[0] < self.bollinger.lines.bot[0] * 1.02:
                conditions_met += 1

            # 条件3：KDJ金叉
            if self.kdj_k[0] > self.kdj_d[0]:
                conditions_met += 1

            # 条件4：成交量放大
            if self.data.volume[0] > self.volume_ma[0] * 1.2:
                conditions_met += 1

            # 至少满足3个条件
            if conditions_met >= 3:
                self.log(
                    f"激进买入 | 收盘价: {self.data.close[0]:.2f} | "
                    f"RSI: {self.rsi[0]:.1f} | 满足{conditions_met}个条件"
                )
                self.order = self.buy(size=self.p.stake)
                self.buy_bar = len(self.data)
                self.hold_days = 0

        # 卖出条件
        else:
            if not self.can_sell():
                return

            self.hold_days = len(self.data) - self.buy_bar
            buy_price = self.buy_price if self.buy_price else self.data.close[0]
            profit_pct = (self.data.close[0] - buy_price) / buy_price

            # 止损止盈检查
            if profit_pct <= -self.p.stop_loss:
                self.order = self.sell(size=self.position.size)
                self.log(f"止损卖出 | 亏损: {profit_pct*100:.2f}%")
            elif profit_pct >= self.p.target_profit:
                self.order = self.sell(size=self.position.size)
                self.log(f"目标止盈 | 盈利: {profit_pct*100:.2f}%")
            elif profit_pct >= self.p.quick_profit and self.rsi[0] > 50:
                self.order = self.sell(size=self.position.size)
                self.log(f"快速止盈 | 盈利: {profit_pct*100:.2f}%")
            elif self.hold_days >= self.p.max_hold_days:
                self.order = self.sell(size=self.position.size)
                self.log(f"到期平仓 | 持仓{self.hold_days}天")
            elif self.rsi[0] > self.p.rsi_overbought and self.data.close[0] > self.bollinger.lines.top[0]:
                self.order = self.sell(size=self.position.size)
                self.log(f"技术卖出 | RSI超买")


class UltraAggressiveOscillation(BaseStrategy):
    """
    极激进震荡策略（UltraAggressive - 方案1）

    策略特点：
        1. 极短期RSI(3)捕捉快速反转
        2. 极宽松入场条件（2/5即可）
        3. 允许连续交易（0天间隔）
        4. 更大止损空间(25%)换取更高胜率
        5. 3-5%快速止盈，短线兑现

    风险等级：⚠️⚠️⚠️ 极高风险
        - 可能频繁触发止损
        - 手续费侵蚀利润
        - 需要极强的心理承受能力

    适合场景：
        - 高波动股票
        - 震荡明显的市场
        - 能承受高风险的投资者
    """

    params = (
        # 极短期RSI参数（调整为避免除零）
        ('rsi_period', 5),          # RSI（5天，更稳定）
        ('rsi_oversold', 40),       # 极宽松的超卖阈值
        ('rsi_overbought', 60),     # 极宽松的超买阈值

        # 布林带参数（调整为避免除零）
        ('bb_period', 6),           # 短期布林带（至少6天）
        ('bb_dev', 1.5),            # 较窄的带宽

        # KDJ参数
        ('kdj_period', 9),
        ('kdj_k_period', 3),
        ('kdj_d_period', 3),

        # 止损止盈（方案1）
        ('stop_loss', 0.25),        # 25%止损（允许更大亏损）
        ('quick_profit', 0.03),     # 3%快速止盈
        ('target_profit', 0.05),    # 5%目标止盈

        # 交易频率控制（极激进）
        ('min_trade_interval', 0),  # 0天间隔（允许连续交易）
        ('max_hold_days', 5),       # 最多持仓5天（快进快出）

        # 交易数量
        ('stake', 300),             # 增加到300股（提高资金利用率）
    )

    def __init__(self):
        """策略初始化"""
        super().__init__()

        # RSI（极短期）
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=self.p.rsi_period
        )

        # 布林带（极短期）
        self.bollinger = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.bb_period,
            devfactor=self.p.bb_dev
        )

        # KDJ
        self.stoch = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_period,
            period_dfast=self.p.kdj_d_period
        )
        self.kdj_k = self.stoch.percK
        self.kdj_d = self.stoch.percD

        # 成交量
        self.volume_ma = bt.indicators.SMA(self.data.volume, period=5)

        # 状态记录
        self.buy_bar = 0
        self.hold_days = 0
        self.last_trade_bar = 0
        self.consecutive_losses = 0  # 连续亏损次数

        logger.info(f"极激进震荡策略初始化完成")
        logger.info(f"短期RSI({self.p.rsi_period}), 布林带({self.p.bb_period})")
        logger.info(f"止损25%, 快速止盈3%, 目标止盈5%")
        logger.info(f"极高风险警告：可能频繁交易")

    def next(self):
        """核心交易逻辑"""
        if self.order:
            return

        # === 买入逻辑 ===
        if not self.position:
            # 极宽松入场条件：5个条件中满足2个即可
            conditions_met = 0
            signals = []

            # 条件1：RSI偏低（< 40）
            if self.rsi[0] < self.p.rsi_oversold:
                conditions_met += 1
                signals.append(f"RSI({self.rsi[0]:.1f})")

            # 条件2：价格低于布林带中轨
            if self.data.close[0] < self.bollinger.lines.mid[0]:
                conditions_met += 1
                signals.append("价格低于中轨")

            # 条件3：KDJ金叉或K值上升
            if self.kdj_k[0] > self.kdj_d[0] or self.kdj_k[0] > self.kdj_k[-1]:
                conditions_met += 1
                signals.append("KDJ信号")

            # 条件4：成交量高于均值
            if self.data.volume[0] > self.volume_ma[0]:
                conditions_met += 1
                signals.append("成交量放大")

            # 只需满足2个条件即可买入（极宽松）
            if conditions_met >= 2:
                # 检查交易间隔（允许0天，即连续交易）
                bars_since_last = len(self.data) - self.last_trade_bar
                if bars_since_last >= self.p.min_trade_interval:
                    self.log(
                        f"极激进买入 | 价格: {self.data.close[0]:.2f} | "
                        f"RSI: {self.rsi[0]:.1f} | "
                        f"信号: {', '.join(signals)} | "
                        f"满足{conditions_met}/5条件"
                    )
                    self.order = self.buy(size=self.p.stake)
                    self.buy_bar = len(self.data)
                    self.hold_days = 0

        # === 卖出逻辑 ===
        else:
            # T+1检查
            if not self.can_sell():
                return

            self.hold_days = len(self.data) - self.buy_bar
            buy_price = self.buy_price if self.buy_price else self.data.close[0]
            profit_pct = (self.data.close[0] - buy_price) / buy_price

            # 多重卖出条件（优先级从高到低）

            # 1. 硬止损：25%止损（保护性止损）
            if profit_pct <= -self.p.stop_loss:
                self.log(
                    f"硬止损 | 亏损: {profit_pct*100:.2f}% | "
                    f"持仓{self.hold_days}天"
                )
                self.order = self.sell(size=self.position.size)
                self.consecutive_losses += 1
                return

            # 2. 目标止盈：5%立即兑现
            if profit_pct >= self.p.target_profit:
                self.log(
                    f"目标止盈 | 盈利: {profit_pct*100:.2f}% | "
                    f"持仓{self.hold_days}天"
                )
                self.order = self.sell(size=self.position.size)
                self.consecutive_losses = 0
                return

            # 3. 快速止盈：3% + RSI不再超卖
            if profit_pct >= self.p.quick_profit and self.rsi[0] > 45:
                self.log(
                    f"快速止盈 | 盈利: {profit_pct*100:.2f}% | "
                    f"RSI: {self.rsi[0]:.1f}"
                )
                self.order = self.sell(size=self.position.size)
                self.consecutive_losses = 0
                return

            # 4. 技术卖出：RSI超买 + 价格触及布林带上轨
            if self.rsi[0] > self.p.rsi_overbought and self.data.close[0] > self.bollinger.lines.top[0]:
                self.log(
                    f"技术卖出 | RSI超买({self.rsi[0]:.1f}) | "
                    f"盈利: {profit_pct*100:.2f}%"
                )
                self.order = self.sell(size=self.position.size)
                return

            # 5. 时间止损：持仓超过5天
            if self.hold_days >= self.p.max_hold_days:
                if profit_pct > 0:
                    self.log(
                        f"时间止损(盈利) | 盈利: {profit_pct*100:.2f}% | "
                        f"持仓{self.hold_days}天"
                    )
                else:
                    self.log(
                        f"时间止损(亏损) | 亏损: {abs(profit_pct)*100:.2f}% | "
                        f"持仓{self.hold_days}天"
                    )
                self.order = self.sell(size=self.position.size)
                return

            # 6. 动态止损：回撤超过峰值的一半
            # （记录最高价，如果从最高点回撤超过一定比例则卖出）
            # 这里简化为：如果盈利超过2%后回撤到1%以下
            if profit_pct > 0.02 and profit_pct < 0.01:
                self.log(
                    f"动态止损 | 盈利回撤到: {profit_pct*100:.2f}%"
                )
                self.order = self.sell(size=self.position.size)
                return


# ==================== 测试代码 ====================
if __name__ == "__main__":
    """
    测试震荡策略
    """
    from data.data_feed import AStockDataFeed
    from core.backtest_engine import BacktestEngine
    from utils.logger import logger

    logger.info("=== 震荡策略测试 ===")

    # 获取数据
    data_feed = AStockDataFeed()
    df = data_feed.get_stock_data(
        symbol="002202",
        start_date="2024-01-01",
        end_date="2025-01-12"
    )

    if df.empty:
        logger.error("数据获取失败")
        exit(1)

    # 测试高频震荡策略
    logger.info("\n【测试1】高频震荡策略")
    engine = BacktestEngine(initial_cash=100000, use_a_stock_comm=True)
    engine.add_data(df)
    engine.add_strategy(HighFrequencyOscillation)
    result = engine.run()

    logger.info(f"\n{result}")

    # 测试超激进策略
    logger.info("\n【测试2】超激进震荡策略")
    engine2 = BacktestEngine(initial_cash=100000, use_a_stock_comm=True)
    engine2.add_data(df)
    engine2.add_strategy(AggressiveOscillation)
    result2 = engine2.run()

    logger.info(f"\n{result2}")
