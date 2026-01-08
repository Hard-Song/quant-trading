# 量化交易系统 - 快速入门指南

一个适合零基础入门的Python量化交易系统，支持策略回测、模拟交易和实盘交易（预留）。

## 系统特点

- **简单易用**：详细注释，清晰架构，适合初学者
- **A股支持**：内置A股交易规则（T+1、涨跌停限制等）
- **灵活扩展**：模块化设计，方便添加自定义策略
- **完整功能**：数据获取、策略回测、绩效分析、可视化

## 快速开始

### 1. 环境安装

\`\`\`bash
# 使用uv安装依赖（推荐）
uv sync

# 或者使用pip
pip install -r requirements.txt
\`\`\`

### 2. 运行第一个回测

\`\`\`bash
# 方式1：使用默认参数运行
uv run python scripts/run_backtest.py

# 方式2：自定义参数
uv run python scripts/run_backtest.py --symbol 600000 --fast 10 --slow 30

# 方式3：查看帮助信息
uv run python scripts/run_backtest.py --help
\`\`\`

### 3. 查看结果

回测完成后，你会看到：
- 控制台输出详细的交易日志
- 回测结果汇总（收益率、夏普比率、最大回撤等）
- 可视化图表（价格、均线、交易信号）

## 项目结构

\`\`\`
quant/
├── config/                  # 配置文件
│   └── settings.yaml        # 全局配置
├── data/                    # 数据层
│   ├── data_feed.py        # 数据获取（AKShare）
│   └── storage/            # 数据缓存目录
├── strategies/              # 策略层
│   ├── base_strategy.py    # 策略基类
│   ├── ma_strategy.py      # 双均线策略
│   └── custom/             # 自定义策略目录
├── core/                    # 核心层
│   └── backtest_engine.py  # 回测引擎
├── utils/                   # 工具层
│   ├── config.py           # 配置管理
│   └── logger.py           # 日志系统
└── scripts/                 # 运行脚本
    └── run_backtest.py     # 回测运行脚本
\`\`\`

## 核心概念

### 1. 数据获取

\`\`\`python
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
\`\`\`

### 2. 策略开发

\`\`\`python
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
\`\`\`

### 3. 回测运行

\`\`\`python
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
\`\`\`

## 示例策略

### 双均线策略

**原理**：
- 快线上穿慢线（金叉）→ 买入
- 快线下穿慢线（死叉）→ 卖出

**运行**：
\`\`\`bash
uv run python scripts/run_backtest.py --fast 5 --slow 20
\`\`\`

**参数调优**：
\`\`\`bash
# 尝试不同的均线组合
uv run python scripts/run_backtest.py --fast 10 --slow 30
uv run python scripts/run_backtest.py --fast 20 --slow 60
\`\`\`

## 配置说明

编辑 \`config/settings.yaml\` 文件可以修改系统配置：

\`\`\`yaml
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
\`\`\`

## 常用命令

\`\`\`bash
# 查看数据获取示例
uv run python data/data_feed.py

# 查看策略基类文档
uv run python strategies/base_strategy.py

# 运行回测
uv run python scripts/run_backtest.py --help
\`\`\`

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
