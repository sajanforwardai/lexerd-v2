# A/B Backtesting Framework for Phase 2 Validation

A production-grade backtesting and statistical validation framework for comparing Tier 2 baseline vs. Tier 3 candidate strategies in the group1-rag system.

## Overview

This framework enables rigorous A/B testing of trading/ranking strategies with:

- **30-60 day historical backtests** with realistic market data
- **Statistical significance testing** via bootstrap resampling
- **Comprehensive metrics**: Sharpe ratio, Sortino, max drawdown, Information Ratio, p-values
- **GO/CONDITIONAL_GO/NO_GO decisions** based on 90% confidence threshold (p < 0.10)
- **Transaction cost modeling** (slippage, commissions)
- **Edge case handling** (data gaps, survivorship bias)
- **JSON + Markdown reporting** with comparison tables

## Components

### 1. BacktestEngine (`backtest_engine.py`)
Main orchestrator for running backtests.

**Key Methods:**
- `run_backtest()` - Execute full A/B test comparing Tier 2 vs Tier 3
- `load_historical_data()` - Load or generate price data
- `handle_data_gaps()` - Forward-fill missing trading days
- `adjust_for_survivorship_bias()` - Apply -0.1% annual adjustment
- `validate_backtest_integrity()` - Quality checks on results

**Example:**
```python
config = BacktestConfig(
    start_date='2024-01-01',
    end_date='2024-03-01',
    symbol='SPY',
    confidence_level=0.90,
    n_bootstrap=1000,
)

engine = BacktestEngine(config)
result = engine.run_backtest(tier2_signals, tier3_signals, prices, dates)
```

### 2. StrategyExecutor (`strategy_executor.py`)
Executes strategy signals with position management.

**Features:**
- Long/short position handling
- Transaction costs (entry/exit slippage + commission)
- Risk management (stop-loss, take-profit)
- Daily P&L calculation
- Trade-level tracking

**Example:**
```python
strategy_config = StrategyConfig(
    entry_slippage=0.001,
    exit_slippage=0.001,
    commission_per_trade=0.0005,
    stop_loss=0.05,  # 5%
    take_profit=0.10,  # 10%
)

executor = StrategyExecutor(strategy_config)
result = executor.execute_strategy(dates, prices, signals)
```

### 3. MetricsCalculator (`metrics_calculator.py`)
Calculates financial performance metrics.

**Metrics:**
- **Sharpe Ratio** - Risk-adjusted return (daily-based, annualized)
- **Sortino Ratio** - Downside risk-adjusted return
- **Max Drawdown** - Peak-to-trough decline
- **Calmar Ratio** - Annual return / max drawdown
- **Win Rate** - % of positive days
- **Profit Factor** - Gross profit / gross loss
- **Information Ratio** - Excess return vs benchmark
- **Volatility** - Daily volatility (annualized)

**Example:**
```python
calc = MetricsCalculator(risk_free_rate=0.02)
metrics = calc.calculate_metrics(
    returns=[0.001, 0.002, -0.001, ...],
    benchmark_returns=[...],  # Optional
)

print(f"Sharpe: {metrics.sharpe_ratio:.4f}")
print(f"Max Drawdown: {metrics.max_drawdown:.2f}%")
```

### 4. StatisticalValidator (`statistical_validator.py`)
Tests statistical significance of improvement via bootstrap resampling.

**Tests:**
- Bootstrap confidence intervals (default 90%)
- One-tailed hypothesis test (H1: Tier 3 > Tier 2)
- Cohen's d effect size
- Permutation test (distribution-free alternative)
- Required sample size calculation

**Decision Logic:**
- **GO**: p_value < 0.10 + positive Sharpe diff
- **CONDITIONAL_GO**: 0.10 ≤ p_value < 0.20 + positive Sharpe diff
- **NO_GO**: negative Sharpe diff or p_value ≥ 0.20

**Example:**
```python
validator = StatisticalValidator(confidence_level=0.90, n_bootstrap=1000)
result = validator.validate_improvement(tier2_returns, tier3_returns)

if result.significant_at_level:
    print(f"✓ Tier 3 wins with {result.p_value:.4f} p-value")
else:
    print(f"✗ No significant improvement (p={result.p_value:.4f})")
```

### 5. ResultsReporter (`reporter.py`)
Generates comprehensive reports in JSON and Markdown formats.

**Outputs:**
- **JSON**: Machine-readable full results with all metrics
- **Markdown**: Human-readable report with tables and recommendations

**Example:**
```python
reporter = ResultsReporter()

# JSON report
json_report = reporter.generate_report(
    result,
    format=ReportFormat.JSON,
    output_path='/path/to/report.json'
)

# Markdown report
md_report = reporter.generate_report(
    result,
    format=ReportFormat.MARKDOWN,
    output_path='/path/to/report.md'
)
```

## Data Sources

### Mock Data
Default mode using geometric Brownian motion:

