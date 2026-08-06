# 20-Minute Quickstart: Group One Trading RAG Monitoring

Get the P&L tracking and regime shift detection system running in 20 minutes.

## What You'll Have After 20 Minutes

- ✓ P&L tracker recording trades and calculating daily metrics
- ✓ Backtest comparator detecting divergence from baseline
- ✓ Regime shift detector monitoring correlation breakdowns
- ✓ Volatility spike detector alerting on vol spikes
- ✓ Failure mode tracker logging issues
- ✓ Full daily monitoring cycle running end-to-end

## Prerequisites (2 minutes)

```bash
# Verify Python 3.8+
python --version

# Install required packages
pip install numpy pandas scipy pytest

# Navigate to monitoring directory
cd /workspace/group1-rag/monitoring
```

## Step 1: Run Tests (3 minutes)

Verify all components are working:

```bash
# Run test suite
pytest test_monitoring.py -v

# Expected output: 24/24 tests PASSED
```

If any tests fail, check the error messages and ensure numpy/scipy are properly installed.

## Step 2: Run Example Cycle (5 minutes)

Execute a complete daily monitoring cycle:

```bash
# Run example
python example_tracking.py

# Expected output: Full monitoring report with:
# - Daily P&L calculations
# - Strategy aggregation
# - Backtest comparison
# - Regime analysis
# - Vol spike monitoring
# - Correlation checks
# - Failure tracking
```

Review the output to understand the monitoring flow.

## Step 3: Load Your Data (7 minutes)

Create a simple data loader for your trades:

```python
# Create file: load_trades.py
from datetime import datetime
from pnl_tracker import PnLTracker, TradeExecution

def load_today_trades() -> list:
    """Load trades from your execution system."""
    trades = [
        TradeExecution(
            date="2024-01-15",
            strategy="tier2_baseline",
            instrument="SPY",
            entry_price=450.0,
            exit_price=452.0,
            entry_time="09:30",
            exit_time="14:00",
            quantity=100,
            side="long",
            realized_pnl=0.0,  # Will be computed
            entry_cost=25.0,
            exit_cost=25.0,
        ),
        # Add more trades...
    ]
    return trades

# Run it
if __name__ == "__main__":
    tracker = PnLTracker()
    trades = load_today_trades()
    tracker.record_trades_batch(trades)
    
    summary = tracker.calculate_daily_summary("2024-01-15")
    print(f"Daily P&L: ${summary.total_pnl:,.2f}")
```

## Step 4: Connect to Your Backtest (3 minutes)

Link monitoring to your backtest engine:

```python
# In your monitoring script
from backtest_comparison import BacktestComparator, BacktestBaseline, LivePerformance

comparator = BacktestComparator()

# From your backtest results
backtest = BacktestBaseline(
    strategy_name="tier2_baseline",
    expected_sharpe_ratio=1.45,  # From backtest_engine.tier2_metrics.sharpe_ratio
    expected_annual_return=0.15,  # From backtest_engine.tier2_metrics.total_return
    expected_max_drawdown=-0.08,
    expected_volatility=0.12,
    expected_win_rate=0.56,
    expected_profit_factor=1.65,
    backtest_period=("2023-01-01", "2023-12-31"),
)

# Your live performance
live = LivePerformance(
    strategy_name="tier2_baseline",
    actual_sharpe_ratio=1.42,  # Calculate from returns
    actual_return=0.145,
    actual_max_drawdown=-0.085,
    actual_volatility=0.125,
    actual_win_rate=0.54,
    actual_profit_factor=1.60,
    live_period=("2024-01-01", "2024-01-15"),
    n_trades=248,
)

comparison = comparator.compare(backtest, live)
if comparison.divergence_alert:
    print(f"ALERT: {comparison.live_performance.actual_return:.1%} vs "
          f"{comparison.backtest_baseline.expected_annual_return:.1%}")
```

## Common Tasks

### Check Daily P&L

