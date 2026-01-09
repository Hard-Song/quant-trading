# -*- coding: utf-8 -*-
"""
选股器管理器模块
提供选股器的自动发现、加载和管理功能
"""

import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Type, Optional, Any
from dataclasses import dataclass, field

from .base_screener import BaseScreener, ScreeningResult, get_registered_screeners
from core.data_manager import DataManager
from utils.logger import logger


@dataclass
class ScreenerConfig:
    """
    选股器配置

    属性:
        name: 选股器名称
        params: 选股参数字典
        enabled: 是否启用
    """
    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class ScreenerManager:
    """
    选股器管理器

    核心功能：
        1. 自动发现和加载选股器插件
        2. 管理选股器的生命周期
        3. 提供选股器查询和实例化接口
        4. 支持组合选股

    使用示例:
        # 创建管理器
        manager = ScreenerManager()

        # 列出所有可用选股器
        screeners = manager.list_screeners()
        print(screeners)

        # 获取选股器实例
        screener = manager.get_screener('factor')

        # 运行选股
        result = screener.screen(stock_list=['000001', '600000'])

        # 组合选股
        composite = manager.create_composite(['factor', 'technical'], logic='AND')
        result = composite.screen(stock_list)
    """

    def __init__(self, data_manager: DataManager = None, auto_discover: bool = True):
        """
        初始化选股器管理器

        参数:
            data_manager: 数据管理器
            auto_discover: 是否自动发现选股器
        """
        self.data_manager = data_manager or DataManager()

        # 选股器注册表 {名称: 类}
        self._screeners: Dict[str, Type[BaseScreener]] = {}

        # 选股器实例缓存 {名称: 实例}
        self._instances: Dict[str, BaseScreener] = {}

        # 自动发现选股器
        if auto_discover:
            self.discover_screeners()

        logger.info(f"选股器管理器初始化完成，已加载 {len(self._screeners)} 个选股器")

    def discover_screeners(self):
        """
        自动发现并加载选股器

        发现路径：
            1. screeners/ 目录下的所有模块
            2. screeners/custom/ 目录下的自定义选股器
        """
        logger.info("开始自动发现选股器...")

        # 1. 加载已注册的选股器（通过装饰器注册的）
        registered = get_registered_screeners()
        for name, cls in registered.items():
            self._screeners[name] = cls
            logger.debug(f"加载已注册选股器: {name}")

        # 2. 扫描screeners目录
        screeners_dir = Path(__file__).parent
        self._scan_directory(screeners_dir, exclude=['__pycache__', 'custom'])

        # 3. 扫描custom目录（用户自定义选股器）
        custom_dir = screeners_dir / 'custom'
        if custom_dir.exists():
            self._scan_directory(custom_dir)

        logger.info(f"选股器发现完成: {len(self._screeners)} 个")

    def _scan_directory(self, directory: Path, exclude: List[str] = None):
        """
        扫描目录并加载选股器

        参数:
            directory: 目录路径
            exclude: 排除的目录列表
        """
        exclude = exclude or []

        for file_path in directory.glob('*.py'):
            # 跳过__init__.py和排除的目录
            if file_path.name.startswith('__') or any(ex in file_path.parts for ex in exclude):
                continue

            # 动态导入模块
            try:
                # 构建模块路径
                rel_path = file_path.relative_to(Path(__file__).parent.parent)
                module_name = str(rel_path.with_suffix('')).replace('\\', '.')

                module = importlib.import_module(module_name)

                # 查找模块中的BaseScreener子类
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # 检查是否是BaseScreener的子类，且不是BaseScreener本身
                    if (issubclass(obj, BaseScreener) and
                        obj is not BaseScreener and
                        obj.__module__ == module_name):

                        screener_name = obj.name or obj.__name__
                        self._screeners[screener_name] = obj
                        logger.debug(f"加载选股器: {screener_name} from {file_path.name}")

            except Exception as e:
                logger.warning(f"加载选股器失败 {file_path.name}: {e}")

    def list_screeners(self, category: str = None) -> Dict[str, Dict[str, str]]:
        """
        列出所有可用的选股器

        参数:
            category: 按类别过滤 (factor/technical/pattern/custom)

        返回:
            Dict: {选股器名称: {description, category}}
        """
        result = {}
        for name, cls in self._screeners.items():
            # 创建临时实例获取信息
            if category:
                # 如果需要过滤类别
                temp_instance = cls(self.data_manager)
                if temp_instance.category != category:
                    continue

            temp_instance = cls(self.data_manager)
            info = temp_instance.get_info()
            result[name] = info

        return result

    def get_screener(
        self,
        name: str,
        **kwargs
    ) -> BaseScreener:
        """
        获取选股器实例

        参数:
            name: 选股器名称
            **kwargs: 传递给选股器的参数

        返回:
            BaseScreener: 选股器实例

        异常:
            ValueError: 选股器不存在
        """
        if name not in self._screeners:
            available = ', '.join(self._screeners.keys())
            raise ValueError(f"选股器 '{name}' 不存在。可用选股器: {available}")

        # 检查缓存
        if name in self._instances and not kwargs:
            return self._instances[name]

        # 创建新实例
        screener_cls = self._screeners[name]
        instance = screener_cls(self.data_manager)

        # 如果有参数，设置属性
        if kwargs:
            for key, value in kwargs.items():
                setattr(instance, key, value)

        # 缓存无参数的实例
        if not kwargs:
            self._instances[name] = instance

        logger.info(f"创建选股器实例: {name}")
        return instance

    def create_composite(
        self,
        screener_names: List[str],
        logic: str = 'AND',
        configs: List[Dict[str, Any]] = None
    ) -> 'CompositeScreener':
        """
        创建组合选股器

        参数:
            screener_names: 子选股器名称列表
            logic: 组合逻辑 ('AND' 或 'OR')
            configs: 每个子选股器的参数配置

        返回:
            CompositeScreener: 组合选股器实例
        """
        from .composite_screener import CompositeScreener

        composite = CompositeScreener(logic=logic, data_manager=self.data_manager)

        # 添加子选股器
        for i, name in enumerate(screener_names):
            params = configs[i] if configs and i < len(configs) else {}
            screener = self.get_screener(name, **params)
            composite.add_screener(screener)

        logger.info(f"创建组合选股器: {logic} 逻辑, {len(screener_names)} 个子选股器")
        return composite

    def screen(
        self,
        screener_name: str,
        stock_list: List[str],
        **kwargs
    ) -> ScreeningResult:
        """
        快捷方法：执行选股

        参数:
            screener_name: 选股器名称
            stock_list: 股票列表
            **kwargs: 选股参数

        返回:
            ScreeningResult: 选股结果
        """
        screener = self.get_screener(screener_name)
        return screener.screen(stock_list, **kwargs)

    def batch_screen(
        self,
        screener_configs: List[ScreenerConfig],
        stock_list: List[str]
    ) -> Dict[str, ScreeningResult]:
        """
        批量执行多个选股器

        参数:
            screener_configs: 选股器配置列表
            stock_list: 股票列表

        返回:
            Dict[str, ScreeningResult]: {选股器名称: 选股结果}
        """
        results = {}

        for config in screener_configs:
            if not config.enabled:
                continue

            logger.info(f"执行选股器: {config.name}")
            try:
                screener = self.get_screener(config.name)
                result = screener.screen(stock_list, **config.params)
                results[config.name] = result
            except Exception as e:
                logger.error(f"选股器 {config.name} 执行失败: {e}")

        return results

    def reload(self):
        """重新加载所有选股器"""
        logger.info("重新加载选股器...")
        self._screeners.clear()
        self._instances.clear()
        self.discover_screeners()
        logger.info("重新加载完成")

    def get_stats(self) -> Dict[str, int]:
        """
        获取统计信息

        返回:
            Dict: 统计数据
        """
        # 按类别统计
        category_count = {}
        for name, cls in self._screeners.items():
            temp_instance = cls(self.data_manager)
            category = temp_instance.category or 'unknown'
            category_count[category] = category_count.get(category, 0) + 1

        return {
            'total_screeners': len(self._screeners),
            'cached_instances': len(self._instances),
            'by_category': category_count,
        }


# ==================== 便捷函数 ====================
def create_screener_manager() -> ScreenerManager:
    """
    创建选股器管理器的便捷函数

    返回:
        ScreenerManager: 选股器管理器实例
    """
    return ScreenerManager()


def list_all_screeners() -> Dict[str, Dict[str, str]]:
    """
    列出所有可用选股器的便捷函数

    返回:
        Dict: {选股器名称: 信息}
    """
    manager = ScreenerManager()
    return manager.list_screeners()
