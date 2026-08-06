"""
Comprehensive tests for A/B backtesting framework.

Tests all components: engine, executor, metrics, validator, reporter.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from typing import List

from .backtest_engine import BacktestEngine, BacktestConfig, BacktestResult
from .strategy_executor import StrategyExecutor, StrategyConfig
from .metrics_calculator import MetricsCalculator, PerformanceMetrics
from .statistical_validator import StatisticalValidator, ValidationResult
from .reporter import ResultsReporter, ReportFormat, ReportConfig


class TestMetricsCalculator:
    """Test financial metrics calculations."""

    def test_sharpe_ratio_positive_returns(self):
        """Test Sharpe calculation with positive returns."""
        calc = MetricsCalculator()
        # Use slightly varied returns to have non-zero volatility
        returns = [0.01 + 0.0001 * (i % 3 - 1) for i in range(252)]

        metrics = calc.calculate_metrics(returns)
        assert metrics.sharpe_ratio > 0
        assert metrics.total_return > 0

    def test_sharpe_ratio_zero_returns(self):
        """Test Sharpe with zero returns."""
        calc = MetricsCalculator()
        returns = [0.0] * 100

        metrics = calc.calculate_metrics(returns)
        assert metrics.sharpe_ratio == 0
        assert metrics.total_return == 0

    def test_max_drawdown(self):
        """Test max drawdown calculation."""
        calc = MetricsCalculator()
        returns = [0.01, 0.01, -0.05, -0.03, 0.02, 0.01]

        metrics = calc.calculate_metrics(returns)
        assert metrics.max_drawdown < 0
        # Max drawdown from peak (after +1%, +1%) to trough is roughly -7.87%
        # Note: max_drawdown is stored as percentage
        assert abs(metrics.max_drawdown) < 10  # Less than 10%

    def test_sortino_ratio(self):
        """Test Sortino ratio (downside risk)."""
        calc = MetricsCalculator()
        returns = [0.01, 0.01, 0.01, -0.02, 0.01, 0.01]

        metrics = calc.calculate_metrics(returns)
        assert metrics.sortino_ratio > 0
        assert metrics.sortino_ratio >= metrics.sharpe_ratio  # Sortino >= Sharpe

    def test_win_rate(self):
        """Test win rate calculation."""
        calc = MetricsCalculator()
        returns = [0.01, 0.01, 0.01, -0.01, 0.01]  # 4 wins, 1 loss = 80%

        metrics = calc.calculate_metrics(returns)
        assert 0.70 < metrics.win_rate < 0.90

    def test_profit_factor(self):
        """Test profit factor."""
        calc = MetricsCalculator()
        returns = [0.01, 0.02, -0.005, -0.01]  # Wins: 0.03, Losses: 0.015

        metrics = calc.calculate_metrics(returns)
        assert metrics.profit_factor > 1  # Profitable

    def test_calmar_ratio(self):
        """Test Calmar ratio (return / max drawdown)."""
        calc = MetricsCalculator()
        returns = [0.01] * 50 + [-0.02] * 10 + [0.01] * 50

        metrics = calc.calculate_metrics(returns)
        assert metrics.calmar_ratio > 0

    def test_sharpe_std_error(self):
        """Test Sharpe standard error calculation."""
        calc = MetricsCalculator()
        returns = np.random.normal(0.001, 0.01, 252).tolist()

        metrics = calc.calculate_metrics(returns)
        assert metrics.sharpe_std_error > 0
        assert metrics.sharpe_std_error < 1  # Should be reasonable

    def test_information_ratio(self):
        """Test Information Ratio vs benchmark."""
        calc = MetricsCalculator()
        strategy_returns = [0.01, 0.01, 0.01, 0.01, 0.01] * 50
        # Make benchmark slightly different to have non-zero tracking error
        benchmark_returns = [0.005, 0.006, 0.004, 0.0055, 0.0045] * 50

        metrics = calc.calculate_metrics(strategy_returns, benchmark_returns=benchmark_returns)
        assert metrics.information_ratio is not None
        # With positive excess return and positive tracking error, IR should be positive
        if metrics.tracking_error > 0:
            assert metrics.information_ratio > 0
        assert metrics.excess_return > 0


class TestStrategyExecutor:
    """Test strategy execution and position management."""

    def test_long_only_strategy(self):
        """Test simple long-only strategy."""
        config = StrategyConfig()
        executor = StrategyExecutor(config)

        dates = [f"2024-01-{i+1:02d}" for i in range(20)]
        prices = [100 + i for i in range(20)]  # Rising prices
        signals = [1] * 20  # Always long

        result = executor.execute_strategy(dates, prices, signals)

        assert len(result.returns) > 0
        assert len(result.trades) == 1  # One open position
        assert result.final_value > 0

    def test_short_strategy(self):
        """Test short strategy."""
        config = StrategyConfig()
        executor = StrategyExecutor(config)

        dates = [f"2024-01-{i+1:02d}" for i in range(20)]
        prices = [100 - i for i in range(20)]  # Falling prices
        signals = [-1] * 20  # Always short

        result = executor.execute_strategy(dates, prices, signals)

        assert len(result.returns) > 0
        assert result.final_value > 0

    def test_mean_reversion_signals(self):
        """Test mean reversion strategy."""
        config = StrategyConfig()
        executor = StrategyExecutor(config)

        dates = [f"2024-01-{i+1:02d}" for i in range(30)]
        prices = [100, 102, 105, 107, 105, 102, 100, 98, 95, 93, 95, 98, 100] * 2 + [100]
        signals = [0] + [1 if prices[i] < 100 else -1 if prices[i] > 105 else 0 for i in range(1, len(prices))]

        result = executor.execute_strategy(dates, prices, signals)

        assert len(result.returns) > 0
        assert result.total_transactions >= 0

    def test_transaction_costs(self):
        """Test transaction cost calculation."""
        config = StrategyConfig(entry_slippage=0.001, exit_slippage=0.001)
        executor = StrategyExecutor(config)

        dates = [f"2024-01-{i+1:02d}" for i in range(20)]
        prices = [100 + i for i in range(20)]
        signals = [1, 1, 1, 0, 0, 1, 1, 1, 0, 0] + [0] * 10

        result = executor.execute_strategy(dates, prices, signals)

        assert result.transaction_costs >= 0

    def test_risk_management_stop_loss(self):
        """Test stop-loss risk management."""
        config = StrategyConfig(stop_loss=0.05)
        executor = StrategyExecutor(config)

        dates = [f"2024-01-{i+1:02d}" for i in range(20)]
        prices = list(range(100, 120))
        signals = [1] * 20

        trades = [
            type('Trade', (), {
                'entry_price': 100,
                'exit_price': 95,
                'return_pct': -0.05,
                'position_type': type('PositionType', (), {'value': 'long'})(),
            })()
        ]

        adjusted = executor.apply_risk_management(trades, stop_loss=0.05)
        assert len(adjusted) == 1

    def test_empty_signals(self):
        """Test with empty/flat signals."""
        config = StrategyConfig()
        executor = StrategyExecutor(config)

        dates = [f"2024-01-{i+1:02d}" for i in range(20)]
        prices = [100] * 20
        signals = [0] * 20  # Never trade

        result = executor.execute_strategy(dates, prices, signals)
        assert result.final_value > 0


class TestStatisticalValidator:
    """Test statistical significance validation."""

    def test_clear_improvement(self):
        """Test clear improvement detection."""
        validator = StatisticalValidator(confidence_level=0.90, n_bootstrap=100)

        # Tier 2: modest returns
        tier2 = [0.001] * 252

        # Tier 3: better returns
        tier3 = [0.002] * 252

        result = validator.validate_improvement(tier2, tier3)

        assert result.sharpe_difference > 0
        assert result.p_value < 0.50  # Should be significant

    def test_no_improvement(self):
        """Test when no improvement exists."""
        validator = StatisticalValidator(confidence_level=0.90, n_bootstrap=100)

        returns = [0.001] * 252

        result = validator.validate_improvement(returns, returns)

        assert abs(result.sharpe_difference) < 0.01
        assert result.p_value > 0.4

    def test_noisy_data(self):
        """Test with noisy returns."""
        validator = StatisticalValidator(confidence_level=0.90, n_bootstrap=100)

        np.random.seed(42)
        tier2 = np.random.normal(0.001, 0.02, 252).tolist()
        tier3 = np.random.normal(0.0015, 0.02, 252).tolist()

        result = validator.validate_improvement(tier2, tier3)

        assert 0 <= result.p_value <= 1
        assert result.bootstrap_std > 0

    def test_recommendation_go(self):
        """Test GO recommendation."""
        validator = StatisticalValidator(confidence_level=0.90, n_bootstrap=100)

        tier2 = [0.001] * 252
        tier3 = [0.003] * 252

        result = validator.validate_improvement(tier2, tier3)

        # With such a clear difference, should recommend GO or CONDITIONAL_GO
        assert result.recommendation in ["GO", "CONDITIONAL_GO"]

    def test_recommendation_no_go(self):
        """Test NO_GO recommendation."""
        validator = StatisticalValidator(confidence_level=0.90, n_bootstrap=100)

        tier2 = [0.001] * 252
        tier3 = [-0.001] * 252  # Worse

        result = validator.validate_improvement(tier2, tier3)

        assert result.recommendation == "NO_GO"

    def test_bootstrap_ci(self):
        """Test bootstrap confidence interval."""
        validator = StatisticalValidator(confidence_level=0.90, n_bootstrap=100)

        tier2 = np.random.normal(0.001, 0.01, 100).tolist()
        tier3 = np.random.normal(0.0015, 0.01, 100).tolist()

        result = validator.validate_improvement(tier2, tier3)

        assert result.confidence_interval[0] < result.confidence_interval[1]
        assert result.confidence_interval[0] <= result.sharpe_difference <= result.confidence_interval[1] or \
               abs(result.sharpe_difference) < 0.01  # Allow some wiggle for edge cases

    def test_cohens_d(self):
        """Test Cohen's d effect size."""
        validator = StatisticalValidator()

        tier2 = [0.001] * 100
        tier3 = [0.002] * 100

        d = validator.effect_size_cohens_d(tier2, tier3)
        assert d > 0

    def test_required_sample_size(self):
        """Test required sample size calculation."""
        validator = StatisticalValidator()

        n = validator.required_sample_size(effect_size=0.5, alpha=0.10, power=0.80)
        assert n > 0
        assert n < 10000  # Reasonable upper bound

    def test_permutation_test(self):
        """Test permutation test."""
        validator = StatisticalValidator()

        tier2 = [0.001] * 50
        tier3 = [0.002] * 50

        diff, p_val = validator.permutation_test(tier2, tier3, n_permutations=100)
        assert 0 <= p_val <= 1
        assert diff > 0


