# Quant Trading Framework

一个完整的**量化交易回测框架**，支持策略开发、选股、批量回测和策略对比。

## ✨ 核心特性

### 1. 策略开发
- 🔌 **插件式架构**：轻松添加自定义策略
- 📊 **丰富的指标**：内置MA、MACD、RSI等常用指标
- 🎯 **灵活的参数**：支持动态配置策略参数
- 📈 **可视化**：自动生成回测图表

### 2. 选股系统
- 🎯 **多因子选股**：PE、PB、市值等基本面因子
- 📊 **技术指标选股**：RSI、MACD、均线等技术指标
- 🧩 **组合选股**：支持AND/OR逻辑组合多个选股器
- 🔧 **自定义扩展**：插件式架构，轻松添加自定义选股器

### 3. 批量回测
- ⚡ **并行处理**：支持多线程并行回测，提高效率
- 📊 **汇总报告**：自动生成详细的回测汇总表
- 🏆 **排名分析**：按收益率、夏普比率等指标排名
- 💾 **结果保存**：自动保存回测结果到CSV文件

### 4. 策略对比
- 🔬 **多策略对比**：在同一股票上对比多个策略
- 📊 **详细指标**：收益率、夏普比率、最大回撤、胜率等
- 📈 **可视化对比**：生成对比图表
- 🏆 **最佳策略**：自动识别表现最好的策略

### 5. 数据管理
- 💾 **智能缓存**：自动缓存数据，避免重复API调用
- 🔄 **数据复用**：多个策略共享同一份数据
- 📂 **持久化存储**：支持pickle格式持久化缓存

## 🚀 快速开始

### 环境安装

```bash
# 使用uv安装依赖
uv pip install -r requirements.txt
```

### 1. 单策略回测

```bash
# 使用默认参数回测
uv run python scripts/run_backtest.py

# 指定股票和策略
uv run python scripts/run_backtest.py --symbol 000001 --strategy macd

# 自定义策略参数
uv run python scripts/run_backtest.py --fast 10 --slow 30
```

### 2. 策略对比

```bash
# 对比MA和MACD策略
uv run python scripts/compare_strategies.py --strategies ma macd

# 对比多个参数组合
uv run python scripts/compare_strategies.py --strategies ma_params --params "5,20 10,30 20,60"
```

### 3. 选股

```bash
# 列出所有可用选股器
uv run python scripts/run_screener.py --list

# 因子选股：低PE
uv run python scripts/run_screener.py --screener low_pe --max-pe 15

# 技术选股：RSI超卖
uv run python scripts/run_screener.py --screener oversold --rsi-threshold 30

# 组合选股：低PE + RSI超卖
uv run python scripts/run_screener.py --composite low_pe oversold --logic AND
```

### 4. 批量回测

```bash
# 对指定股票批量回测
uv run python scripts/run_batch_backtest.py --symbols 000001 600000

# 先选股，再批量回测
uv run python scripts/run_batch_backtest.py --screener low_pe --max-pe 30 --stock-limit 50
```

## 📁 项目结构

```
quant/
├── core/                        # 核心模块
│   ├── backtest_engine.py       # 回测引擎
│   ├── data_manager.py          # 数据管理器（缓存）
│   ├── strategy_comparator.py   # 策略对比器
│   └── batch_backtest_engine.py # 批量回测引擎
│
├── strategies/                  # 策略模块
│   ├── base_strategy.py         # 策略基类
│   ├── ma_strategy.py           # 双均线策略
│   └── macd_strategy.py         # MACD策略
│
├── screeners/                   # 选股器模块
│   ├── base_screener.py         # 选股器基类
│   ├── screener_manager.py      # 选股器管理器
│   ├── factor_screener.py       # 因子选股器
│   ├── technical_screener.py    # 技术指标选股器
│   ├── composite_screener.py    # 组合选股器
│   └── custom/                  # 自定义选股器
│
├── data/                        # 数据模块
│   └── data_feed.py             # 数据源（AKShare）
│
├── scripts/                     # 脚本工具
│   ├── run_backtest.py          # 单策略回测
│   ├── compare_strategies.py    # 策略对比
│   ├── run_screener.py          # 选股
│   └── run_batch_backtest.py    # 批量回测
│
└── docs/                        # 文档
    ├── MULTI_STRATEGY_COMPARISON.md
    └── SCREENER_GUIDE.md
```

## 核心概念

### 1. 数据获取

