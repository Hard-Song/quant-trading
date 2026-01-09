# -*- coding: utf-8 -*-
"""
批量回测脚本
对多只股票运行同一策略，生成汇总报告

使用方法:
    # 基本用法
    uv run python scripts/run_batch_backtest.py --symbols 000001 600000

    # 指定策略和参数
    uv run python scripts/run_batch_backtest.py --strategy ma --fast 5 --slow 20

    # 先选股，再批量回测
    uv run python scripts/run_batch_backtest.py --screener low_pe --max-pe 30 --stock-limit 50

    # 使用股票列表文件
    uv run python scripts/run_batch_backtest.py --stock-file stocks.txt
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import BatchBacktestEngine, run_batch_backtest
from strategies.ma_strategy import DualMovingAverage
from strategies.macd_strategy import MACDStrategy
from screeners import ScreenerManager
from data.data_feed import AStockDataFeed
from utils.logger import logger


# 策略映射
STRATEGIES = {
    'ma': DualMovingAverage,
    'macd': MACDStrategy,
}


def run_batch_backtest_cmd(
    symbols: list[str],
    strategy_name: str = 'ma',
    start_date: str = '2023-01-01',
    end_date: str = '2024-12-31',
    strategy_params: dict = None,
    initial_cash: float = 100000,
    parallel: bool = True,
    top_n: int = 10,
    save_results: bool = True,
):
    """
    运行批量回测

    参数:
        symbols: 股票代码列表
        strategy_name: 策略名称
        start_date: 开始日期
        end_date: 结束日期
        strategy_params: 策略参数
        initial_cash: 初始资金
        parallel: 是否并行处理
        top_n: 显示前N名
        save_results: 是否保存结果
    """
    logger.info("=" * 80)
    logger.info("批量回测系统")
    logger.info("=" * 80)

    # 获取策略类
    strategy_class = STRATEGIES.get(strategy_name, DualMovingAverage)

    logger.info(f"\n策略: {strategy_class.__name__}")
    logger.info(f"股票数量: {len(symbols)}")
    logger.info(f"时间范围: {start_date} ~ {end_date}")
    logger.info(f"策略参数: {strategy_params}")

    # 创建批量回测引擎
    batch_engine = BatchBacktestEngine(
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        initial_cash=initial_cash,
        max_workers=4,
    )

    # 运行批量回测
    batch_result = batch_engine.run_batch(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        parallel=parallel,
    )

    # 打印汇总
    print("\n" + "=" * 80)
    print("批量回测汇总")
    print("=" * 80)
    print(batch_result)

    # 打印统计信息
    stats = batch_result.get_statistics()
    print("\n详细统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # 打印前N名
    if top_n > 0:
        print(f"\n前 {top_n} 名股票:")
        top_df = batch_result.get_top_n(n=top_n, metric='total_return')
        print(top_df.to_string(index=False))

    # 保存结果
    if save_results:
        batch_engine.save_results(batch_result)

        # 同时保存前N名
        reports_dir = Path(__file__).parent.parent / "reports"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        top_file = reports_dir / f"batch_top{top_n}_{strategy_name}_{timestamp}.csv"
        top_df.to_csv(top_file, index=False, encoding='utf-8-sig')
        logger.info(f"\n前{top_n}名已保存: {top_file}")

    logger.info("\n" + "=" * 80)
    logger.info("批量回测完成！")
    logger.info("=" * 80)

    return batch_result


def run_with_screener(
    screener_name: str,
    strategy_name: str = 'ma',
    start_date: str = '2023-01-01',
    end_date: str = '2024-12-31',
    stock_limit: int = 100,
    screener_params: dict = None,
    strategy_params: dict = None,
    **kwargs
):
    """
    先选股，再批量回测

    参数:
        screener_name: 选股器名称
        strategy_name: 策略名称
        start_date: 开始日期
        end_date: 结束日期
        stock_limit: 股票数量限制
        screener_params: 选股参数
        strategy_params: 策略参数
        **kwargs: 其他参数
    """
    logger.info("=" * 80)
    logger.info("选股 + 批量回测")
    logger.info("=" * 80)

    # 1. 获取股票列表
    logger.info("\n【步骤1】获取股票列表")
    data_feed = AStockDataFeed()
    all_stocks_df = data_feed.get_stock_list()
    all_stocks = all_stocks_df['代码'].tolist()[:stock_limit]
    logger.info(f"获取到 {len(all_stocks)} 只股票")

    # 2. 选股
    logger.info(f"\n【步骤2】执行选股: {screener_name}")
    manager = ScreenerManager()
    screener = manager.get_screener(screener_name)

    screener_params = screener_params or {}
    screening_result = screener.screen(
        stock_list=all_stocks,
        **screener_params
    )

    print(screening_result)

    if not screening_result.symbols:
        logger.error("没有选中的股票，无法继续回测")
        return

    logger.info(f"选中 {len(screening_result.symbols)} 只股票")

    # 3. 批量回测
    logger.info(f"\n【步骤3】批量回测: {strategy_name}")
    batch_result = run_batch_backtest_cmd(
        symbols=screening_result.symbols,
        strategy_name=strategy_name,
        start_date=start_date,
        end_date=end_date,
        strategy_params=strategy_params,
        **kwargs
    )

    return batch_result


def parse_args():
    """解析命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='批量回测系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  %(prog)s --symbols 000001 600000 000002

  # 指定策略和参数
  %(prog)s --strategy macd --symbols 000001 600000

  # 先选股再回测
  %(prog)s --screener low_pe --max-pe 30 --stock-limit 50

  # 使用股票列表文件
  %(prog)s --stock-file stocks.txt

  # 指定日期范围
  %(prog)s --start 2022-01-01 --end 2024-12-31

  # 查看前20名
  %(prog)s --top-n 20

