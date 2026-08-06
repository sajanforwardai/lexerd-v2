"""
P&L Tracking and Aggregation System

Tracks daily trade executions and aggregates P&L by multiple dimensions:
- Strategy (tier2_baseline, tier3_candidate, etc.)
- Instrument (SPY, QQQ, IWM, etc.)
- Regime (normal, spike, breakdown)
- Trader/Book (optional multi-book aggregation)

Real-time Greeks exposure tracking at close.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from enum import Enum
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class Regime(Enum):
    """Market regime classification."""
    NORMAL = "normal"
    VOLATILITY_SPIKE = "volatility_spike"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    TAIL_RISK = "tail_risk"


@dataclass
class GreeksSnapshot:
    """Greeks exposure at position close."""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TradeExecution:
    """Single trade execution record."""
    date: str  # YYYY-MM-DD
    strategy: str  # tier2_baseline, tier3_candidate, etc.
    instrument: str  # SPY, QQQ, etc.
    entry_price: float
    exit_price: float
    entry_time: str  # HH:MM:SS or datetime string
    exit_time: str
    quantity: int
    side: str  # "long" or "short"
    realized_pnl: float  # P&L from closed position
    unrealized_pnl: float = 0.0  # P&L from open position
    entry_cost: float = 0.0  # Slippage + commission at entry
    exit_cost: float = 0.0  # Slippage + commission at exit
    greeks_entry: Optional[GreeksSnapshot] = None
    greeks_exit: Optional[GreeksSnapshot] = None
    regime: str = Regime.NORMAL.value
    book_id: str = "default"


@dataclass
class DailyPnLSummary:
    """Daily P&L aggregation."""
    date: str
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    gross_profit: float  # Sum of winning trades
    gross_loss: float  # Sum of losing trades
    winning_trades: int
    losing_trades: int
    trade_count: int
    avg_win: float
    avg_loss: float
    win_rate: float
    profit_factor: float  # Gross profit / abs(gross loss)


@dataclass
class GreeksAggregate:
    """Greeks exposure aggregated by dimension."""
    dimension_name: str  # "strategy", "instrument", or "regime"
    dimension_value: str  # e.g., "tier2_baseline" or "SPY"
    delta_exposure: float
    gamma_exposure: float
    vega_exposure: float
    theta_exposure: float
    rho_exposure: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PnLTracker:
    """Track P&L and Greeks across multiple dimensions."""

    def __init__(self):
        """Initialize P&L tracker."""
        self.trades: List[TradeExecution] = []
        self.daily_summaries: Dict[str, DailyPnLSummary] = {}
        self.greeks_by_strategy: Dict[str, GreeksAggregate] = {}
        self.greeks_by_instrument: Dict[str, GreeksAggregate] = {}
        self.greeks_by_regime: Dict[str, GreeksAggregate] = {}

    def record_trade(self, trade: TradeExecution) -> None:
        """Record a trade execution.

        Args:
            trade: TradeExecution with all required fields
        """
        # Validate trade
        if trade.exit_price <= 0 or trade.entry_price <= 0:
            raise ValueError("Prices must be positive")
        if trade.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if trade.side not in ["long", "short"]:
            raise ValueError("Side must be 'long' or 'short'")

        # Calculate realized P&L if closed
        if trade.realized_pnl == 0:
            if trade.side == "long":
                trade.realized_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
            else:
                trade.realized_pnl = (trade.entry_price - trade.exit_price) * trade.quantity

        # Deduct transaction costs
        total_costs = trade.entry_cost + trade.exit_cost
        trade.realized_pnl -= total_costs

        self.trades.append(trade)
        logger.info(
            f"Recorded trade: {trade.strategy} {trade.instrument} "
            f"{trade.side} P&L: ${trade.realized_pnl:.2f}"
        )

    def record_trades_batch(self, trades: List[TradeExecution]) -> None:
        """Record multiple trades at once.

        Args:
            trades: List of TradeExecution
        """
        for trade in trades:
            self.record_trade(trade)

    def calculate_daily_summary(self, summary_date: str) -> DailyPnLSummary:
        """Calculate daily P&L summary for given date.

        Args:
            summary_date: YYYY-MM-DD

        Returns:
            DailyPnLSummary with aggregated daily metrics
        """
        day_trades = [t for t in self.trades if t.date == summary_date]

        if not day_trades:
            return DailyPnLSummary(
                date=summary_date,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                total_pnl=0.0,
                gross_profit=0.0,
                gross_loss=0.0,
                winning_trades=0,
                losing_trades=0,
                trade_count=0,
                avg_win=0.0,
                avg_loss=0.0,
                win_rate=0.0,
                profit_factor=0.0,
            )

        realized_pnl = sum(t.realized_pnl for t in day_trades)
        unrealized_pnl = sum(t.unrealized_pnl for t in day_trades)
        total_pnl = realized_pnl + unrealized_pnl

        # Winning/losing trades
        wins = [t.realized_pnl for t in day_trades if t.realized_pnl > 0]
        losses = [t.realized_pnl for t in day_trades if t.realized_pnl < 0]

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = sum(losses) if losses else 0.0
        winning_trades = len(wins)
        losing_trades = len(losses)

        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
        avg_loss = abs(gross_loss) / losing_trades if losing_trades > 0 else 0.0
        win_rate = winning_trades / len(day_trades) if day_trades else 0.0
        profit_factor = gross_profit / abs(gross_loss) if gross_loss != 0 else 0.0

        summary = DailyPnLSummary(
            date=summary_date,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            gross_profit=gross_profit,
            gross_loss=abs(gross_loss),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            trade_count=len(day_trades),
            avg_win=avg_win,
            avg_loss=avg_loss,
            win_rate=win_rate,
            profit_factor=profit_factor,
        )

        self.daily_summaries[summary_date] = summary
        return summary

    def aggregate_by_strategy(self, date_range: Tuple[str, str]) -> Dict[str, Dict]:
        """Aggregate P&L by strategy for date range.

        Args:
            date_range: Tuple of (start_date, end_date) as YYYY-MM-DD

        Returns:
            Dict mapping strategy -> aggregated metrics
        """
        start_date, end_date = date_range
        filtered_trades = [
            t for t in self.trades
            if start_date <= t.date <= end_date
        ]

        result = {}
        for strategy in set(t.strategy for t in filtered_trades):
            strategy_trades = [t for t in filtered_trades if t.strategy == strategy]
            result[strategy] = self._aggregate_trades(strategy_trades)

        return result

    def aggregate_by_instrument(self, date_range: Tuple[str, str]) -> Dict[str, Dict]:
        """Aggregate P&L by instrument for date range.

        Args:
            date_range: Tuple of (start_date, end_date) as YYYY-MM-DD

        Returns:
            Dict mapping instrument -> aggregated metrics
        """
        start_date, end_date = date_range
        filtered_trades = [
            t for t in self.trades
            if start_date <= t.date <= end_date
        ]

        result = {}
        for instrument in set(t.instrument for t in filtered_trades):
            inst_trades = [t for t in filtered_trades if t.instrument == instrument]
            result[instrument] = self._aggregate_trades(inst_trades)

        return result

    def aggregate_by_regime(self, date_range: Tuple[str, str]) -> Dict[str, Dict]:
        """Aggregate P&L by regime for date range.

        Args:
            date_range: Tuple of (start_date, end_date) as YYYY-MM-DD

        Returns:
            Dict mapping regime -> aggregated metrics
        """
        start_date, end_date = date_range
        filtered_trades = [
            t for t in self.trades
            if start_date <= t.date <= end_date
        ]

        result = {}
        for regime in set(t.regime for t in filtered_trades):
            regime_trades = [t for t in filtered_trades if t.regime == regime]
            result[regime] = self._aggregate_trades(regime_trades)

        return result

    def _aggregate_trades(self, trades: List[TradeExecution]) -> Dict:
        """Aggregate metrics for a list of trades.

        Args:
            trades: List of TradeExecution

        Returns:
            Dict with aggregated metrics
        """
        if not trades:
            return {
                "trade_count": 0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "total_pnl": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "winning_trades": 0,
                "losing_trades": 0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
            }

        realized_pnl = sum(t.realized_pnl for t in trades)
        unrealized_pnl = sum(t.unrealized_pnl for t in trades)
        total_pnl = realized_pnl + unrealized_pnl

        wins = [t.realized_pnl for t in trades if t.realized_pnl > 0]
        losses = [t.realized_pnl for t in trades if t.realized_pnl < 0]

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = sum(losses) if losses else 0.0

        return {
            "trade_count": len(trades),
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "gross_profit": gross_profit,
            "gross_loss": abs(gross_loss),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "avg_win": gross_profit / len(wins) if wins else 0.0,
            "avg_loss": abs(gross_loss) / len(losses) if losses else 0.0,
            "win_rate": len(wins) / len(trades) if trades else 0.0,
            "profit_factor": gross_profit / abs(gross_loss) if gross_loss != 0 else 0.0,
        }

    def get_daily_greeks(
        self,
        strategy: Optional[str] = None,
        instrument: Optional[str] = None,
    ) -> GreeksAggregate:
        """Aggregate Greeks exposure at end of day.

        Args:
            strategy: Optional strategy filter
            instrument: Optional instrument filter

        Returns:
            GreeksAggregate with exposure metrics
        """
        filtered_trades = self.trades
        if strategy:
            filtered_trades = [t for t in filtered_trades if t.strategy == strategy]
        if instrument:
            filtered_trades = [t for t in filtered_trades if t.instrument == instrument]

        # Use most recent Greeks snapshot
        latest_greeks = None
        for trade in reversed(filtered_trades):
            if trade.greeks_exit:
                latest_greeks = trade.greeks_exit
                break

        if latest_greeks:
            return GreeksAggregate(
                dimension_name="strategy" if strategy else "instrument",
                dimension_value=strategy or instrument or "all",
                delta_exposure=latest_greeks.delta,
                gamma_exposure=latest_greeks.gamma,
                vega_exposure=latest_greeks.vega,
                theta_exposure=latest_greeks.theta,
                rho_exposure=latest_greeks.rho,
            )

        return GreeksAggregate(
            dimension_name="strategy" if strategy else "instrument",
            dimension_value=strategy or instrument or "all",
            delta_exposure=0.0,
            gamma_exposure=0.0,
            vega_exposure=0.0,
            theta_exposure=0.0,
            rho_exposure=0.0,
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Convert trades to pandas DataFrame for analysis.

        Returns:
            DataFrame with all trades
        """
        data = []
        for trade in self.trades:
            data.append({
                "date": trade.date,
                "strategy": trade.strategy,
                "instrument": trade.instrument,
                "side": trade.side,
                "quantity": trade.quantity,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "entry_cost": trade.entry_cost,
                "exit_cost": trade.exit_cost,
                "realized_pnl": trade.realized_pnl,
                "unrealized_pnl": trade.unrealized_pnl,
                "regime": trade.regime,
                "book_id": trade.book_id,
            })

        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_summary_report(self, start_date: str, end_date: str) -> Dict:
        """Generate comprehensive summary report for date range.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD

        Returns:
            Dict with multi-dimensional analysis
        """
        return {
            "period": {"start": start_date, "end": end_date},
            "by_strategy": self.aggregate_by_strategy((start_date, end_date)),
            "by_instrument": self.aggregate_by_instrument((start_date, end_date)),
            "by_regime": self.aggregate_by_regime((start_date, end_date)),
            "total": self._aggregate_trades(self.trades),
        }
