"""
Correlation Breakdown Detector

Monitors pairwise correlation matrices between strategies.
Baseline: 252-day rolling correlation
Trigger: condition number >10 or >2x increase = breakdown detected
Action: reduce cross-correlated position sizes via safety limits
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import deque
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class CorrelationSnapshot:
    """Correlation matrix snapshot."""
    timestamp: datetime
    strategies: List[str]
    correlation_matrix: np.ndarray  # NxN correlation matrix
    period_days: int = 252


@dataclass
class CorrelationMetrics:
    """Computed correlation metrics."""
    timestamp: datetime
    condition_number: float
    max_correlation: float
    avg_correlation: float
    principal_eigenvalue: float  # Largest eigenvalue
    eigenvalue_ratio: float  # Ratio of first to last eigenvalue


@dataclass
class CorrelationBreakdown:
    """Detected correlation breakdown event."""
    timestamp: datetime
    condition_number: float
    prev_condition_number: Optional[float]
    condition_number_change: float  # Ratio of current to previous
    strategy_pairs: List[Tuple[str, str, float]] = field(default_factory=list)  # (s1, s2, correlation)
    severity: str = "WARNING"  # "INFO", "WARNING", "CRITICAL"
    recommended_actions: List[str] = field(default_factory=list)


class CorrelationBaselineCalculator:
    """Maintain rolling correlation baseline."""

    def __init__(self, window_days: int = 252):
        """Initialize baseline calculator.

        Args:
            window_days: Rolling window for baseline (252 = 1 year)
        """
        self.window_days = window_days
        self.returns_history: Dict[str, deque] = {}  # strategy -> deque of daily returns

    def update(self, strategy: str, daily_return: float) -> None:
        """Update returns history for a strategy.

        Args:
            strategy: Strategy identifier
            daily_return: Daily return for this strategy
        """
        if strategy not in self.returns_history:
            self.returns_history[strategy] = deque(maxlen=self.window_days)

        self.returns_history[strategy].append(daily_return)

    def get_correlation_matrix(self, strategies: List[str]) -> Optional[np.ndarray]:
        """Compute correlation matrix for given strategies.

        Args:
            strategies: List of strategy identifiers

        Returns:
            NxN correlation matrix or None if insufficient data
        """
        # Check all strategies have data
        if not all(s in self.returns_history for s in strategies):
            return None

        # Find common length (minimum data available)
        min_length = min(len(self.returns_history[s]) for s in strategies)
        if min_length < 30:  # Need at least 30 data points
            return None

        # Build returns array: NxT (N strategies, T observations)
        returns_list = []
        for strategy in strategies:
            returns = np.array(list(self.returns_history[strategy]))[-min_length:]
            returns_list.append(returns)

        returns_matrix = np.array(returns_list)

        # Compute correlation
        corr_matrix = np.corrcoef(returns_matrix)
        return corr_matrix


class CorrelationDetector:
    """Detect correlation breakdowns and hedging failures."""

    # Condition number thresholds
    NORMAL_CONDITION_THRESHOLD = 5.0  # Normal market
    ELEVATED_CONDITION_THRESHOLD = 10.0  # Some correlation
    BREAKDOWN_CONDITION_THRESHOLD = 20.0  # Significant breakdown
    EXTREME_CONDITION_THRESHOLD = 50.0  # Extreme stress

    # Change detection
    CONDITION_NUMBER_CHANGE_THRESHOLD = 2.0  # 2x jump = breakdown

    def __init__(self):
        """Initialize correlation detector."""
        self.baseline_calc = CorrelationBaselineCalculator()
        self.metrics_history: List[CorrelationMetrics] = []
        self.breakdowns: List[CorrelationBreakdown] = []
        self.current_metrics: Optional[CorrelationMetrics] = None

    def update(
        self,
        snapshot: CorrelationSnapshot,
        strategies: List[str],
    ) -> Optional[CorrelationBreakdown]:
        """Process correlation snapshot and detect breakdowns.

        Args:
            snapshot: CorrelationSnapshot with current correlation matrix
            strategies: List of strategies being monitored

        Returns:
            CorrelationBreakdown if detected, else None
        """
        # Compute metrics
        metrics = self._compute_metrics(snapshot, strategies)
        self.metrics_history.append(metrics)

        # Detect breakdown
        breakdown = None
        if self.current_metrics:
            breakdown = self._detect_breakdown(self.current_metrics, metrics)
            if breakdown:
                self.breakdowns.append(breakdown)
                logger.warning(
                    f"CORRELATION BREAKDOWN: CN {self.current_metrics.condition_number:.1f} -> "
                    f"{metrics.condition_number:.1f} ({breakdown.condition_number_change:.1f}x)"
                )

        # Check absolute levels
        if metrics.condition_number > self.BREAKDOWN_CONDITION_THRESHOLD:
            if not breakdown or breakdown.severity != "CRITICAL":
                breakdown = CorrelationBreakdown(
                    timestamp=metrics.timestamp,
                    condition_number=metrics.condition_number,
                    prev_condition_number=(
                        self.current_metrics.condition_number
                        if self.current_metrics else None
                    ),
                    condition_number_change=(
                        metrics.condition_number / (self.current_metrics.condition_number or 1.0)
                        if self.current_metrics else 0.0
                    ),
                    severity="CRITICAL",
                )
                self.breakdowns.append(breakdown)
                logger.critical(f"CRITICAL CORRELATION BREAKDOWN: CN = {metrics.condition_number:.1f}")

        self.current_metrics = metrics

        # Generate recommendations
        if breakdown:
            breakdown.recommended_actions = self._recommend_actions(breakdown)
            breakdown.strategy_pairs = self._identify_correlated_pairs(snapshot)

        return breakdown

    def _compute_metrics(
        self,
        snapshot: CorrelationSnapshot,
        strategies: List[str],
    ) -> CorrelationMetrics:
        """Compute correlation metrics from snapshot.

        Args:
            snapshot: CorrelationSnapshot
            strategies: List of strategy names

        Returns:
            CorrelationMetrics
        """
        corr_matrix = snapshot.correlation_matrix

        # Eigenvalue decomposition
        try:
            eigenvalues = np.linalg.eigvalsh(corr_matrix)
            eigenvalues = np.sort(eigenvalues)[::-1]
            condition_number = eigenvalues[0] / eigenvalues[-1] if eigenvalues[-1] > 0 else np.inf
            principal_eigenvalue = eigenvalues[0]
            eigenvalue_ratio = eigenvalues[0] / eigenvalues[-1] if eigenvalues[-1] > 0 else np.inf
        except np.linalg.LinAlgError:
            logger.warning("Failed to compute eigenvalues")
            condition_number = self.NORMAL_CONDITION_THRESHOLD
            principal_eigenvalue = 1.0
            eigenvalue_ratio = 1.0

        # Correlation statistics
        # Upper triangle of correlation matrix (excluding diagonal)
        n = corr_matrix.shape[0]
        upper_triangle = corr_matrix[np.triu_indices(n, k=1)]
        max_correlation = np.max(upper_triangle) if len(upper_triangle) > 0 else 0.0
        avg_correlation = np.mean(np.abs(upper_triangle)) if len(upper_triangle) > 0 else 0.0

        return CorrelationMetrics(
            timestamp=snapshot.timestamp,
            condition_number=condition_number,
            max_correlation=max_correlation,
            avg_correlation=avg_correlation,
            principal_eigenvalue=principal_eigenvalue,
            eigenvalue_ratio=eigenvalue_ratio,
        )

    def _detect_breakdown(
        self,
        prev_metrics: CorrelationMetrics,
        curr_metrics: CorrelationMetrics,
    ) -> Optional[CorrelationBreakdown]:
        """Detect if breakdown occurred between snapshots.

        Args:
            prev_metrics: Previous metrics
            curr_metrics: Current metrics

        Returns:
            CorrelationBreakdown if detected, else None
        """
        # Check for condition number jump
        cn_change = curr_metrics.condition_number / max(prev_metrics.condition_number, 1.0)

        if cn_change >= self.CONDITION_NUMBER_CHANGE_THRESHOLD:
            severity = "CRITICAL" if cn_change > 3.0 else "WARNING"
            return CorrelationBreakdown(
                timestamp=curr_metrics.timestamp,
                condition_number=curr_metrics.condition_number,
                prev_condition_number=prev_metrics.condition_number,
                condition_number_change=cn_change,
                severity=severity,
            )

        # Check for level-based breakdown
        if (
            prev_metrics.condition_number < self.BREAKDOWN_CONDITION_THRESHOLD
            and curr_metrics.condition_number >= self.BREAKDOWN_CONDITION_THRESHOLD
        ):
            return CorrelationBreakdown(
                timestamp=curr_metrics.timestamp,
                condition_number=curr_metrics.condition_number,
                prev_condition_number=prev_metrics.condition_number,
                condition_number_change=cn_change,
                severity="WARNING",
            )

        return None

    def _identify_correlated_pairs(
        self,
        snapshot: CorrelationSnapshot,
    ) -> List[Tuple[str, str, float]]:
        """Identify highly correlated strategy pairs.

        Args:
            snapshot: CorrelationSnapshot

        Returns:
            List of (strategy1, strategy2, correlation) tuples sorted by correlation
        """
        pairs = []
        n = len(snapshot.strategies)

        for i in range(n):
            for j in range(i + 1, n):
                corr = snapshot.correlation_matrix[i, j]
                if abs(corr) > 0.6:  # Significant correlation
                    pairs.append((
                        snapshot.strategies[i],
                        snapshot.strategies[j],
                        corr,
                    ))

        # Sort by correlation magnitude
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        return pairs[:10]  # Top 10 pairs

    def _recommend_actions(self, breakdown: CorrelationBreakdown) -> List[str]:
        """Recommend actions based on breakdown severity.

        Args:
            breakdown: CorrelationBreakdown

        Returns:
            List of recommended actions
        """
        actions = []

        if breakdown.severity == "CRITICAL":
            actions = [
                "PAUSE_CORRELATED_TRADES",
                "REDUCE_POSITION_SIZES_50PCT",
                "HEDGE_CORRELATION_RISK",
                "ESCALATE_TO_HUMAN",
                "REVIEW_PORTFOLIO_CONSTRUCTION",
            ]
        elif breakdown.condition_number > self.ELEVATED_CONDITION_THRESHOLD:
            actions = [
                "REDUCE_POSITION_SIZES_25PCT",
                "INCREASE_HEDGE_RATIOS",
                "MONITOR_CORRELATION_CLOSELY",
                "TIGHTEN_RISK_LIMITS",
            ]
        else:
            actions = [
                "MONITOR_CORRELATION",
                "REVIEW_HEDGING",
            ]

        return actions

    def get_breakdown_history(self, n_recent: int = 100) -> List[Dict]:
        """Get recent breakdown history.

        Args:
            n_recent: Number of recent breakdowns

        Returns:
            List of breakdowns as dicts
        """
        return [
            {
                "timestamp": b.timestamp.isoformat(),
                "condition_number": b.condition_number,
                "change_ratio": b.condition_number_change,
                "severity": b.severity,
                "top_pairs": [
                    {"strategy1": p[0], "strategy2": p[1], "correlation": p[2]}
                    for p in b.strategy_pairs[:5]
                ],
                "actions": b.recommended_actions,
            }
            for b in self.breakdowns[-n_recent:]
        ]

    def get_current_metrics(self) -> Optional[Dict]:
        """Get current correlation metrics.

        Returns:
            Current metrics as dict or None
        """
        if not self.current_metrics:
            return None

        return {
            "timestamp": self.current_metrics.timestamp.isoformat(),
            "condition_number": self.current_metrics.condition_number,
            "max_correlation": self.current_metrics.max_correlation,
            "avg_correlation": self.current_metrics.avg_correlation,
            "principal_eigenvalue": self.current_metrics.principal_eigenvalue,
        }

    def is_normal_correlation(self) -> bool:
        """Check if correlation structure is normal.

        Returns:
            True if condition number below normal threshold
        """
        if not self.current_metrics:
            return True
        return self.current_metrics.condition_number < self.NORMAL_CONDITION_THRESHOLD

    def get_correlation_stress_level(self) -> float:
        """Get market correlation stress level (0-1).

        Returns:
            Stress level where 0 = normal, 1 = extreme
        """
        if not self.current_metrics:
            return 0.0

        # Map condition number to stress level
        cn = self.current_metrics.condition_number
        if cn <= self.NORMAL_CONDITION_THRESHOLD:
            return 0.0
        elif cn <= self.ELEVATED_CONDITION_THRESHOLD:
            return (cn - self.NORMAL_CONDITION_THRESHOLD) / (
                self.ELEVATED_CONDITION_THRESHOLD - self.NORMAL_CONDITION_THRESHOLD
            ) * 0.33
        elif cn <= self.BREAKDOWN_CONDITION_THRESHOLD:
            return 0.33 + (cn - self.ELEVATED_CONDITION_THRESHOLD) / (
                self.BREAKDOWN_CONDITION_THRESHOLD - self.ELEVATED_CONDITION_THRESHOLD
            ) * 0.33
        elif cn <= self.EXTREME_CONDITION_THRESHOLD:
            return 0.66 + (cn - self.BREAKDOWN_CONDITION_THRESHOLD) / (
                self.EXTREME_CONDITION_THRESHOLD - self.BREAKDOWN_CONDITION_THRESHOLD
            ) * 0.34
        else:
            return 1.0
