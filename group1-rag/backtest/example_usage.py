"""
Example usage of the A/B backtesting framework.

Demonstrates how to:
1. Set up configurations
2. Generate or load data
3. Run backtests
4. Generate reports
5. Interpret results
"""

from backtest_engine import BacktestEngine, BacktestConfig
from strategy_executor import StrategyConfig
from reporter import ResultsReporter, ReportFormat, ReportConfig
import numpy as np


def example_1_simple_comparison():
    """Example 1: Simple Tier 2 vs Tier 3 comparison."""
    print("=" * 80)
    print("Example 1: Simple Strategy Comparison")
    print("=" * 80)

    # Configure backtest
    config = BacktestConfig(
        start_date='2024-01-01',
        end_date='2024-03-01',
        symbol='SPY',
        data_source='mock',
        confidence_level=0.90,
        n_bootstrap=1000,
    )

    engine = BacktestEngine(config)

    # Load historical data
    dates, prices, volumes = engine.load_historical_data(
        symbol='SPY',
        start_date='2024-01-01',
        end_date='2024-03-01',
    )

    print(f"Loaded {len(dates)} trading days of price data")

    # Define strategies
    # Tier 2: Simple moving average crossover (slower, baseline)
    tier2_signals = []
    window = 10
    for i in range(len(prices)):
        if i < window:
            tier2_signals.append(0)
        else:
            ma = np.mean(prices[i-window:i])
            if prices[i] > ma:
                tier2_signals.append(1)  # Long signal
            elif prices[i] < ma * 0.99:
                tier2_signals.append(-1)  # Short signal
            else:
                tier2_signals.append(0)  # Flat

    # Tier 3: Faster moving average crossover (more responsive)
    tier3_signals = []
    window = 5
    for i in range(len(prices)):
        if i < window:
            tier3_signals.append(0)
        else:
            ma = np.mean(prices[i-window:i])
            if prices[i] > ma:
                tier3_signals.append(1)  # Long signal
            elif prices[i] < ma * 0.98:
                tier3_signals.append(-1)  # Short signal
            else:
                tier3_signals.append(0)  # Flat

    # Run backtest
    result = engine.run_backtest(tier2_signals, tier3_signals, prices, dates)

    # Print summary
    print(f"\nResults Summary:")
    print(f"  Winner: {result.winner.upper()}")
    print(f"  Recommendation: {result.recommendation}")
    print(f"  Tier 2 Sharpe: {result.tier2_metrics.sharpe_ratio:.4f}")
    print(f"  Tier 3 Sharpe: {result.tier3_metrics.sharpe_ratio:.4f}")
    print(f"  Sharpe Difference: {result.validation_result.sharpe_difference:.4f}")
    print(f"  P-Value: {result.validation_result.p_value:.4f}")
    print(f"  Significant (90%): {result.validation_result.significant_at_level}")

    return result


def example_2_full_report_generation():
    """Example 2: Generate comprehensive reports."""
    print("\n" + "=" * 80)
    print("Example 2: Full Report Generation")
    print("=" * 80)

    config = BacktestConfig(
        start_date='2024-01-01',
        end_date='2024-03-01',
        confidence_level=0.90,
    )

    engine = BacktestEngine(config)
    dates, prices, _ = engine.load_historical_data('SPY', '2024-01-01', '2024-03-01')

    # Simple buy-and-hold vs. momentum
    tier2_signals = [1] * len(prices)  # Always long
    tier3_signals = [1 if i % 3 == 0 else 0 for i in range(len(prices))]  # Entry every 3 days

    result = engine.run_backtest(tier2_signals, tier3_signals, prices, dates)

    # Generate JSON report
    reporter = ResultsReporter()
    json_report = reporter.generate_report(
        result,
        format=ReportFormat.JSON,
        output_path='/tmp/backtest_report.json'
    )
    print("✓ JSON report saved to /tmp/backtest_report.json")

    # Generate Markdown report
    md_report = reporter.generate_report(
        result,
        format=ReportFormat.MARKDOWN,
        output_path='/tmp/backtest_report.md'
    )
    print("✓ Markdown report saved to /tmp/backtest_report.md")

    # Generate both formats
    both_report = reporter.generate_report(
        result,
        format=ReportFormat.BOTH,
        output_path='/tmp/backtest_report_full.md'
    )
    print("✓ Combined report saved to /tmp/backtest_report_full.md")

    return result


