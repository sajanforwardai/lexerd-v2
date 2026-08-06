"""
Group One RAG Tier 3 Safety Systems
=======================================

Comprehensive risk management framework with:
- Position limits enforcement (multi-tier: soft/warning/hard)
- Correlation regime detection (eigenvalue analysis)
- Circuit breaker (daily losses, vol spikes, black swan triggers)
- Human escalation alerting
- Pre/post-trade risk validation

Target Performance:
- 100% position limit enforcement (zero violations)
- Correlation detection: <500ms (eigenvalue decomposition)
- Circuit breaker latency: <100ms
"""

import dataclasses
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np
from collections import defaultdict
from dataclasses import field, dataclass
import time


# ============================================================================
# Configuration & Data Structures
# ============================================================================

class LimitTier(Enum):
    """Risk tier levels: soft warning -> hard stop"""
    SOFT = 0.70      # 70% of limit: warning
    WARNING = 0.85   # 85% of limit: strong warning
    HARD = 1.00      # 100%: hard stop


class RiskMetric(Enum):
    """Greeks and risk metrics"""
    DELTA = "delta"       # directional exposure (notional change per 1% spot)
    GAMMA = "gamma"       # delta convexity (delta change per 1% spot)
    VEGA = "vega"         # volatility sensitivity (per 1% vol change)
    THETA = "theta"       # time decay (daily P&L from time passing)
    RHO = "rho"           # interest rate sensitivity


class CircuitBreakerTrigger(Enum):
    """Circuit breaker activation reasons"""
    DAILY_LOSS = "daily_loss_exceeded"
    VOL_SPIKE = "volatility_spike"
    BLACK_SWAN = "black_swan_liquidation"
    CORRELATION_BREAK = "correlation_regime_break"


@dataclass
class GreeksSnapshot:
    """Greeks aggregation snapshot for a position/book"""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, float]:
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "vega": self.vega,
            "theta": self.theta,
            "rho": self.rho,
        }


@dataclass
class PositionData:
    """Position metadata for limit tracking"""
    instrument_id: str
    notional_usd: float
    side: str  # "long" or "short"
    greeks: GreeksSnapshot
    timestamp: datetime = field(default_factory=datetime.utcnow)
    book_id: Optional[str] = None


@dataclass
class RiskAlert:
    """Risk alert/escalation event"""
    timestamp: datetime
    alert_type: str  # e.g., "limit_breach", "regime_change", "circuit_breaker"
    severity: str    # "info", "warning", "critical"
    message: str
    metadata: Dict = field(default_factory=dict)


# ============================================================================
# 1. PositionLimits - Multi-tier notional & Greeks enforcement
# ============================================================================

