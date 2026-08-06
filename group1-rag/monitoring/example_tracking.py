"""
Example: Full Daily Monitoring Cycle

Demonstrates end-to-end usage of all monitoring components:
1. Load daily trade executions
2. Calculate P&L and Greeks aggregation
3. Compare live performance to backtest baseline
4. Monitor regime shifts via correlation matrix
5. Detect volatility spikes
6. Check correlation breakdowns
7. Log failures and pattern match
8. Generate daily monitoring report
"""

from datetime import datetime, timedelta
import numpy as np
from pnl_tracker import PnLTracker, TradeExecution, GreeksSnapshot, Regime
from backtest_comparison import BacktestComparator, BacktestBaseline, LivePerformance
from regime_shift_detector import RegimeShiftDetector, MarketSnapshot
from vol_spike_detector import VolatilitySpikeDetector, VolatilitySnapshot
from correlation_detector import CorrelationDetector, CorrelationSnapshot
from failure_mode_tracker import FailureModeTracker, FailureCategory, FailureSeverity


def load_daily_trades() -> list:
    """Load trades executed today."""
    return [
        TradeExecution(
            date="2024-01-15",
            strategy="tier2_baseline",
            instrument="SPY",
            entry_price=450.00,
            exit_price=451.50,
            entry_time="09:30",
            exit_time="11:45",
            quantity=100,
            side="long",
            realized_pnl=150.0 - 50.0,  # (451.5-450)*100 - costs
            unrealized_pnl=0.0,
            entry_cost=25.0,
            exit_cost=25.0,
            greeks_exit=GreeksSnapshot(
                delta=0.95,
                gamma=0.02,
                vega=0.50,
                theta=-0.01,
                rho=0.15,
            ),
        ),
        TradeExecution(
            date="2024-01-15",
            strategy="tier2_baseline",
            instrument="QQQ",
            entry_price=380.00,
            exit_price=382.00,
            entry_time="10:00",
            exit_time="14:30",
            quantity=50,
            side="long",
            realized_pnl=100.0 - 40.0,
            unrealized_pnl=0.0,
            entry_cost=20.0,
            exit_cost=20.0,
            greeks_exit=GreeksSnapshot(
                delta=0.92,
                gamma=0.03,
                vega=0.65,
                theta=-0.015,
                rho=0.12,
            ),
        ),
        TradeExecution(
            date="2024-01-15",
            strategy="tier3_candidate",
            instrument="SPY",
            entry_price=450.50,
            exit_price=451.00,
            entry_time="11:00",
            exit_time="13:15",
            quantity=80,
            side="long",
            realized_pnl=40.0 - 30.0,
            unrealized_pnl=0.0,
            entry_cost=15.0,
            exit_cost=15.0,
            greeks_exit=GreeksSnapshot(
                delta=0.88,
                gamma=0.04,
                vega=0.48,
                theta=-0.01,
                rho=0.14,
            ),
        ),
    ]


def load_market_snapshots(n_snapshots: int = 8) -> list:
    """Load intraday market snapshots (hourly)."""
    snapshots = []
    base_time = datetime(2024, 1, 15, 9, 30)

    for i in range(n_snapshots):
        timestamp = base_time + timedelta(hours=i)

        # Create realistic correlation matrix
        # Starting with low correlation, moving to moderate
        correlation_factor = min(0.5 + i * 0.08, 0.90)
        corr_matrix = np.array([
            [1.0, correlation_factor, correlation_factor * 0.7],
            [correlation_factor, 1.0, correlation_factor * 0.8],
            [correlation_factor * 0.7, correlation_factor * 0.8, 1.0],
        ])

        # VIX level increasing during day
        vix_level = 15.0 + i * 1.5

        snapshot = MarketSnapshot(
            timestamp=timestamp,
            vix_level=vix_level,
            vix_1m_skew=0.05 + i * 0.01,
            vix_term_slope=0.05 - i * 0.008,
            correlation_matrix=corr_matrix,
            strategies=["tier2_baseline", "tier3_candidate", "momentum"],
        )
        snapshots.append(snapshot)

    return snapshots


