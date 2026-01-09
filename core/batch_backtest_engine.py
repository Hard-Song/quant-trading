# -*- coding: utf-8 -*-
"""
批量回测引擎模块
支持单策略 vs 多股票的批量回测，生成汇总报告
"""

import backtrader as bt
import pandas as pd
from pathlib import Path
from typing import List, Dict, Type, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from core.backtest_engine import BacktestEngine, BacktestResult
from core.data_manager import DataManager
from utils.logger import logger


@dataclass
class BatchBacktestResult:
    """
    批量回测结果

    属性:
        strategy_name: 策略名称
        start_date: 开始日期
        end_date: 结束日期
        total_stocks: 总股票数
        success_count: 成功回测数量
        fail_count: 失败回测数量
        results: {股票代码: BacktestResult}
    """
    strategy_name: str
    start_date: str
    end_date: str
    total_stocks: int
    success_count: int = 0
    fail_count: int = 0
    results: Dict[str, BacktestResult] = field(default_factory=dict)

    def get_summary(self) -> pd.DataFrame:
        """
        获取汇总表格

        返回:
            DataFrame: 所有股票的回测结果汇总
        """
        data = []
        for symbol, result in self.results.items():
            data.append({
                '股票代码': symbol,
                '初始资金': result.initial_cash,
                '最终资金': round(result.final_value, 2),
                '总收益率(%)': round(result.total_return, 2),
                '交易次数': result.total_trades,
                '胜率(%)': round(result.win_rate, 2),
                '最大回撤(%)': round(result.max_drawdown, 2),
                '夏普比率': round(result.sharpe_ratio, 2),
            })

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('总收益率(%)', ascending=False)
            df.reset_index(drop=True, inplace=True)

        return df

    def get_top_n(self, n: int = 10, metric: str = 'total_return') -> pd.DataFrame:
        """
        获取表现最好的前N只股票

        参数:
            n: 返回前N只
            metric: 排序指标 ('total_return', 'sharpe_ratio', 'win_rate')

        返回:
            DataFrame: 前N只股票的回测结果
        """
        df = self.get_summary()

        if df.empty:
            return df

        metric_map = {
            'total_return': '总收益率(%)',
            'sharpe_ratio': '夏普比率',
            'win_rate': '胜率(%)',
            'max_drawdown': '最大回撤(%)',
        }

        if metric not in metric_map:
            raise ValueError(f"不支持的指标: {metric}")

        col = metric_map[metric]

        if metric == 'max_drawdown':
            # 回撤越小越好
            df_sorted = df.sort_values(col, ascending=True)
        else:
            # 其他指标越大越好
            df_sorted = df.sort_values(col, ascending=False)

        return df_sorted.head(n)

    def get_statistics(self) -> Dict[str, any]:
        """
        获取统计信息

        返回:
            Dict: 统计数据
        """
        if not self.results:
            return {}

        returns = [r.total_return for r in self.results.values()]
        sharpe_ratios = [r.sharpe_ratio for r in self.results.values()]
        win_rates = [r.win_rate for r in self.results.values()]
        max_drawdowns = [r.max_drawdown for r in self.results.values()]

        positive_count = sum(1 for r in returns if r > 0)
        negative_count = sum(1 for r in returns if r < 0)

        return {
            '总股票数': self.total_stocks,
            '成功回测': self.success_count,
            '失败回测': self.fail_count,
            '平均收益率': round(sum(returns) / len(returns), 2) if returns else 0,
            '收益率标准差': round(pd.Series(returns).std(), 2) if returns else 0,
            '最高收益率': round(max(returns), 2) if returns else 0,
            '最低收益率': round(min(returns), 2) if returns else 0,
            '盈利股票数': positive_count,
            '亏损股票数': negative_count,
            '盈利比例': f"{positive_count / len(returns) * 100:.2f}%" if returns else "0%",
            '平均夏普比率': round(sum(sharpe_ratios) / len(sharpe_ratios), 2) if sharpe_ratios else 0,
            '平均胜率': round(sum(win_rates) / len(win_rates), 2) if win_rates else 0,
            '平均最大回撤': round(sum(max_drawdowns) / len(max_drawdowns), 2) if max_drawdowns else 0,
        }

    def __str__(self):
        """格式化输出"""
        stats = self.get_statistics()
        summary = f"""
========== 批量回测结果 ==========
策略: {self.strategy_name}
时间范围: {self.start_date} ~ {self.end_date}
----------------------------------
总股票数: {self.total_stocks}
成功回测: {self.success_count}
失败回测: {self.fail_count}
----------------------------------
"""
        if stats:
            summary += "收益统计:\n"
            for key, value in stats.items():
                if '股票数' not in key:  # 跳过已经显示的
                    summary += f"  {key}: {value}\n"

        summary += "=" * 32 + "\n"
        return summary


