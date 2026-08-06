"""
Regime Shift Detector using Eigenvalue Decomposition

Detects market regime changes by monitoring correlation matrix structure.
Uses condition number as primary signal: jump >2x = regime break detected.

Input: 1-hour market snapshots (VIX, skew, term structure, correlations)
Output: <1s detection, alert within 1 min of shift
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    """1-hour market snapshot."""
    timestamp: datetime
    vix_level: float  # VIX index level
    vix_1m_skew: float  # 1M vs ATM skew (positive = OTM puts expensive)
    vix_term_slope: float  # (1M VIX - 3M VIX) / (spot VIX)
    correlation_matrix: np.ndarray  # NxN correlation matrix between strategies
    strategies: List[str]  # Strategy names corresponding to matrix rows/cols


@dataclass
class RegimeState:
    """Current regime classification."""
    timestamp: datetime
    regime_name: str  # "normal", "elevated_vol", "correlation_breakdown", "tail_risk"
    confidence: float  # 0-1 confidence level
    condition_number: float  # Condition number of correlation matrix
    eigenvalues: np.ndarray  # Eigenvalues of correlation matrix
    regime_change_detected: bool = False
    magnitude: float = 0.0  # Magnitude of regime shift (0-1)


@dataclass
class RegimeShiftAlert:
    """Alert triggered by regime shift detection."""
    timestamp: datetime
    alert_type: str  # "regime_shift_detected"
    previous_regime: str
    new_regime: str
    condition_number_change: float  # % change in condition number
    magnitude: float  # Magnitude of shift (0-1)
    required_actions: List[str] = field(default_factory=list)
    severity: str = "WARNING"  # "INFO", "WARNING", "CRITICAL"


class RegimeShiftDetector:
    """Detect regime shifts using eigenvalue decomposition."""

    # Condition number thresholds
    NORMAL_CONDITION_NUMBER = 5.0  # Typical normal market
    ELEVATED_CONDITION_NUMBER = 10.0  # Some correlation breakdown
    STRESSED_CONDITION_NUMBER = 20.0  # Significant breakdown
    EXTREME_CONDITION_NUMBER = 50.0  # Extreme tail risk

    # VIX thresholds
    VIX_NORMAL = 15.0
    VIX_ELEVATED = 25.0
    VIX_STRESSED = 40.0

    # Change detection threshold
    CONDITION_NUMBER_CHANGE_THRESHOLD = 2.0  # 2x jump = alarm

    def __init__(self, window_size: int = 60):
        """Initialize regime detector.

        Args:
            window_size: Number of snapshots to keep in rolling window
        """
        self.window_size = window_size
        self.snapshots: deque = deque(maxlen=window_size)
        self.regimes: List[RegimeState] = []
        self.current_regime: Optional[RegimeState] = None
        self.alerts: List[RegimeShiftAlert] = []

    def update(self, snapshot: MarketSnapshot) -> Optional[RegimeShiftAlert]:
        """Process new market snapshot and detect regime shifts.

        Args:
            snapshot: New 1-hour market snapshot

        Returns:
            RegimeShiftAlert if shift detected, else None
        """
        self.snapshots.append(snapshot)

        # Calculate eigenvalue decomposition
        try:
            eigenvalues = np.linalg.eigvalsh(snapshot.correlation_matrix)
            eigenvalues = np.sort(eigenvalues)[::-1]  # Sort descending
            condition_number = eigenvalues[0] / eigenvalues[-1] if eigenvalues[-1] > 0 else np.inf
        except np.linalg.LinAlgError:
            logger.warning("Failed to compute eigenvalues, using fallback")
            condition_number = self.NORMAL_CONDITION_NUMBER
            eigenvalues = np.ones(snapshot.correlation_matrix.shape[0])

        # Classify regime
        new_regime = self._classify_regime(snapshot, condition_number, eigenvalues)

        # Detect regime change
        alert = None
        if self.current_regime and self.current_regime.regime_name != new_regime.regime_name:
            alert = self._generate_shift_alert(self.current_regime, new_regime, snapshot)
            self.alerts.append(alert)
            logger.warning(f"REGIME SHIFT: {self.current_regime.regime_name} -> {new_regime.regime_name}")

        # Check condition number jump
        if self.current_regime:
            cn_change = new_regime.condition_number / max(self.current_regime.condition_number, 1.0)
            if cn_change > self.CONDITION_NUMBER_CHANGE_THRESHOLD:
                if not alert:
                    alert = self._generate_condition_number_alert(
                        self.current_regime, new_regime, cn_change, snapshot
                    )
                    self.alerts.append(alert)
                    logger.warning(
                        f"CONDITION NUMBER JUMP: {self.current_regime.condition_number:.2f} -> "
                        f"{new_regime.condition_number:.2f} ({cn_change:.1f}x)"
                    )

        self.current_regime = new_regime
        self.regimes.append(new_regime)

        return alert

    def _classify_regime(
        self,
        snapshot: MarketSnapshot,
        condition_number: float,
        eigenvalues: np.ndarray,
    ) -> RegimeState:
        """Classify current regime based on multiple signals.

        Args:
            snapshot: Market snapshot
            condition_number: Condition number of correlation matrix
            eigenvalues: Eigenvalues in descending order

        Returns:
            RegimeState classification
        """
        vix = snapshot.vix_level
        term_slope = snapshot.vix_term_slope

        # Regime logic
        if condition_number > self.EXTREME_CONDITION_NUMBER and vix > self.VIX_STRESSED:
            regime_name = "tail_risk"
            confidence = 0.95
            magnitude = 1.0
        elif condition_number > self.STRESSED_CONDITION_NUMBER:
            regime_name = "correlation_breakdown"
            confidence = 0.85
            magnitude = 0.8
        elif condition_number > self.ELEVATED_CONDITION_NUMBER or vix > self.VIX_STRESSED:
            regime_name = "elevated_correlation"
            confidence = 0.75
            magnitude = 0.5
        elif vix > self.VIX_ELEVATED:
            regime_name = "elevated_vol"
            confidence = 0.80
            magnitude = 0.3
        else:
            regime_name = "normal"
            confidence = 0.90 if condition_number < self.NORMAL_CONDITION_NUMBER else 0.70
            magnitude = 0.0

        # Adjust for term structure
        if term_slope < -0.1:  # Inverted term structure
            regime_name = "inverted_term_structure"
            confidence = min(confidence, 0.80)
            magnitude = max(magnitude, 0.3)

        return RegimeState(
            timestamp=snapshot.timestamp,
            regime_name=regime_name,
            confidence=confidence,
            condition_number=condition_number,
            eigenvalues=eigenvalues,
        )

    def _generate_shift_alert(
        self,
        prev_regime: RegimeState,
        new_regime: RegimeState,
        snapshot: MarketSnapshot,
    ) -> RegimeShiftAlert:
        """Generate alert for regime shift.

        Args:
            prev_regime: Previous regime state
            new_regime: New regime state
            snapshot: Current snapshot

        Returns:
            RegimeShiftAlert
        """
        cn_change = new_regime.condition_number / max(prev_regime.condition_number, 1.0)

        # Determine required actions
        actions = []
        if new_regime.regime_name in ["correlation_breakdown", "tail_risk"]:
            actions = [
                "PAUSE_NEW_TRADES",
                "REVIEW_OPEN_POSITIONS",
                "CHECK_CORRELATION_HEDGES",
                "ESCALATE_TO_HUMAN",
            ]
        elif new_regime.regime_name == "elevated_vol":
            actions = [
                "REDUCE_POSITION_SIZES",
                "TIGHTEN_STOP_LOSSES",
                "INCREASE_MONITORING_FREQUENCY",
            ]
        elif new_regime.regime_name == "normal":
            actions = ["RESUME_NORMAL_OPERATIONS", "UNWIND_HEDGES"]

        severity = "CRITICAL" if new_regime.regime_name == "tail_risk" else "WARNING"

        return RegimeShiftAlert(
            timestamp=new_regime.timestamp,
            alert_type="regime_shift_detected",
            previous_regime=prev_regime.regime_name,
            new_regime=new_regime.regime_name,
            condition_number_change=cn_change,
            magnitude=new_regime.magnitude,
            required_actions=actions,
            severity=severity,
        )

    def _generate_condition_number_alert(
        self,
        prev_regime: RegimeState,
        new_regime: RegimeState,
        cn_change: float,
        snapshot: MarketSnapshot,
    ) -> RegimeShiftAlert:
        """Generate alert for condition number jump.

        Args:
            prev_regime: Previous regime state
            new_regime: New regime state
            cn_change: Change ratio in condition number
            snapshot: Current snapshot

        Returns:
            RegimeShiftAlert
        """
        return RegimeShiftAlert(
            timestamp=new_regime.timestamp,
            alert_type="condition_number_jump",
            previous_regime=prev_regime.regime_name,
            new_regime=new_regime.regime_name,
            condition_number_change=cn_change,
            magnitude=new_regime.magnitude,
            required_actions=[
                "ALERT_RISK_COMMITTEE",
                "CHECK_HEDGING_EFFECTIVENESS",
                "REVIEW_CROSS_CORRELATION_TRADES",
            ],
            severity="CRITICAL" if cn_change > 3.0 else "WARNING",
        )

    def get_regime_history(self, n_recent: int = 100) -> List[Dict]:
        """Get recent regime history.

        Args:
            n_recent: Number of recent regimes to return

        Returns:
            List of regime states as dicts
        """
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "regime": r.regime_name,
                "confidence": r.confidence,
                "condition_number": r.condition_number,
                "magnitude": r.magnitude,
            }
            for r in self.regimes[-n_recent:]
        ]

    def get_current_regime(self) -> Optional[Dict]:
        """Get current regime state.

        Returns:
            Current regime as dict or None
        """
        if not self.current_regime:
            return None

        return {
            "timestamp": self.current_regime.timestamp.isoformat(),
            "regime": self.current_regime.regime_name,
            "confidence": self.current_regime.confidence,
            "condition_number": self.current_regime.condition_number,
            "magnitude": self.current_regime.magnitude,
        }

    def get_alerts(self, n_recent: int = 50) -> List[Dict]:
        """Get recent alerts.

        Args:
            n_recent: Number of recent alerts

        Returns:
            List of alerts as dicts
        """
        return [
            {
                "timestamp": a.timestamp.isoformat(),
                "type": a.alert_type,
                "severity": a.severity,
                "from_regime": a.previous_regime,
                "to_regime": a.new_regime,
                "condition_number_change": a.condition_number_change,
                "actions": a.required_actions,
            }
            for a in self.alerts[-n_recent:]
        ]

    def is_normal_regime(self) -> bool:
        """Check if currently in normal regime.

        Returns:
            True if current regime is "normal"
        """
        if not self.current_regime:
            return True
        return self.current_regime.regime_name == "normal"

    def get_stress_level(self) -> float:
        """Get current market stress level (0-1).

        Returns:
            Stress level where 0 = normal, 1 = extreme
        """
        if not self.current_regime:
            return 0.0
        return self.current_regime.magnitude