class PositionLimits:
    """
    Multi-tier position and Greek limits with soft/warning/hard enforcement.

    Enforces:
    - Notional exposure caps per instrument/book/portfolio
    - Greeks limits (delta, gamma, vega) with multi-tier alerts
    - Aggregates across all open positions

    Performance: O(1) limit checks via pre-computed aggregations.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.positions: Dict[str, PositionData] = {}

        # Define limits by tier (notional USD)
        self.notional_limits = {
            "instrument": 100_000_000,      # $100M per instrument
            "book": 500_000_000,             # $500M per book
            "portfolio": 2_000_000_000,      # $2B total
        }

        # Greeks limits (aggregated)
        self.greeks_limits = {
            RiskMetric.DELTA: {"soft": 500_000_000, "hard": 1_000_000_000},
            RiskMetric.GAMMA: {"soft": 50_000_000, "hard": 100_000_000},
            RiskMetric.VEGA: {"soft": 25_000_000, "hard": 50_000_000},
            RiskMetric.THETA: {"soft": 5_000_000, "hard": 10_000_000},
        }

        # Cached aggregations (updated on position change)
        self._agg_cache = {}
        self._cache_valid = False

    def add_position(self, position: PositionData) -> Tuple[bool, Optional[str]]:
        """
        Add/update a position and validate against limits.

        Returns: (success: bool, violation_msg: Optional[str])
        Raises: ValueError if hard limit would be breached (zero-tolerance).
        """
        pos_id = position.instrument_id

        # Update position
        old_position = self.positions.get(pos_id)
        self.positions[pos_id] = position
        self._cache_valid = False

        # Check limits
        violation = self._check_position_limits(pos_id)
        if violation:
            # Revert on hard limit breach
            if old_position:
                self.positions[pos_id] = old_position
            else:
                del self.positions[pos_id]
            self._cache_valid = False
            raise ValueError(f"Hard limit violation: {violation}")

        # Return warning if soft limit hit
        warning = self._check_position_warnings(pos_id)
        return True, warning

    def get_aggregated_greeks(self) -> GreeksSnapshot:
        """Get total portfolio Greeks (cached)."""
        if not self._cache_valid:
            self._recompute_aggregations()

        return GreeksSnapshot(
            delta=self._agg_cache.get("delta", 0.0),
            gamma=self._agg_cache.get("gamma", 0.0),
            vega=self._agg_cache.get("vega", 0.0),
            theta=self._agg_cache.get("theta", 0.0),
            rho=self._agg_cache.get("rho", 0.0),
        )

    def get_notional_by_instrument(self) -> Dict[str, float]:
        """Get total notional per instrument."""
        return {
            instr_id: abs(pos.notional_usd)
            for instr_id, pos in self.positions.items()
        }

    def get_notional_by_book(self) -> Dict[str, float]:
        """Get total notional per book."""
        by_book = defaultdict(float)
        for pos in self.positions.values():
            book_id = pos.book_id or "default"
            by_book[book_id] += abs(pos.notional_usd)
        return dict(by_book)

    def _recompute_aggregations(self) -> None:
        """Recompute cached aggregations (called on position change)."""
        agg = {
            "delta": 0.0,
            "gamma": 0.0,
            "vega": 0.0,
            "theta": 0.0,
            "rho": 0.0,
        }

        for pos in self.positions.values():
            # Apply directional sign
            sign = 1.0 if pos.side == "long" else -1.0
            agg["delta"] += sign * pos.greeks.delta
            agg["gamma"] += pos.greeks.gamma  # Gamma always additive
            agg["vega"] += sign * pos.greeks.vega
            agg["theta"] += pos.greeks.theta
            agg["rho"] += sign * pos.greeks.rho

        self._agg_cache = agg
        self._cache_valid = True

    def _check_position_limits(self, instrument_id: str) -> Optional[str]:
        """
        Check hard limits (100% tier). Returns violation message if breached.
        This check is MANDATORY - no trading if violated.
        """
        notional = abs(self.positions[instrument_id].notional_usd)

        # Check instrument limit
        if notional > self.notional_limits["instrument"]:
            return (
                f"Instrument {instrument_id}: "
                f"{notional:,.0f} > {self.notional_limits['instrument']:,.0f}"
            )

        # Check book limit
        by_book = self.get_notional_by_book()
        book_id = self.positions[instrument_id].book_id or "default"
        book_notional = by_book.get(book_id, 0.0)
        if book_notional > self.notional_limits["book"]:
            return (
                f"Book {book_id}: "
                f"{book_notional:,.0f} > {self.notional_limits['book']:,.0f}"
            )

        # Check portfolio limit
        total_notional = sum(by_book.values())
        if total_notional > self.notional_limits["portfolio"]:
            return (
                f"Portfolio total: "
                f"{total_notional:,.0f} > {self.notional_limits['portfolio']:,.0f}"
            )

        # Check Greeks hard limits
        agg_greeks = self.get_aggregated_greeks()
        greeks_dict = agg_greeks.to_dict()

        for metric, limits in self.greeks_limits.items():
            value = abs(greeks_dict[metric.value])
            hard_limit = limits["hard"]
            if value > hard_limit:
                return f"{metric.value.upper()} hard limit: {value:,.0f} > {hard_limit:,.0f}"

        return None

    def _check_position_warnings(self, instrument_id: str) -> Optional[str]:
        """
        Check soft/warning limits (70% and 85% tiers).
        Returns warning message if soft limit exceeded.
        """
        warnings = []
        notional = abs(self.positions[instrument_id].notional_usd)

        # Soft limit (70%)
        soft_threshold = self.notional_limits["instrument"] * LimitTier.SOFT.value
        if notional > soft_threshold:
            warnings.append(
                f"Instrument {instrument_id} at "
                f"{notional / self.notional_limits['instrument'] * 100:.1f}% of limit"
            )

        # Check aggregated Greeks soft/warning limits
        agg_greeks = self.get_aggregated_greeks()
        greeks_dict = agg_greeks.to_dict()

        for metric, limits in self.greeks_limits.items():
            value = abs(greeks_dict[metric.value])
            soft_limit = limits["soft"]
            hard_limit = limits["hard"]

            if value > soft_limit:
                pct = value / hard_limit * 100
                warnings.append(f"{metric.value.upper()} at {pct:.1f}% of hard limit")

        return " | ".join(warnings) if warnings else None


# ============================================================================
# 2. CorrelationDetector - Eigenvalue regime change detection
# ============================================================================

class CorrelationDetector:
    """
    Detects correlation regime breaks using eigenvalue decomposition.

    Method:
    - Compute rolling correlation matrix of instruments/factors
    - Compute eigenvalues and condition number (max_eigenvalue / min_eigenvalue)
    - Flag if condition number > 10 (indicates strong correlation dependencies)

    Interpretation:
    - Condition number ~1: independent assets
    - Condition number ~3-5: moderate correlation
    - Condition number >10: regime break or crisis (forced correlation)

    Performance target: <500ms per update
    """

    def __init__(self, window_size: int = 60, condition_threshold: float = 10.0,
                 logger: Optional[logging.Logger] = None):
        """
        Args:
            window_size: rolling window for correlation (in periods, e.g., 60 days)
            condition_threshold: flag if condition number > this value
            logger: optional logger instance
        """
        self.window_size = window_size
        self.condition_threshold = condition_threshold
        self.logger = logger or logging.getLogger(__name__)

        # Time series data (rolling window)
        self.price_data: Dict[str, List[float]] = defaultdict(list)
        self.timestamps: List[datetime] = []

        # Cached analysis results
        self._correlation_matrix: Optional[np.ndarray] = None
        self._eigenvalues: Optional[np.ndarray] = None
        self._condition_number: Optional[float] = None
        self._regime_state = "normal"  # "normal" or "break"

    def add_price_update(self, instrument_id: str, price: float,
                        timestamp: Optional[datetime] = None) -> None:
        """Add a price observation for regime detection."""
        timestamp = timestamp or datetime.utcnow()

        # Add timestamp if new
        if not self.timestamps or self.timestamps[-1] != timestamp:
            self.timestamps.append(timestamp)

        self.price_data[instrument_id].append(price)

        # Trim to window size
        if len(self.timestamps) > self.window_size:
            self.timestamps.pop(0)
            for instr_id in self.price_data:
                if len(self.price_data[instr_id]) > self.window_size:
                    self.price_data[instr_id].pop(0)

        # Invalidate cache
        self._correlation_matrix = None
        self._eigenvalues = None
        self._condition_number = None

    def detect_regime_break(self) -> Tuple[bool, Optional[float]]:
        """
        Detect if current market is in regime break state.

        Returns:
            (is_regime_break: bool, condition_number: Optional[float])
        """
        start_time = time.time()

        # Need minimum data to compute correlation
        if len(self.price_data) < 2 or len(self.timestamps) < 2:
            return False, None

        # Compute correlation matrix and eigenvalues
        self._compute_eigenanalysis()

        elapsed_ms = (time.time() - start_time) * 1000

        if self._condition_number is None:
            return False, None

        # Update regime state
        old_state = self._regime_state
        self._regime_state = (
            "break" if self._condition_number > self.condition_threshold else "normal"
        )

        if old_state != self._regime_state:
            self.logger.warning(
                f"Regime transition {old_state} -> {self._regime_state} "
                f"(condition number: {self._condition_number:.2f}, latency: {elapsed_ms:.1f}ms)"
            )

        return self._regime_state == "break", self._condition_number

    def get_condition_number(self) -> Optional[float]:
        """Get current condition number (cached)."""
        if self._condition_number is None:
            self._compute_eigenanalysis()
        return self._condition_number

    def get_eigenvalues(self) -> Optional[np.ndarray]:
        """Get eigenvalues of correlation matrix (cached)."""
        if self._eigenvalues is None:
            self._compute_eigenanalysis()
        return self._eigenvalues

    def _compute_eigenanalysis(self) -> None:
        """Compute correlation matrix and eigenvalue decomposition."""
        if not self.price_data or len(self.price_data) < 2:
            return

        # Build price matrix (instruments x time)
        instruments = sorted(self.price_data.keys())
        prices = np.array([self.price_data[instr] for instr in instruments])

        # Compute log returns
        if prices.shape[1] < 2:
            return

        log_returns = np.diff(np.log(prices), axis=1)

        # Compute correlation matrix
        self._correlation_matrix = np.corrcoef(log_returns)

        # Compute eigenvalues
        try:
            eigenvalues = np.linalg.eigvalsh(self._correlation_matrix)
            eigenvalues = np.sort(eigenvalues)[::-1]  # descending order
            self._eigenvalues = eigenvalues

            # Condition number = max eigenvalue / min eigenvalue
            if eigenvalues[-1] > 1e-10:  # avoid division by zero
                self._condition_number = eigenvalues[0] / eigenvalues[-1]
            else:
                self._condition_number = np.inf
        except np.linalg.LinAlgError:
            self.logger.error("Failed to compute eigenvalue decomposition")
            self._condition_number = None


# ============================================================================
# 3. CircuitBreaker - Daily loss limits, vol spikes, liquidation triggers
# ============================================================================

class CircuitBreaker:
    """
    Market circuit breaker with multiple triggers:

    1. Daily loss limit: cumulative P&L loss exceeds threshold
    2. Volatility spike: realized vol increases >X% in short window
    3. Black swan: extreme move detection (>3-sigma or crash pattern)

    Once triggered, ALL trading halts until manual override or market close.

    Performance target: <100ms per check
    """

    def __init__(self, daily_loss_limit_usd: float = 50_000_000,
                 vol_spike_threshold: float = 0.50,  # 50% vol increase
                 black_swan_sigma: float = 3.0,
                 logger: Optional[logging.Logger] = None):
        """
        Args:
            daily_loss_limit_usd: stop at this cumulative daily loss
            vol_spike_threshold: trigger if realized vol spikes > X%
            black_swan_sigma: trigger on move > N standard deviations
            logger: optional logger
        """
        self.daily_loss_limit_usd = daily_loss_limit_usd
        self.vol_spike_threshold = vol_spike_threshold
        self.black_swan_sigma = black_swan_sigma
        self.logger = logger or logging.getLogger(__name__)

        # Daily tracking (reset at market open)
        self.trading_date = datetime.utcnow().date()
        self.daily_pnl_usd = 0.0
        self.daily_max_loss_usd = 0.0

        # Circuit breaker state
        self.is_triggered = False
        self.trigger_reason: Optional[CircuitBreakerTrigger] = None
        self.trigger_time: Optional[datetime] = None

        # Volatility tracking
        self.recent_returns: List[float] = []
        self.realized_vol: Optional[float] = None
        self.vol_baseline: float = 0.15  # 15% baseline vol

        # Price history for black swan detection
        self.price_history: List[float] = []
        self.return_history: List[float] = []

    def update_pnl(self, pnl_change_usd: float) -> Tuple[bool, Optional[str]]:
        """
        Update daily P&L. Check loss limit.

        Returns: (trading_allowed: bool, message: Optional[str])
        """
        start_time = time.time()

        # Reset if new trading day
        current_date = datetime.utcnow().date()
        if current_date != self.trading_date:
            self.trading_date = current_date
            self.daily_pnl_usd = 0.0
            self.daily_max_loss_usd = 0.0
            self.is_triggered = False
            self.trigger_reason = None
            self.trigger_time = None

        # Update P&L
        self.daily_pnl_usd += pnl_change_usd
        if self.daily_pnl_usd < self.daily_max_loss_usd:
            self.daily_max_loss_usd = self.daily_pnl_usd

        # Check loss limit
        loss = abs(self.daily_max_loss_usd)
        if loss > self.daily_loss_limit_usd:
            self.is_triggered = True
            self.trigger_reason = CircuitBreakerTrigger.DAILY_LOSS
            self.trigger_time = datetime.utcnow()
            msg = (
                f"CIRCUIT BREAKER TRIGGERED: Daily loss ${loss:,.0f} "
                f"exceeds limit ${self.daily_loss_limit_usd:,.0f}"
            )
            self.logger.critical(msg)
            return False, msg

        elapsed_ms = (time.time() - start_time) * 1000
        assert elapsed_ms < 100, f"Circuit breaker check took {elapsed_ms:.1f}ms (target <100ms)"

        return not self.is_triggered, None

    def update_price(self, price: float) -> Tuple[bool, Optional[str]]:
        """
        Update price history and check for vol spikes / black swan.

        Returns: (trading_allowed: bool, message: Optional[str])
        """
        start_time = time.time()

        self.price_history.append(price)

        # Compute return if we have history
        if len(self.price_history) > 1:
            ret = (self.price_history[-1] - self.price_history[-2]) / self.price_history[-2]
            self.return_history.append(ret)
            self.recent_returns.append(ret)

            # Keep recent history for vol computation
            if len(self.recent_returns) > 20:
                self.recent_returns.pop(0)

            # Check for black swan (extreme move)
            if len(self.return_history) > 1:
                recent_std = np.std(self.return_history[-20:]) if len(self.return_history) >= 20 else np.std(self.return_history)
                if recent_std > 0:
                    z_score = abs(ret) / recent_std
                    if z_score > self.black_swan_sigma:
                        self.is_triggered = True
                        self.trigger_reason = CircuitBreakerTrigger.BLACK_SWAN
                        self.trigger_time = datetime.utcnow()
                        msg = (
                            f"CIRCUIT BREAKER TRIGGERED: Black swan detected "
                            f"(move: {ret*100:.2f}%, z-score: {z_score:.2f})"
                        )
                        self.logger.critical(msg)
                        return False, msg

            # Check vol spike
            if len(self.return_history) >= 20:
                recent_vol = np.std(self.return_history[-20:]) * np.sqrt(252)  # annualized
                if self.realized_vol is not None:
                    vol_change = (recent_vol - self.realized_vol) / self.realized_vol
                    if vol_change > self.vol_spike_threshold:
                        self.is_triggered = True
                        self.trigger_reason = CircuitBreakerTrigger.VOL_SPIKE
                        self.trigger_time = datetime.utcnow()
                        msg = (
                            f"CIRCUIT BREAKER TRIGGERED: Vol spike "
                            f"({vol_change*100:.1f}% increase)"
                        )
                        self.logger.critical(msg)
                        return False, msg

                self.realized_vol = recent_vol

        elapsed_ms = (time.time() - start_time) * 1000
        assert elapsed_ms < 100, f"Price update took {elapsed_ms:.1f}ms (target <100ms)"

        return not self.is_triggered, None

    def override_trigger(self, reason: str) -> None:
        """Manual override to re-enable trading (for authorized personnel only)."""
        self.logger.warning(f"Circuit breaker manually overridden: {reason}")
        self.is_triggered = False
        self.trigger_reason = None


# ============================================================================
# 4. HumanEscalation - Alert logging and manual review triggers
# ============================================================================

class HumanEscalation:
    """
    Manages risk alerts and escalation to human traders/risk managers.

    Logs all unusual patterns and triggers manual review alerts via:
    - Severity-based filtering (info, warning, critical)
    - Threshold-based batching (delay non-critical to avoid alert fatigue)
    - Audit trail (all alerts timestamped and immutable)
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.alerts: List[RiskAlert] = []

        # Alert thresholds by severity
        self.alert_delay_ms = {
            "info": 60_000,      # batch info alerts, send every 60s
            "warning": 10_000,   # send warning within 10s
            "critical": 0,       # critical: immediate
        }

        self.last_batch_time = {
            "info": datetime.utcnow(),
            "warning": datetime.utcnow(),
            "critical": datetime.utcnow(),
        }

    def log_alert(self, alert_type: str, severity: str, message: str,
                  metadata: Optional[Dict] = None) -> RiskAlert:
        """
        Log a risk alert.

        Args:
            alert_type: e.g., "limit_breach", "regime_change", "vol_spike"
            severity: "info", "warning", or "critical"
            message: human-readable alert message
            metadata: additional context (limit values, current value, etc.)

        Returns: RiskAlert object
        """
        alert = RiskAlert(
            timestamp=datetime.utcnow(),
            alert_type=alert_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )

        self.alerts.append(alert)

        # Log immediately
        log_func = {
            "info": self.logger.info,
            "warning": self.logger.warning,
            "critical": self.logger.critical,
        }.get(severity, self.logger.info)

        log_func(f"[{alert_type}] {message}")

        return alert

    def get_pending_alerts(self, since: Optional[datetime] = None) -> List[RiskAlert]:
        """Get alerts since timestamp (default: last batch)."""
        if since is None:
            since = datetime.utcnow() - timedelta(minutes=5)

        return [alert for alert in self.alerts if alert.timestamp >= since]

    def should_escalate(self, severity: str) -> bool:
        """Check if alert of this severity should be escalated now."""
        if severity == "critical":
            return True

        last_time = self.last_batch_time[severity]
        delay_ms = self.alert_delay_ms[severity]
        elapsed_ms = (datetime.utcnow() - last_time).total_seconds() * 1000

        return elapsed_ms > delay_ms

    def mark_escalated(self, severity: str) -> None:
        """Mark that alerts of this severity were escalated."""
        self.last_batch_time[severity] = datetime.utcnow()

    def get_audit_trail(self, start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None) -> List[RiskAlert]:
        """Get audit trail of all alerts in time window."""
        start_time = start_time or datetime.utcnow() - timedelta(days=1)
        end_time = end_time or datetime.utcnow()

        return [
            alert for alert in self.alerts
            if start_time <= alert.timestamp <= end_time
        ]