def load_volatility_snapshots(n_snapshots: int = 8) -> list:
    """Load intraday volatility snapshots."""
    snapshots = []
    base_time = datetime(2024, 1, 15, 9, 30)

    for i in range(n_snapshots):
        timestamp = base_time + timedelta(hours=i)

        # Vol slowly increasing
        realized_vol = 0.12 + i * 0.01

        snapshot = VolatilitySnapshot(
            timestamp=timestamp,
            instrument="SPY",
            price=451.0 + i * 0.5,
            returns=[0.01] * 5,
            realized_vol=realized_vol,
        )
        snapshots.append(snapshot)

    return snapshots


def main():
    """Run complete daily monitoring cycle."""

    print("=" * 80)
    print("GROUP ONE TRADING RAG - PHASE 3 MONITORING CYCLE")
    print("=" * 80)
    print()

    # ========================================================================
    # Initialize Components
    # ========================================================================
    print("[1/8] Initializing monitoring components...")

    pnl_tracker = PnLTracker()
    backtest_comparator = BacktestComparator()
    regime_detector = RegimeShiftDetector()
    vol_detector = VolatilitySpikeDetector()
    corr_detector = CorrelationDetector()
    failure_tracker = FailureModeTracker()

    print("  ✓ PnL Tracker initialized")
    print("  ✓ Backtest Comparator initialized")
    print("  ✓ Regime Shift Detector initialized")
    print("  ✓ Volatility Spike Detector initialized")
    print("  ✓ Correlation Detector initialized")
    print("  ✓ Failure Mode Tracker initialized")
    print()

    # ========================================================================
    # Step 1: Record Daily Trades
    # ========================================================================
    print("[2/8] Recording daily trades...")

    trades = load_daily_trades()
    pnl_tracker.record_trades_batch(trades)

    for trade in trades:
        print(
            f"  ✓ {trade.strategy:20} {trade.instrument:5} "
            f"${trade.realized_pnl:>8.2f}"
        )

    daily_summary = pnl_tracker.calculate_daily_summary("2024-01-15")
    print(f"\n  Daily Total P&L: ${daily_summary.total_pnl:,.2f}")
    print(f"  Trade Count: {daily_summary.trade_count}")
    print(f"  Win Rate: {daily_summary.win_rate:.1%}")
    print()

    # ========================================================================
    # Step 2: Aggregate P&L by Dimension
    # ========================================================================
    print("[3/8] Aggregating P&L by strategy and instrument...")

    by_strategy = pnl_tracker.aggregate_by_strategy(("2024-01-15", "2024-01-15"))
    by_instrument = pnl_tracker.aggregate_by_instrument(("2024-01-15", "2024-01-15"))

    for strategy, metrics in by_strategy.items():
        print(
            f"  {strategy:25} P&L: ${metrics['realized_pnl']:>8.2f} "
            f"({metrics['trade_count']} trades)"
        )

    print()
    for instrument, metrics in by_instrument.items():
        print(
            f"  {instrument:25} P&L: ${metrics['realized_pnl']:>8.2f} "
            f"({metrics['trade_count']} trades)"
        )
    print()

    # ========================================================================
    # Step 3: Compare to Backtest Baseline
    # ========================================================================
    print("[4/8] Comparing live performance to backtest...")

    backtest_baseline = BacktestBaseline(
        strategy_name="tier2_baseline",
        expected_sharpe_ratio=1.45,
        expected_annual_return=0.15,
        expected_max_drawdown=-0.08,
        expected_volatility=0.12,
        expected_win_rate=0.56,
        expected_profit_factor=1.65,
        backtest_period=("2023-01-01", "2023-12-31"),
    )

    live_performance = LivePerformance(
        strategy_name="tier2_baseline",
        actual_sharpe_ratio=1.42,
        actual_return=0.145,  # Slight underperformance
        actual_max_drawdown=-0.085,
        actual_volatility=0.125,  # Slightly higher vol
        actual_win_rate=0.54,  # Slightly lower win rate
        actual_profit_factor=1.60,
        live_period=("2024-01-01", "2024-01-15"),
        n_trades=248,
    )

    comparison = backtest_comparator.compare(backtest_baseline, live_performance)

    print(f"  Strategy: {comparison.strategy_name}")
    print(f"  Backtest Sharpe: {comparison.backtest_baseline.expected_sharpe_ratio:.2f}")
    print(f"  Live Sharpe: {comparison.live_performance.actual_sharpe_ratio:.2f}")
    print(f"  Sharpe Variance: {comparison.sharpe_variance_pct:.1f}%")
    print()
    print(f"  Backtest Return: {comparison.backtest_baseline.expected_annual_return:.1%}")
    print(f"  Live Return: {comparison.live_performance.actual_return:.1%}")
    print(f"  Return Variance: {comparison.return_variance_pct:.1f}%")
    print()
    print(f"  Variance Magnitude: {comparison.variance_magnitude}")
    print(f"  Divergence Alert: {'YES - INVESTIGATE' if comparison.divergence_alert else 'NO'}")
    print(f"  Recommendation: {comparison.recommendation}")
    print()

    if comparison.variance_drivers:
        print("  Top Variance Drivers:")
        for driver in comparison.variance_drivers[:3]:
            print(
                f"    • {driver.driver_name:25} {driver.impact_bps:>6.0f} bps "
                f"({driver.direction}, {driver.confidence:.0%} confidence)"
            )
    print()

    # ========================================================================
    # Step 4: Monitor Regime Shifts
    # ========================================================================
    print("[5/8] Monitoring regime shifts via correlation analysis...")

    market_snapshots = load_market_snapshots(n_snapshots=8)
    regime_alerts = []

    for snapshot in market_snapshots:
        alert = regime_detector.update(snapshot)
        if alert:
            regime_alerts.append(alert)

    current_regime = regime_detector.get_current_regime()
    print(f"  Current Regime: {current_regime['regime']}")
    print(f"  Condition Number: {current_regime['condition_number']:.2f}")
    print(f"  VIX Level: {market_snapshots[-1].vix_level:.1f}")
    print(f"  Regime Confidence: {current_regime['confidence']:.0%}")
    print()

    if regime_alerts:
        print(f"  Regime Shift Alerts: {len(regime_alerts)}")
        for alert in regime_alerts[-3:]:
            print(
                f"    • {alert.previous_regime:20} -> {alert.new_regime:20} "
                f"(severity: {alert.severity})"
            )
    else:
        print("  No regime shifts detected")
    print()

    # ========================================================================
    # Step 5: Detect Volatility Spikes
    # ========================================================================
    print("[6/8] Monitoring volatility spikes...")

    # Establish baseline
    for i in range(30):
        vol_detector.baseline_calc.update("SPY", 0.01)

    vol_snapshots = load_volatility_snapshots(n_snapshots=8)
    vol_spikes = []

    for snapshot in vol_snapshots:
        spike = vol_detector.update(snapshot)
        if spike:
            vol_spikes.append(spike)

    current_baseline = vol_detector.baseline_calc.get_baseline("SPY")
    print(f"  SPY Volatility Baseline (30d): {current_baseline:.1%}")
    print(f"  Current Realized Vol: {vol_snapshots[-1].realized_vol:.1%}")
    print(f"  Vol Ratio: {vol_snapshots[-1].realized_vol / current_baseline:.2f}x")
    print()

    if vol_spikes:
        print(f"  Volatility Spike Alerts: {len(vol_spikes)}")
        for spike in vol_spikes:
            print(
                f"    • {spike.instrument} spike {spike.spike_ratio:.1f}x "
                f"(duration: {spike.duration_minutes}min, severity: {spike.severity})"
            )
    else:
        print("  No volatility spikes detected")
    print()

    # ========================================================================
    # Step 6: Check Correlation Breakdowns
    # ========================================================================
    print("[7/8] Monitoring correlation breakdowns...")

    corr_breakdowns = []
    for snapshot in market_snapshots:
        strategies = snapshot.strategies
        breakdown = corr_detector.update(snapshot, strategies)
        if breakdown:
            corr_breakdowns.append(breakdown)

    current_corr = corr_detector.get_current_metrics()
    if current_corr:
        print(f"  Current Condition Number: {current_corr['condition_number']:.2f}")
        print(f"  Max Strategy Correlation: {current_corr['max_correlation']:.2f}")
        print(f"  Avg Strategy Correlation: {current_corr['avg_correlation']:.2f}")
        print()

        if corr_breakdowns:
            print(f"  Correlation Breakdown Alerts: {len(corr_breakdowns)}")
            for breakdown in corr_breakdowns[-2:]:
                print(
                    f"    • CN change: {breakdown.condition_number_change:.1f}x "
                    f"(severity: {breakdown.severity})"
                )
        else:
            print("  No correlation breakdowns detected")
    print()

    # ========================================================================
    # Step 7: Log Failures and Match Patterns
    # ========================================================================
    print("[8/8] Logging failures and pattern matching...")

    # Example: Small execution slippage (known mode)
    failure1 = failure_tracker.record_failure(
        timestamp=datetime.utcnow() - timedelta(hours=2),
        category=FailureCategory.EXECUTION_FAILURE,
        severity=FailureSeverity.MINOR,
        strategy="tier2_baseline",
        instrument="SPY",
        description="Slippage exceeded expected levels in regime change",
        financial_impact=2500.0,
        root_cause="Market liquidity reduced during correlation spike",
    )

    print(f"  Failure recorded: {failure1.category.value}")
    print(f"    Strategy: {failure1.strategy}")
    print(f"    Impact: ${failure1.financial_impact:,.0f}")
    print(f"    Known Mode: {'YES' if failure1.is_known_mode else 'NO'}")
    if failure1.matched_failure_modes:
        print(f"    Matched Modes: {', '.join(failure1.matched_failure_modes)}")
    print()

    # ========================================================================
    # Summary Report
    # ========================================================================
    print("=" * 80)
    print("DAILY MONITORING REPORT SUMMARY")
    print("=" * 80)
    print()

    summary_report = pnl_tracker.get_summary_report("2024-01-15", "2024-01-15")

    print("P&L Summary:")
    print(f"  Total P&L: ${daily_summary.total_pnl:,.2f}")
    print(f"  Realized: ${daily_summary.realized_pnl:,.2f}")
    print(f"  Unrealized: ${daily_summary.unrealized_pnl:,.2f}")
    print()

    print("Trading Activity:")
    print(f"  Total Trades: {daily_summary.trade_count}")
    print(f"  Winning Trades: {daily_summary.winning_trades}")
    print(f"  Losing Trades: {daily_summary.losing_trades}")
    print(f"  Win Rate: {daily_summary.win_rate:.1%}")
    print(f"  Profit Factor: {daily_summary.profit_factor:.2f}")
    print()

    print("Risk Indicators:")
    print(f"  Current Regime: {current_regime['regime']}")
    print(f"  Condition Number: {current_regime['condition_number']:.2f}")
    print(f"  VIX: {market_snapshots[-1].vix_level:.1f}")
    print(f"  Vol Spike Active: {'YES' if vol_detector.is_spiking('SPY') else 'NO'}")
    print()

    print("Alerts Summary:")
    print(f"  Regime Shift Alerts: {len(regime_alerts)}")
    print(f"  Volatility Spike Alerts: {len(vol_spikes)}")
    print(f"  Correlation Breakdown Alerts: {len(corr_breakdowns)}")
    print(f"  Failure Events: 1")
    print()

    print("Backtest Comparison:")
    print(f"  Return Variance: {comparison.return_variance_pct:.1f}%")
    print(f"  Status: {'INVESTIGATE' if comparison.divergence_alert else 'MONITOR'}")
    print()

    print("=" * 80)
    print("CYCLE COMPLETE - All monitoring systems operational")
    print("=" * 80)


if __name__ == "__main__":
    main()
