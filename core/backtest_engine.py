# -*- coding: utf-8 -*-
"""
回测引擎模块
封装Backtrader的Cerebro引擎，提供简洁的回测接口
"""

import backtrader as bt
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Type, Dict, Any, Optional
from dataclasses import dataclass
from utils.logger import logger
from utils.config import config
from core.commission_scheme import get_a_stock_commission


@dataclass
class BacktestResult:
    """
    回测结果数据类

    属性说明：
        - initial_cash: 初始资金
        - final_value: 最终资金
        - total_return: 总收益率
        - total_trades: 总交易次数
        - win_rate: 胜率
        - max_drawdown: 最大回撤
        - sharpe_ratio: 夏普比率
    """
    initial_cash: float
    final_value: float
    total_return: float
    total_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float

    def __str__(self):
        """格式化输出回测结果"""
        return f"""
=== 回测结果汇总 ===
初始资金: {self.initial_cash:.2f}
最终资金: {self.final_value:.2f}
总收益率: {self.total_return:.2f}%
交易次数: {self.total_trades}
胜率: {self.win_rate:.2f}%
最大回撤: {self.max_drawdown:.2f}%
夏普比率: {self.sharpe_ratio:.2f}
"""


class BacktestEngine:
    """
    回测引擎类

    功能说明：
        1. 封装Backtrader的Cerebro引擎
        2. 提供简洁的API来运行回测
        3. 自动处理数据加载、策略设置、绩效分析

    使用流程：
        1. 创建引擎实例
        2. 添加数据
        3. 添加策略
        4. 运行回测
        5. 分析结果

    使用示例：
        # 创建引擎
        engine = BacktestEngine(initial_cash=100000)

        # 添加数据
        engine.add_data(df)

        # 添加策略
        engine.add_strategy(DualMovingAverage, fast_period=5, slow_period=20)

        # 运行回测
        result = engine.run()

        # 显示结果
        print(result)
    """

    def __init__(
        self,
        initial_cash: float = 100000,
        commission: float = 0.0003,
        slippage: float = 0.0001,
        use_a_stock_comm: bool = True,
        stamp_duty: float = 0.001,
        transfer_fee: float = 0.00002,
        market: str = 'sh',
    ):
        """
        初始化回测引擎

        参数:
            initial_cash: 初始资金（默认10万）
            commission: 手续费率（默认万分之3）
            slippage: 滑点（默认万分之一）
            use_a_stock_comm: 是否使用A股真实手续费结构（默认True）
            stamp_duty: 印花税率（默认千分之一，仅卖出收取）
            transfer_fee: 过户费率（默认十万分之二，双向收取）
            market: 市场类型（'sh'=沪市，'sz'=深市）

        说明：
            - 当use_a_stock_comm=True时，使用A股真实手续费结构
              包括佣金（双向，最低5元）+ 印花税（卖出0.1%）+ 过户费（双向）
            - 当use_a_stock_comm=False时，使用简单的比例手续费
            - 滑点是指实际成交价与预期价格的差异
        """
        # 创建Cerebro引擎
        self.cerebro = bt.Cerebro()

        # 设置初始资金
        self.cerebro.broker.setcash(initial_cash)

        # 设置手续费
        if use_a_stock_comm:
            # 使用A股真实手续费结构
            self.cerebro.broker.addcommissioninfo(
                get_a_stock_commission(
                    commission=commission,
                    stamp_duty=stamp_duty,
                    transfer_fee=transfer_fee,
                    market=market,
                )
            )
            logger.info(f"使用A股真实手续费结构")
            logger.info(f"  佣金: {commission*10000:.1f}‰（双向，最低5元）")
            logger.info(f"  印花税: {stamp_duty*100:.2f}%（仅卖出）")
            logger.info(f"  过户费: {transfer_fee*100000:.1f}‱（双向）")
        else:
            # 使用简单的比例手续费
            self.cerebro.broker.setcommission(commission=commission)
            logger.info(f"使用简单手续费: {commission*10000:.1f}‰")

        # 设置滑点
        # 滑点是指实际成交价与预期价格的差异
        self.cerebro.broker.set_slippage_perc(slippage)

        # 记录参数
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage
        self.use_a_stock_comm = use_a_stock_comm

        logger.info(f"回测引擎初始化完成")
        logger.info(f"初始资金: {initial_cash:.2f}, 滑点: {slippage*10000:.1f}‰")

    def add_data(
        self,
        df: pd.DataFrame,
        datetime_column: Optional[str] = None,
        open_col: str = 'open',
        high_col: str = 'high',
        low_col: str = 'low',
        close_col: str = 'close',
        volume_col: str = 'volume',
    ) -> None:
        """
        添加价格数据

        参数:
            df: 包含OHLCV数据的DataFrame
            datetime_column: 日期列名（如果作为索引则不需要指定）
            open_col: 开盘价列名
            high_col: 最高价列名
            low_col: 最低价列名
            close_col: 收盘价列名
            volume_col: 成交量列名

        说明：
            DataFrame必须包含以下列：
            - 开盘价、最高价、最低价、收盘价、成交量
            - 日期必须是datetime类型或作为索引
        """
        # 创建数据源
        data = bt.feeds.PandasData(
            dataname=df,
            datetime=None if datetime_column is None else datetime_column,
            open=open_col,
            high=high_col,
            low=low_col,
            close=close_col,
            volume=volume_col,
        )

        # 添加到Cerebro
        self.cerebro.adddata(data)

        logger.info(f"数据已添加 | 数据范围: {df.index[0]} 到 {df.index[-1]}")
        logger.info(f"数据条数: {len(df)}")

    def add_strategy(self, strategy_class: Type[bt.Strategy], **kwargs) -> None:
        """
        添加策略

        参数:
            strategy_class: 策略类（继承自bt.Strategy）
            **kwargs: 策略参数

        示例:
            engine.add_strategy(
                DualMovingAverage,
                fast_period=5,
                slow_period=20
            )
        """
        self.cerebro.addstrategy(strategy_class, **kwargs)

        logger.info(f"策略已添加: {strategy_class.__name__}")
        logger.info(f"策略参数: {kwargs}")

    def add_analyzer(self, analyzer_class: Type[bt.Analyzer], **kwargs) -> None:
        """
        添加分析器

        参数:
            analyzer_class: 分析器类
            **kwargs: 分析器参数

        常用分析器：
            - bt.analyzers.SharpeRatio: 夏普比率
            - bt.analyzers.DrawDown: 回撤分析
            - bt.analyzers.TradeAnalyzer: 交易分析
        """
        self.cerebro.addanalyzer(analyzer_class, **kwargs)

        logger.info(f"分析器已添加: {analyzer_class.__name__}")

    def run(self) -> BacktestResult:
        """
        运行回测

        返回:
            BacktestResult: 回测结果对象

        说明：
            执行回测并返回绩效指标
        """
        logger.info("=" * 60)
        logger.info("开始回测...")
        logger.info("=" * 60)

        # 添加默认分析器（如果用户没有手动添加）
        # 检查是否已有分析器
        if not self.cerebro.analyzers:
            self._add_default_analyzers()

        # 运行回测
        # cerebro.run() 返回策略列表
        strategies = self.cerebro.run()

        # 获取第一个策略实例
        strategy = strategies[0]

        # 提取回测结果
        result = self._extract_result(strategy)

        logger.info("=" * 60)
        logger.info("回测完成")
        logger.info("=" * 60)

        return result

    def plot(self, save_path: str = None, style: str = 'candlestick') -> None:
        """
        绘制回测结果图表

        参数:
            save_path: 图表保存路径（可选）
            style: 图表样式 ('candlestick' 或 'line')

        说明：
            显示价格、指标、交易信号、持仓价值等
        """
        try:
            # 设置图表样式
            plt.style.use('seaborn-v0_8-darkgrid')

            # 绘制图表
            fig = self.cerebro.plot(style=style, barup='r', bardown='g')[0][0]

            # 保存图表
            if save_path:
                fig.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"图表已保存到: {save_path}")

        except Exception as e:
            logger.error(f"绘制图表失败: {e}")

    def _add_default_analyzers(self) -> None:
        """
        添加默认分析器

        说明：
            自动添加常用的分析器
        """
        # 夏普比率（年化）
        self.cerebro.addanalyzer(
            bt.analyzers.SharpeRatio,
            _name='sharpe',
            timeframe=bt.TimeFrame.Days,
            annualize=True,
            riskfreerate=0.03  # 无风险利率3%
        )

        # 回撤分析
        self.cerebro.addanalyzer(
            bt.analyzers.DrawDown,
            _name='drawdown'
        )

        # 交易分析
        self.cerebro.addanalyzer(
            bt.analyzers.TradeAnalyzer,
            _name='trades'
        )

        # 收益分析
        self.cerebro.addanalyzer(
            bt.analyzers.Returns,
            _name='returns',
            timeframe=bt.TimeFrame.Days,
        )

        logger.info("已添加默认分析器")

    def _extract_result(self, strategy: bt.Strategy) -> BacktestResult:
        """
        提取回测结果

        参数:
            strategy: 策略实例

        返回:
            BacktestResult: 回测结果对象
        """
        # 获取最终资金
        final_value = self.cerebro.broker.getvalue()

        # 计算总收益率
        total_return = ((final_value - self.initial_cash) / self.initial_cash) * 100

        # 提取分析器结果
        analyzers = strategy.analyzers

        # 夏普比率
        try:
            sharpe_ratio = analyzers.sharpe.get_analysis().get('sharperatio', 0)
            if sharpe_ratio is None:
                sharpe_ratio = 0.0
        except (AttributeError, KeyError):
            sharpe_ratio = 0.0

        # 最大回撤
        try:
            drawdown = analyzers.drawdown.get_analysis()
            max_drawdown = drawdown.get('max', {}).get('drawdown', 0)
        except (AttributeError, KeyError):
            max_drawdown = 0.0

        # 交易分析
        try:
            trades = analyzers.trades.get_analysis()
            total_trades = trades.get('total', {}).get('total', 0)
            won_trades = trades.get('won', {}).get('total', 0)
            win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
        except (AttributeError, KeyError):
            total_trades = 0
            win_rate = 0.0

        # 构造结果对象
        result = BacktestResult(
            initial_cash=self.initial_cash,
            final_value=final_value,
            total_return=total_return,
            total_trades=total_trades,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
        )

        return result


# ==================== 测试代码 ====================
if __name__ == "__main__":
    """
    回测引擎测试
    """
    from data.data_feed import AStockDataFeed
    from strategies.ma_strategy import DualMovingAverage

    logger.info("=== 回测引擎测试 ===")

    # 1. 获取数据
    data_feed = AStockDataFeed()
    df = data_feed.get_stock_data(
        symbol="000001",
        start_date="2023-01-01",
        end_date="2024-12-31"
    )

    if df.empty:
        logger.error("数据获取失败，无法继续回测")
        exit(1)

    # 2. 创建回测引擎
    engine = BacktestEngine(
        initial_cash=100000,
        commission=0.0003,
    )

    # 3. 添加数据
    engine.add_data(df)

    # 4. 添加策略
    engine.add_strategy(
        DualMovingAverage,
        fast_period=5,
        slow_period=20,
    )

    # 5. 运行回测
    result = engine.run()

    # 6. 显示结果
    print(result)