# ============================================================================
# 5. RiskValidator - Pre/post-trade validation
# ============================================================================

class RiskValidator:
    """
    Pre-trade and post-trade risk validation.

    Pre-trade:
    - Aggregate Greeks for proposed position
    - Check against limits before execution
    - Validate order parameters

    Post-trade:
    - Verify actual P&L bounds
    - Reconcile expected vs. actual Greeks
    - Flag slippage/execution issues
    """

    def __init__(self, position_limits: PositionLimits,
                 logger: Optional[logging.Logger] = None):
        self.position_limits = position_limits
        self.logger = logger or logging.getLogger(__name__)

        # Post-trade validation thresholds
        self.max_slippage_pct = 0.10  # 10% max slippage
        self.max_greeks_deviation_pct = 0.15  # 15% Greeks deviation

    def validate_trade(self, position: PositionData) -> Tuple[bool, Optional[str]]:
        """
        Pre-trade validation: check if position is acceptable.

        Returns: (is_valid: bool, issue: Optional[str])
        """
        # Check against limits
        try:
            self.position_limits.add_position(position)
        except ValueError as e:
            return False, str(e)

        # Check Greeks are reasonable (no extreme values)
        greeks = position.greeks
        greeks_max = 1_000_000_000  # $1B reasonable max per Greek

        for greek_name in ["delta", "gamma", "vega"]:
            greek_val = abs(getattr(greeks, greek_name))
            if greek_val > greeks_max:
                return False, f"{greek_name} exceeds maximum: {greek_val:,.0f}"

        return True, None

    def validate_execution(self, expected_greeks: GreeksSnapshot,
                          actual_greeks: GreeksSnapshot,
                          expected_price: float,
                          actual_price: float,
                          size: float) -> Tuple[bool, Optional[str]]:
        """
        Post-trade validation: check execution quality.

        Returns: (is_valid: bool, issue: Optional[str])
        """
        issues = []

        # Check price slippage
        if expected_price > 0:
            slippage = abs(actual_price - expected_price) / expected_price
            if slippage > self.max_slippage_pct:
                issues.append(
                    f"Price slippage {slippage*100:.2f}% exceeds {self.max_slippage_pct*100:.1f}%"
                )

        # Check Greeks deviation
        for greek_name in ["delta", "gamma", "vega", "theta"]:
            expected_val = abs(getattr(expected_greeks, greek_name))
            actual_val = abs(getattr(actual_greeks, greek_name))

            if expected_val > 0:
                deviation = abs(actual_val - expected_val) / expected_val
                if deviation > self.max_greeks_deviation_pct:
                    issues.append(
                        f"{greek_name} deviation {deviation*100:.2f}% "
                        f"(expected {expected_val:,.0f}, got {actual_val:,.0f})"
                    )

        return len(issues) == 0, " | ".join(issues) if issues else None

    def validate_pnl_bounds(self, notional: float, expected_pnl: float,
                           actual_pnl: float, risk_limit_pct: float = 0.10) -> Tuple[bool, Optional[str]]:
        """
        Validate post-trade P&L is within expected bounds.

        Args:
            notional: position notional
            expected_pnl: expected P&L from model
            actual_pnl: realized P&L
            risk_limit_pct: acceptable deviation % (default 10%)

        Returns: (is_valid: bool, issue: Optional[str])
        """
        if abs(notional) < 1.0:
            return True, None

        bound = abs(expected_pnl) * risk_limit_pct
        deviation = abs(actual_pnl - expected_pnl)

        if deviation > bound:
            return (
                False,
                f"P&L deviation ${deviation:,.0f} exceeds bound ${bound:,.0f} "
                f"(expected ${expected_pnl:,.0f}, got ${actual_pnl:,.0f})"
            )

        return True, None


