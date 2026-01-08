# -*- coding: utf-8 -*-
"""
日志管理模块
基于loguru实现统一的日志记录
"""

import sys
from pathlib import Path
from loguru import logger
from typing import Optional


def get_logger(name: str = "quant", log_file: Optional[str] = None, level: str = "INFO"):
    """
    获取配置好的logger实例

    参数:
        name: logger名称，用于区分不同模块
        log_file: 日志文件路径，如果不指定则使用默认路径
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)

    返回:
        logger实例

    使用示例:
        from utils.logger import get_logger

        logger = get_logger("backtest")
        logger.info("回测开始")
        logger.error("发生错误")
    """

    # 移除默认的handler（避免重复日志）
    logger.remove()

    # 日志格式
    # {time: YYYY-MM-DD HH:mm:ss} - 时间戳
    # {level} - 日志级别
    # {name} - 模块名称
    # {function} - 函数名
    # {line} - 行号
    # {message} - 日志内容
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # 添加控制台输出handler
    logger.add(
        sys.stdout,
        format=log_format,
        level=level,
        colorize=True,  # 彩色输出
    )

    # 添加文件输出handler
    if log_file is None:
        # 创建logs目录
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / "quant_trading.log"

    logger.add(
        log_file,
        format=log_format,
        level=level,
        rotation="10 MB",  # 日志文件大小达到10MB时自动轮转
        retention="30 days",  # 保留30天的日志
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
    )

    return logger


# 创建全局logger实例
# 可以在其他模块中直接导入使用
# from utils.logger import logger
logger = get_logger("quant")


if __name__ == "__main__":
    """
    测试代码
    运行此文件可以验证日志功能是否正常
    """
    # 测试不同级别的日志
    logger.debug("这是DEBUG级别日志")
    logger.info("这是INFO级别日志")
    logger.warning("这是WARNING级别日志")
    logger.error("这是ERROR级别日志")

    # 测试格式化输出
    stock_code = "000001"
    price = 10.5
    logger.info(f"股票 {stock_code} 价格: {price:.2f}")

    print("\n[OK] 日志测试完成，请查看控制台输出和 logs/quant_trading.log 文件")