class BatchBacktestEngine:
    """
    批量回测引擎

    核心功能：
        1. 对多只股票运行同一策略
        2. 支持并行处理提高效率
        3. 生成汇总报告和排名
        4. 自动处理数据缓存

    使用场景：
        - 选股后的批量回测
        - 策略在不同股票上的表现评估
        - 大样本量的策略验证

    使用示例:
        # 创建批量回测引擎
        batch_engine = BatchBacktestEngine(
            strategy=DualMovingAverage,
            strategy_params={'fast_period': 5, 'slow_period': 20}
        )

        # 运行批量回测
        result = batch_engine.run_batch(
            symbols=['000001', '600000', '000002'],
            start_date='2023-01-01',
            end_date='2024-12-31'
        )

        # 查看汇总
        print(result)
        print(result.get_summary())

        # 获取前10名
        top10 = result.get_top_n(n=10)
        print(top10)

        # 获取统计信息
        stats = result.get_statistics()
        print(stats)
    """

    def __init__(
        self,
        strategy_class: Type[bt.Strategy],
        strategy_params: Dict = None,
        initial_cash: float = 100000,
        commission: float = 0.0003,
        max_workers: int = 4,
    ):
        """
        初始化批量回测引擎

        参数:
            strategy_class: 策略类
            strategy_params: 策略参数
            initial_cash: 初始资金
            commission: 手续费率
            max_workers: 最大并行线程数
        """
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.initial_cash = initial_cash
        self.commission = commission
        self.max_workers = max_workers

        # 数据管理器（共享，避免重复获取数据）
        self.data_manager = DataManager()

        # 线程锁（用于日志输出）
        self._lock = threading.Lock()

        logger.info(f"批量回测引擎初始化完成")
        logger.info(f"策略: {strategy_class.__name__}")
        logger.info(f"策略参数: {strategy_params}")
        logger.info(f"并行线程数: {max_workers}")

    def run_batch(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        parallel: bool = True,
        show_progress: bool = True,
    ) -> BatchBacktestResult:
        """
        运行批量回测

        参数:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            parallel: 是否并行处理
            show_progress: 是否显示进度

        返回:
            BatchBacktestResult: 批量回测结果
        """
        logger.info("=" * 80)
        logger.info(f"开始批量回测")
        logger.info(f"策略: {self.strategy_class.__name__}")
        logger.info(f"股票数量: {len(symbols)}")
        logger.info(f"时间范围: {start_date} ~ {end_date}")
        logger.info(f"并行处理: {'是' if parallel else '否'}")
        logger.info("=" * 80)

        results = {}
        success_count = 0
        fail_count = 0

        if parallel and len(symbols) > 1:
            # 并行处理
            results, success_count, fail_count = self._run_parallel(
                symbols, start_date, end_date, show_progress
            )
        else:
            # 串行处理
            results, success_count, fail_count = self._run_sequential(
                symbols, start_date, end_date, show_progress
            )

        # 创建批量回测结果
        batch_result = BatchBacktestResult(
            strategy_name=self.strategy_class.__name__,
            start_date=start_date,
            end_date=end_date,
            total_stocks=len(symbols),
            success_count=success_count,
            fail_count=fail_count,
            results=results
        )

        logger.info("=" * 80)
        logger.info(f"批量回测完成")
        logger.info(f"成功: {success_count}, 失败: {fail_count}")
        logger.info("=" * 80)

        return batch_result

    def _run_parallel(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        show_progress: bool
    ) -> Tuple[Dict, int, int]:
        """并行运行回测"""
        results = {}
        success_count = 0
        fail_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_symbol = {
                executor.submit(
                    self._backtest_single,
                    symbol,
                    start_date,
                    end_date
                ): symbol
                for symbol in symbols
            }

            # 收集结果
            for i, future in enumerate(as_completed(future_to_symbol), 1):
                symbol = future_to_symbol[future]

                if show_progress and i % 10 == 0:
                    logger.info(f"进度: {i}/{len(symbols)}")

                try:
                    result = future.result()
                    if result:
                        results[symbol] = result
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    with self._lock:
                        logger.error(f"股票 {symbol} 回测失败: {e}")
                    fail_count += 1

        return results, success_count, fail_count

    def _run_sequential(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        show_progress: bool
    ) -> Tuple[Dict, int, int]:
        """串行运行回测"""
        results = {}
        success_count = 0
        fail_count = 0

        for i, symbol in enumerate(symbols, 1):
            if show_progress and i % 10 == 0:
                logger.info(f"进度: {i}/{len(symbols)}")

            try:
                result = self._backtest_single(symbol, start_date, end_date)
                if result:
                    results[symbol] = result
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"股票 {symbol} 回测失败: {e}")
                fail_count += 1

        return results, success_count, fail_count

    def _backtest_single(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Optional[BacktestResult]:
        """
        对单只股票运行回测

        参数:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        返回:
            BacktestResult or None
        """
        try:
            # 获取数据（使用共享的数据管理器，自动缓存）
            df = self.data_manager.get_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )

            if df.empty:
                logger.debug(f"股票 {symbol} 数据为空")
                return None

            # 创建回测引擎
            engine = BacktestEngine(
                initial_cash=self.initial_cash,
                commission=self.commission,
            )

            # 添加数据
            engine.add_data(df)

            # 添加策略
            engine.add_strategy(self.strategy_class, **self.strategy_params)

            # 运行回测
            with self._lock:
                logger.debug(f"股票 {symbol} 回测中...")

            result = engine.run()

            return result

        except Exception as e:
            with self._lock:
                logger.debug(f"股票 {symbol} 回测异常: {e}")
            return None

    def save_results(
        self,
        batch_result: BatchBacktestResult,
        output_dir: str = None,
        save_summary: bool = True,
        save_details: bool = True
    ):
        """
        保存批量回测结果

        参数:
            batch_result: 批量回测结果
            output_dir: 输出目录
            save_summary: 是否保存汇总表
            save_details: 是否保存详细结果
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "reports"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        strategy_name = batch_result.strategy_name

        # 保存汇总表
        if save_summary:
            summary_file = output_dir / f"batch_{strategy_name}_summary_{timestamp}.csv"
            summary_df = batch_result.get_summary()
            summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
            logger.info(f"汇总表已保存: {summary_file}")

        # 保存详细结果
        if save_details:
            details_file = output_dir / f"batch_{strategy_name}_details_{timestamp}.csv"
            details_df = batch_result.get_summary()
            details_df.to_csv(details_file, index=False, encoding='utf-8-sig')
            logger.info(f"详细结果已保存: {details_file}")

        # 保存统计信息
        stats_file = output_dir / f"batch_{strategy_name}_stats_{timestamp}.txt"
        with open(stats_file, 'w', encoding='utf-8') as f:
            f.write(str(batch_result))
            f.write("\n\n详细统计:\n")
            stats = batch_result.get_statistics()
            for key, value in stats.items():
                f.write(f"  {key}: {value}\n")
        logger.info(f"统计信息已保存: {stats_file}")


# ==================== 便捷函数 ====================
def run_batch_backtest(
    strategy_class: Type[bt.Strategy],
    symbols: List[str],
    start_date: str,
    end_date: str,
    strategy_params: Dict = None,
    **kwargs
) -> BatchBacktestResult:
    """
    批量回测的便捷函数

    参数:
        strategy_class: 策略类
        symbols: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        strategy_params: 策略参数
        **kwargs: 传递给BatchBacktestEngine的参数

    返回:
        BatchBacktestResult: 批量回测结果
    """
    engine = BatchBacktestEngine(
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        **kwargs
    )

    return engine.run_batch(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date
    )
