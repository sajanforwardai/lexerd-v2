"""
Observation Collector for Trading System
=========================================

Captures live trading observations including:
- Trade executions and outcomes
- Market regime shifts
- Volatility changes
- Greeks snapshots
- Escalations and anomalies

Supports both real-time collection and mock observation streams.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class RegiType(Enum):
    """Market regime types."""
    BULL_LOW_VOL = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR_LOW_VOL = "bear_low_vol"
    BEAR_HIGH_VOL = "bear_high_vol"
    STRESS = "stress"
    NORMAL = "normal"


class TradeStatus(Enum):
    """Trade execution status."""
    INITIATED = "initiated"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class TradeObservation:
    """Represents a single trade execution."""
    trade_id: str
    timestamp: str
    strategy: str
    instrument: str
    side: str  # "buy" or "sell"
    quantity: float
    entry_price: float
    exit_price: Optional[float]
    pnl: Optional[float]
    status: TradeStatus
    greeks: Dict[str, float]  # delta, gamma, theta, vega, rho
    regime_at_entry: str
    regime_at_exit: Optional[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


@dataclass
class RegimeShift:
    """Represents a market regime shift detection."""
    timestamp: str
    from_regime: str
    to_regime: str
    volatility_change: float  # percentage change
    trigger: str  # "volatility", "directional", "correlation", "event"
    confidence: float  # 0-1
    description: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Escalation:
    """Represents an escalation event (anomaly, warning, etc.)."""
    timestamp: str
    level: str  # "warning", "error", "critical"
    category: str  # "position", "loss", "volatility", "correlations", "other"
    message: str
    context: Dict[str, Any]
    resolved: bool = False
    resolution_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ObservationCollector:
    """
    Collects trading observations from live system or mock sources.

    Stores observations in memory with optional persistence to JSON.
    Supports querying by time range, strategy, instrument, or regime.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize collector.

        Args:
            storage_path: Path to persist observations to JSON file
        """
        self.storage_path = storage_path
        self.trades: List[TradeObservation] = []
        self.regime_shifts: List[RegimeShift] = []
        self.escalations: List[Escalation] = []
        self.current_regime = "normal"
        self.observation_count = 0

    def record_trade(
        self,
        trade_id: str,
        strategy: str,
        instrument: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: Optional[float] = None,
        pnl: Optional[float] = None,
        status: TradeStatus = TradeStatus.FILLED,
        greeks: Optional[Dict[str, float]] = None,
        regime_at_entry: Optional[str] = None,
        regime_at_exit: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TradeObservation:
        """
        Record a trade observation.

        Args:
            trade_id: Unique trade identifier
            strategy: Strategy name (e.g., "gamma_scalping")
            instrument: Instrument traded (e.g., "BTC/USD")
            side: "buy" or "sell"
            quantity: Trade size
            entry_price: Entry price
            exit_price: Exit price (if trade closed)
            pnl: P&L result
            status: Trade status
            greeks: Dict of Greeks at time of trade
            regime_at_entry: Market regime at entry
            regime_at_exit: Market regime at exit
            metadata: Additional context

        Returns:
            TradeObservation object
        """
        trade = TradeObservation(
            trade_id=trade_id,
            timestamp=datetime.utcnow().isoformat(),
            strategy=strategy,
            instrument=instrument,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            status=status,
            greeks=greeks or {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0},
            regime_at_entry=regime_at_entry or self.current_regime,
            regime_at_exit=regime_at_exit,
            metadata=metadata or {}
        )

        self.trades.append(trade)
        self.observation_count += 1
        logger.info(
            f"Recorded trade: {trade_id} ({strategy} {side} {quantity} @ {entry_price})"
        )
        return trade

    def record_regime_shift(
        self,
        from_regime: str,
        to_regime: str,
        volatility_change: float,
        trigger: str = "volatility",
        confidence: float = 0.8,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> RegimeShift:
        """
        Record a market regime shift.

        Args:
            from_regime: Previous regime
            to_regime: New regime
            volatility_change: Volatility percentage change
            trigger: What triggered the shift
            confidence: Confidence in shift detection [0-1]
            description: Human-readable description
            metadata: Additional context

        Returns:
            RegimeShift object
        """
        shift = RegimeShift(
            timestamp=datetime.utcnow().isoformat(),
            from_regime=from_regime,
            to_regime=to_regime,
            volatility_change=volatility_change,
            trigger=trigger,
            confidence=confidence,
            description=description,
            metadata=metadata or {}
        )

        self.regime_shifts.append(shift)
        self.current_regime = to_regime
        self.observation_count += 1
        logger.info(
            f"Recorded regime shift: {from_regime} -> {to_regime} "
            f"(vol {volatility_change:+.1f}%, confidence {confidence:.2f})"
        )
        return shift

    def record_escalation(
        self,
        level: str,
        category: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Escalation:
        """
        Record an escalation event.

        Args:
            level: "warning", "error", or "critical"
            category: Event category
            message: Human-readable message
            context: Context about the escalation

        Returns:
            Escalation object
        """
        escalation = Escalation(
            timestamp=datetime.utcnow().isoformat(),
            level=level,
            category=category,
            message=message,
            context=context or {}
        )

        self.escalations.append(escalation)
        self.observation_count += 1
        logger.warning(f"Recorded escalation [{level}]: {message}")
        return escalation

    def resolve_escalation(self, escalation_index: int) -> bool:
        """Mark an escalation as resolved."""
        if 0 <= escalation_index < len(self.escalations):
            self.escalations[escalation_index].resolved = True
            self.escalations[escalation_index].resolution_time = datetime.utcnow().isoformat()
            return True
        return False

    def get_trades_by_strategy(self, strategy: str) -> List[TradeObservation]:
        """Get all trades for a specific strategy."""
        return [t for t in self.trades if t.strategy == strategy]

    def get_trades_by_regime(self, regime: str) -> List[TradeObservation]:
        """Get all trades executed in a specific regime."""
        return [t for t in self.trades if t.regime_at_entry == regime]

    def get_trades_by_instrument(self, instrument: str) -> List[TradeObservation]:
        """Get all trades for a specific instrument."""
        return [t for t in self.trades if t.instrument == instrument]

    def get_active_escalations(self) -> List[Escalation]:
        """Get unresolved escalations."""
        return [e for e in self.escalations if not e.resolved]

    def get_regime_history(self) -> List[Dict[str, Any]]:
        """Get timeline of regime shifts."""
        return [shift.to_dict() for shift in self.regime_shifts]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of observations."""
        win_trades = [t for t in self.trades if t.pnl and t.pnl > 0]
        loss_trades = [t for t in self.trades if t.pnl and t.pnl < 0]
        neutral_trades = [t for t in self.trades if t.pnl and t.pnl == 0]

        total_pnl = sum(t.pnl for t in self.trades if t.pnl)
        win_rate = len(win_trades) / len(self.trades) if self.trades else 0.0

        return {
            "total_observations": self.observation_count,
            "total_trades": len(self.trades),
            "winning_trades": len(win_trades),
            "losing_trades": len(loss_trades),
            "neutral_trades": len(neutral_trades),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl_per_trade": total_pnl / len(self.trades) if self.trades else 0.0,
            "regime_shifts": len(self.regime_shifts),
            "active_escalations": len(self.get_active_escalations()),
            "current_regime": self.current_regime
        }

    def export_observations(self, filepath: str) -> bool:
        """Export all observations to JSON."""
        try:
            export = {
                "exported_at": datetime.utcnow().isoformat(),
                "summary": self.get_summary(),
                "trades": [t.to_dict() for t in self.trades],
                "regime_shifts": [r.to_dict() for r in self.regime_shifts],
                "escalations": [e.to_dict() for e in self.escalations]
            }

            with open(filepath, 'w') as f:
                json.dump(export, f, indent=2)

            logger.info(f"Exported observations to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to export observations: {e}")
            return False

    def import_observations(self, filepath: str) -> bool:
        """Import observations from JSON."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            for trade_dict in data.get("trades", []):
                trade_dict["status"] = TradeStatus(trade_dict["status"])
                trade = TradeObservation(**trade_dict)
                self.trades.append(trade)

            for shift_dict in data.get("regime_shifts", []):
                shift = RegimeShift(**shift_dict)
                self.regime_shifts.append(shift)

            for esc_dict in data.get("escalations", []):
                esc = Escalation(**esc_dict)
                self.escalations.append(esc)

            logger.info(f"Imported observations from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to import observations: {e}")
            return False


class MockObservationStream:
    """Generates mock trading observations for testing."""

    def __init__(self, seed: int = 42):
        """
        Initialize mock stream.

        Args:
            seed: Random seed for reproducibility
        """
        import random
        random.seed(seed)
        self.random = random

    def generate_mock_trades(self, collector: ObservationCollector, count: int = 50):
        """Generate mock trades."""
        strategies = ["gamma_scalping", "vol_arbitrage", "delta_hedging", "pairs_trading"]
        instruments = ["BTC/USD", "ETH/USD", "SPY"]
        regimes = ["bull_low_vol", "bull_high_vol", "bear_low_vol", "bear_high_vol", "stress"]

        for i in range(count):
            strategy = self.random.choice(strategies)
            instrument = self.random.choice(instruments)
            regime = self.random.choice(regimes)
            side = self.random.choice(["buy", "sell"])
            quantity = self.random.uniform(0.1, 10.0)
            entry_price = self.random.uniform(100, 10000)

            # 70% of trades close
            if self.random.random() < 0.7:
                price_change = self.random.gauss(0, 0.02)  # 2% std dev
                exit_price = entry_price * (1 + price_change)
                pnl = (exit_price - entry_price) * quantity if side == "buy" else (entry_price - exit_price) * quantity
            else:
                exit_price = None
                pnl = None

            greeks = {
                "delta": self.random.uniform(-1, 1),
                "gamma": self.random.uniform(0, 0.5),
                "theta": self.random.uniform(-0.1, 0.1),
                "vega": self.random.uniform(-1, 1),
                "rho": self.random.uniform(-0.5, 0.5)
            }

            collector.record_trade(
                trade_id=f"mock_trade_{i}",
                strategy=strategy,
                instrument=instrument,
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=pnl,
                greeks=greeks,
                regime_at_entry=regime,
                regime_at_exit=regime if exit_price else None
            )

    def generate_mock_regime_shifts(self, collector: ObservationCollector, count: int = 5):
        """Generate mock regime shifts."""
        regimes = ["bull_low_vol", "bull_high_vol", "bear_low_vol", "bear_high_vol", "stress"]
        triggers = ["volatility", "directional", "correlation", "event"]

        current_regime = "normal"
        for i in range(count):
            new_regime = self.random.choice(regimes)
            vol_change = self.random.gauss(0, 15)  # 15% std dev

            collector.record_regime_shift(
                from_regime=current_regime,
                to_regime=new_regime,
                volatility_change=vol_change,
                trigger=self.random.choice(triggers),
                confidence=self.random.uniform(0.75, 0.99),
                description=f"Shift from {current_regime} to {new_regime}"
            )

            current_regime = new_regime

    def generate_mock_escalations(self, collector: ObservationCollector, count: int = 3):
        """Generate mock escalations."""
        levels = ["warning", "error"]
        categories = ["position", "loss", "volatility", "correlations"]

        for i in range(count):
            collector.record_escalation(
                level=self.random.choice(levels),
                category=self.random.choice(categories),
                message=f"Mock escalation {i}: test event",
                context={"mock": True, "index": i}
            )
