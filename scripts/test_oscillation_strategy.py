# -*- coding: utf-8 -*-
"""
震荡策略测试脚本
在金风科技（002202）上测试高频震荡策略
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_feed import AStockDataFeed
from core.backtest_engine import BacktestEngine
from strategies.oscillation_strategy import (
    HighFrequencyOscillation,
    AggressiveOscillation,
    UltraAggressiveOscillation
)
from strategies.ma_strategy import DualMovingAverage
from strategies.macd_strategy import MACDStrategy
from utils.logger import logger
import pandas as pd


def calculate_date_range(days_back: int = 120):
    """计算日期范围"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


def run_backtest(strategy_class, strategy_params, df, strategy_name):
    """运行回测"""
    logger.info(f"\n{'='*60}")
    logger.info(f"策略: {strategy_name}")
    logger.info(f"参数: {strategy_params}")
    logger.info(f"{'='*60}\n")

    engine = BacktestEngine(
        initial_cash=100000,
        use_a_stock_comm=True,
    )
    engine.add_data(df)
    engine.add_strategy(strategy_class, **strategy_params)
    result = engine.run()

    return result


def analyze_trading_frequency(result, strategy_name):
    """分析交易频率"""
    logger.info(f"\n--- {strategy_name} 交易分析 ---")
    logger.info(f"总交易次数: {result.total_trades}")

    # 计算平均交易频率（假设120天）
    if result.total_trades > 0:
        avg_days_per_trade = 120 / result.total_trades
        logger.info(f"平均交易频率: 每 {avg_days_per_trade:.1f} 天交易一次")

        if avg_days_per_trade <= 3:
            logger.info(f"✓ 满足高频交易要求（≤3天）")
        else:
            logger.warning(f"✗ 未满足高频交易要求（要求≤3天，实际{avg_days_per_trade:.1f}天）")
    else:
        logger.warning("该策略未产生任何交易")


def main():
    """主函数"""
    logger.info("="*80)
    logger.info("震荡策略测试 - 金风科技（002202）")
    logger.info("="*80)

    # 1. 获取数据（过去120天）
    start_date, end_date = calculate_date_range(days_back=120)
    logger.info(f"\n数据范围: {start_date} ~ {end_date}\n")

    data_feed = AStockDataFeed()
    df = data_feed.get_stock_data(
        symbol="002202",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq"
    )

    if df.empty:
        logger.error("数据获取失败")
        return

    logger.info(f"成功获取 {len(df)} 条数据")

    # 2. 定义要测试的策略
    strategies = {
        '基准-MA(5,20)': {
            'class': DualMovingAverage,
            'params': {'fast_period': 5, 'slow_period': 20}
        },
        '基准-MACD': {
            'class': MACDStrategy,
            'params': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9}
        },
        '高频震荡(宽松)': {
            'class': HighFrequencyOscillation,
            'params': {
                'rsi_period': 6,
                'rsi_oversold': 35,  # 放宽到35
                'rsi_overbought': 65,  # 放宽到65
                'bb_period': 10,
                'stake': 200,
                'min_trade_interval': 2,  # 缩短最小间隔
            }
        },
        '超激进震荡策略': {
            'class': AggressiveOscillation,
            'params': {}
        },
        '极激进震荡策略⚠️': {
            'class': UltraAggressiveOscillation,
            'params': {}
        },
    }

    # 3. 运行所有策略
    results = {}
    for name, info in strategies.items():
        try:
            result = run_backtest(
                info['class'],
                info['params'],
                df,
                name
            )
            results[name] = result
            analyze_trading_frequency(result, name)
        except Exception as e:
            logger.error(f"策略 {name} 回测失败: {e}")

    # 4. 生成对比报告
    logger.info(f"\n{'='*100}")
    logger.info("策略对比报告")
    logger.info(f"{'='*100}\n")

    comparison_data = []
    for name, result in results.items():
        comparison_data.append({
            '策略': name,
            '最终资金(元)': round(result.final_value, 2),
            '总收益率(%)': round(result.total_return, 2),
            '交易次数': result.total_trades,
            '胜率(%)': round(result.win_rate, 2),
            '最大回撤(%)': round(result.max_drawdown, 2),
            '夏普比率': round(result.sharpe_ratio, 2),
            '交易频率(天/次)': round(120 / result.total_trades, 1) if result.total_trades > 0 else float('inf'),
        })

    df_comparison = pd.DataFrame(comparison_data)
    df_comparison = df_comparison.sort_values('总收益率(%)', ascending=False)

    print("\n" + "="*120)
    print(df_comparison.to_string(index=False))
    print("="*120 + "\n")

    # 5. 风险分析
    logger.info("风险分析:")
    logger.info("-" * 60)

    for name, result in results.items():
        if result.total_return < -20:
            logger.error(f"⚠️  {name}: 触及20%止损红线！收益: {result.total_return:.2f}%")
        elif result.total_return < 0:
            logger.warning(f"⚠️  {name}: 亏损 {abs(result.total_return):.2f}%")
        elif result.total_return < 5:
            logger.info(f"ℹ️  {name}: 微利 {result.total_return:.2f}%")
        else:
            logger.info(f"✓ {name}: 盈利 {result.total_return:.2f}%")

    # 6. 保存结果
    output_dir = project_root / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"oscillation_strategies_{timestamp}.csv"
    df_comparison.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"\n结果已保存到: {output_file}")

    # 7. 推荐建议
    logger.info("\n" + "="*80)
    logger.info("策略推荐")
    logger.info("="*80)

    if results:
        # 找出收益率最高的策略
        best_name = df_comparison.iloc[0]['策略']
        best_return = df_comparison.iloc[0]['总收益率(%)']
        best_trades = df_comparison.iloc[0]['交易次数']

        logger.info(f"\n最佳收益策略: {best_name}")
        logger.info(f"  收益率: {best_return:.2f}%")
        logger.info(f"  交易次数: {best_trades}")

        # 检查是否满足高频要求
        if best_trades >= 40:  # 120天至少40次交易，平均3天一次
            logger.info(f"  ✓ 满足高频交易要求")
        else:
            logger.warning(f"  ✗ 未满足高频交易要求（需要≥40次，实际{best_trades}次）")

        logger.info("\n策略选择建议:")
        if best_return > 10:
            logger.info("  - 当前市场适合震荡策略，建议使用高频震荡策略")
            logger.info("  - 注意严格止损，控制单笔亏损在20%以内")
        elif best_return > 0:
            logger.info("  - 当前市场波动适中，震荡策略表现一般")
            logger.info("  - 可以考虑降低交易频率，等待更好的机会")
        else:
            logger.warning("  - 当前市场可能不适合震荡策略")
            logger.warning("  - 建议改用趋势跟踪策略或空仓观望")


if __name__ == "__main__":
    main()
