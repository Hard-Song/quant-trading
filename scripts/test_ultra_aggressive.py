# -*- coding: utf-8 -*-
"""
单独测试极激进震荡策略
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_feed import AStockDataFeed
from core.backtest_engine import BacktestEngine
from strategies.oscillation_strategy import UltraAggressiveOscillation
from utils.logger import logger

def main():
    logger.info("="*80)
    logger.info("极激进震荡策略单独测试")
    logger.info("="*80)

    # 获取数据（过去120天）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=120)

    data_feed = AStockDataFeed()
    df = data_feed.get_stock_data(
        symbol="002202",
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        adjust="qfq"
    )

    if df.empty:
        logger.error("数据获取失败")
        return

    logger.info(f"成功获取 {len(df)} 条数据\n")

    # 运行回测
    logger.info("开始运行极激进震荡策略...")
    engine = BacktestEngine(
        initial_cash=100000,
        use_a_stock_comm=True,
    )
    engine.add_data(df)
    engine.add_strategy(UltraAggressiveOscillation)

    try:
        result = engine.run()
        logger.info(f"\n回测完成！")
        logger.info(f"最终资金: {result.final_value:.2f}")
        logger.info(f"收益率: {result.total_return:.2f}%")
        logger.info(f"交易次数: {result.total_trades}")
        logger.info(f"胜率: {result.win_rate:.2f}%")
        logger.info(f"最大回撤: {result.max_drawdown:.2f}%")
        logger.info(f"夏普比率: {result.sharpe_ratio:.2f}")

        # 计算交易频率
        if result.total_trades > 0:
            avg_days = 120 / result.total_trades
            logger.info(f"\n交易频率: 每 {avg_days:.1f} 天交易一次")

            if avg_days <= 3:
                logger.info("✓ 满足高频交易要求（≤3天）")
            else:
                logger.warning(f"✗ 未满足高频交易要求（需要≤3天，实际{avg_days:.1f}天）")
        else:
            logger.warning("该策略未产生任何交易")

    except Exception as e:
        logger.error(f"回测失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