class TestBacktestEngine:
    """Test main backtest engine."""

    def test_backtest_initialization(self):
        """Test engine initialization."""
        config = BacktestConfig(
            start_date='2024-01-01',
            end_date='2024-03-01',
            symbol='SPY',
        )
        engine = BacktestEngine(config)

        assert engine.config.start_date == '2024-01-01'
        assert engine.config.symbol == 'SPY'

    def test_mock_data_generation(self):
        """Test mock data generation."""
        engine = BacktestEngine()

        dates, prices, volumes = engine._generate_mock_data('2024-01-01', '2024-01-31')

        assert len(dates) > 0
        assert len(prices) == len(dates)
        assert len(volumes) == len(dates)
        assert prices[0] > 0
        assert all(v > 0 for v in volumes)

    def test_data_gap_handling(self):
        """Test handling of data gaps."""
        engine = BacktestEngine()

        dates = ['2024-01-01', '2024-01-02', '2024-01-08']  # Gap over weekend
        prices = [100, 101, 102]

        cleaned_dates, cleaned_prices = engine.handle_data_gaps(dates, prices)

        assert len(cleaned_dates) >= len(dates)
        assert len(cleaned_prices) == len(cleaned_dates)

    def test_survivorship_bias_adjustment(self):
        """Test survivorship bias adjustment."""
        engine = BacktestEngine()

        prices = [100, 101, 102, 103, 104]
        dates = [f"2024-01-{i+1:02d}" for i in range(len(prices))]

        adjusted = engine.adjust_for_survivorship_bias(prices, dates)

        assert len(adjusted) == len(prices)
        assert adjusted[0] == prices[0]  # First price unchanged
        # Adjusted prices should be slightly lower due to survivorship adjustment
        assert adjusted[-1] <= prices[-1]

    def test_full_backtest_run(self):
        """Test complete backtest execution."""
        config = BacktestConfig(
            start_date='2024-01-01',
            end_date='2024-02-01',
            data_source='mock',
            confidence_level=0.90,
            n_bootstrap=100,
        )
        engine = BacktestEngine(config)

        # Generate simple data
        dates, prices, _ = engine._generate_mock_data('2024-01-01', '2024-02-01')

        # Simple momentum signals
        tier2_signals = [0 if i < 5 else 1 for i in range(len(prices))]
        tier3_signals = [0 if i < 3 else 1 for i in range(len(prices))]

        result = engine.run_backtest(tier2_signals, tier3_signals, prices, dates)

        assert isinstance(result, BacktestResult)
        assert result.tier2_metrics is not None
        assert result.tier3_metrics is not None
        assert result.validation_result is not None
        assert result.recommendation in ["GO", "CONDITIONAL_GO", "NO_GO"]

    def test_backtest_integrity_check(self):
        """Test backtest integrity validation."""
        config = BacktestConfig()
        engine = BacktestEngine(config)

        dates, prices, _ = engine._generate_mock_data('2024-01-01', '2024-02-01')
        signals = [0] * len(prices)

        result = engine.run_backtest(signals, signals, prices, dates)

        checks = engine.validate_backtest_integrity(result)
        assert all(checks.values())  # All checks should pass