```python
config = BacktestConfig(data_source='mock')
engine = BacktestEngine(config)
dates, prices, volumes = engine.load_historical_data(
    symbol='SPY',
    start_date='2024-01-01',
    end_date='2024-03-01',
)
```

Generates realistic price paths with:
- Configurable volatility (default 1.5% daily)
- Configurable drift (default 0.05% daily)
- Actual trading day dates (weekends/holidays excluded)

### Real Data
Production mode using yfinance or other connectors:

```python
config = BacktestConfig(data_source='real')
engine = BacktestEngine(config)
```

Falls back to mock data gracefully if yfinance unavailable.

## Edge Cases & Quality Checks

### Data Gaps
Missing trading days (e.g., holidays) are forward-filled:
```python
cleaned_dates, cleaned_prices = engine.handle_data_gaps(dates, prices)
```

### Survivorship Bias
Historical backtests include only surviving companies. Applied as -0.1% annual return adjustment:
```python
adjusted_prices = engine.adjust_for_survivorship_bias(prices, dates)
```

### Integrity Validation
Pre-deployment checks:
```python
checks = engine.validate_backtest_integrity(result)
# Verifies: sufficient data, valid returns, reasonable metrics, valid p-values
```

## Transaction Costs

Realistic modeling of:
- **Entry slippage**: Adverse price movement when entering (default 10 bps)
- **Exit slippage**: Adverse price movement when exiting (default 10 bps)
- **Commission**: Per-trade cost (default 5 bps = 0.05%)

Total cost per round-trip: ~25-30 bps

```python
StrategyConfig(
    entry_slippage=0.001,    # 10 bps
    exit_slippage=0.001,     # 10 bps
    commission_per_trade=0.0005,  # 5 bps
)
```

## Usage Examples

### Example 1: Simple Comparison
```python
from backtest_engine import BacktestEngine, BacktestConfig
from reporter import ResultsReporter, ReportFormat

# Configure
config = BacktestConfig(
    start_date='2024-01-01',
    end_date='2024-03-01',
    confidence_level=0.90,
    n_bootstrap=1000,
)

# Run backtest
engine = BacktestEngine(config)
dates, prices, _ = engine.load_historical_data('SPY', '2024-01-01', '2024-03-01')

tier2_signals = [1] * len(prices)  # Always long
tier3_signals = [1 if i % 2 == 0 else 0 for i in range(len(prices))]

result = engine.run_backtest(tier2_signals, tier3_signals, prices, dates)

# Generate report
reporter = ResultsReporter()
md_report = reporter.generate_report(result, format=ReportFormat.MARKDOWN)
print(md_report)
```

### Example 2: Moving Average Crossover
```python
import numpy as np

# Generate signals
def ma_signal(prices, window):
    signals = []
    for i in range(len(prices)):
        if i < window:
            signals.append(0)
        else:
            ma = np.mean(prices[i-window:i])
            if prices[i] > ma:
                signals.append(1)  # Long
            elif prices[i] < ma * 0.99:
                signals.append(-1)  # Short
            else:
                signals.append(0)  # Flat
    return signals

tier2_signals = ma_signal(prices, window=10)  # Slower
tier3_signals = ma_signal(prices, window=5)   # Faster

result = engine.run_backtest(tier2_signals, tier3_signals, prices, dates)
```

### Example 3: With Risk Management
```python
from strategy_executor import StrategyConfig

strategy_config = StrategyConfig(
    entry_slippage=0.001,
    exit_slippage=0.001,
    commission_per_trade=0.0005,
    stop_loss=0.05,      # 5% stop loss
    take_profit=0.10,    # 10% take profit
)

config = BacktestConfig(
    start_date='2024-01-01',
    end_date='2024-02-01',
    strategy_config=strategy_config,
)

result = engine.run_backtest(tier2_signals, tier3_signals, prices, dates)
```

## Output Formats

### Markdown Report
Includes:
- Executive summary with recommendation
- Performance comparison table
- Detailed metrics for each tier
- Statistical analysis with hypothesis test results
- Risk analysis (max drawdown, volatility)
- Sample trade history
- GO/CONDITIONAL_GO/NO_GO recommendation

### JSON Report
Structured output with:
- Metadata (dates, symbol, confidence level)
- Tier 2 metrics and execution details
- Tier 3 metrics and execution details
- Comparison metrics (Sharpe diff, p-value, CI)
- Decision (winner, recommendation)

## Interpretation Guide

### Decision Thresholds
| Condition | Recommendation |
|-----------|-----------------|
| p_value < 0.10 + Sharpe_diff > 0 | GO |
| 0.10 ≤ p_value < 0.20 + Sharpe_diff > 0 | CONDITIONAL_GO |
| Sharpe_diff ≤ 0 OR p_value ≥ 0.20 | NO_GO |

### P-Value
- **p < 0.05**: Very strong evidence (95% confidence)
- **p < 0.10**: Strong evidence (90% confidence) ← **This is our threshold**
- **p < 0.20**: Moderate evidence (80% confidence)
- **p ≥ 0.20**: Weak evidence

