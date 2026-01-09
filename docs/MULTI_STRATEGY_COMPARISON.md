# 多策略对比功能说明

## 新增功能

### 1. 数据管理器 (DataManager)
**位置**: `core/data_manager.py`

**功能**:
- 统一管理数据获取和缓存
- 避免重复API调用
- 支持内存缓存和持久化缓存

**使用示例**:
```python
from core.data_manager import DataManager

# 创建数据管理器
manager = DataManager()

# 获取数据（第一次会调用API）
df1 = manager.get_data(
    symbol="000001",
    start_date="2023-01-01",
    end_date="2024-12-31"
)

# 再次获取（从缓存读取，不调用API）
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
```

---

### 2. 策略比较器 (StrategyComparator)
**位置**: `core/strategy_comparator.py`

**功能**:
- 对同一股票运行多个策略
- 自动处理数据缓存（所有策略共享一份数据）
- 生成对比报告和图表

**使用示例**:
```python
from core.strategy_comparator import StrategyComparator, StrategyTestConfig
from strategies.ma_strategy import DualMovingAverage
from strategies.macd_strategy import MACDStrategy

# 创建比较器
comparator = StrategyComparator(
    initial_cash=100000,
    commission=0.0003
)

# 定义要对比的策略
strategies = [
    StrategyTestConfig('MA(5,20)', DualMovingAverage, {
        'fast_period': 5,
        'slow_period': 20
    }),
    StrategyTestConfig('MACD(12,26,9)', MACDStrategy, {
        'fast_period': 12,
        'slow_period': 26,
        'signal_period': 9
    }),
]

# 运行对比
result = comparator.compare(
    symbol="000001",
    start_date="2023-01-01",
    end_date="2024-12-31",
    strategies=strategies
)

# 查看结果
print(result.to_dataframe())

# 获取最佳策略
best_name, best_result = result.get_best_strategy('total_return')
print(f"最佳策略: {best_name}")

# 绘制对比图表
comparator.plot_comparison(result)
```

---

### 3. 策略对比脚本
**位置**: `scripts/compare_strategies.py`

**基本用法**:
```bash
# 默认对比 (MA vs MACD)
uv run python scripts/compare_strategies.py

# 指定股票和日期
uv run python scripts/compare_strategies.py --symbol 600000 --start 2023-01-01

# 对比多个策略
uv run python scripts/compare_strategies.py --strategies ma macd macd_trend

# 对比多个MA参数组合
uv run python scripts/compare_strategies.py --strategies ma_params

# 自定义MA参数
uv run python scripts/compare_strategies.py --strategies ma_params --params "5,20 10,30 20,60"

# 对比所有策略
uv run python scripts/compare_strategies.py --strategies all

# 不显示图表
uv run python scripts/compare_strategies.py --no-plot

# 指定初始资金
uv run python scripts/compare_strategies.py --cash 50000
```

**可用参数**:
- `--symbol`: 股票代码 (默认: 000001)
- `--start`: 开始日期 (默认: 2023-01-01)
- `--end`: 结束日期 (默认: 2024-12-31)
- `--strategies`: 策略列表 (ma, macd, macd_trend, macd_rsi, ma_params, macd_params, all)
- `--params`: 自定义参数 (用于ma_params或macd_params)
- `--cash`: 初始资金 (默认: 100000)
- `--no-plot`: 不显示图表
- `--no-save`: 不保存报告

**可用策略类型**:
- `ma`: 双均线策略
- `macd`: MACD策略
- `macd_trend`: MACD+趋势过滤
- `macd_rsi`: MACD+RSI组合
- `ma_params`: 多个MA参数组合
- `macd_params`: 多个MACD参数组合
- `all`: 所有策略

---

## 核心优势

### 1. 避免重复API调用
**问题**: 以前每个策略都会单独获取数据
```python
# 以前的做法
engine1 = BacktestEngine()
df1 = data_feed.get_stock_data(...)  # API调用1次
engine1.add_data(df1)
engine1.add_strategy(MA)
engine1.run()

engine2 = BacktestEngine()
df2 = data_feed.get_stock_data(...)  # API调用第2次!
engine2.add_data(df2)
engine2.add_strategy(MACD)
engine2.run()
```

**现在**: 只调用一次API
```python
# 现在的做法
comparator = StrategyComparator()
result = comparator.compare(
    symbol="000001",
    strategies=[MA, MACD, ...]
)
# 数据只获取一次，所有策略共享
```

### 2. 方便的策略对比
- 自动生成对比表格
- 自动识别最佳策略
- 支持可视化对比图表

### 3. 支持参数优化
```bash
# 对比多个参数组合
uv run python scripts/compare_strategies.py --strategies ma_params --params "5,20 10,30 20,60"
```

---

## 输出示例

### 对比报告
```
================================================================================
策略对比报告 - 000001
回测期间: 2023-01-01 ~ 2024-12-31
================================================================================
           策略   初始资金        最终资金  总收益率(%)  交易次数  胜率(%)  最大回撤(%)   夏普比率
MACD(12,26,9) 100000 100069.4513     0.07    17  29.41     0.23 -13.90
     MA(5,20) 100000  99827.7988    -0.17    18  27.78     0.31 -14.88

================================================================================
最佳策略分析
================================================================================
[最高收益率] MACD(12,26,9) (0.07%)
[最高夏普比率] MA(5,20) (-14.88)
[最小回撤] MACD(12,26,9) (0.23%)
================================================================================
```

### 生成的文件
报告保存在: `reports/comparison_{symbol}_{timestamp}.csv`

---

## 性能对比

| 场景 | 以前 | 现在 |
|------|------|------|
| 对比2个策略 | API调用2次 | API调用1次 |
| 对比5个策略 | API调用5次 | API调用1次 |
| 批量回测10只股票 | API调用10次×策略数 | API调用10次 |

---

## 下一步扩展

### 计划中的功能:
1. **选股分析器** (StockScreener)
   - 多因子选股
   - 技术指标选股
   - 行业/概念选股

2. **批量回测引擎** (BatchBacktestEngine)
   - 单策略 vs 多股票
   - 生成汇总报告
   - 性能排名

3. **参数优化器** (ParameterOptimizer)
   - 网格搜索
   - 遗传算法优化
   - 贝叶斯优化

---

## 注意事项

1. **数据缓存**: 默认启用持久化缓存，缓存在 `data/cache/` 目录
2. **编码问题**: Windows终端可能显示乱码，建议使用 `--no-plot` 模式查看结果
3. **数据量**: 确保有足够的数据（建议至少200条），否则某些策略可能失败
