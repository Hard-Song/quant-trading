# -*- coding: utf-8 -*-
"""
策略比较器模块
支持多个策略的并行对比回测，生成对比报告
"""

import backtrader as bt
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Type, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from core.backtest_engine import BacktestEngine, BacktestResult
from core.data_manager import DataManager
from utils.logger import logger


@dataclass
class StrategyTestConfig:
    """
    策略测试配置

    属性:
        name: 策略名称（用于标识）
        strategy_class: 策略类
        params: 策略参数字典
    """
    name: str
    strategy_class: Type[bt.Strategy]
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """
    策略对比结果

    属性:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        results: 各策略的回测结果 {策略名: BacktestResult}
    """
    symbol: str
    start_date: str
    end_date: str
    results: Dict[str, BacktestResult] = field(default_factory=dict)

    def to_dataframe(self) -> pd.DataFrame:
        """
        转换为DataFrame格式

        返回:
            DataFrame: 策略对比表格
        """
        data = []
        for strategy_name, result in self.results.items():
            data.append({
                '策略': strategy_name,
                '初始资金': result.initial_cash,
                '最终资金': result.final_value,
                '总收益率(%)': round(result.total_return, 2),
                '交易次数': result.total_trades,
                '胜率(%)': round(result.win_rate, 2),
                '最大回撤(%)': round(result.max_drawdown, 2),
                '夏普比率': round(result.sharpe_ratio, 2),
            })

        df = pd.DataFrame(data)
        df = df.sort_values('总收益率(%)', ascending=False)
        df.reset_index(drop=True, inplace=True)

        return df

    def get_best_strategy(self, metric: str = 'total_return') -> tuple[str, BacktestResult]:
        """
        获取最佳策略

        参数:
            metric: 评价指标 ('total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate')

        返回:
            (策略名, 回测结果)
        """
        if not self.results:
            return None, None

        metric_map = {
            'total_return': 'total_return',
            'sharpe_ratio': 'sharpe_ratio',
            'max_drawdown': 'max_drawdown',
            'win_rate': 'win_rate',
        }

        if metric not in metric_map:
            raise ValueError(f"不支持的评价指标: {metric}")

        attr = metric_map[metric]

        # 根据指标确定排序方向
        reverse = True  # 收益率、夏普比率、胜率都是越大越好
        if metric == 'max_drawdown':
            reverse = False  # 回撤越小越好

        best_strategy = max(
            self.results.items(),
            key=lambda x: getattr(x[1], attr) if reverse else -getattr(x[1], attr)
        )

        return best_strategy