### Confidence Interval
If 0 is outside the 90% CI and entire interval is positive → strong evidence of improvement.

### Effect Size (Cohen's d)
- **d < 0.2**: Small effect (practical significance?)
- **0.2 ≤ d < 0.5**: Small-to-medium effect
- **0.5 ≤ d < 0.8**: Medium effect
- **d ≥ 0.8**: Large effect

## Running Tests

Comprehensive test suite in `test_backtest.py`:

```bash
cd /workspace/group1-rag/backtest

# Run all tests
pytest test_backtest.py -v

# Run specific test class
pytest test_backtest.py::TestMetricsCalculator -v

# Run with coverage
pytest test_backtest.py --cov=. --cov-report=html
```

Test categories:
- **MetricsCalculator**: Sharpe, Sortino, drawdown, profit factor
- **StrategyExecutor**: Long/short execution, transaction costs, risk management
- **StatisticalValidator**: Bootstrap CI, hypothesis tests, effect sizes
- **BacktestEngine**: Full workflow, data loading, integrity checks
- **ResultsReporter**: JSON/Markdown generation
- **EdgeCases**: Insufficient data, gaps, zero volatility

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           BacktestEngine (Orchestrator)                 │
│  - run_backtest()                                       │
│  - load_historical_data()                               │
│  - handle_data_gaps()                                   │
│  - adjust_for_survivorship_bias()                       │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌─────────────────────────────────────────────────────┐
   │          StrategyExecutor (2x, for each tier)       │
   │  - execute_strategy()                               │
   │  - generate_signals()                               │
   │  - apply_risk_management()                          │
   └──────────────┬──────────────────────────────────────┘
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
   ┌──────────────────┐  ┌──────────────────┐
   │ MetricsCalculator│  │StatisticalValidator
   │ - calculate_*()  │  │ - validate_improvement()
   │ - _calculate_*() │  │ - bootstrap_sharpe_diff()
   └──────────────────┘  │ - permutation_test()
        │                └──────────────────┘
        │                      │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────────┐
        │   ResultsReporter        │
        │ - generate_report()      │
        │ - _generate_json()       │
        │ - _generate_markdown()   │
        └──────────────────────────┘
```

## Key Design Decisions

1. **Bootstrap over parametric tests**: No assumptions about return distribution
2. **One-tailed test**: H1 is directional (Tier 3 > Tier 2)
3. **90% confidence (p < 0.10)**: Conservative threshold for trading decisions
4. **Sharpe ratio as primary metric**: Risk-adjusted, comparable across strategies
5. **Mock data default**: Reproducible, no external dependencies
6. **Forward-fill gaps**: Conservative, doesn't artificially improve metrics
7. **Survivorship bias adjustment**: -0.1% annual (typical historical estimate)

## Production Checklist

Before deploying Tier 3 to production:

- [ ] ✓ Minimum 30 days of backtest data
- [ ] ✓ p-value < 0.10 (90% confidence)
- [ ] ✓ Sharpe difference > 0
- [ ] ✓ No data gaps or gaps properly handled
- [ ] ✓ Max drawdown acceptable
- [ ] ✓ Transaction costs modeled
- [ ] ✓ Integrity checks pass
- [ ] ✓ Effect size > small (Cohen's d > 0.2)
- [ ] ✓ Recommendation = GO

## Future Enhancements

- [ ] Real-time P&L monitoring
- [ ] Walk-forward analysis (rolling windows)
- [ ] Monte Carlo simulation
- [ ] Stress testing (market regimes)
- [ ] Factor exposure analysis
- [ ] Correlation analysis between tier 2 and 3
- [ ] Parameter sensitivity analysis
- [ ] Backtesting GUI dashboard

## Troubleshooting

### Issue: "Insufficient data" error
**Solution**: Ensure backtest period ≥ 30 days. Default: 60-day window.

### Issue: Unrealistic Sharpe ratios (> 3)
**Cause**: Usually mock data or insufficient diversification
**Solution**: Verify signal generation logic, check for look-ahead bias

### Issue: High transaction costs
**Cause**: Excessive trading (small lookback windows, tight thresholds)
**Solution**: Increase minimum holding period, reduce commission estimates if realistic

### Issue: Tier 2 and 3 are identical
**Cause**: Signals are identical or strategies are too similar
**Solution**: Ensure tier 3 has meaningful difference from baseline

## References

- Sharpe, W. F. (1994). "The Sharpe Ratio". The Journal of Portfolio Management.
- Sortino, F., & Price, L. N. (1994). "Performance measurement in a downside risk framework".
- Efron, B., & Tibshirani, R. J. (1993). "An Introduction to the Bootstrap".
- Pedersen, M. H., & Razin, I. (2018). "Risk Parity Fundamentals".

## License

Internal use only - ForwardAI group1-rag project.