```python
from pnl_tracker import PnLTracker

tracker = PnLTracker()
# ... record trades ...

summary = tracker.calculate_daily_summary("2024-01-15")
print(f"P&L: ${summary.total_pnl:,.2f}")
print(f"Win Rate: {summary.win_rate:.1%}")
print(f"Profit Factor: {summary.profit_factor:.2f}")
```

### Check P&L by Strategy

```python
by_strategy = tracker.aggregate_by_strategy(("2024-01-15", "2024-01-15"))
for strategy, metrics in by_strategy.items():
    print(f"{strategy}: ${metrics['realized_pnl']:,.2f} "
          f"({metrics['trade_count']} trades)")
```

### Detect Regime Shift

```python
from regime_shift_detector import RegimeShiftDetector, MarketSnapshot
import numpy as np

detector = RegimeShiftDetector()

# Create correlation snapshot
corr = np.eye(3)  # Normal correlation
snapshot = MarketSnapshot(
    timestamp=datetime.utcnow(),
    vix_level=15.0,
    vix_1m_skew=0.05,
    vix_term_slope=0.03,
    correlation_matrix=corr,
    strategies=["tier2", "tier3", "momentum"],
)

alert = detector.update(snapshot)
print(f"Regime: {detector.get_current_regime()['regime']}")
```

### Monitor Vol Spikes

```python
from vol_spike_detector import VolatilitySpikeDetector, VolatilitySnapshot

detector = VolatilitySpikeDetector()

# Establish baseline (need 30 observations first)
for i in range(30):
    detector.baseline_calc.update("SPY", 0.01)  # 1% daily return

# Check for spikes
snapshot = VolatilitySnapshot(
    timestamp=datetime.utcnow(),
    instrument="SPY",
    price=450.0,
    returns=[0.02, 0.015, 0.018],
    realized_vol=0.18,  # Current vol
)

spike = detector.update(snapshot)
if spike:
    print(f"SPIKE: {spike.spike_ratio:.1f}x baseline")
```

### Log Failures

```python
from failure_mode_tracker import FailureModeTracker, FailureCategory, FailureSeverity

tracker = FailureModeTracker()

event = tracker.record_failure(
    timestamp=datetime.utcnow(),
    category=FailureCategory.EXECUTION_FAILURE,
    severity=FailureSeverity.MODERATE,
    strategy="tier2",
    instrument="SPY",
    description="Slippage during vol spike",
    financial_impact=5000.0,
)

print(f"Known mode: {event.is_known_mode}")
```

### Get Weekly Summary

```python
summary = tracker.get_weekly_summary("2024-01-15")
print(f"Weekly P&L Impact: ${summary.total_financial_impact:,.0f}")
print(f"Events: {summary.total_events}")
print(f"Top Recommendations: {summary.top_recommendations[:3]}")
```

## Full Integration Example

Here's a minimal daily run script:

