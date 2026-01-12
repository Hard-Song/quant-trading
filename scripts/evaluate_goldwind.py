# -*- coding: utf-8 -*-
"""
策略评估脚本
在金风科技（002202）上评估不同策略在过去60天的表现
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_feed import AStockDataFeed
from core.backtest_engine import BacktestEngine
from strategies.ma_strategy import DualMovingAverage
from strategies.macd_strategy import MACDStrategy
from utils.logger import logger
import pandas as pd


def calculate_date_range(days_back: int = 60) -> tuple:
    """
    计算日期范围

    参数:
        days_back: 回溯天数

    返回:
        (start_date, end_date): 格式为 "YYYY-MM-DD"
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    # 格式化为字符串
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    logger.info(f"回测时间范围: {start_str} ~ {end_str}")
    logger.info(f"回溯天数: {days_back}天")

    return start_str, end_str


def evaluate_strategy(
    strategy_class,
    strategy_params: dict,
    df,
    strategy_name: str
):
    """
    评估单个策略

    参数:
        strategy_class: 策略类
        strategy_params: 策略参数
        df: 数据DataFrame
        strategy_name: 策略名称

    返回:
        BacktestResult: 回测结果
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"开始评估策略: {strategy_name}")
    logger.info(f"策略参数: {strategy_params}")
    logger.info(f"{'='*60}\n")

    # 创建回测引擎
    # 使用A股真实手续费结构
    engine = BacktestEngine(
        initial_cash=100000,
        use_a_stock_comm=True,  # 启用A股手续费
    )

    # 添加数据
    engine.add_data(df)

    # 添加策略
    engine.add_strategy(strategy_class, **strategy_params)

    # 运行回测
    result = engine.run()

    logger.info(f"\n策略 {strategy_name} 回测完成")

    return result


def compare_strategies(results_dict: dict):
    """
    对比多个策略的结果

    参数:
        results_dict: {策略名称: BacktestResult}
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"策略对比报告 - 金风科技（002202）")
    logger.info(f"{'='*80}\n")

    # 构建对比表格
    comparison_data = []
    for strategy_name, result in results_dict.items():
        comparison_data.append({
            '策略': strategy_name,
            '最终资金(元)': round(result.final_value, 2),
            '总收益率(%)': round(result.total_return, 2),
            '交易次数': result.total_trades,
            '胜率(%)': round(result.win_rate, 2),
            '最大回撤(%)': round(result.max_drawdown, 2),
            '夏普比率': round(result.sharpe_ratio, 2),
        })

    # 创建DataFrame
    df_comparison = pd.DataFrame(comparison_data)

    # 按总收益率排序
    df_comparison = df_comparison.sort_values('总收益率(%)', ascending=False)
    df_comparison.reset_index(drop=True, inplace=True)

    # 打印对比表格
    print("\n" + "="*100)
    print("策略对比结果")
    print("="*100)
    print(df_comparison.to_string(index=False))
    print("="*100 + "\n")

    # 找出最佳策略
    best_strategy = df_comparison.iloc[0]
    print(f"🏆 最佳策略: {best_strategy['策略']}")
    print(f"   收益率: {best_strategy['总收益率(%)']:.2f}%")
    print(f"   夏普比率: {best_strategy['夏普比率']:.2f}")
    print(f"   最大回撤: {best_strategy['最大回撤(%)']:.2f}%\n")

    return df_comparison


def main():
    """
    主函数：评估多个策略
    """
    logger.info("="*80)
    logger.info("策略评估 - 金风科技（002202）")
    logger.info("="*80)

    # 1. 计算日期范围（过去60天）
    start_date, end_date = calculate_date_range(days_back=60)
    logger.info("")

    # 2. 获取数据
    logger.info("开始获取金风科技（002202）数据...")
    data_feed = AStockDataFeed()
    df = data_feed.get_stock_data(
        symbol="002202",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq"  # 前复权
    )

    if df.empty:
        logger.error("数据获取失败，无法继续评估")
        return

    logger.info(f"成功获取 {len(df)} 条数据\n")
    logger.info(f"数据范围: {df.index[0]} ~ {df.index[-1]}")
    logger.info(f"价格区间: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
    logger.info("")

    # 3. 定义要测试的策略
    strategies_to_test = {
        'MA(5,20)': {
            'class': DualMovingAverage,
            'params': {'fast_period': 5, 'slow_period': 20}
        },
        'MA(10,30)': {
            'class': DualMovingAverage,
            'params': {'fast_period': 10, 'slow_period': 30}
        },
        'MA(20,60)': {
            'class': DualMovingAverage,
            'params': {'fast_period': 20, 'slow_period': 60}
        },
        'MACD(12,26,9)': {
            'class': MACDStrategy,
            'params': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9}
        },
        'MACD(快速)': {
            'class': MACDStrategy,
            'params': {'fast_period': 8, 'slow_period': 17, 'signal_period': 9}
        },
    }

    # 4. 运行所有策略
    results = {}
    for strategy_name, strategy_info in strategies_to_test.items():
        try:
            result = evaluate_strategy(
                strategy_class=strategy_info['class'],
                strategy_params=strategy_info['params'],
                df=df,
                strategy_name=strategy_name
            )
            results[strategy_name] = result
        except Exception as e:
            logger.error(f"策略 {strategy_name} 回测失败: {e}")

    # 5. 对比结果
    if results:
        comparison_df = compare_strategies(results)

        # 保存结果到CSV
        output_dir = project_root / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"goldwind_002222_evaluation_{timestamp}.csv"
        comparison_df.to_csv(output_file, index=False, encoding='utf-8-sig')

        logger.info(f"对比结果已保存到: {output_file}")

    logger.info("\n" + "="*80)
    logger.info("评估完成")
    logger.info("="*80)


if __name__ == "__main__":
    main()
