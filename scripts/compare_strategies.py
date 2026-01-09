# -*- coding: utf-8 -*-
"""
策略比较脚本
用于比较多个策略在同一股票上的表现

使用方法:
    # 方式1: 默认比较（MA vs MACD）
    uv run python scripts/compare_strategies.py

    # 方式2: 指定股票和日期
    uv run python scripts/compare_strategies.py --symbol 600000 --start 2023-01-01

    # 方式3: 比较多个参数组合
    uv run python scripts/compare_strategies.py --strategies ma_params --params 5,20 10,30

    # 方式4: 比较指定策略
    uv run python scripts/compare_strategies.py --strategies ma macd macd_trend
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.strategy_comparator import StrategyComparator, StrategyTestConfig
from strategies.ma_strategy import DualMovingAverage
from strategies.macd_strategy import MACDStrategy, MACDWithTrend, MACDWithRSI
from utils.logger import logger
from utils.config import config


# 策略工厂
def create_strategy_configs(strategy_type: str, params_str: str = None) -> list[StrategyTestConfig]:
    """
    根据类型创建策略配置列表

    参数:
        strategy_type: 策略类型
            - 'ma': 双均线策略
            - 'macd': MACD策略
            - 'ma_params': 多个参数组合的MA策略
            - 'macd_params': 多个参数组合的MACD策略
            - 'all': 所有策略
        params_str: 参数字符串（用逗号分隔）

    返回:
        策略配置列表
    """
    configs = []

    if strategy_type == 'ma':
        # 单个MA策略（默认参数）
        configs = [
            StrategyTestConfig('MA(5,20)', DualMovingAverage, {'fast_period': 5, 'slow_period': 20})
        ]

    elif strategy_type == 'macd':
        # 单个MACD策略（默认参数）
        configs = [
            StrategyTestConfig('MACD(12,26,9)', MACDStrategy, {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9
            })
        ]

    elif strategy_type == 'ma_params':
        # 多个参数组合的MA策略
        if params_str:
            # 解析参数字符串: "5,20 10,30"
            param_sets = [p.split(',') for p in params_str.split()]
            configs = [
                StrategyTestConfig(f'MA({p[0]},{p[1]})', DualMovingAverage, {
                    'fast_period': int(p[0]),
                    'slow_period': int(p[1])
                })
                for p in param_sets
            ]
        else:
            # 默认参数组合
            configs = [
                StrategyTestConfig('MA(5,20)', DualMovingAverage, {'fast_period': 5, 'slow_period': 20}),
                StrategyTestConfig('MA(10,30)', DualMovingAverage, {'fast_period': 10, 'slow_period': 30}),
                StrategyTestConfig('MA(20,60)', DualMovingAverage, {'fast_period': 20, 'slow_period': 60}),
            ]

    elif strategy_type == 'macd_params':
        # 多个参数组合的MACD策略
        if params_str:
            # 解析参数字符串: "12,26,9 8,18,6"
            param_sets = [p.split(',') for p in params_str.split()]
            configs = [
                StrategyTestConfig(f'MACD({p[0]},{p[1]},{p[2]})', MACDStrategy, {
                    'fast_period': int(p[0]),
                    'slow_period': int(p[1]),
                    'signal_period': int(p[2])
                })
                for p in param_sets
            ]
        else:
            # 默认参数组合
            configs = [
                StrategyTestConfig('MACD(12,26,9)', MACDStrategy, {
                    'fast_period': 12,
                    'slow_period': 26,
                    'signal_period': 9
                }),
                StrategyTestConfig('MACD(8,18,6)', MACDStrategy, {
                    'fast_period': 8,
                    'slow_period': 18,
                    'signal_period': 6
                }),
            ]

    elif strategy_type == 'all':
        # 所有策略
        configs = [
            StrategyTestConfig('MA(5,20)', DualMovingAverage, {'fast_period': 5, 'slow_period': 20}),
            StrategyTestConfig('MACD(12,26,9)', MACDStrategy, {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9
            }),
            StrategyTestConfig('MACD+Trend', MACDWithTrend, {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9,
                'trend_period': 200
            }),
            StrategyTestConfig('MACD+RSI', MACDWithRSI, {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9,
                'rsi_period': 14,
            }),
        ]

    return configs


def parse_strategy_args(strategies_list: list[str]) -> list[StrategyTestConfig]:
    """
    解析命令行策略参数

    参数:
        strategies_list: 策略类型列表

    返回:
        策略配置列表
    """
    all_configs = []

    strategy_mapping = {
        'ma': lambda: create_strategy_configs('ma'),
        'macd': lambda: create_strategy_configs('macd'),
        'macd_trend': lambda: [StrategyTestConfig('MACD+Trend', MACDWithTrend, {
            'fast_period': 12,
            'slow_period': 26,
            'signal_period': 9,
            'trend_period': 200
        })],
        'macd_rsi': lambda: [StrategyTestConfig('MACD+RSI', MACDWithRSI, {
            'fast_period': 12,
            'slow_period': 26,
            'signal_period': 9,
            'rsi_period': 14,
        })],
    }

    for strategy_type in strategies_list:
        if strategy_type in strategy_mapping:
            all_configs.extend(strategy_mapping[strategy_type]())
        else:
            logger.warning(f"未知的策略类型: {strategy_type}")

    return all_configs


def run_comparison(
    symbol: str = "000001",
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31",
    strategies: list[StrategyTestConfig] = None,
    initial_cash: float = 100000,
    show_plot: bool = True,
    save_report: bool = True,
) -> None:
    """
    运行策略对比

    参数:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        strategies: 策略配置列表
        initial_cash: 初始资金
        show_plot: 是否显示图表
        save_report: 是否保存报告
    """
    logger.info("=" * 80)
    logger.info("量化交易策略对比系统")
    logger.info("=" * 80)

    # 如果没有指定策略，使用默认策略
    if strategies is None:
        strategies = [
            StrategyTestConfig('MA(5,20)', DualMovingAverage, {'fast_period': 5, 'slow_period': 20}),
            StrategyTestConfig('MACD(12,26,9)', MACDStrategy, {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9
            }),
        ]

    logger.info(f"\n对比策略数量: {len(strategies)}")
    for i, strategy_config in enumerate(strategies, 1):
        logger.info(f"  {i}. {strategy_config.name}")

    # 获取手续费配置
    from utils.config import config as app_config
    commission = app_config.get('backtest.commission', 0.0003)

    # 创建比较器
    comparator = StrategyComparator(
        initial_cash=initial_cash,
        commission=commission,
    )

    # 运行对比
    result = comparator.compare(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        strategies=strategies,
        adjust="qfq"
    )

    # 打印摘要
    comparator.print_summary(result)

    # 保存报告
    if save_report:
        report_dir = Path(__file__).parent.parent / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"comparison_{symbol}_{timestamp}.csv"

        df = result.to_dataframe()
        df.to_csv(report_file, index=False, encoding='utf-8-sig')
        logger.info(f"\n报告已保存到: {report_file}")

    # 绘制图表
    if show_plot:
        try:
            logger.info("\n正在绘制对比图表...")
            comparator.plot_comparison(result)
        except Exception as e:
            logger.warning(f"图表绘制失败: {e}")

    logger.info("\n" + "=" * 80)
    logger.info("策略对比完成！")
    logger.info("=" * 80)


def parse_args():
    """
    解析命令行参数
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='量化交易策略对比系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                                    # 默认对比(MA vs MACD)
  %(prog)s --strategies ma macd              # 对比MA和MACD
  %(prog)s --strategies ma_params            # 对比多个MA参数组合
  %(prog)s --strategies ma_params --params "5,20 10,30"  # 自定义MA参数
  %(prog)s --strategies all                  # 对比所有策略
  %(prog)s --symbol 600000                   # 对比浦发银行
  %(prog)s --start 2022-01-01 --end 2024-12-31  # 指定日期范围
  %(prog)s --cash 50000                      # 设置初始资金5万
  %(prog)s --no-plot                         # 不显示图表