```python
# daily_monitoring.py
from datetime import datetime
from pnl_tracker import PnLTracker, TradeExecution
from backtest_comparison import BacktestComparator, BacktestBaseline, LivePerformance
from regime_shift_detector import RegimeShiftDetector, MarketSnapshot
from vol_spike_detector import VolatilitySpikeDetector, VolatilitySnapshot
from failure_mode_tracker import FailureModeTracker, FailureCategory, FailureSeverity
import numpy as np

# Initialize
pnl = PnLTracker()
backtest_comp = BacktestComparator()
regime = RegimeShiftDetector()
vol = VolatilitySpikeDetector()
failures = FailureModeTracker()

# Load and process trades
trades = [
    TradeExecution(
        date="2024-01-15",
        strategy="tier2",
        instrument="SPY",
        entry_price=450.0,
        exit_price=452.0,
        entry_time="09:30",
        exit_time="14:00",
        quantity=100,
        side="long",
        realized_pnl=200.0 - 50.0,
        entry_cost=25.0,
        exit_cost=25.0,
    ),
]
pnl.record_trades_batch(trades)

# Get daily P&L
summary = pnl.calculate_daily_summary("2024-01-15")
print(f"\n{'='*60}")
print(f"DAILY MONITORING REPORT - 2024-01-15")
print(f"{'='*60}")
print(f"P&L: ${summary.total_pnl:,.2f}")
print(f"Trades: {summary.trade_count}")
print(f"Win Rate: {summary.win_rate:.1%}")

# Compare to backtest
backtest = BacktestBaseline(
    strategy_name="tier2",
    expected_sharpe_ratio=1.45,
    expected_annual_return=0.15,
    expected_max_drawdown=-0.08,
    expected_volatility=0.12,
    expected_win_rate=0.56,
    expected_profit_factor=1.65,
    backtest_period=("2023-01-01", "2023-12-31"),
)

live = LivePerformance(
    strategy_name="tier2",
    actual_sharpe_ratio=1.42,
    actual_return=0.145,
    actual_max_drawdown=-0.085,
    actual_volatility=0.125,
    actual_win_rate=0.54,
    actual_profit_factor=1.60,
    live_period=("2024-01-01", "2024-01-15"),
    n_trades=248,
)

comparison = backtest_comp.compare(backtest, live)
print(f"\nBacktest Comparison:")
print(f"  Return: {live.actual_return:.1%} vs {backtest.expected_annual_return:.1%}")
print(f"  Status: {'DIVERGENCE ALERT' if comparison.divergence_alert else 'MONITOR'}")

# Check regime
corr = np.eye(3)
snapshot = MarketSnapshot(
    timestamp=datetime.utcnow(),
    vix_level=15.0,
    vix_1m_skew=0.05,
    vix_term_slope=0.03,
    correlation_matrix=corr,
    strategies=["tier2", "tier3", "momentum"],
)
regime.update(snapshot)
current = regime.get_current_regime()
print(f"\nRegime: {current['regime']} (CN: {current['condition_number']:.2f})")

print(f"\n{'='*60}")
print("Monitoring complete.")
```

Run it daily:
```bash
python daily_monitoring.py
```

## Next Steps

1. **Connect to execution system**: Load actual trades instead of mock data
2. **Automate snapshots**: Ingest VIX, correlation matrix, vol data every hour
3. **Add alerting**: Route divergence alerts to Slack/email
4. **Extend failure modes**: Add known modes specific to your strategies
5. **Integrate with learning loop**: Feed regime shifts and failures back to Phase 4

## Troubleshooting

| Problem | Solution |
|---------|----------|
| ImportError: numpy | `pip install numpy` |
| Test failures | Run `pytest test_monitoring.py -v` to see details |
| Regime detection always "normal" | Check correlation matrix eigenvalues |
| Vol spike never triggers | Baseline needs 30 observations; use dummy data if needed |
| Backtest comparison shows no variance | Live and backtest metrics too similar; try 5% difference |

## FAQ

**Q: What if I don't have historical correlation matrices?**
A: Use identity matrix (uncorrelated) as starting point; real data comes in automatically.

**Q: How often should I run the full cycle?**
A: Daily after market close for comprehensive review; hourly for regime/vol monitoring.

**Q: Can I customize thresholds?**
A: Yes, all thresholds are configurable. See README.md Tuning section.

**Q: What market data do I need?**
A: Minimum: daily returns, VIX, correlation matrix. Ideal: hourly snapshots.

**Q: How do I extend the failure mode library?**
A: Add entries to `FailureModeTracker.known_modes` dict.

## Support

- **Full Documentation**: See README.md
- **Test Suite**: `pytest test_monitoring.py -v`
- **Example**: `python example_tracking.py`
- **Code**: Each module has docstrings and type hints

---

**Time Estimate**: 20 minutes  
**Complexity**: Beginner  
**Dependencies**: numpy, pandas, scipy, pytest  
**Status**: Production Ready ✓
