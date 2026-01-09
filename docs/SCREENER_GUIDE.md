# 选股器系统使用指南

## 系统概述

选股器系统是一个**插件式架构**的股票筛选框架，支持：
- 🔌 **插件式扩展**：轻松添加自定义选股器
- 🎯 **组合选股**：支持AND/OR逻辑组合多个选股器
- 📊 **多因子筛选**：支持基本面、技术指标、形态等多种选股策略
- 🔄 **自动发现**：自动发现并加载所有选股器插件

## 快速开始

### 1. 查看所有可用选股器

```bash
uv run python scripts/run_screener.py --list
```

输出示例：
```
【FACTOR】
  - factor               : 基于基本面因子进行选股
  - high_market_cap      : 筛选大市值蓝筹股
  - low_pe               : 筛选低市盈率股票

【TECHNICAL】
  - golden_cross         : 筛选金叉形态股票
  - oversold             : 筛选RSI超卖股票
  - technical            : 基于技术指标进行选股

【CUSTOM】
  - momentum             : 筛选涨幅最大的股票（动量策略）
  - my_custom            : 自定义选股策略示例
```

### 2. 因子选股

```bash
# 低PE选股
uv run python scripts/run_screener.py --screener low_pe --max-pe 15

# 多因子选股
uv run python scripts/run_screener.py --screener factor --pe 0 30 --pb 0 3 --market-cap 50 1000
```

### 3. 技术选股

```bash
# RSI超卖选股
uv run python scripts/run_screener.py --screener oversold --rsi-threshold 30

# MACD金叉选股
uv run python scripts/run_screener.py --screener golden_cross
```

### 4. 动量选股

```bash
# 最近20天涨幅前50只
uv run python scripts/run_screener.py --screener momentum --days 20 --top-n 50
```

### 5. 组合选股

```bash
# 低PE + RSI超卖 (AND逻辑)
uv run python scripts/run_screener.py --composite low_pe oversold --logic AND --max-pe 30 --rsi-threshold 40

# 低PE OR 超卖 (OR逻辑)
uv run python scripts/run_screener.py --composite low_pe oversold --logic OR --max-pe 30 --rsi-threshold 40
```

## Python API 使用

### 方式1：使用ScreenerManager

```python
from screeners import ScreenerManager

# 创建管理器
manager = ScreenerManager()

# 获取选股器实例
screener = manager.get_screener('low_pe')

# 执行选股
result = screener.screen(
    stock_list=['000001', '600000', '000002'],
    max_pe=15
)

# 查看结果
print(result)
print(result.symbols)  # ['000001', '600002']

# 转换为DataFrame
df = result.to_dataframe()
print(df)

# 保存结果
df.to_csv('selected_stocks.csv', index=False)
```

### 方式2：直接使用选股器类

```python
from screeners.factor_screener import FactorScreener

# 创建选股器
screener = FactorScreener()

# 执行选股
result = screener.screen(
    stock_list=['000001', '600000', ...],
    pe=(0, 30),      # PE 0-30
    pb=(0, 3),       # PB 0-3
    market_cap=(50, 1000)  # 市值50-1000亿
)

# 查看结果
print(f"选中 {len(result.symbols)} 只股票")
print(f"选股率: {result.get_selection_rate():.2f}%")
```

### 方式3：组合选股

```python
from screeners import ScreenerManager

manager = ScreenerManager()

# 创建组合选股器
composite = manager.create_composite(
    screener_names=['low_pe', 'oversold'],
    logic='AND'
)

# 执行选股
result = composite.screen(
    stock_list=['000001', '600000', ...]
)

print(result)
```

## 创建自定义选股器

### 步骤1：创建选股器文件

在 `screeners/custom/` 目录下创建你的选股器：

```python
# screeners/custom/my_screener.py
from screeners.base_screener import BaseScreener, ScreeningResult, register_screener
from typing import List
import pandas as pd

@register_screener('my_strategy')
class MyStrategyScreener(BaseScreener):
    """我的自定义选股器"""

    name = "我的选股策略"
    description = "这是一个自定义选股器示例"
    category = "custom"

    def screen(
        self,
        stock_list: List[str],
        **kwargs
    ) -> ScreeningResult:
        """执行选股"""
        selected = []
        details = {}

        for symbol in stock_list:
            # 获取数据
            df = self.get_stock_data(symbol)

            if df.empty:
                continue

            # 自定义选股逻辑
            if self.my_condition(df):
                selected.append(symbol)
                details[symbol] = {
                    'close': df['close'].iloc[-1],
                    'volume': df['volume'].iloc[-1]
                }

        # 返回结果
        return self.create_result(
            symbols=selected,
            total_count=len(stock_list),
            details=details
        )

    def my_condition(self, df: pd.DataFrame) -> bool:
        """自定义选股条件"""
        # 示例：最近3天连续上涨
        recent = df.tail(3)
        return all(
            recent['close'].iloc[i] > recent['close'].iloc[i-1]
            for i in range(1, len(recent))
        )
```

### 步骤2：自动加载

ScreenerManager 会自动发现并加载你的选股器：

```python
from screeners import ScreenerManager

manager = ScreenerManager()

# 你的选股器已经自动加载
screener = manager.get_screener('my_strategy')

# 使用
result = screener.screen(stock_list=['000001', '600000'])
```

## 预置选股器详解

### 1. FactorScreener（因子选股器）

**功能**：基于基本面因子选股

**支持的因子**：
- `pe`: 市盈率
- `pb`: 市净率
- `ps`: 市销率
- `market_cap`: 市值（亿）
- `turnover`: 换手率（%）