def example_3_statistical_significance():
    """Example 3: Understanding statistical significance."""
    print("\n" + "=" * 80)
    print("Example 3: Statistical Significance Testing")
    print("=" * 80)

    config = BacktestConfig(
        start_date='2024-01-01',
        end_date='2024-02-01',
        confidence_level=0.90,
        n_bootstrap=1000,
    )

    engine = BacktestEngine(config)
    dates, prices, _ = engine.load_historical_data('SPY', '2024-01-01', '2024-02-01')

    # Tier 2: Baseline (modest returns)
    tier2_signals = [1] * len(prices)

    # Tier 3: Slightly better (more selective entry)
    tier3_signals = [1 if i % 2 == 0 else 0 for i in range(len(prices))]

    result = engine.run_backtest(tier2_signals, tier3_signals, prices, dates)

    val = result.validation_result

    print(f"\nStatistical Analysis:")
    print(f"  Tier 2 Sharpe: {val.tier2_sharpe:.4f}")
    print(f"  Tier 3 Sharpe: {val.tier3_sharpe:.4f}")
    print(f"  Difference: {val.sharpe_difference:.4f}")
    print(f"\nConfidence Interval (90%):")
    print(f"  Lower bound: {val.confidence_interval[0]:.4f}")
    print(f"  Upper bound: {val.confidence_interval[1]:.4f}")
    print(f"\nHypothesis Test:")
    print(f"  H0: Tier 3 Sharpe ≤ Tier 2 Sharpe")
    print(f"  H1: Tier 3 Sharpe > Tier 2 Sharpe")
    print(f"  P-Value: {val.p_value:.4f}")
    print(f"  Significance Level (α): 0.10")
    print(f"  Decision: {'Reject H0 ✓' if val.significant_at_level else 'Fail to Reject H0 ✗'}")
    print(f"\nRecommendation: {result.recommendation}")

    return result


def example_4_risk_management():
    """Example 4: Using risk management features."""
    print("\n" + "=" * 80)
    print("Example 4: Risk Management (Stop-Loss & Take-Profit)")
    print("=" * 80)

    strategy_config = StrategyConfig(
        entry_slippage=0.001,
        exit_slippage=0.001,
        commission_per_trade=0.0005,
        stop_loss=0.05,  # 5% stop loss
        take_profit=0.10,  # 10% take profit
    )

    config = BacktestConfig(
        start_date='2024-01-01',
        end_date='2024-02-01',
        strategy_config=strategy_config,
    )

    engine = BacktestEngine(config)
    dates, prices, _ = engine.load_historical_data('SPY', '2024-01-01', '2024-02-01')

    tier2_signals = [0, 1, 1, 1, 0] * 8
    tier3_signals = [0, 1, 1, 0, 1] * 8

    result = engine.run_backtest(tier2_signals, tier3_signals, prices, dates)

    print(f"\nRisk Management Results:")
    print(f"  Tier 2 Max Drawdown: {result.tier2_metrics.max_drawdown:.2f}%")
    print(f"  Tier 3 Max Drawdown: {result.tier3_metrics.max_drawdown:.2f}%")
    print(f"  Tier 2 Volatility: {result.tier2_metrics.volatility:.2f}%")
    print(f"  Tier 3 Volatility: {result.tier3_metrics.volatility:.2f}%")
    print(f"  Tier 2 Transaction Costs: ${result.tier2_execution.transaction_costs:.4f}")
    print(f"  Tier 3 Transaction Costs: ${result.tier3_execution.transaction_costs:.4f}")

    return result


def example_5_data_quality_checks():
    """Example 5: Data quality and edge case handling."""
    print("\n" + "=" * 80)
    print("Example 5: Data Quality Checks")
    print("=" * 80)

    config = BacktestConfig()
    engine = BacktestEngine(config)

    dates, prices, _ = engine.load_historical_data('SPY', '2024-01-01', '2024-02-01')

    print(f"\nOriginal Data:")
    print(f"  Number of days: {len(dates)}")
    print(f"  Price range: ${min(prices):.2f} - ${max(prices):.2f}")

    # Check for data gaps
    cleaned_dates, cleaned_prices = engine.handle_data_gaps(dates, prices)
    print(f"\nAfter Gap Handling:")
    print(f"  Number of days: {len(cleaned_dates)}")

    # Adjust for survivorship bias
    adjusted_prices = engine.adjust_for_survivorship_bias(prices, dates)
    print(f"\nAfter Survivorship Bias Adjustment:")
    print(f"  First price: ${prices[0]:.2f}")
    print(f"  Last price (original): ${prices[-1]:.2f}")
    print(f"  Last price (adjusted): ${adjusted_prices[-1]:.2f}")

    # Run backtest with cleaned data
    signals = [1] * len(cleaned_prices)
    result = engine.run_backtest(signals, signals, cleaned_prices, cleaned_dates)

    # Validate integrity
    checks = engine.validate_backtest_integrity(result)
    print(f"\nBacktest Integrity Checks:")
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")

    return result


def main():
    """Run all examples."""
    try:
        # Run examples
        result1 = example_1_simple_comparison()
        result2 = example_2_full_report_generation()
        result3 = example_3_statistical_significance()
        result4 = example_4_risk_management()
        result5 = example_5_data_quality_checks()

        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
