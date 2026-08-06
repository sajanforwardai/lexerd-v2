"""
A/B Backtesting Framework for Phase 2 Validation.

Tier 3 candidate vs Tier 2 baseline comparison with statistical significance testing.
"""

from .backtest_engine import BacktestEngine, BacktestConfig, BacktestResult
from .strategy_executor import StrategyExecutor, StrategyConfig, ExecutionResult
from .metrics_calculator import MetricsCalculator, PerformanceMetrics
from .statistical_validator import StatisticalValidator, ValidationResult
from .reporter import ResultsReporter, ReportFormat

__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "StrategyExecutor",
    "StrategyConfig",
    "ExecutionResult",
    "MetricsCalculator",
    "PerformanceMetrics",
    "StatisticalValidator",
    "ValidationResult",
    "ResultsReporter",
    "ReportFormat",
]
