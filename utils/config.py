# -*- coding: utf-8 -*-
"""
配置管理模块
负责加载和管理系统配置文件
"""

import yaml
import os
from pathlib import Path
from typing import Any, Dict


class Config:
    """
    配置管理器

    功能说明：
    1. 从YAML文件加载配置
    2. 提供统一的配置访问接口
    3. 支持配置热更新（预留）

    使用示例：
        config = Config()
        initial_cash = config.get('backtest.initial_cash')
        data_path = config.get('data.storage_path')
    """

    _instance = None  # 单例模式，确保全局只有一个配置实例

    def __new__(cls, config_path: str = None):
        """
        实现单例模式

        参数:
            config_path: 配置文件路径，默认为 config/settings.yaml
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str = None):
        """
        初始化配置管理器

        参数:
            config_path: 配置文件路径，默认为 config/settings.yaml
        """
        # 如果已经初始化过，直接返回
        if self._initialized:
            return

        # 设置配置文件路径
        if config_path is None:
            # 获取项目根目录（当前文件的上上级目录）
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "settings.yaml"

        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}

        # 加载配置文件
        self._load_config()
        self._initialized = True

    def _load_config(self) -> None:
        """
        加载YAML配置文件

        说明:
            读取config/settings.yaml文件并解析为字典
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)

            print(f"[OK] 配置文件加载成功: {self.config_path}")

        except FileNotFoundError:
            print(f"[FAIL] 配置文件不存在: {self.config_path}")
            self._config = {}

        except yaml.YAMLError as e:
            print(f"[FAIL] 配置文件解析错误: {e}")
            self._config = {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项

        参数:
            key: 配置键，支持点号分隔的多级键，例如 'backtest.initial_cash'
            default: 默认值，当配置项不存在时返回

        返回:
            配置值或默认值

        示例:
            config = Config()
            cash = config.get('backtest.initial_cash', 100000)
        """
        # 使用点号分割键名，例如 'backtest.initial_cash' -> ['backtest', 'initial_cash']
        keys = key.split('.')

        # 从配置字典中逐层查找
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        设置配置项（运行时修改，不保存到文件）

        参数:
            key: 配置键
            value: 配置值

        注意:
            此方法只修改内存中的配置，不会写入YAML文件
        """
        keys = key.split('.')
        config = self._config

        # 遍历到倒数第二层
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # 设置最后一层的值
        config[keys[-1]] = value

    def reload(self) -> None:
        """
        重新加载配置文件

        说明:
            当配置文件被外部修改后，可以调用此方法重新加载
        """
        self._load_config()


# 创建全局配置实例（单例）
config = Config()


if __name__ == "__main__":
    """
    测试代码
    运行此文件可以验证配置加载是否正常
    """
    # 创建配置实例
    cfg = Config()

    # 测试读取配置
    print("\n=== 配置测试 ===")
    print(f"初始资金: {cfg.get('backtest.initial_cash')}")
    print(f"手续费率: {cfg.get('backtest.commission')}")
    print(f"数据源: {cfg.get('data.provider')}")
    print(f"T+1规则: {cfg.get('a_stocks.t_plus_one')}")

    # 测试默认值
    print(f"\n不存在的配置项: {cfg.get('nonexistent.key', '默认值')}")