class StrategyComparator:
    """
    策略比较器

    核心功能：
        1. 对同一股票运行多个策略
        2. 收集每个策略的回测结果
        3. 生成对比报告（表格、图表）
        4. 自动处理数据缓存

    使用场景：
        - 策略选择：比较不同策略在同一股票上的表现
        - 参数优化：比较同一策略的不同参数组合
        - 策略评估：综合评估策略的风险收益特征

    使用示例：
        # 创建比较器
        comparator = StrategyComparator()

        # 定义要比较的策略
        strategies = [
            StrategyTestConfig('MA5-20', DualMovingAverage, {'fast_period': 5, 'slow_period': 20}),
            StrategyTestConfig('MA10-30', DualMovingAverage, {'fast_period': 10, 'slow_period': 30}),
            StrategyTestConfig('MACD', MACDStrategy, {}),
        ]

        # 运行对比
        result = comparator.compare(
            symbol="000001",
            start_date="2023-01-01",
            end_date="2024-12-31",
            strategies=strategies
        )

        # 查看结果
        print(result.to_dataframe())

        # 获取最佳策略
        best_name, best_result = result.get_best_strategy('total_return')
        print(f"最佳策略: {best_name}")
    """

    def __init__(self, initial_cash: float = 100000, commission: float = 0.0003):
        """
        初始化策略比较器

        参数:
            initial_cash: 初始资金
            commission: 手续费率
        """
        self.initial_cash = initial_cash
        self.commission = commission

        # 数据管理器（复用，避免重复获取数据）
        self.data_manager = DataManager()

        logger.info(f"策略比较器初始化完成")
        logger.info(f"初始资金: {initial_cash}, 手续费: {commission}")

    def compare(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        strategies: List[StrategyTestConfig],
        adjust: str = "qfq",
    ) -> ComparisonResult:
        """
        运行策略对比

        参数:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            strategies: 策略配置列表
            adjust: 复权类型

        返回:
            ComparisonResult: 对比结果对象
        """
        logger.info("=" * 80)
        logger.info(f"开始策略对比回测")
        logger.info(f"股票代码: {symbol}")
        logger.info(f"时间范围: {start_date} ~ {end_date}")
        logger.info(f"策略数量: {len(strategies)}")
        logger.info("=" * 80)

        # 1. 获取数据（只获取一次，所有策略共享）
        logger.info("\n【步骤1】获取股票数据")
        df = self.data_manager.get_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )

        if df.empty:
            logger.error("数据获取失败，无法继续回测")
            return ComparisonResult(symbol, start_date, end_date)

        logger.info(f"✓ 数据获取成功，共 {len(df)} 条记录")

        # 2. 运行每个策略
        logger.info("\n【步骤2】运行策略回测")
        results = {}

        for i, strategy_config in enumerate(strategies, 1):
            logger.info(f"\n[{i}/{len(strategies)}] 运行策略: {strategy_config.name}")

            try:
                # 创建回测引擎
                engine = BacktestEngine(
                    initial_cash=self.initial_cash,
                    commission=self.commission,
                )

                # 添加数据（数据已缓存，不会重复调用API）
                engine.add_data(df)

                # 添加策略
                engine.add_strategy(
                    strategy_config.strategy_class,
                    **strategy_config.params
                )

                # 运行回测
                result = engine.run()

                # 保存结果
                results[strategy_config.name] = result

                logger.info(f"✓ 策略 {strategy_config.name} 回测完成")
                logger.info(f"  总收益率: {result.total_return:.2f}%")
                logger.info(f"  夏普比率: {result.sharpe_ratio:.2f}")
                logger.info(f"  最大回撤: {result.max_drawdown:.2f}%")

            except Exception as e:
                logger.error(f"✗ 策略 {strategy_config.name} 回测失败: {e}")
                continue

        # 3. 构造对比结果
        comparison_result = ComparisonResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            results=results
        )

        logger.info("\n" + "=" * 80)
        logger.info(f"策略对比完成！成功运行 {len(results)}/{len(strategies)} 个策略")
        logger.info("=" * 80)

        return comparison_result

    def compare_batch(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        strategies: List[StrategyTestConfig],
        adjust: str = "qfq",
    ) -> Dict[str, ComparisonResult]:
        """
        批量对比（多股票）

        参数:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            strategies: 策略配置列表
            adjust: 复权类型

        返回:
            Dict[str, ComparisonResult]: {股票代码: 对比结果}
        """
        logger.info(f"批量策略对比：{len(symbols)} 只股票 × {len(strategies)} 个策略")

        results = {}
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"\n[{i}/{len(symbols)}] 处理股票: {symbol}")

            result = self.compare(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                strategies=strategies,
                adjust=adjust
            )

            results[symbol] = result

        return results

    def plot_comparison(self, result: ComparisonResult, save_path: str = None):
        """
        绘制策略对比图表

        参数:
            result: 对比结果对象
            save_path: 图表保存路径（可选）
        """
        try:
            # 创建对比表格
            df = result.to_dataframe()

            # 创建图表
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle(f'策略对比分析 - {result.symbol}\n{result.start_date} ~ {result.end_date}',
                        fontsize=14, fontweight='bold')

            # 1. 总收益率对比
            ax1 = axes[0, 0]
            colors = ['green' if x > 0 else 'red' for x in df['总收益率(%)']]
            ax1.barh(df['策略'], df['总收益率(%)'], color=colors)
            ax1.set_xlabel('总收益率 (%)')
            ax1.set_title('总收益率对比')
            ax1.axvline(x=0, color='black', linestyle='-', linewidth=0.5)

            # 2. 夏普比率对比
            ax2 = axes[0, 1]
            ax2.barh(df['策略'], df['夏普比率'], color='steelblue')
            ax2.set_xlabel('夏普比率')
            ax2.set_title('夏普比率对比')
            ax2.axvline(x=1.0, color='red', linestyle='--', linewidth=0.8, label='基准线(1.0)')
            ax2.legend()

            # 3. 最大回撤对比
            ax3 = axes[1, 0]
            ax3.barh(df['策略'], df['最大回撤(%)'], color='orange')
            ax3.set_xlabel('最大回撤 (%)')
            ax3.set_title('最大回撤对比（越小越好）')

            # 4. 胜率对比
            ax4 = axes[1, 1]
            colors = ['green' if x > 50 else 'gray' for x in df['胜率(%)']]
            ax4.barh(df['策略'], df['胜率(%)'], color=colors)
            ax4.set_xlabel('胜率 (%)')
            ax4.set_title('胜率对比')
            ax4.axvline(x=50, color='black', linestyle='--', linewidth=0.8, label='50%基准线')
            ax4.legend()

            plt.tight_layout()

            # 保存图表
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"图表已保存到: {save_path}")

            plt.show()

        except Exception as e:
            logger.error(f"绘制对比图表失败: {e}")

    def print_summary(self, result: ComparisonResult):
        """
        打印策略对比摘要

        参数:
            result: 对比结果对象
        """
        df = result.to_dataframe()

        print("\n" + "=" * 80)
        print(f"策略对比报告 - {result.symbol}")
        print(f"回测期间: {result.start_date} ~ {result.end_date}")
        print("=" * 80)

        print(df.to_string(index=False))

        print("\n" + "=" * 80)
        print("最佳策略分析")
        print("=" * 80)

        # 收益率最佳
        best_return_name, best_return_result = result.get_best_strategy('total_return')
        if best_return_name:
            print(f"[最高收益率] {best_return_name} ({best_return_result.total_return:.2f}%)")

        # 夏普比率最佳
        best_sharpe_name, best_sharpe_result = result.get_best_strategy('sharpe_ratio')
        if best_sharpe_name:
            print(f"[最高夏普比率] {best_sharpe_name} ({best_sharpe_result.sharpe_ratio:.2f})")

        # 回撤最小
        best_drawdown_name, best_drawdown_result = result.get_best_strategy('max_drawdown')
        if best_drawdown_name:
            print(f"[最小回撤] {best_drawdown_name} ({best_drawdown_result.max_drawdown:.2f}%)")

        print("=" * 80 + "\n")


# ==================== 测试代码 ====================
if __name__ == "__main__":
    """
    策略比较器测试
    """
    from strategies.ma_strategy import DualMovingAverage
    from strategies.macd_strategy import MACDStrategy

    logger.info("=== 策略比较器测试 ===")

    # 1. 创建比较器
    comparator = StrategyComparator(
        initial_cash=100000,
        commission=0.0003,
    )

    # 2. 定义要比较的策略
    strategies = [
        StrategyTestConfig('MA(5,20)', DualMovingAverage, {'fast_period': 5, 'slow_period': 20}),
        StrategyTestConfig('MA(10,30)', DualMovingAverage, {'fast_period': 10, 'slow_period': 30}),
        StrategyTestConfig('MACD', MACDStrategy, {'fast_period': 12, 'slow_period': 26, 'signal_period': 9}),
    ]

    # 3. 运行对比
    result = comparator.compare(
        symbol="000001",
        start_date="2024-01-01",
        end_date="2024-12-31",
        strategies=strategies,
        adjust="qfq"
    )

    # 4. 打印摘要
    comparator.print_summary(result)

    # 5. 绘制对比图表
    comparator.plot_comparison(result)

    logger.info("测试完成")
