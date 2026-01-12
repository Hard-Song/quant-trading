# -*- coding: utf-8 -*-
"""
策略基类模块
定义所有交易策略的基础接口和通用方法
"""

import backtrader as bt
from typing import Dict, Any
from utils.logger import logger


class BaseStrategy(bt.Strategy):
    """
    交易策略基类

    功能说明：
        1. 定义策略的基本框架
        2. 提供通用方法：买入、卖出、日志记录
        3. 记录交易过程和绩效指标

    所有自定义策略都应该继承此类，并实现以下方法：
        - __init__(): 策略初始化
        - next(): 每个bar都会调用，在这里实现交易逻辑

    生命周期方法（按执行顺序）：
        1. __init__(): 策略开始时调用一次
        2. start(): 回测开始前调用
        3. prenext(): 数据不足时调用
        4. next(): 数据充足时，每个bar调用一次
        5. stop(): 回测结束时调用

    使用示例：
        class MyStrategy(BaseStrategy):
            def __init__(self):
                super().__init__()
                # 初始化指标

            def next(self):
                # 实现交易逻辑
                if self.data.close[0] > self.data.close[-1]:
                    self.buy()
    """

    # 策略参数（可以在运行时动态修改）
    params = (
        ('log_level', 'info'),  # 日志级别
        ('t_plus_one', True),   # 是否启用T+1交易限制（默认启用）
    )

    def __init__(self):
        """
        策略初始化
        """
        super().__init__()

        # 记录交易日期
        self.trade_dates = []

        # 记录订单状态
        self.order = None  # 当前订单
        self.buy_price = None  # 买入价格
        self.buy_comm = None  # 买入手续费

        # T+1交易限制：记录买入日期
        # {持仓索引: 买入日期}
        self.buy_dates = {}

        logger.info(f"策略初始化: {self.__class__.__name__}")
        logger.info(f"T+1限制: {'启用' if self.p.t_plus_one else '禁用'}")

    def start(self):
        """
        回测开始前调用
        """
        logger.info("=" * 60)
        logger.info(f"回测开始 - 策略: {self.__class__.__name__}")
        logger.info(f"初始资金: {self.broker.getvalue():.2f}")
        logger.info("=" * 60)

    def next(self):
        """
        核心方法：每个bar都会调用

        说明：
            1. self.data 是价格数据
            2. self.data.close[0] 当前收盘价
            3. self.data.close[-1] 前一天收盘价
            4. self.data.close[-2] 前两天收盘价
            5. len(self.data) 当前bar索引

        注意：
            子类必须实现此方法
        """
        pass

    def stop(self):
        """
        回测结束时调用
        """
        # 计算最终收益
        final_value = self.broker.getvalue()
        profit = final_value - self.broker.startingcash
        profit_percent = (profit / self.broker.startingcash) * 100

        logger.info("=" * 60)
        logger.info(f"回测结束 - 策略: {self.__class__.__name__}")
        logger.info(f"最终资金: {final_value:.2f}")
        logger.info(f"总收益: {profit:.2f} ({profit_percent:.2f}%)")
        logger.info(f"交易次数: {len(self.trade_dates)}")
        logger.info("=" * 60)

    def notify_order(self, order):
        """
        订单状态变化通知

        参数:
            order: Backtrader的订单对象

        订单状态（order.status）：
            - order.Submitted: 订单已提交
            - order.Accepted: 订单已接受
            - order.Completed: 订单已完成
            - order.Canceled: 订单已取消
            - order.Margin: 保证金不足
            - order.Rejected: 订单被拒绝
        """
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已提交或已接受，等待执行
            return

        if order.status in [order.Completed]:
            # 订单已完成
            if order.isbuy():
                # 买入订单
                self.log(
                    f"买入执行 | "
                    f"价格: {order.executed.price:.2f} | "
                    f"数量: {order.executed.size} | "
                    f"手续费: {order.executed.comm:.2f} | "
                    f"总成本: {order.executed.value:.2f}"
                )
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm

                # T+1限制：记录买入日期
                if self.p.t_plus_one:
                    buy_date = self.data.datetime.date(0)
                    # 使用数据索引作为key
                    # 注意：这里简化处理，实际可能需要更复杂的逻辑
                    self.buy_dates['last_buy'] = buy_date
                    self.log(f"T+1记录: 买入日期 {buy_date}")
            else:
                # 卖出订单
                self.log(
                    f"卖出执行 | "
                    f"价格: {order.executed.price:.2f} | "
                    f"数量: {order.executed.size} | "
                    f"手续费: {order.executed.comm:.2f}"
                )

                # 计算这笔交易的收益
                if self.buy_price is not None:
                    profit = (order.executed.price - self.buy_price) * order.executed.size
                    profit_percent = ((order.executed.price - self.buy_price) / self.buy_price) * 100
                    self.log(
                        f"交易收益: {profit:.2f} ({profit_percent:.2f}%)"
                    )

                # T+1限制：清除买入日期记录
                if self.p.t_plus_one and 'last_buy' in self.buy_dates:
                    del self.buy_dates['last_buy']

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            # 订单失败
            self.log(f"订单失败: {order.getstatusname()}")

        # 重置订单状态
        self.order = None

    def notify_trade(self, trade):
        """
        交易完成通知

        参数:
            trade: Backtrader的交易对象

        说明：
            每当买入和卖出配对完成一个交易周期时调用
        """
        if trade.isclosed:
            # 交易已平仓
            profit = trade.pnl  # 净利润（已扣除手续费）
            profit_percent = (trade.pnl / self.broker.startingcash) * 100

            self.log(
                f"交易平仓 | "
                f"净利润: {profit:.2f} | "
                f"收益率: {profit_percent:.2f}%"
            )

    def log(self, message: str, level: str = "info"):
        """
        记录日志

        参数:
            message: 日志消息
            level: 日志级别
        """
        # 获取当前日期
        current_date = self.data.datetime.date(0)

        # 记录日志
        log_message = f"{current_date} | {message}"

        if level.lower() == "info":
            logger.info(log_message)
        elif level.lower() == "warning":
            logger.warning(log_message)
        elif level.lower() == "error":
            logger.error(log_message)
        elif level.lower() == "debug":
            logger.debug(log_message)
        else:
            logger.info(log_message)

    def buy_signal(self) -> bool:
        """
        买入信号判断（子类可重写）

        返回:
            bool: 是否应该买入
        """
        return False

    def sell_signal(self) -> bool:
        """
        卖出信号判断（子类可重写）

        返回:
            bool: 是否应该卖出
        """
        return False

    def can_sell(self) -> bool:
        """
        检查是否可以卖出（T+1限制）

        返回:
            bool: True=可以卖出，False=不能卖出（T+1限制）

        说明：
            A股T+1交易规则：当天买入的股票，当天不能卖出，只能在下一个交易日及以后卖出
        """
        if not self.p.t_plus_one:
            # 未启用T+1限制
            return True

        if 'last_buy' not in self.buy_dates:
            # 没有买入记录，可以卖出
            return True

        # 获取当前日期和买入日期
        current_date = self.data.datetime.date(0)
        buy_date = self.buy_dates['last_buy']

        # 检查是否是买入当天
        if current_date == buy_date:
            self.log(f"T+1限制: 今天({current_date})买入，今天不能卖出")
            return False

        # 可以卖出
        return True