可用策略:
  ma    双均线策略
  macd  MACD策略
        """
    )

    # 选股相关
    parser.add_argument(
        '--screener',
        type=str,
        help='选股器名称（先选股再回测）'
    )
    parser.add_argument(
        '--stock-limit',
        type=int,
        default=100,
        help='选股时的股票数量限制（默认：100）'
    )

    # 股票列表
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='股票代码列表'
    )
    parser.add_argument(
        '--stock-file',
        type=str,
        help='股票列表文件（每行一个股票代码）'
    )

    # 策略相关
    parser.add_argument(
        '--strategy',
        type=str,
        default='ma',
        choices=['ma', 'macd'],
        help='策略类型（默认：ma）'
    )

    # MA策略参数
    parser.add_argument(
        '--fast',
        type=int,
        default=5,
        help='快线周期（默认：5）'
    )
    parser.add_argument(
        '--slow',
        type=int,
        default=20,
        help='慢线周期（默认：20）'
    )

    # MACD策略参数
    parser.add_argument(
        '--macd-fast',
        type=int,
        default=12,
        help='MACD快线周期（默认：12）'
    )
    parser.add_argument(
        '--macd-slow',
        type=int,
        default=26,
        help='MACD慢线周期（默认：26）'
    )
    parser.add_argument(
        '--macd-signal',
        type=int,
        default=9,
        help='MACD信号线周期（默认：9）'
    )

    # 选股参数
    parser.add_argument(
        '--max-pe',
        type=float,
        help='最大PE（用于low_pe选股器）'
    )
    parser.add_argument(
        '--rsi-threshold',
        type=float,
        help='RSI阈值（用于oversold选股器）'
    )

    # 日期范围
    parser.add_argument(
        '--start',
        type=str,
        default='2023-01-01',
        help='开始日期（默认：2023-01-01）'
    )
    parser.add_argument(
        '--end',
        type=str,
        default='2024-12-31',
        help='结束日期（默认：2024-12-31）'
    )

    # 其他参数
    parser.add_argument(
        '--cash',
        type=float,
        default=100000,
        help='初始资金（默认：100000）'
    )
    parser.add_argument(
        '--no-parallel',
        action='store_true',
        help='不使用并行处理'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=10,
        help='显示前N名（默认：10）'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='不保存结果'
    )

    return parser.parse_args()


if __name__ == "__main__":
    """主程序入口"""
    args = parse_args()

    # 获取股票列表
    if args.stock_file:
        # 从文件读取
        with open(args.stock_file, 'r') as f:
            symbols = [line.strip() for line in f if line.strip()]
    elif args.symbols:
        # 命令行参数
        symbols = args.symbols
    else:
        symbols = None

    # 构建策略参数
    strategy_params = {}
    if args.strategy == 'ma':
        strategy_params = {
            'fast_period': args.fast,
            'slow_period': args.slow,
        }
    elif args.strategy == 'macd':
        strategy_params = {
            'fast_period': args.macd_fast,
            'slow_period': args.macd_slow,
            'signal_period': args.macd_signal,
        }

    # 构建选股参数
    screener_params = {}
    if args.max_pe:
        screener_params['max_pe'] = args.max_pe
    if args.rsi_threshold:
        screener_params['rsi_threshold'] = args.rsi_threshold

    # 执行批量回测
    if args.screener:
        # 先选股，再回测
        run_with_screener(
            screener_name=args.screener,
            strategy_name=args.strategy,
            start_date=args.start,
            end_date=args.end,
            stock_limit=args.stock_limit,
            screener_params=screener_params,
            strategy_params=strategy_params,
            parallel=not args.no_parallel,
            top_n=args.top_n,
            save_results=not args.no_save,
        )
    elif symbols:
        # 直接批量回测
        run_batch_backtest_cmd(
            symbols=symbols,
            strategy_name=args.strategy,
            start_date=args.start,
            end_date=args.end,
            strategy_params=strategy_params,
            initial_cash=args.cash,
            parallel=not args.no_parallel,
            top_n=args.top_n,
            save_results=not args.no_save,
        )
    else:
        print("请指定 --symbols 或 --screener 参数")
        print("使用 --help 查看帮助信息")
