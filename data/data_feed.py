# -*- coding: utf-8 -*-
"""
A股数据获取模块
使用AKShare获取股票历史行情数据
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path


class AStockDataFeed:
    """
    A股数据源类

    功能说明：
    1. 获取A股历史行情数据（开高低收、成交量等）
    2. 获取股票列表
    3. 数据缓存机制（避免频繁请求API）

    支持的数据字段：
        - 日期、开盘价、最高价、最低价、收盘价
        - 成交量、成交额、涨跌幅、涨跌额、换手率

    使用示例：
        # 创建数据源实例
        data_feed = AStockDataFeed()

        # 获取单只股票数据
        df = data_feed.get_stock_data("000001", "2023-01-01", "2024-12-31")

        # 获取股票列表
        stocks = data_feed.get_stock_list()
    """

    def __init__(self, cache_dir: str = None):
        """
        初始化数据源

        参数:
            cache_dir: 数据缓存目录，默认为 ./data/storage
        """
        if cache_dir is None:
            # 设置默认缓存目录
            project_root = Path(__file__).parent.parent
            cache_dir = project_root / "data" / "storage"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        print(f"[OK] 数据源初始化完成，缓存目录: {self.cache_dir}")

    def get_stock_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        获取股票历史行情数据

        参数:
            symbol: 股票代码，例如 "000001"（平安银行）
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"
            adjust: 复权类型
                - "qfq": 前复权（默认，推荐用于回测）
                - "hfq": 后复权
                - "": 不复权

        返回:
            DataFrame包含以下列：
                - 日期、开盘、最高、最低、收盘
                - 成交量、成交额、振幅、涨跌幅、涨跌额、换手率

        示例:
            df = data_feed.get_stock_data(
                symbol="000001",
                start_date="2023-01-01",
                end_date="2024-12-31",
                adjust="qfq"
            )
            print(df.head())
        """
        try:
            # AKShare的股票历史行情接口
            # 注意：stock_zh_a_hist 接口直接使用原始6位数字代码即可
            # - 深市: 000001, 000002 等
            # - 沪市: 600000, 600001 等
            # 不需要添加 "sh" 或 "sz" 前缀

            ak_symbol = symbol
            print(f"正在获取 {symbol} 的数据...")

            # 调用AKShare接口获取历史行情
            # ak.stock_zh_a_hist() 的参数说明：
            # - symbol: 股票代码
            # - period: 数据周期 (daily, weekly, monthly)
            # - start_date: 开始日期
            # - end_date: 结束日期
            # - adjust: 复权类型 ("", "qfq", "hfq")
            df = ak.stock_zh_a_hist(
                symbol=ak_symbol,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust=adjust
            )

            # 数据预处理
            if df is not None and not df.empty:
                # 重命名列名为英文（方便后续处理）
                df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '最高': 'high',
                    '最低': 'low',
                    '收盘': 'close',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '振幅': 'amplitude',
                    '涨跌幅': 'percent_change',
                    '涨跌额': 'change',
                    '换手率': 'turnover'
                }, inplace=True)

                # 设置日期为索引
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)

                # 按日期排序
                df.sort_index(inplace=True)

                print(f"[OK] 成功获取 {len(df)} 条数据")
                return df
            else:
                print(f"[FAIL] 未获取到数据")
                return pd.DataFrame()

        except Exception as e:
            print(f"[FAIL] 获取数据失败: {e}")
            return pd.DataFrame()

    def get_stock_list(self, market: str = "all") -> pd.DataFrame:
        """
        获取A股股票列表

        参数:
            market: 市场类型
                - "all": 全部A股（默认）
                - "sh": 沪市
                - "sz": 深市

        返回:
            DataFrame包含股票代码、名称、市场等信息

        示例:
            stocks = data_feed.get_stock_list()
            print(stocks.head())
        """
        try:
            print(f"正在获取A股列表...")

            if market == "all":
                # 获取沪深A股列表
                df = ak.stock_info_a_code_name()
            elif market == "sh":
                # 仅获取沪市
                df = ak.stock_info_sh_name_code()
            elif market == "sz":
                # 仅获取深市
                df = ak.stock_info_sz_name_code()
            else:
                raise ValueError(f"不支持的市场类型: {market}")

            print(f"[OK] 成功获取 {len(df)} 只股票")
            return df

        except Exception as e:
            print(f"[FAIL] 获取股票列表失败: {e}")
            return pd.DataFrame()

    def save_to_cache(self, symbol: str, df: pd.DataFrame) -> None:
        """
        保存数据到本地缓存

        参数:
            symbol: 股票代码
            df: 要保存的数据
        """
        if df.empty:
            print("数据为空，跳过保存")
            return

        # 生成缓存文件路径
        cache_file = self.cache_dir / f"{symbol}.csv"

        # 保存为CSV文件
        df.to_csv(cache_file, encoding='utf-8-sig')
        print(f"[OK] 数据已缓存到: {cache_file}")

    def load_from_cache(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        从本地缓存加载数据

        参数:
            symbol: 股票代码

        返回:
            DataFrame或None（如果缓存不存在）
        """
        cache_file = self.cache_dir / f"{symbol}.csv"

        if cache_file.exists():
            df = pd.read_csv(cache_file, index_col='date', parse_dates=True)
            print(f"[OK] 从缓存加载 {len(df)} 条数据")
            return df
        else:
            print(f"缓存文件不存在: {cache_file}")
            return None


# ==================== 测试代码 ====================
if __name__ == "__main__":
    """
    测试数据获取功能
    """
    from loguru import logger
    # from utils.logger import logger

    logger.info("=== 数据获取测试 ===")

    # 创建数据源实例
    data_feed = AStockDataFeed()

    # 测试1: 获取股票列表
    print("\n【测试1】获取股票列表")
    stocks = data_feed.get_stock_list()
    if not stocks.empty:
        print(f"股票总数: {len(stocks)}")
        print(f"前5只股票:\n{stocks.head()}")

    # 测试2: 获取单只股票数据
    print("\n【测试2】获取平安银行(000001)历史数据")
    df = data_feed.get_stock_data(
        symbol="000001",
        start_date="2024-01-01",
        end_date="2024-12-31",
        adjust=""
    )

    if not df.empty:
        print(f"\n数据形状: {df.shape}")
        print(f"数据列名: {df.columns.tolist()}")
        print(f"\n前5条数据:\n{df.head()}")
        print(f"\n后5条数据:\n{df.tail()}")

        # 测试3: 缓存数据
        print("\n【测试3】保存数据到缓存")
        data_feed.save_to_cache("000001", df)

    logger.info("[OK] 数据获取测试完成")