可用策略类型:
  ma           双均线策略（默认）
  macd         MACD策略
  macd_trend   MACD+趋势过滤
  macd_rsi     MACD+RSI组合
  ma_params    多个MA参数组合
  macd_params  多个MACD参数组合
  all          所有策略
        """
    )

    parser.add_argument(
        '--symbol',
        type=str,
        default='000001',
        help='股票代码（默认: 000001）'
    )

    parser.add_argument(
        '--start',
        type=str,
        default='2023-01-01',
        help='开始日期，格式YYYY-MM-DD（默认: 2023-01-01）'
    )

    parser.add_argument(
        '--end',
        type=str,
        default='2024-12-31',
        help='结束日期，格式YYYY-MM-DD（默认: 2024-12-31）'
    )

    parser.add_argument(
        '--strategies',
        type=str,
        nargs='+',
        default=['ma', 'macd'],
        choices=['ma', 'macd', 'macd_trend', 'macd_rsi', 'ma_params', 'macd_params', 'all'],
        help='要对比的策略列表（默认: ma macd）'
    )

    parser.add_argument(
        '--params',
        type=str,
        help='策略参数（用于ma_params或macd_params）格式: "5,20 10,30"'
    )

    parser.add_argument(
        '--cash',
        type=float,
        default=100000,
        help='初始资金（默认: 100000）'
    )

    parser.add_argument(
        '--no-plot',
        action='store_true',
        help='不显示图表'
    )

    parser.add_argument(
        '--no-save',
        action='store_true',
        help='不保存报告'
    )

    return parser.parse_args()


if __name__ == "__main__":
    """
    主程序入口
    """
    # 解析参数
    args = parse_args()

    # 构建策略配置
    if 'all' in args.strategies:
        # 对比所有策略
        strategies = create_strategy_configs('all')
    elif 'ma_params' in args.strategies:
        # MA参数组合
        strategies = create_strategy_configs('ma_params', args.params)
    elif 'macd_params' in args.strategies:
        # MACD参数组合
        strategies = create_strategy_configs('macd_params', args.params)
    else:
        # 解析策略列表
        strategies = parse_strategy_args(args.strategies)

    # 运行对比
    run_comparison(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        strategies=strategies,
        initial_cash=args.cash,
        show_plot=not args.no_plot,
        save_report=not args.no_save,
    )
