"""
Abstract Base Class for Strategy Agents
========================================

Defines the interface all trading strategy agents must implement.
Each agent specializes in a particular market regime and trading approach,
tracking performance via closed-loop feedback from ObservationCollector.

Architecture:
- Abstract StrategyAgent base with regime-aware selection
- Agents track win rate, PnL, and execution quality by regime
- Integration with learning loop: feedback from ObservationCollector
- Elo rating updates based on strategy performance outcomes
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of trading actions agents can select."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    HEDGE = "hedge"
    REBALANCE = "rebalance"
    EXIT = "exit"


@dataclass
class MarketState:
    """Current market state snapshot."""
    volatility: float  # Current realized volatility [0, 1]
    volatility_term_structure: Dict[str, float]  # Vol at different maturities
    skew: float  # Skew level [-1, 1] (negative=put skew)
    term_structure_slope: float  # ATM vol curve slope
    events: List[str]  # Active events ("earnings", "econ_data", etc.)
    regime: str  # Current detected regime
    price_momentum: float  # [-1, 1] momentum indicator
    correlation_regime: str  # Correlation state
    liquidity_score: float  # Liquidity level [0, 1]
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class GreeksSnapshot:
    """Greeks at time of decision."""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    vol_of_vol: float  # Volatility of volatility
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, float]:
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "vol_of_vol": self.vol_of_vol
        }


@dataclass
class StrategySelection:
    """Output from agent.select_action()."""
    strategy_name: str  # Name of selected strategy
    action_type: ActionType  # Type of action
    confidence: float  # [0.0, 1.0] confidence in this decision
    rationale: str  # Human-readable explanation
    target_exposure: float  # Desired position size/delta
    hedge_ratio: Optional[float] = None  # Hedge ratio if hedging
    exit_signal: bool = False  # Force exit flag
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass
class AgentPerformance:
    """Performance tracking for an agent."""
    agent_name: str
    regime: str
    win_rate: float = 0.0
    total_pnl: float = 0.0
    trade_count: int = 0
    avg_pnl_per_trade: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    elo_rating: float = 1600.0  # Starting Elo
    elo_change_today: float = 0.0
    last_updated: str = ""
    selections_made: int = 0  # How many times this agent was selected

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.utcnow().isoformat()


class StrategyAgent(ABC):
    """
    Abstract base class for trading strategy agents.

    Each agent implements a specialized strategy for particular market regimes.
    Agents maintain performance metrics and update via closed-loop learning.
    """

    def __init__(self, name: str):
        """
        Initialize strategy agent.

        Args:
            name: Unique agent name (e.g., "GammaScalpingAgent")
        """
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

        # Performance tracking by regime
        self.performance_by_regime: Dict[str, AgentPerformance] = {}

        # Historical decisions and outcomes
        self.decision_history: List[Dict[str, Any]] = []

        # Regime specializations (override in subclass)
        self.optimized_regimes: List[str] = []

        logger.info(f"Initialized StrategyAgent: {name}")

    @abstractmethod
    def select_action(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> StrategySelection:
        """
        Select action for current market state.

        This is the core decision function. Agents analyze market conditions
        and Greeks to select the best strategy for the detected regime.

        Args:
            regime: Current market regime label
            greeks: Greeks snapshot (delta, gamma, theta, vega, rho, vol-of-vol)
            market_state: Current market state (vol, skew, events, etc.)

        Returns:
            StrategySelection with chosen action and confidence

        Contract:
        - Must return valid StrategySelection with confidence in [0.0, 1.0]
        - Confidence reflects agent's belief in the decision
        - Rationale should explain the decision logic
        - Should specialize in particular regimes (high confidence there)
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Return human-readable description of this agent's strategy."""
        pass

    def get_performance(self, regime: Optional[str] = None) -> AgentPerformance:
        """
        Get performance metrics for this agent.

        Args:
            regime: Optional regime to filter by. If None, returns overall.

        Returns:
            AgentPerformance with current metrics
        """
        if regime:
            return self.performance_by_regime.get(
                regime,
                AgentPerformance(agent_name=self.name, regime=regime)
            )

        # Aggregate across all regimes
        total_pnl = sum(p.total_pnl for p in self.performance_by_regime.values())
        total_trades = sum(p.trade_count for p in self.performance_by_regime.values())

        return AgentPerformance(
            agent_name=self.name,
            regime="overall",
            total_pnl=total_pnl,
            trade_count=total_trades,
            avg_pnl_per_trade=total_pnl / total_trades if total_trades > 0 else 0.0,
            elo_rating=self._calculate_overall_elo()
        )

    def update_performance(
        self,
        regime: str,
        pnl: float,
        trade_count: int = 1,
        is_win: bool = True
    ):
        """
        Update performance metrics after trade execution.

        Called by learning loop with trade outcomes from ObservationCollector.

        Args:
            regime: Regime where trade executed
            pnl: P&L from closed trade
            trade_count: Number of trades (default 1)
            is_win: Whether trade was profitable
        """
        if regime not in self.performance_by_regime:
            self.performance_by_regime[regime] = AgentPerformance(
                agent_name=self.name,
                regime=regime
            )

        perf = self.performance_by_regime[regime]
        perf.total_pnl += pnl
        perf.trade_count += trade_count

        if perf.trade_count > 0:
            perf.avg_pnl_per_trade = perf.total_pnl / perf.trade_count
            win_trades = sum(
                1 for d in self.decision_history
                if d.get("regime") == regime and d.get("pnl", 0) > 0
            )
            perf.win_rate = win_trades / perf.trade_count if perf.trade_count > 0 else 0.0

        perf.last_updated = datetime.utcnow().isoformat()

        self.logger.debug(
            f"Updated performance - regime={regime}, pnl={pnl}, "
            f"total_trades={perf.trade_count}, win_rate={perf.win_rate:.2f}"
        )

    def record_decision(
        self,
        selection: StrategySelection,
        market_state: MarketState,
        greeks: GreeksSnapshot,
        pnl: Optional[float] = None
    ):
        """
        Record this agent's decision for later analysis.

        Args:
            selection: The StrategySelection returned
            market_state: Market state at time of decision
            greeks: Greeks at time of decision
            pnl: P&L if trade closed (filled by learning loop later)
        """
        self.decision_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "strategy": selection.strategy_name,
            "action": selection.action_type.value,
            "confidence": selection.confidence,
            "regime": market_state.regime,
            "volatility": market_state.volatility,
            "greeks": greeks.to_dict(),
            "pnl": pnl,
            "metadata": selection.metadata
        })

    def _calculate_overall_elo(self) -> float:
        """Calculate overall Elo across regimes."""
        if not self.performance_by_regime:
            return 1600.0
        return sum(
            p.elo_rating for p in self.performance_by_regime.values()
        ) / len(self.performance_by_regime)

    def get_expertise_vector(self) -> Dict[str, float]:
        """
        Get expertise vector: agent's relative strength in each regime.

        Returns:
            Dict of {regime: relative_strength [0, 1]}
        """
        if not self.performance_by_regime:
            return {}

        # Normalize Elo ratings to [0, 1]
        min_elo = min(p.elo_rating for p in self.performance_by_regime.values())
        max_elo = max(p.elo_rating for p in self.performance_by_regime.values())

        elo_range = max_elo - min_elo
        if elo_range == 0:
            return {r: 0.5 for r in self.performance_by_regime.keys()}

        return {
            regime: (perf.elo_rating - min_elo) / elo_range
            for regime, perf in self.performance_by_regime.items()
        }

    def __repr__(self) -> str:
        return f"{self.name}(elo={self._calculate_overall_elo():.0f}, trades={sum(p.trade_count for p in self.performance_by_regime.values())})"