# ============================================================================
# SafetySystems - Main coordinator
# ============================================================================

class SafetySystems:
    """
    Unified safety system coordinator.

    Orchestrates all 5 safety modules:
    1. PositionLimits - notional & Greeks enforcement
    2. CorrelationDetector - regime break detection
    3. CircuitBreaker - daily loss & vol spike detection
    4. HumanEscalation - alert logging & escalation
    5. RiskValidator - pre/post-trade validation

    All checks run BEFORE trade execution (pre-trade gate).
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or self._setup_logger()

        # Initialize all subsystems
        self.position_limits = PositionLimits(self.logger)
        self.correlation_detector = CorrelationDetector(logger=self.logger)
        self.circuit_breaker = CircuitBreaker(logger=self.logger)
        self.human_escalation = HumanEscalation(self.logger)
        self.risk_validator = RiskValidator(self.position_limits, self.logger)

    def _setup_logger(self) -> logging.Logger:
        """Setup default logger."""
        logger = logging.getLogger("SafetySystems")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)-8s %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def pre_trade_check(self, position: PositionData) -> Tuple[bool, List[str]]:
        """
        Pre-trade risk gate: run all checks before execution.

        Returns:
            (is_approved: bool, messages: List[str])
        """
        messages = []

        # Check 1: Circuit breaker
        if self.circuit_breaker.is_triggered:
            messages.append(
                f"CIRCUIT BREAKER ACTIVE: {self.circuit_breaker.trigger_reason.value}"
            )
            return False, messages

        # Check 2: Position limits
        try:
            _, warning = self.position_limits.add_position(position)
            if warning:
                messages.append(f"Position limit warning: {warning}")
                self.human_escalation.log_alert(
                    "limit_warning", "warning", warning
                )
        except ValueError as e:
            messages.append(f"Position limit breach: {str(e)}")
            self.human_escalation.log_alert(
                "limit_breach", "critical", str(e),
                {"position": position.instrument_id, "notional": position.notional_usd}
            )
            return False, messages

        # Check 3: Risk validation
        is_valid, issue = self.risk_validator.validate_trade(position)
        if not is_valid:
            messages.append(f"Trade validation failed: {issue}")
            self.human_escalation.log_alert(
                "validation_failed", "warning", issue
            )
            return False, messages

        # Check 4: Correlation regime (warning only)
        is_regime_break, condition_num = self.correlation_detector.detect_regime_break()
        if is_regime_break:
            msg = (
                f"Correlation regime break detected (condition number: {condition_num:.2f})"
            )
            messages.append(msg)
            self.human_escalation.log_alert(
                "regime_change", "warning", msg,
                {"condition_number": condition_num}
            )

        return True, messages

    def post_trade_validation(self, position_id: str, expected_greeks: GreeksSnapshot,
                            actual_greeks: GreeksSnapshot, execution_price: float,
                            realized_pnl: float) -> Tuple[bool, List[str]]:
        """
        Post-trade validation: check execution quality and P&L.

        Returns: (is_valid: bool, issues: List[str])
        """
        issues = []

        # Retrieve position for context
        pos = self.position_limits.positions.get(position_id)
        if not pos:
            return False, ["Position not found in limits tracking"]

        # Check execution quality
        is_valid, issue = self.risk_validator.validate_execution(
            expected_greeks, actual_greeks,
            pos.greeks.delta / abs(pos.notional_usd + 1e-8),  # implied price
            execution_price,
            abs(pos.notional_usd)
        )
        if not is_valid:
            issues.append(f"Execution quality issue: {issue}")
            self.human_escalation.log_alert(
                "execution_quality", "warning", issue
            )

        # Check P&L bounds
        expected_pnl = pos.greeks.delta * 0.01  # rough approximation
        is_valid, issue = self.risk_validator.validate_pnl_bounds(
            pos.notional_usd, expected_pnl, realized_pnl
        )
        if not is_valid:
            issues.append(f"P&L validation issue: {issue}")
            self.human_escalation.log_alert(
                "pnl_anomaly", "warning", issue
            )

        return len(issues) == 0, issues

    def get_system_status(self) -> Dict:
        """Get comprehensive system status snapshot."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "circuit_breaker": {
                "triggered": self.circuit_breaker.is_triggered,
                "reason": self.circuit_breaker.trigger_reason.value if self.circuit_breaker.trigger_reason else None,
                "daily_pnl": self.circuit_breaker.daily_pnl_usd,
            },
            "position_limits": {
                "notional_by_instrument": self.position_limits.get_notional_by_instrument(),
                "notional_by_book": self.position_limits.get_notional_by_book(),
                "aggregated_greeks": self.position_limits.get_aggregated_greeks().to_dict(),
            },
            "correlation": {
                "condition_number": self.correlation_detector.get_condition_number(),
                "regime": self.correlation_detector._regime_state,
            },
            "alerts_pending": len(self.human_escalation.get_pending_alerts()),
        }
