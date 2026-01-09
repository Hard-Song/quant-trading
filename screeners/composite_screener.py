# -*- coding: utf-8 -*-
"""
组合选股器模块
支持多个选股器的组合使用（AND/OR逻辑）
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict

from .base_screener import BaseScreener, ScreeningResult, register_screener
from utils.logger import logger


@register_screener('composite')
class CompositeScreener(BaseScreener):
    """
    组合选股器

    支持多个选股器的组合，可以灵活设置AND/OR逻辑：
        - AND逻辑：股票必须同时满足所有选股器条件
        - OR逻辑：股票满足任一选股器条件即可

    使用示例:
        # 方式1: 使用ScreenerManager创建
        manager = ScreenerManager()
        composite = manager.create_composite(
            screener_names=['factor', 'technical'],
            logic='AND'
        )
        result = composite.screen(stock_list)

        # 方式2: 手动创建
        composite = CompositeScreener(logic='AND')
        factor_screener = FactorScreener()
        technical_screener = TechnicalScreener()
        composite.add_screener(factor_screener, pe=(0, 30))
        composite.add_screener(technical_screener, rsi=(0, 40))
        result = composite.screen(stock_list)
    """

    name = "组合选股器"
    description = "组合多个选股器进行综合选股"
    category = "composite"

    def __init__(self, data_manager=None, logic='AND', *args, **kwargs):
        """
        初始化组合选股器

        参数:
            data_manager: 数据管理器
            logic: 组合逻辑 ('AND' 或 'OR')
            *args, **kwargs: 传递给父类的参数
        """
        # 兼容不同的调用方式
        # 如果第一个参数是字符串，可能是逻辑参数（向后兼容）
        if isinstance(data_manager, str):
            logic = data_manager
            data_manager = None

        # 如果没有提供data_manager，创建一个默认的
        if data_manager is None:
            from core.data_manager import DataManager
            data_manager = DataManager()

        super().__init__(data_manager=data_manager, *args, **kwargs)

        if logic not in ['AND', 'OR']:
            raise ValueError(f"不支持的逻辑类型: {logic}，必须是 'AND' 或 'OR'")

        self.logic = logic

        # 子选股器列表 [(screener, params), ...]
        self._screeners: List[tuple] = []

        logger.info(f"创建组合选股器，逻辑: {logic}")

    def add_screener(
        self,
        screener: BaseScreener,
        params: Dict[str, Any] = None
    ):
        """
        添加子选股器

        参数:
            screener: 选股器实例
            params: 选股参数

        使用示例:
            composite.add_screener(
                FactorScreener(),
                params={'pe': (0, 30), 'pb': (0, 3)}
            )
        """
        self._screeners.append((screener, params or {}))
        logger.info(f"添加选股器: {screener.name} (逻辑: {self.logic})")

    def remove_screener(self, screener: BaseScreener):
        """
        移除子选股器

        参数:
            screener: 要移除的选股器实例
        """
        self._screeners = [(s, p) for s, p in self._screeners if s != screener]
        logger.info(f"移除选股器: {screener.name}")

    def screen(
        self,
        stock_list: list[str],
        **kwargs
    ) -> ScreeningResult:
        """
        执行组合选股

        参数:
            stock_list: 股票代码列表
            **kwargs: 传递给所有子选股器的额外参数

        返回:
            ScreeningResult: 选股结果
        """
        if not self._screeners:
            raise ValueError("请先添加至少一个子选股器")

        logger.info("=" * 60)
        logger.info(f"组合选股: {self.name} ({self.logic} 逻辑)")
        logger.info(f"子选股器数量: {len(self._screeners)}")
        logger.info(f"股票数量: {len(stock_list)}")
        logger.info("=" * 60)

        # 验证股票列表
        stock_list = self.validate_stock_list(stock_list)

        # 执行所有子选股器
        all_results = []
        for i, (screener, params) in enumerate(self._screeners, 1):
            logger.info(f"\n[{i}/{len(self._screeners)}] 执行选股器: {screener.name}")

            # 合并参数
            final_params = {**params, **kwargs}

            try:
                result = screener.screen(stock_list, **final_params)
                all_results.append(result)
                logger.info(f"✓ 选股完成: {len(result.symbols)} 只")
            except Exception as e:
                logger.error(f"✗ 选股失败: {e}")
                continue

        if not all_results:
            raise RuntimeError("所有子选股器都执行失败")

        # 根据逻辑合并结果
        if self.logic == 'AND':
            selected = self._apply_and_logic(all_results)
        else:  # OR
            selected = self._apply_or_logic(all_results)

        # 合并详细信息
        details = {}
        for result in all_results:
            details.update(result.details)

        # 创建结果
        final_result = self.create_result(
            symbols=selected,
            total_count=len(stock_list),
            details=details
        )

        logger.info(f"\n组合选股完成: {len(selected)}/{len(stock_list)}")
        logger.info(f"选股率: {final_result.get_selection_rate():.2f}%")

        # 打印每个子选股器的情况
        for i, (screener, _) in enumerate(self._screeners, 1):
            if i <= len(all_results):
                result = all_results[i - 1]
                logger.info(f"  {screener.name}: {len(result.symbols)} 只")

        return final_result

    def _apply_and_logic(self, results: List[ScreeningResult]) -> List[str]:
        """
        应用AND逻辑：股票必须同时满足所有选股器

        参数:
            results: 所有子选股器结果

        返回:
            List[str]: 同时满足所有条件的股票列表
        """
        # 统计每只股票出现的次数
        stock_count = defaultdict(int)
        stock_details = {}

        for result in results:
            for symbol in result.symbols:
                stock_count[symbol] += 1
                if symbol not in stock_details:
                    stock_details[symbol] = result.details.get(symbol, {})

        # 筛选出在所有结果中都出现的股票
        required_count = len(results)
        selected = [s for s, count in stock_count.items() if count == required_count]

        logger.info(f"AND逻辑: {len(selected)} 只股票满足所有 {required_count} 个条件")

        return selected

    def _apply_or_logic(self, results: List[ScreeningResult]) -> List[str]:
        """
        应用OR逻辑：股票满足任一选股器即可

        参数:
            results: 所有子选股器结果

        返回:
            List[str]: 满足任一条件的股票列表
        """
        # 收集所有出现过的股票（去重）
        selected_set = set()
        for result in results:
            selected_set.update(result.symbols)

        selected = list(selected_set)

        logger.info(f"OR逻辑: {len(selected)} 只股票满足至少 1 个条件")

        return selected

    def get_info(self) -> Dict[str, Any]:
        """
        获取组合选股器信息

        返回:
            Dict: 选股器信息
        """
        info = super().get_info()
        info['logic'] = self.logic
        info['sub_screeners'] = [
            {
                'name': s.name,
                'params': p
            }
            for s, p in self._screeners
        ]
        return info

    def __repr__(self) -> str:
        """字符串表示"""
        screener_names = [s.name for s, _ in self._screeners]
        return f"<CompositeScreener: {self.logic} logic, {len(self._screeners)} screeners ({', '.join(screener_names)})>"


class WeightedCompositeScreener(CompositeScreener):
    """
    加权组合选股器

    允许为每个子选股器设置权重，最终按加权得分排序

    使用示例:
        weighted = WeightedCompositeScreener()
        weighted.add_screener(FactorScreener(), weight=0.6, params={'pe': (0, 30)})
        weighted.add_screener(TechnicalScreener(), weight=0.4, params={'rsi': (0, 40)})
        result = weighted.screen(stock_list, top_n=50)
    """

    name = "加权组合选股器"
    description = "按权重组合多个选股器"
    category = "composite"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # {(screener, params): weight}
        self._weights: Dict[tuple, float] = {}

    def add_screener(
        self,
        screener: BaseScreener,
        weight: float = 1.0,
        params: Dict[str, Any] = None
    ):
        """
        添加带权重的子选股器

        参数:
            screener: 选股器实例
            weight: 权重（0-1）
            params: 选股参数
        """
        super().add_screener(screener, params)
        self._weights[(screener, params or {})] = weight
        logger.info(f"添加选股器: {screener.name}, 权重: {weight}")

    def screen(
        self,
        stock_list: List[str],
        top_n: int = None,
        **kwargs
    ) -> ScreeningResult:
        """
        执行加权组合选股

        参数:
            stock_list: 股票代码列表
            top_n: 返回前N只股票（按得分排序）
            **kwargs: 额外参数

        返回:
            ScreeningResult: 选股结果
        """
        # 调用父类方法
        result = super().screen(stock_list, **kwargs)

        # 如果指定了top_n，按得分排序
        if top_n and len(result.symbols) > top_n:
            # TODO: 实现加权得分计算
            logger.warning("加权得分计算功能待实现，返回全部结果")

        return result