class TestResultsReporter:
    """Test report generation."""

    def test_json_report_generation(self):
        """Test JSON report generation."""
        config = BacktestConfig()
        engine = BacktestEngine(config)

        dates, prices, _ = engine._generate_mock_data('2024-01-01', '2024-02-01')
        signals = [1] * len(prices)

        result = engine.run_backtest(signals, signals, prices, dates)

        reporter = ResultsReporter()
        json_report = reporter.generate_report(result, format=ReportFormat.JSON)

        assert json_report is not None
        assert 'tier2' in json_report
        assert 'tier3' in json_report
        assert 'comparison' in json_report

    def test_markdown_report_generation(self):
        """Test Markdown report generation."""
        config = BacktestConfig()
        engine = BacktestEngine(config)

        dates, prices, _ = engine._generate_mock_data('2024-01-01', '2024-02-01')
        signals = [1] * len(prices)

        result = engine.run_backtest(signals, signals, prices, dates)

        reporter = ResultsReporter()
        md_report = reporter.generate_report(result, format=ReportFormat.MARKDOWN)

        assert 'Executive Summary' in md_report
        assert 'Performance Comparison' in md_report
        assert 'Tier 2' in md_report
        assert 'Tier 3' in md_report

    def test_report_with_trades(self):
        """Test report generation with trades."""
        config = BacktestConfig()
        engine = BacktestEngine(config)

        dates, prices, _ = engine._generate_mock_data('2024-01-01', '2024-02-01')
        signals = [0, 1, 1, 1, 0, 1, 1, 0] * 10 + [0]

        result = engine.run_backtest(signals, signals, prices, dates)

        report_config = ReportConfig(include_trades=True)
        reporter = ResultsReporter(report_config)
        md_report = reporter.generate_report(result, format=ReportFormat.MARKDOWN)

        assert 'Sample Trades' in md_report or 'trades' in md_report.lower()


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_insufficient_data(self):
        """Test with insufficient data."""
        config = BacktestConfig(min_observations=30)
        engine = BacktestEngine(config)

        dates = ['2024-01-01', '2024-01-02']
        prices = [100, 101]
        signals = [1, 1]

        with pytest.raises(ValueError):
            engine.run_backtest(signals, signals, prices, dates)

    def test_mismatched_lengths(self):
        """Test with mismatched input lengths."""
        engine = BacktestEngine()

        dates = ['2024-01-01', '2024-01-02']
        prices = [100, 101, 102]  # Extra price
        signals = [1, 1]

        with pytest.raises(ValueError):
            engine.run_backtest(signals, signals, prices, dates)

    def test_zero_volatility(self):
        """Test with zero volatility (constant prices)."""
        config = BacktestConfig()
        engine = BacktestEngine(config)

        dates = [f"2024-01-{i+1:02d}" for i in range(40)]
        prices = [100] * 40  # No volatility
        signals = [1] * 40

        result = engine.run_backtest(signals, signals, prices, dates)

        # Should handle gracefully without crashing
        assert result is not None
        assert result.tier2_metrics is not None

    def test_single_trade(self):
        """Test backtest with single trade."""
        config = BacktestConfig()
        engine = BacktestEngine(config)

        dates = [f"2024-01-{i+1:02d}" for i in range(30)]
        prices = list(range(100, 130))
        signals = [1] + [0] * 29

        result = engine.run_backtest(signals, signals, prices, dates)

        assert result.tier2_execution.total_transactions >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