```python
from data.data_feed import AStockDataFeed

# 创建数据源
data_feed = AStockDataFeed()

# 获取股票数据
df = data_feed.get_stock_data(
    symbol="000001",      # 股票代码
    start_date="2023-01-01",
    end_date="2024-12-31",
    adjust="qfq"         # 前复权
)
```

### 2. 策略开发

```python
from strategies.base_strategy import BaseStrategy
import backtrader as bt

class MyStrategy(BaseStrategy):
    params = (
        ('period', 20),
    )

    def __init__(self):
        super().__init__()
        # 计算指标
        self.sma = bt.indicators.SMA(self.data.close, period=self.p.period)

    def next(self):
        # 实现交易逻辑
        if self.data.close[0] > self.sma[0]:
            self.buy()
        elif self.data.close[0] < self.sma[0]:
            self.sell()
```

### 3. 回测运行

```python
from core.backtest_engine import BacktestEngine
from strategies.ma_strategy import DualMovingAverage

# 创建引擎
engine = BacktestEngine(initial_cash=100000)

# 添加数据和策略
engine.add_data(df)
engine.add_strategy(DualMovingAverage, fast_period=5, slow_period=20)

# 运行回测
result = engine.run()
print(result)
```

## 示例策略

### 双均线策略

**原理**：
- 快线上穿慢线（金叉）→ 买入
- 快线下穿慢线（死叉）→ 卖出

**运行**：
```bash
uv run python scripts/run_backtest.py --fast 5 --slow 20
```

**参数调优**：
```bash
# 尝试不同的均线组合
uv run python scripts/run_backtest.py --fast 10 --slow 30
uv run python scripts/run_backtest.py --fast 20 --slow 60
```

## 配置说明

编辑 \`config/settings.yaml\` 文件可以修改系统配置：

```yaml
# 回测配置
backtest:
  initial_cash: 100000    # 初始资金
  commission: 0.0003      # 手续费（万分之3）

# A股交易规则
a_stocks:
  t_plus_one: true        # T+1交易
  limit_up: 0.10          # 涨跌停10%
  min_unit: 100          # 最小交易单位100股

# 日志配置
logging:
  level: "INFO"          # 日志级别
  file: "./logs/quant_trading.log"
```

## 常用命令

```bash
# 查看数据获取示例
uv run python data/data_feed.py

# 查看策略基类文档
uv run python strategies/base_strategy.py

# 运行回测
uv run python scripts/run_backtest.py --help
```

## 常见问题

### Q1: 数据获取失败怎么办？
**A**: AKShare依赖网络，可能需要：
- 检查网络连接
- 更换股票代码
- 稍后重试

### Q2: 如何添加自定义策略？
**A**:
1. 在 \`strategies/custom/\` 创建新文件
2. 继承 \`BaseStrategy\` 类
3. 实现 \`next()\` 方法
4. 在 \`scripts/run_backtest.py\` 中导入使用

### Q3: 回测没有交易信号？
**A**: 可能的原因：
- 策略参数不合适（调整均线周期）
- 时间范围太短
- 股票价格波动小

### Q4: 图表无法显示？
**A**:
- Windows用户：确保安装了matplotlib依赖
- 使用 \`--no-plot\` 参数跳过图表

### Q5: 选股测试速度很慢？
**A**: 这是正常现象，原因和解决方案：
- **原因**: 因子选股器需要获取每只股票的实时基本面数据，每只股票约需1-2秒
- **当前状态**: 50只股票需要1-2分钟
- **优化建议**:
  - 减少 \`--stock-limit\` 参数值（测试时使用10-20只）
  - 使用更具体的选股条件（缩小筛选范围）
  - 避免频繁运行选股，可缓存结果重复使用
- **批量回测**: 先用小规模测试（10-20只），确认效果后再扩大规模

### Q6: Windows终端显示乱码？
**A**: 编码问题导致特殊字符显示异常：
- 不影响功能使用，仅影响日志显示
- 解决方案：设置终端编码为UTF-8（如果支持）
- 或使用 \`--no-save\` 参数减少日志输出

## 下一步

- [ ] 尝试不同的股票代码
- [ ] 调整策略参数，寻找最优参数
- [ ] 开发自己的交易策略
- [ ] 查看回测日志，理解交易逻辑
- [ ] 学习更多技术指标（RSI、MACD等）

## 技术支持

- 查看日志文件：\`logs/quant_trading.log\`
- 查看数据缓存：\`data/storage/\`
- 查看代码注释：每个文件都有详细注释

## 许可证

MIT License
