# -*- coding: utf-8 -*-
"""
选股脚本
使用插件式选股器进行股票筛选

使用方法:
    # 列出所有可用选股器
    uv run python scripts/run_screener.py --list

    # 因子选股
    uv run python scripts/run_screener.py --screener factor --pe 0 30 --pb 0 3

    # 技术选股
    uv run python scripts/run_screener.py --screener technical --rsi 0 30

    # 组合选股
    uv run python scripts/run_screener.py --composite factor technical --logic AND

    # 自定义选股器
    uv run python scripts/run_screener.py --screener my_custom
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from screeners import ScreenerManager
from data.data_feed import AStockDataFeed
from utils.logger import logger


def list_screeners():
    """列出所有可用选股器"""
    print("\n" + "=" * 80)
    print("可用选股器列表")
    print("=" * 80 + "\n")

    manager = ScreenerManager()
    screeners = manager.list_screeners()

    # 按类别分组
    by_category = {}
    for name, info in screeners.items():
        category = info.get('category', 'unknown')
        if category not in by_category:
            by_category[category] = []
        by_category[category].append((name, info))

    # 打印
    for category, items in sorted(by_category.items()):
        print(f"\n【{category.upper()}】")
        for name, info in items:
            print(f"  - {name:20s} : {info.get('description', '无描述')}")

    print("\n" + "=" * 80)
    print(f"总计: {len(screeners)} 个选股器\n")


def get_stock_list(limit: int = 100) -> list[str]:
    """
    获取股票列表

    参数:
        limit: 限制数量（用于测试）

    返回:
        List[str]: 股票代码列表
    """
    logger.info("获取股票列表...")

    data_feed = AStockDataFeed()
    df = data_feed.get_stock_list(market='all')

    if df.empty:
        logger.error("获取股票列表失败")
        return []

    # 提取股票代码
    symbols = df['code'].tolist()

    # 限制数量（用于测试）
    if limit:
        symbols = symbols[:limit]

    logger.info(f"获取到 {len(symbols)} 只股票")

    return symbols


def run_screener(
    screener_name: str,
    stock_list: list[str] = None,
    stock_limit: int = 100,
    **kwargs
):
    """
    运行单个选股器

    参数:
        screener_name: 选股器名称
        stock_list: 股票列表（如果为None，则自动获取）
        stock_limit: 股票列表数量限制
        **kwargs: 选股参数
    """
    logger.info("=" * 80)
    logger.info(f"选股器: {screener_name}")
    logger.info("=" * 80)

    # 获取股票列表
    if stock_list is None:
        stock_list = get_stock_list(limit=stock_limit)

    if not stock_list:
        logger.error("股票列表为空")
        return

    # 创建选股器管理器
    manager = ScreenerManager()

    # 运行选股
    result = manager.screen(
        screener_name=screener_name,
        stock_list=stock_list,
        **kwargs
    )

    # 打印结果
    print(result)

    # 打印详细结果
    if result.symbols:
        print(f"\n选中的股票 ({len(result.symbols)}):")
        for i, symbol in enumerate(result.symbols[:20], 1):  # 只显示前20只
            print(f"  {i}. {symbol}")

        if len(result.symbols) > 20:
            print(f"  ... 还有 {len(result.symbols) - 20} 只")

    # 保存结果
    save_result(result)

    return result


def run_composite_screener(
    screener_names: list[str],
    logic: str = 'AND',
    stock_list: list[str] = None,
    stock_limit: int = 100,
    configs: list[dict] = None,
):
    """
    运行组合选股器

    参数:
        screener_names: 子选股器名称列表
        logic: 组合逻辑 ('AND' 或 'OR')
        stock_list: 股票列表
        stock_limit: 股票列表数量限制
        configs: 每个子选股器的参数配置
    """
    logger.info("=" * 80)
    logger.info(f"组合选股: {' + '.join(screener_names)} ({logic} 逻辑)")
    logger.info("=" * 80)

    # 获取股票列表
    if stock_list is None:
        stock_list = get_stock_list(limit=stock_limit)

    if not stock_list:
        logger.error("股票列表为空")
        return

    # 创建选股器管理器
    manager = ScreenerManager()

    # 创建组合选股器
    composite = manager.create_composite(
        screener_names=screener_names,
        logic=logic,
        configs=configs
    )

    # 运行选股
    result = composite.screen(stock_list)

    # 打印结果
    print(result)

    # 打印详细结果
    if result.symbols:
        print(f"\n选中的股票 ({len(result.symbols)}):")
        for i, symbol in enumerate(result.symbols[:20], 1):
            print(f"  {i}. {symbol}")

        if len(result.symbols) > 20:
            print(f"  ... 还有 {len(result.symbols) - 20} 只")

    # 保存结果
    save_result(result)

    return result


def save_result(result):
    """保存选股结果"""
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"screening_{result.screener_name}_{timestamp}.csv"

    df = result.to_dataframe()
    df.to_csv(report_file, index=False, encoding='utf-8-sig')

    logger.info(f"\n结果已保存到: {report_file}")


def parse_args():
    """解析命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='插件式选股系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有可用选股器
  %(prog)s --list

  # 因子选股：低PE
  %(prog)s --screener low_pe --max-pe 15

  # 因子选股：自定义条件
  %(prog)s --screener factor --pe 0 30 --pb 0 3 --market-cap 50 1000

  # 技术选股：RSI超卖
  %(prog)s --screener oversold --rsi-threshold 30

  # 技术选股：MACD金叉
  %(prog)s --screener golden_cross

  # 动量选股
  %(prog)s --screener momentum --days 20 --top-n 50

  # 组合选股（AND逻辑）
  %(prog)s --composite factor technical --logic AND --pe 0 30 --rsi 0 40

  # 自定义选股器
  %(prog)s --screener my_custom

  # 限制股票数量（用于测试）
  %(prog)s --screener factor --stock-limit 50
        """
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='列出所有可用选股器'
    )

    parser.add_argument(
        '--screener',
        type=str,
        help='选股器名称'
    )

    parser.add_argument(
        '--composite',
        nargs='+',
        help='组合选股：指定多个选股器名称'
    )

    parser.add_argument(
        '--logic',
        type=str,
        choices=['AND', 'OR'],
        default='AND',
        help='组合逻辑（AND或OR，默认：AND）'
    )

    # 因子选股参数
    parser.add_argument('--pe', nargs=2, type=float, metavar=('MIN', 'MAX'), help='PE范围')
    parser.add_argument('--pb', nargs=2, type=float, metavar=('MIN', 'MAX'), help='PB范围')
    parser.add_argument('--market-cap', nargs=2, type=float, metavar=('MIN', 'MAX'), help='市值范围（亿）')

    # 技术选股参数
    parser.add_argument('--rsi', nargs=2, type=float, metavar=('MIN', 'MAX'), help='RSI范围')
    parser.add_argument('--rsi-threshold', type=float, help='RSI阈值（用于oversold）')
    parser.add_argument('--ma-short', type=int, default=5, help='短期均线周期')
    parser.add_argument('--ma-long', type=int, default=20, help='长期均线周期')

    # 动量选股参数
    parser.add_argument('--days', type=int, default=20, help='统计天数')
    parser.add_argument('--top-n', type=int, default=50, help='前N只股票')

    # 通用参数
    parser.add_argument(
        '--stock-limit',
        type=int,
        default=100,
        help='股票列表数量限制（用于测试，默认：100）'
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

    # 列出所有选股器
    if args.list:
        list_screeners()
        exit(0)

    # 组合选股
    if args.composite:
        run_composite_screener(
            screener_names=args.composite,
            logic=args.logic,
            stock_limit=args.stock_limit
        )
    # 单个选股器
    elif args.screener:
        # 构建选股参数
        kwargs = {}

        if args.pe:
            kwargs['pe'] = tuple(args.pe)
        if args.pb:
            kwargs['pb'] = tuple(args.pb)
        if args.market_cap:
            kwargs['market_cap'] = tuple(args.market_cap)
        if args.rsi:
            kwargs['rsi'] = tuple(args.rsi)
        if args.rsi_threshold:
            kwargs['rsi_threshold'] = args.rsi_threshold
        if args.ma_short:
            kwargs['ma_short'] = args.ma_short
        if args.ma_long:
            kwargs['ma_long'] = args.ma_long
        if args.days:
            kwargs['days'] = args.days
        if args.top_n:
            kwargs['top_n'] = args.top_n

        run_screener(
            screener_name=args.screener,
            stock_limit=args.stock_limit,
            **kwargs
        )
    else:
        print("请使用 --list 查看可用选股器，或指定 --screener 或 --composite 参数")
        print("使用 --help 查看帮助信息")
