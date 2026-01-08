# -*- coding: utf-8 -*-
"""
回测运行脚本
用于运行策略回测的便捷脚本

使用方法:
    # 方式1: 直接运行（使用默认参数）
    uv run python scripts/run_backtest.py

    # 方式2: 指定股票代码和日期
    uv run python scripts/run_backtest.py --symbol 000001 --start 2023-01-01 --end 2024-12-31

    # 方式3: 自定义策略参数
    uv run python scripts/run_backtest.py --fast 10 --slow 30
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_feed import AStockDataFeed
from strategies.ma_strategy import DualMovingAverage
from core.backtest_engine import BacktestEngine
from utils.logger import logger
from utils.config import config


def run_backtest(
    symbol: str = "000001",
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
    fast_period: int = 5,
    slow_period: int = 20,
    initial_cash: float = 100000,
    show_plot: bool = True,
) -> None:
    """
    运行回测

    参数:
        symbol: 股票代码（默认000001平安银行）
        start_date: 开始日期
        end_date: 结束日期
        fast_period: 快线周期
        slow_period: 慢线周期
        initial_cash: 初始资金
        show_plot: 是否显示图表

    使用示例:
        run_backtest(
            symbol="000001",
            start_date="2023-01-01",
            end_date="2024-12-31",
            fast_period=5,
            slow_period=20
        )
    """

    logger.info("=" * 80)
    logger.info("量化交易回测系统")
    logger.info("=" * 80)

    # ==================== 步骤1: 获取数据 ====================
    logger.info("\n【步骤1】获取股票数据")
    logger.info(f"股票代码: {symbol}")
    logger.info(f"时间范围: {start_date} 至 {end_date}")

    data_feed = AStockDataFeed()
    df = data_feed.get_stock_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        adjust="qfq"  # 前复权
    )

    # 检查数据
    if df.empty:
        logger.error("数据获取失败，请检查股票代码或日期范围")
        return

    logger.info(f"✓ 数据获取成功，共 {len(df)} 条记录")
    logger.info(f"数据范围: {df.index[0]} 至 {df.index[-1]}")
    logger.info(f"\n数据预览:\n{df.head()}")

    # ==================== 步骤2: 创建回测引擎 ====================
    logger.info("\n【步骤2】创建回测引擎")
    logger.info(f"初始资金: {initial_cash:.2f}")

    # 从配置文件读取手续费
    commission = config.get('backtest.commission', 0.0003)
    logger.info(f"手续费率: {commission:.4f}")

    engine = BacktestEngine(
        initial_cash=initial_cash,
        commission=commission,
    )

    # ==================== 步骤3: 添加数据和策略 ====================
    logger.info("\n【步骤3】配置策略参数")
    logger.info(f"策略: 双均线策略")
    logger.info(f"快线周期: {fast_period} 天")
    logger.info(f"慢线周期: {slow_period} 天")

    # 添加数据
    engine.add_data(df)

    # 添加策略
    engine.add_strategy(
        DualMovingAverage,
        fast_period=fast_period,
        slow_period=slow_period,
    )

    # ==================== 步骤4: 运行回测 ====================
    logger.info("\n【步骤4】运行回测")

    result = engine.run()

    # ==================== 步骤5: 显示结果 ====================
    logger.info("\n【步骤5】回测结果")
    print(result)

    # 绘制图表
    if show_plot:
        logger.info("\n正在绘制图表...")
        try:
            engine.plot()
            logger.info("✓ 图表已显示（关闭图表窗口以退出程序）")
        except Exception as e:
            logger.warning(f"图表绘制失败: {e}")

    logger.info("\n" + "=" * 80)
    logger.info("回测完成！")
    logger.info("=" * 80)


def parse_args():
    """
    解析命令行参数

    使用argparse处理命令行参数

    示例:
        python run_backtest.py --symbol 000001 --fast 10 --slow 30
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='量化交易回测系统 - 双均线策略',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 使用默认参数
  %(prog)s --symbol 600000          # 回测浦发银行
  %(prog)s --fast 10 --slow 30      # 使用10日和30日均线
  %(prog)s --start 2022-01-01       # 指定开始日期
  %(prog)s --cash 50000             # 设置初始资金5万
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
        '--fast',
        type=int,
        default=5,
        help='快线周期（默认: 5）'
    )

    parser.add_argument(
        '--slow',
        type=int,
        default=20,
        help='慢线周期（默认: 20）'
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

    return parser.parse_args()


if __name__ == "__main__":
    """
    主程序入口

    说明：
        1. 解析命令行参数
        2. 运行回测
        3. 显示结果
    """
    # 解析参数
    args = parse_args()

    # 运行回测
    run_backtest(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        fast_period=args.fast,
        slow_period=args.slow,
        initial_cash=args.cash,
        show_plot=not args.no_plot,
    )
