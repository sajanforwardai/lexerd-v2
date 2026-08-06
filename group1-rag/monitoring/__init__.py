"""
Group One Trading RAG - Phase 3: P&L Tracking & Regime Shift Detection

Complete monitoring system for real-time market surveillance:
- PnL tracking and aggregation by strategy/instrument/regime
- Backtest vs live performance comparison
- Regime shift detection via eigenvalue decomposition
- Volatility spike detection and characterization
- Correlation breakdown detection
- Failure mode tracking and pattern matching
"""

from pnl_tracker import (
    PnLTracker,
    TradeExecution,
    DailyPnLSummary,
    GreeksSnapshot,
    GreeksAggregate,
    Regime,
)

from backtest_comparison import (
    BacktestComparator,
    BacktestBaseline,
    LivePerformance,
    BacktestComparison,
    VarianceDriver,
)

from regime_shift_detector import (
    RegimeShiftDetector,
    MarketSnapshot,
    RegimeState,
    RegimeShiftAlert,
)

from vol_spike_detector import (
    VolatilitySpikeDetector,
    VolatilitySnapshot,
    VolatilitySpike,
    VolatilityBaselineCalculator,
)

from correlation_detector import (
    CorrelationDetector,
    CorrelationSnapshot,
    CorrelationMetrics,
    CorrelationBreakdown,
    CorrelationBaselineCalculator,
)

from failure_mode_tracker import (
    FailureModeTracker,
    FailureEvent,
    FailureMode,
    FailureCategory,
    FailureSeverity,
    WeeklyFailureSummary,
    MonthlyFailureAnalysis,
)

__all__ = [
    # PnL Tracking
    "PnLTracker",
    "TradeExecution",
    "DailyPnLSummary",
    "GreeksSnapshot",
    "GreeksAggregate",
    "Regime",
    # Backtest Comparison
    "BacktestComparator",
    "BacktestBaseline",
    "LivePerformance",
    "BacktestComparison",
    "VarianceDriver",
    # Regime Shift Detection
    "RegimeShiftDetector",
    "MarketSnapshot",
    "RegimeState",
    "RegimeShiftAlert",
    # Volatility Spike Detection
    "VolatilitySpikeDetector",
    "VolatilitySnapshot",
    "VolatilitySpike",
    "VolatilityBaselineCalculator",
    # Correlation Detection
    "CorrelationDetector",
    "CorrelationSnapshot",
    "CorrelationMetrics",
    "CorrelationBreakdown",
    "CorrelationBaselineCalculator",
    # Failure Tracking
    "FailureModeTracker",
    "FailureEvent",
    "FailureMode",
    "FailureCategory",
    "FailureSeverity",
    "WeeklyFailureSummary",
    "MonthlyFailureAnalysis",
]

__version__ = "1.0.0"
__description__ = "Group One Trading RAG Phase 3: P&L Tracking & Regime Shift Detection"