**使用示例**：
```python
screener = FactorScreener()

result = screener.screen(
    stock_list=stocks,
    pe=(0, 20),           # PE 0-20
    pb=(0, 2),            # PB 0-2
    market_cap=(50, 1000) # 市值50-1000亿
)
```

### 2. TechnicalScreener（技术指标选股器）

**功能**：基于技术指标选股

**支持的指标**：
- `rsi`: RSI范围
- `macd_cross`: MACD金叉/死叉 ('golden', 'death')
- `ma_alignment`: 均线排列 ('bullish', 'bearish')
- `volume_surge`: 是否放量
- `price_above_ma`: 价格是否在均线上方

**使用示例**：
```python
screener = TechnicalScreener()

# RSI超卖
result = screener.screen(
    stock_list=stocks,
    rsi=(0, 30)
)

# MACD金叉
result = screener.screen(
    stock_list=stocks,
    macd_cross='golden'
)

# 多头排列 + 放量
result = screener.screen(
    stock_list=stocks,
    ma_alignment='bullish',
    volume_surge=True
)
```

### 3. CompositeScreener（组合选股器）

**功能**：组合多个选股器

**逻辑**：
- `AND`: 股票必须同时满足所有条件
- `OR`: 股票满足任一条件即可

**使用示例**：
```python
from screeners import ScreenerManager

manager = ScreenerManager()

# 创建组合选股器（AND逻辑）
composite = manager.create_composite(
    screener_names=['factor', 'technical'],
    logic='AND'
)

# 或者手动创建
from screeners import CompositeScreener, FactorScreener, TechnicalScreener

composite = CompositeScreener(logic='AND')
composite.add_screener(FactorScreener(), params={'pe': (0, 30)})
composite.add_screener(TechnicalScreener(), params={'rsi': (0, 40)})

result = composite.screen(stock_list=stocks)
```

### 4. MomentumScreener（动量选股器）

**功能**：筛选涨幅最大的股票

**参数**：
- `days`: 统计天数（默认20天）
- `top_n`: 返回前N只（默认50）
- `min_change_pct`: 最小涨幅%（默认5%）

**使用示例**：
```python
screener = MomentumScreener()

result = screener.screen(
    stock_list=stocks,
    days=20,        # 最近20天
    top_n=50,       # 前50只
    min_change_pct=10  # 涨幅>10%
)
```

## 与回测系统集成

选股器可以与回测系统无缝集成：

```python
from screeners import ScreenerManager
from core import StrategyComparator, BatchBacktestEngine

# 1. 选股
manager = ScreenerManager()
screener = manager.get_screener('factor')
result = screener.screen(
    stock_list=all_stocks,
    pe=(0, 30),
    pb=(0, 3)
)

# 得到选中的股票
selected_stocks = result.symbols

# 2. 批量回测
batch_engine = BatchBacktestEngine()
results = batch_engine.run_batch(
    symbols=selected_stocks,
    strategy=DualMovingAverage,
    start_date='2023-01-01',
    end_date='2024-12-31'
)

# 3. 策略对比
comparator = StrategyComparator()
result = comparator.compare(
    symbol=selected_stocks[0],
    strategies=[MA, MACD, RSI]
)
```

## 最佳实践

### 1. 组合选股策略

**价值+技术**：
```python
# 低估值 + 技术面确认
composite = CompositeScreener(logic='AND')
composite.add_screener(LowPEScreener(), params={'max_pe': 20})
composite.add_screener(GoldenCrossScreener())
```

**多技术确认**：
```python
# RSI超卖 + MACD金叉 + 放量
composite = CompositeScreener(logic='AND')
composite.add_screener(OverSoldScreener(), params={'rsi_threshold': 30})
composite.add_screener(GoldenCrossScreener())
composite.add_screener(TechnicalScreener(), params={'volume_surge': True})
```

### 2. 分层筛选

```python
# 第一层：粗筛选（基本面）
factor = FactorScreener()
result1 = factor.screen(
    stock_list=all_stocks,
    pe=(0, 50),
    market_cap=(50, 5000)
)

# 第二层：精筛选（技术面）
technical = TechnicalScreener()
result2 = technical.screen(
    stock_list=result1.symbols,  # 从第一层结果中筛选
    rsi=(0, 40),
    macd_cross='golden'
)
```

### 3. 性能优化

```python
# 使用相同的数据管理器，避免重复获取数据
from core.data_manager import DataManager

data_manager = DataManager()
screener1 = FactorScreener(data_manager=data_manager)
screener2 = TechnicalScreener(data_manager=data_manager)
```

## 注意事项

1. **数据获取**：因子选股需要获取实时行情，请确保网络连接
2. **股票列表**：可以通过 `AStockDataFeed().get_stock_list()` 获取
3. **结果保存**：选股结果会自动保存到 `reports/` 目录
4. **性能考虑**：筛选大量股票时可能需要较长时间
5. **参数调试**：建议先用少量股票测试参数（使用 `--stock-limit` 参数）

## 常见问题

**Q: 如何添加新的因子？**
A: 编辑 `FactorScreener._get_stock_factors()` 方法，添加新的因子字段。

**Q: 如何修改选股条件？**
A: 子类化选股器并重写 `_check_conditions()` 方法。

**Q: 如何获取历史数据？**
A: 使用 `self.get_stock_data(symbol, start_date, end_date)` 方法。

**Q: 选股器支持实盘吗？**
A: 目前只支持历史数据选股，实盘需要对接实时行情API。
