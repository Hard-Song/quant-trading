# -*- coding: utf-8 -*-
"""
数据管理器模块
统一管理数据获取、缓存和复用，避免重复API调用
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from data.data_feed import AStockDataFeed
from utils.logger import logger
import pickle


@dataclass
class DataRequest:
    """
    数据请求标识
    用于缓存key的生成
    """
    symbol: str
    start_date: str
    end_date: str
    adjust: str = ""

    def __hash__(self):
        """生成唯一标识符"""
        return hash((self.symbol, self.start_date, self.end_date, self.adjust))

    def __eq__(self, other):
        """判断两个请求是否相同"""
        if not isinstance(other, DataRequest):
            return False
        return (
            self.symbol == other.symbol and
            self.start_date == other.start_date and
            self.end_date == other.end_date and
            self.adjust == other.adjust
        )


class DataManager:
    """
    数据管理器

    核心功能：
        1. 数据缓存：避免重复获取相同数据
        2. 批量获取：优化多股票数据获取效率
        3. 数据复用：多个策略共享同一份数据
        4. 持久化：支持数据持久化到本地

    使用场景：
        - 策略对比：多个策略使用同一份股票数据
        - 批量回测：批量获取多只股票数据
        - 参数优化：同一股票、不同参数的回测

    使用示例：
        # 创建数据管理器
        manager = DataManager()

        # 获取数据（自动缓存）
        df = manager.get_data(
            symbol="000001",
            start_date="2023-01-01",
            end_date="2024-12-31"
        )

        # 再次获取相同数据（从缓存读取，不调用API）
        df2 = manager.get_data(
            symbol="000001",
            start_date="2023-01-01",
            end_date="2024-12-31"
        )

        # 批量获取多只股票
        dfs = manager.get_batch_data(
            symbols=["000001", "600000", "000002"],
            start_date="2023-01-01",
            end_date="2024-12-31"
        )
    """

    def __init__(self, cache_dir: str = None, use_persistent_cache: bool = True):
        """
        初始化数据管理器

        参数:
            cache_dir: 缓存目录路径
            use_persistent_cache: 是否使用持久化缓存（pickle文件）
        """
        # 设置缓存目录
        if cache_dir is None:
            project_root = Path(__file__).parent.parent
            cache_dir = project_root / "data" / "cache"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 内存缓存：{DataRequest: DataFrame}
        self._memory_cache: Dict[DataRequest, pd.DataFrame] = {}

        # 是否使用持久化缓存
        self.use_persistent_cache = use_persistent_cache

        # 数据源
        self.data_feed = AStockDataFeed()

        logger.info(f"数据管理器初始化完成")
        logger.info(f"缓存目录: {self.cache_dir}")
        logger.info(f"持久化缓存: {'启用' if use_persistent_cache else '禁用'}")

    def get_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "",
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        获取股票数据（带缓存）

        参数:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型 ("", "qfq", "hfq")
            force_refresh: 是否强制刷新（忽略缓存）

        返回:
            DataFrame: 股票数据
        """
        # 创建数据请求标识
        request = DataRequest(symbol, start_date, end_date, adjust)

        # 如果不强制刷新，尝试从缓存获取
        if not force_refresh:
            # 1. 先查内存缓存
            if request in self._memory_cache:
                logger.info(f"从内存缓存读取数据: {symbol}")
                return self._memory_cache[request].copy()

            # 2. 再查持久化缓存
            if self.use_persistent_cache:
                cached_data = self._load_from_persistent_cache(request)
                if cached_data is not None:
                    logger.info(f"从持久化缓存读取数据: {symbol}")
                    # 存入内存缓存
                    self._memory_cache[request] = cached_data
                    return cached_data.copy()

        # 缓存未命中，从API获取
        logger.info(f"从API获取数据: {symbol} ({start_date} ~ {end_date})")
        df = self.data_feed.get_stock_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )

        if df.empty:
            logger.warning(f"获取数据失败或数据为空: {symbol}")
            return pd.DataFrame()

        # 存入缓存
        self._memory_cache[request] = df

        if self.use_persistent_cache:
            self._save_to_persistent_cache(request, df)

        return df

    def get_batch_data(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        adjust: str = "",
        force_refresh: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取多只股票数据

        参数:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型
            force_refresh: 是否强制刷新

        返回:
            Dict[str, DataFrame]: {股票代码: 数据}
        """
        logger.info(f"批量获取 {len(symbols)} 只股票数据")

        results = {}
        success_count = 0
        fail_count = 0

        for i, symbol in enumerate(symbols, 1):
            logger.info(f"[{i}/{len(symbols)}] 获取 {symbol}...")

            df = self.get_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
                force_refresh=force_refresh
            )

            if not df.empty:
                results[symbol] = df
                success_count += 1
            else:
                fail_count += 1
                logger.warning(f"股票 {symbol} 数据获取失败")

        logger.info(f"批量获取完成 | 成功: {success_count}, 失败: {fail_count}")

        return results

    def clear_cache(self, symbol: str = None):
        """
        清除缓存

        参数:
            symbol: 指定股票代码（None表示清除全部）
        """
        if symbol is None:
            # 清除全部缓存
            self._memory_cache.clear()
            logger.info("已清除全部内存缓存")

            if self.use_persistent_cache:
                # 删除所有缓存文件
                cache_files = list(self.cache_dir.glob("*.pkl"))
                for cache_file in cache_files:
                    cache_file.unlink()
                logger.info(f"已清除 {len(cache_files)} 个持久化缓存文件")
        else:
            # 清除指定股票的缓存
            keys_to_remove = [
                key for key in self._memory_cache
                if key.symbol == symbol
            ]
            for key in keys_to_remove:
                del self._memory_cache[key]

            logger.info(f"已清除股票 {symbol} 的内存缓存")

            if self.use_persistent_cache:
                # 删除指定股票的缓存文件
                cache_files = list(self.cache_dir.glob(f"{symbol}_*.pkl"))
                for cache_file in cache_files:
                    cache_file.unlink()
                logger.info(f"已清除 {len(cache_files)} 个持久化缓存文件")

    def get_cache_info(self) -> Dict[str, int]:
        """
        获取缓存统计信息

        返回:
            Dict: {memory_cache_size, persistent_cache_size}
        """
        persistent_cache_size = len(list(self.cache_dir.glob("*.pkl")))

        return {
            'memory_cache_size': len(self._memory_cache),
            'persistent_cache_size': persistent_cache_size
        }

    def _get_cache_file_path(self, request: DataRequest) -> Path:
        """
        生成缓存文件路径

        参数:
            request: 数据请求对象

        返回:
            Path: 缓存文件路径
        """
        # 文件名格式: {symbol}_{start}_{end}_{adjust}.pkl
        filename = f"{request.symbol}_{request.start_date}_{request.end_date}_{request.adjust}.pkl"
        return self.cache_dir / filename

    def _save_to_persistent_cache(self, request: DataRequest, df: pd.DataFrame):
        """
        保存数据到持久化缓存

        参数:
            request: 数据请求对象
            df: 要缓存的数据
        """
        try:
            cache_file = self._get_cache_file_path(request)
            with open(cache_file, 'wb') as f:
                pickle.dump(df, f)
            logger.debug(f"数据已缓存到: {cache_file.name}")
        except Exception as e:
            logger.warning(f"持久化缓存保存失败: {e}")

    def _load_from_persistent_cache(self, request: DataRequest) -> Optional[pd.DataFrame]:
        """
        从持久化缓存加载数据

        参数:
            request: 数据请求对象

        返回:
            DataFrame或None
        """
        try:
            cache_file = self._get_cache_file_path(request)
            if cache_file.exists():
                with open(cache_file, 'rb') as f:
                    df = pickle.load(f)
                return df
            return None
        except Exception as e:
            logger.warning(f"持久化缓存加载失败: {e}")
            return None


# ==================== 测试代码 ====================
if __name__ == "__main__":
    """
    数据管理器测试
    """
    from utils.logger import logger

    logger.info("=== 数据管理器测试 ===")

    # 1. 创建数据管理器
    manager = DataManager()

    # 2. 测试单次获取
    print("\n【测试1】获取单只股票数据")
    df1 = manager.get_data(
        symbol="000001",
        start_date="2024-01-01",
        end_date="2024-12-31",
        adjust="qfq"
    )
    print(f"数据条数: {len(df1)}")

    # 3. 测试缓存（第二次获取应该从缓存读取）
    print("\n【测试2】测试缓存机制")
    df2 = manager.get_data(
        symbol="000001",
        start_date="2024-01-01",
        end_date="2024-12-31",
        adjust="qfq"
    )
    print(f"数据条数: {len(df2)}")

    # 4. 测试批量获取
    print("\n【测试3】批量获取多只股票")
    dfs = manager.get_batch_data(
        symbols=["000001", "600000"],
        start_date="2024-01-01",
        end_date="2024-12-31",
        adjust="qfq"
    )
    print(f"成功获取 {len(dfs)} 只股票数据")
    for symbol, df in dfs.items():
        print(f"  {symbol}: {len(df)} 条数据")

    # 5. 查看缓存信息
    print("\n【测试4】缓存统计")
    cache_info = manager.get_cache_info()
    print(f"内存缓存: {cache_info['memory_cache_size']} 条")
    print(f"持久化缓存: {cache_info['persistent_cache_size']} 个文件")

    logger.info("测试完成")
