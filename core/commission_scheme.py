# -*- coding: utf-8 -*-
"""
A股手续费计算模块
实现A股真实的手续费结构，包括印花税、佣金、过户费等
"""

import backtrader as bt
from backtrader import CommInfoBase


class AStockCommInfo(CommInfoBase):
    """
    A股手续费计算器

    A股手续费结构：
        1. 印花税：只有卖出时收取，费率0.1%（千分之一）
        2. 佣金：双向收取，通常万分之2.5-5（最低5元）
        3. 过户费：双向收取，费率万分之0.1（深市）/ 万分之0.2（沪市）

    使用说明：
        cerebro.broker.addcommissioninfo(AStockCommInfo(
            commission=0.0003,      # 佣金率（默认万分之3）
            stamp_duty=0.001,       # 印花税率（千分之一，仅卖出）
            transfer_fee=0.00002,   # 过户费率（十万分之二，双向）
            market='sh',            # 市场：sh=沪市，sz=深市
        ))
    """

    params = (
        ('commission', 0.0003),     # 佣金率（默认万分之3）
        ('stamp_duty', 0.001),      # 印花税率（卖出时0.1%）
        ('transfer_fee', 0.00002),  # 过户费率（双向，十万分之二）
        ('market', 'sh'),           # 市场类型：sh=沪市，sz=深市
        ('commtype', CommInfoBase.COMM_PERC),  # 按比例计算
        ('stocklike', True),        # 股票类型
        ('leverage', 1.0),          # 杠杆
    )

    def _getcommission(self, size, price, pseudoexec):
        """
        计算手续费

        参数:
            size: 交易数量（正数=买入，负数=卖出）
            price: 成交价格
            pseudoexec: 是否为伪执行

        返回:
            float: 手续费金额
        """
        # 计算交易金额
        value = abs(size) * price

        # 1. 计算佣金（双向收取）
        commission = value * self.p.commission

        # 佣金最低5元（A股规定）
        commission = max(commission, 5.0)

        # 2. 计算过户费（双向收取）
        transfer_fee = value * self.p.transfer_fee

        # 3. 计算印花税（仅卖出收取）
        stamp_duty = 0.0
        if size < 0:  # 卖出
            stamp_duty = value * self.p.stamp_duty

        # 总手续费
        total_cost = commission + transfer_fee + stamp_duty

        return total_cost


class AStockCommissionInfo:
    """
    A股手续费配置类

    简化配置的手续费类，方便使用

    使用示例：
        from core.commission_scheme import AStockCommissionInfo

        # 创建A股手续费配置
        comm_info = AStockCommissionInfo()

        # 添加到broker
        cerebro.broker.addcommissioninfo(comm_info.get_comm_info())
    """

    def __init__(
        self,
        commission: float = 0.0003,
        stamp_duty: float = 0.001,
        transfer_fee: float = 0.00002,
        market: str = 'sh',
    ):
        """
        初始化手续费配置

        参数:
            commission: 佣金率，默认万分之3
            stamp_duty: 印花税率，默认千分之一（仅卖出）
            transfer_fee: 过户费率，默认十万分之二（双向）
            market: 市场类型，'sh'=沪市，'sz'=深市
        """
        self.commission = commission
        self.stamp_duty = stamp_duty
        self.transfer_fee = transfer_fee
        self.market = market

    def get_comm_info(self):
        """
        获取手续费信息对象

        返回:
            AStockCommInfo: Backtrader手续费计算器
        """
        return AStockCommInfo(
            commission=self.commission,
            stamp_duty=self.stamp_duty,
            transfer_fee=self.transfer_fee,
            market=self.market,
        )

    def __str__(self):
        """手续费配置说明"""
        return f"""
=== A股手续费配置 ===
佣金率: {self.commission * 10000:.1f}‰（双向，最低5元）
印花税率: {self.stamp_duty * 100:.2f}%（仅卖出）
过户费率: {self.transfer_fee * 100000:.1f}‱（双向）
市场类型: {'沪市' if self.market == 'sh' else '深市'}

示例计算（假设交易金额10000元）：
  买入费用 = 10000 × {self.commission * 10000:.1f}‰ + 10000 × {self.transfer_fee * 100000:.1f}‱
           = {10000 * self.commission:.2f} + {10000 * self.transfer_fee:.2f}
           = {10000 * (self.commission + self.transfer_fee):.2f} 元

  卖出费用 = 10000 × {self.commission * 10000:.1f}‰ + 10000 × {self.stamp_duty * 100:.2f}% + 10000 × {self.transfer_fee * 100000:.1f}‱
           = {10000 * self.commission:.2f} + {10000 * self.stamp_duty:.2f} + {10000 * self.transfer_fee:.2f}
           = {10000 * (self.commission + self.stamp_duty + self.transfer_fee):.2f} 元
"""


def get_a_stock_commission(
    commission: float = 0.0003,
    stamp_duty: float = 0.001,
    transfer_fee: float = 0.00002,
    market: str = 'sh',
):
    """
    便捷函数：获取A股手续费计算器

    参数:
        commission: 佣金率，默认万分之3
        stamp_duty: 印花税率，默认千分之一（仅卖出）
        transfer_fee: 过户费率，默认十万分之二（双向）
        market: 市场类型，'sh'=沪市，'sz'=深市

    返回:
        AStockCommInfo: Backtrader手续费计算器

    使用示例：
        from core.commission_scheme import get_a_stock_commission

        # 使用默认参数
        cerebro.broker.addcommissioninfo(get_a_stock_commission())

        # 自定义佣金率
        cerebro.broker.addcommissioninfo(get_a_stock_commission(commission=0.00025))
    """
    return AStockCommInfo(
        commission=commission,
        stamp_duty=stamp_duty,
        transfer_fee=transfer_fee,
        market=market,
    )


# ==================== 测试代码 ====================
if __name__ == "__main__":
    """
    测试手续费计算
    """
    from utils.logger import logger

    logger.info("=== A股手续费计算测试 ===")

    # 测试1：使用默认参数
    print("\n【测试1】默认手续费配置")
    comm_config = AStockCommissionInfo()
    print(comm_config)

    # 测试2：自定义佣金率
    print("\n【测试2】自定义佣金率（万分之2.5）")
    comm_config_custom = AStockCommissionInfo(commission=0.00025)
    print(comm_config_custom)

    # 测试3：计算具体交易费用
    print("\n【测试3】模拟交易费用计算")
    comm_info = get_a_stock_commission()

    # 模拟买入100股，价格10元
    size = 100
    price = 10.0

    buy_cost = comm_info._getcommission(size, price, pseudoexec=False)
    sell_cost = comm_info._getcommission(-size, price, pseudoexec=False)

    print(f"交易数量: {size}股")
    print(f"成交价格: {price}元")
    print(f"交易金额: {size * price:.2f}元")
    print(f"买入费用: {buy_cost:.2f}元")
    print(f"卖出费用: {sell_cost:.2f}元")
    print(f"总费用（一买一卖）: {buy_cost + sell_cost:.2f}元")
    print(f"总费用率: {(buy_cost + sell_cost) / (size * price) * 100:.4f}%")

    logger.info("[OK] 测试完成")
