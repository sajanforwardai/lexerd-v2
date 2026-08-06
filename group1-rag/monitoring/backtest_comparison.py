"""
Backtest vs Live Comparison Engine

Compares backtest predictions (A/B testing baseline) against live trading P&L.
Detects when live performance diverges >10% from backtest expectations.

Analyzes variance sources:
- Slippage and execution quality
- Regime shifts during live trading
- Leverage changes
- Strategy parameter drift
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class BacktestBaseline:
    """Expected performance from backtest."""
    strategy_name: str
    expected_sharpe_ratio: float
    expected_annual_return: float
    expected_max_drawdown: float
    expected_volatility: float
    expected_win_rate: float
    expected_profit_factor: float
    backtest_period: Tuple[str, str]  # (start_date, end_date)


@dataclass
class LivePerformance:
    """Actual live trading performance."""
    strategy_name: str
    actual_sharpe_ratio: float
    actual_return: float  # YTD or period return
    actual_max_drawdown: float
    actual_volatility: float
    actual_win_rate: float
    actual_profit_factor: float
    live_period: Tuple[str, str]
    n_trades: int


@dataclass
class VarianceDriver:
    """Individual variance driver analysis."""
    driver_name: str  # "slippage", "execution_quality", "regime_shift", "leverage_change"
    impact_bps: float  # Basis points impact
    direction: str  # "positive" or "negative"
    confidence: float  # 0-1 confidence in attribution
    description: str


@dataclass
class BacktestComparison:
    """Complete backtest vs live comparison."""
    timestamp: datetime
    strategy_name: str
    backtest_baseline: BacktestBaseline
    live_performance: LivePerformance

    # Variance metrics
    sharpe_variance: float  # Actual - Expected
    sharpe_variance_pct: float  # % difference
    return_variance: float
    return_variance_pct: float
    drawdown_variance: float
    volatility_variance: float
    win_rate_variance: float

    # Analysis
    variance_magnitude: str  # "tiny" (<2%), "small" (2-5%), "moderate" (5-10%), "large" (10-25%), "extreme" (>25%)
    divergence_alert: bool  # True if >10% divergence detected
    variance_drivers: List[VarianceDriver] = field(default_factory=list)

    # Recommendations
    escalation_required: bool = False
    recommendation: str = "MONITOR"  # "MONITOR", "INVESTIGATE", "PAUSE_NEW_TRADES"


class BacktestComparator:
    """Compare backtest predictions to live trading outcomes."""

    # Threshold for divergence alert (% difference)
    DIVERGENCE_THRESHOLD_PCT = 10.0

    # Variance magnitude buckets
    VARIANCE_THRESHOLDS = {
        "tiny": 2.0,
        "small": 5.0,
        "moderate": 10.0,
        "large": 25.0,
    }

    def __init__(self):
        """Initialize comparator."""
        self.comparisons: List[BacktestComparison] = []

    def compare(
        self,
        backtest_baseline: BacktestBaseline,
        live_performance: LivePerformance,
    ) -> BacktestComparison:
        """Compare backtest baseline to live performance.

        Args:
            backtest_baseline: Expected performance from backtest
            live_performance: Actual live trading performance

        Returns:
            BacktestComparison with variance analysis
        """
        # Calculate variances
        sharpe_variance = live_performance.actual_sharpe_ratio - backtest_baseline.expected_sharpe_ratio
        sharpe_variance_pct = (
            (sharpe_variance / backtest_baseline.expected_sharpe_ratio * 100)
            if backtest_baseline.expected_sharpe_ratio != 0 else 0
        )

        return_variance = live_performance.actual_return - backtest_baseline.expected_annual_return
        return_variance_pct = (
            (return_variance / abs(backtest_baseline.expected_annual_return) * 100)
            if backtest_baseline.expected_annual_return != 0 else 0
        )

        drawdown_variance = live_performance.actual_max_drawdown - backtest_baseline.expected_max_drawdown
        volatility_variance = live_performance.actual_volatility - backtest_baseline.expected_volatility
        win_rate_variance = live_performance.actual_win_rate - backtest_baseline.expected_win_rate

        # Determine variance magnitude
        avg_variance_pct = abs((sharpe_variance_pct + return_variance_pct) / 2)
        variance_magnitude = self._classify_variance(avg_variance_pct)

        # Check divergence alert
        divergence_alert = abs(return_variance_pct) > self.DIVERGENCE_THRESHOLD_PCT

        comparison = BacktestComparison(
            timestamp=datetime.utcnow(),
            strategy_name=backtest_baseline.strategy_name,
            backtest_baseline=backtest_baseline,
            live_performance=live_performance,
            sharpe_variance=sharpe_variance,
            sharpe_variance_pct=sharpe_variance_pct,
            return_variance=return_variance,
            return_variance_pct=return_variance_pct,
            drawdown_variance=drawdown_variance,
            volatility_variance=volatility_variance,
            win_rate_variance=win_rate_variance,
            variance_magnitude=variance_magnitude,
            divergence_alert=divergence_alert,
        )

        # Analyze variance drivers
        comparison.variance_drivers = self._analyze_drivers(
            backtest_baseline,
            live_performance,
            return_variance_pct
        )

        # Determine recommendation
        comparison.recommendation = self._recommend_action(comparison)
        comparison.escalation_required = divergence_alert

        self.comparisons.append(comparison)

        if divergence_alert:
            logger.warning(
                f"DIVERGENCE ALERT: {backtest_baseline.strategy_name} "
                f"live return {live_performance.actual_return:.2%} vs backtest "
                f"{backtest_baseline.expected_annual_return:.2%} (diff: {return_variance_pct:.1f}%)"
            )

        return comparison

    def _classify_variance(self, variance_pct: float) -> str:
        """Classify variance magnitude.

        Args:
            variance_pct: Absolute variance percentage

        Returns:
            Variance classification
        """
        variance_abs = abs(variance_pct)
        if variance_abs < self.VARIANCE_THRESHOLDS["tiny"]:
            return "tiny"
        elif variance_abs < self.VARIANCE_THRESHOLDS["small"]:
            return "small"
        elif variance_abs < self.VARIANCE_THRESHOLDS["moderate"]:
            return "moderate"
        elif variance_abs < self.VARIANCE_THRESHOLDS["large"]:
            return "large"
        else:
            return "extreme"

    def _analyze_drivers(
        self,
        backtest: BacktestBaseline,
        live: LivePerformance,
        return_variance_pct: float,
    ) -> List[VarianceDriver]:
        """Analyze potential drivers of variance.

        Args:
            backtest: Backtest baseline
            live: Live performance
            return_variance_pct: Overall return variance %

        Returns:
            List of VarianceDriver with attributions
        """
        drivers = []

        # 1. Volatility regime shift
        vol_variance = live.actual_volatility - backtest.expected_volatility
        if abs(vol_variance) > 0.02:  # >2% volatility change
            drivers.append(VarianceDriver(
                driver_name="volatility_regime",
                impact_bps=abs(vol_variance) * 10000,
                direction="positive" if vol_variance < 0 else "negative",
                confidence=0.7,
                description=f"Realized vol {live.actual_volatility:.2%} vs backtest {backtest.expected_volatility:.2%}",
            ))

        # 2. Win rate degradation
        win_rate_variance = live.actual_win_rate - backtest.expected_win_rate
        if abs(win_rate_variance) > 0.05:  # >5% win rate change
            drivers.append(VarianceDriver(
                driver_name="execution_quality",
                impact_bps=abs(win_rate_variance) * 10000,
                direction="positive" if win_rate_variance > 0 else "negative",
                confidence=0.6,
                description=f"Live win rate {live.actual_win_rate:.1%} vs backtest {backtest.expected_win_rate:.1%}",
            ))

        # 3. Drawdown impact
        dd_variance = live.actual_max_drawdown - backtest.expected_max_drawdown
        if abs(dd_variance) > 0.03:  # >3% drawdown change
            drivers.append(VarianceDriver(
                driver_name="drawdown_impact",
                impact_bps=abs(dd_variance) * 10000,
                direction="positive" if dd_variance < 0 else "negative",
                confidence=0.65,
                description=f"Live max DD {abs(live.actual_max_drawdown):.2%} vs backtest {abs(backtest.expected_max_drawdown):.2%}",
            ))

        # 4. Profit factor degradation
        pf_variance = live.actual_profit_factor - backtest.expected_profit_factor
        if abs(pf_variance) > 0.2:  # >0.2 profit factor change
            drivers.append(VarianceDriver(
                driver_name="profit_factor",
                impact_bps=abs(pf_variance) * 100,
                direction="positive" if pf_variance > 0 else "negative",
                confidence=0.55,
                description=f"Live PF {live.actual_profit_factor:.2f} vs backtest {backtest.expected_profit_factor:.2f}",
            ))

        # Sort by confidence and impact
        drivers.sort(key=lambda x: x.confidence * abs(x.impact_bps), reverse=True)

        return drivers

    def _recommend_action(self, comparison: BacktestComparison) -> str:
        """Recommend action based on divergence analysis.

        Args:
            comparison: BacktestComparison result

        Returns:
            Recommendation string
        """
        if not comparison.divergence_alert:
            return "MONITOR"

        if abs(comparison.return_variance_pct) > 15.0:
            return "PAUSE_NEW_TRADES"
        elif abs(comparison.return_variance_pct) > 12.0:
            return "INVESTIGATE"
        else:
            return "INVESTIGATE"

    def get_comparison_report(self, strategy_name: str, n_recent: int = 10) -> Dict:
        """Get recent comparison reports for a strategy.

        Args:
            strategy_name: Strategy to query
            n_recent: Number of recent comparisons to include

        Returns:
            Dict with comparison analysis
        """
        strategy_comparisons = [
            c for c in self.comparisons
            if c.strategy_name == strategy_name
        ][-n_recent:]

        if not strategy_comparisons:
            return {"strategy": strategy_name, "comparisons": []}

        # Calculate trend
        recent = strategy_comparisons[-1]
        return {
            "strategy": strategy_name,
            "latest_comparison": {
                "timestamp": recent.timestamp.isoformat(),
                "sharpe_variance_pct": recent.sharpe_variance_pct,
                "return_variance_pct": recent.return_variance_pct,
                "variance_magnitude": recent.variance_magnitude,
                "divergence_alert": recent.divergence_alert,
                "recommendation": recent.recommendation,
                "top_drivers": [
                    {
                        "name": d.driver_name,
                        "impact_bps": d.impact_bps,
                        "direction": d.direction,
                        "confidence": d.confidence,
                    }
                    for d in recent.variance_drivers[:3]
                ],
            },
            "comparison_history": [
                {
                    "timestamp": c.timestamp.isoformat(),
                    "return_variance_pct": c.return_variance_pct,
                    "variance_magnitude": c.variance_magnitude,
                }
                for c in strategy_comparisons
            ],
        }

    def alert_divergence(self, comparison: BacktestComparison) -> Optional[Dict]:
        """Generate alert if divergence detected.

        Args:
            comparison: BacktestComparison to check

        Returns:
            Alert dict if divergence, else None
        """
        if not comparison.divergence_alert:
            return None

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "alert_type": "DIVERGENCE",
            "severity": "CRITICAL" if abs(comparison.return_variance_pct) > 15 else "WARNING",
            "strategy": comparison.strategy_name,
            "message": (
                f"{comparison.strategy_name}: Live return {comparison.live_performance.actual_return:.2%} "
                f"diverges {abs(comparison.return_variance_pct):.1f}% from backtest "
                f"{comparison.backtest_baseline.expected_annual_return:.2%}"
            ),
            "return_variance_pct": comparison.return_variance_pct,
            "variance_magnitude": comparison.variance_magnitude,
            "recommendation": comparison.recommendation,
            "top_drivers": [
                {
                    "name": d.driver_name,
                    "impact_bps": d.impact_bps,
                    "direction": d.direction,
                }
                for d in comparison.variance_drivers[:3]
            ],
        }
