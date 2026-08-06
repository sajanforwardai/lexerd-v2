"""
Strategy executor for running Tier 2 baseline and Tier 3 candidate strategies.

Handles position management, entry/exit signals, and transaction costs.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Tuple
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class PositionType(Enum):
    """Position types."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class StrategyConfig:
    """Configuration for strategy execution."""

    # Transaction costs
    entry_slippage: float = 0.001  # 10 bps entry slippage
    exit_slippage: float = 0.001  # 10 bps exit slippage
    commission_per_trade: float = 0.0005  # 5 bps per trade (entry + exit)

    # Position sizing
    position_size: float = 1.0  # % of portfolio per position
    max_leverage: float = 1.0  # Maximum leverage allowed

    # Risk management
    stop_loss: Optional[float] = None  # Stop loss %
    take_profit: Optional[float] = None  # Take profit %

    # Execution
    rebalance_frequency: str = "daily"  # "daily", "weekly", etc.
    hold_until_signal: bool = True  # Hold until exit signal or close


@dataclass
class Trade:
    """Represents a single trade."""
    date: str
    entry_price: float
    exit_price: float
    size: float
    position_type: PositionType
    entry_cost: float  # Slippage + commission at entry
    exit_cost: float  # Slippage + commission at exit
    return_pct: float
    profit: float


@dataclass
class ExecutionResult:
    """Result from strategy execution."""
    returns: List[float]  # Daily returns
    trades: List[Trade]
    positions: List[Dict]  # Position history
    cash_balance: float
    final_value: float
    total_transactions: int
    transaction_costs: float


class StrategyExecutor:
    """Execute strategies with realistic transaction costs and position management."""

    def __init__(self, config: StrategyConfig = None, initial_capital: float = 100000):
        """Initialize executor.

        Args:
            config: Strategy configuration
            initial_capital: Starting portfolio value
        """
        self.config = config or StrategyConfig()
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital

    def execute_strategy(
        self,
        dates: List[str],
        prices: List[float],
        signals: List[float],  # -1, 0, or 1 for short, flat, long
        benchmark_returns: Optional[List[float]] = None,
    ) -> ExecutionResult:
        """Execute strategy based on signals.

        Args:
            dates: List of dates
            prices: List of prices
            signals: Entry/exit signals (-1: short, 0: flat, 1: long)
            benchmark_returns: Optional benchmark returns for tracking

        Returns:
            ExecutionResult with returns, trades, and position history
        """
        if len(dates) != len(prices) or len(dates) != len(signals):
            raise ValueError("dates, prices, and signals must have same length")

        returns = []
        trades = []
        positions = []
        cash_balance = self.initial_capital
        current_position = 0
        entry_price = None
        entry_date = None
        trades_total_costs = 0

        for i in range(1, len(dates)):
            prev_price = prices[i - 1]
            curr_price = prices[i]
            signal = signals[i]

            day_return = 0
            position_changed = False

            # Check for exit signal
            if current_position != 0 and signal == 0:
                # Exit position
                exit_cost = self._calculate_transaction_cost(
                    curr_price, self.config.exit_slippage,
                    self.config.commission_per_trade
                )
                trades_total_costs += exit_cost

                if current_position > 0:
                    # Long exit
                    profit = (curr_price - entry_price - exit_cost) * abs(current_position)
                    return_pct = (curr_price - entry_price - exit_cost) / entry_price
                else:
                    # Short exit
                    profit = (entry_price - curr_price - exit_cost) * abs(current_position)
                    return_pct = (entry_price - curr_price - exit_cost) / entry_price

                trades.append(Trade(
                    date=dates[i],
                    entry_price=entry_price,
                    exit_price=curr_price,
                    size=abs(current_position),
                    position_type=PositionType.LONG if current_position > 0 else PositionType.SHORT,
                    entry_cost=entry_price * self.config.entry_slippage + self.config.commission_per_trade * 2,
                    exit_cost=exit_cost,
                    return_pct=return_pct,
                    profit=profit,
                ))

                cash_balance += profit + (current_position * entry_price)
                current_position = 0
                position_changed = True

            # Check for entry signal
            elif current_position == 0 and signal != 0:
                # Enter new position
                entry_cost = self._calculate_transaction_cost(
                    curr_price, self.config.entry_slippage,
                    self.config.commission_per_trade
                )
                trades_total_costs += entry_cost

                position_size = int(self.config.position_size * cash_balance / curr_price)
                current_position = position_size if signal > 0 else -position_size
                entry_price = curr_price + (entry_cost if signal > 0 else -entry_cost)
                entry_date = dates[i]
                cash_balance -= current_position * curr_price
                position_changed = True

            # Calculate daily P&L
            if current_position != 0:
                if current_position > 0:
                    day_return = (curr_price - prev_price) / prev_price * self.config.position_size
                else:
                    day_return = -(curr_price - prev_price) / prev_price * self.config.position_size
            else:
                # In cash: earn risk-free rate
                day_return = 0.02 / 252  # 2% annual rate

            returns.append(day_return)
            self.portfolio_value *= (1 + day_return)

            # Record position
            positions.append({
                'date': dates[i],
                'position': current_position,
                'price': curr_price,
                'portfolio_value': self.portfolio_value,
            })

        final_value = cash_balance + current_position * prices[-1]

        return ExecutionResult(
            returns=returns,
            trades=trades,
            positions=positions,
            cash_balance=cash_balance,
            final_value=final_value,
            total_transactions=len(trades),
            transaction_costs=trades_total_costs,
        )

    def _calculate_transaction_cost(
        self,
        price: float,
        slippage: float,
        commission: float,
    ) -> float:
        """Calculate total transaction cost."""
        slippage_cost = price * slippage
        return slippage_cost + commission

    def generate_signals(
        self,
        prices: List[float],
        signal_func: Callable[[List[float], int], float],
    ) -> List[float]:
        """Generate entry/exit signals using custom function.

        Args:
            prices: List of prices
            signal_func: Function(prices, index) -> signal (-1, 0, or 1)

        Returns:
            List of signals
        """
        signals = []
        for i in range(len(prices)):
            signal = signal_func(prices, i)
            # Clamp to [-1, 0, 1]
            signal = max(-1, min(1, signal))
            signals.append(signal)

        return signals

    def apply_risk_management(
        self,
        trades: List[Trade],
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> List[Trade]:
        """Apply stop-loss and take-profit adjustments to trades.

        Args:
            trades: List of trades
            stop_loss: Stop loss % (e.g., 0.05 = 5%)
            take_profit: Take profit % (e.g., 0.10 = 10%)

        Returns:
            Adjusted list of trades
        """
        adjusted_trades = []

        for trade in trades:
            return_pct = trade.return_pct

            # Check stop loss
            if stop_loss and return_pct < -stop_loss:
                return_pct = -stop_loss

            # Check take profit
            if take_profit and return_pct > take_profit:
                return_pct = take_profit

            # Update trade
            adjusted_trade = Trade(
                date=trade.date,
                entry_price=trade.entry_price,
                exit_price=trade.entry_price * (1 + return_pct),
                size=trade.size,
                position_type=trade.position_type,
                entry_cost=trade.entry_cost,
                exit_cost=trade.exit_cost,
                return_pct=return_pct,
                profit=trade.entry_price * trade.size * return_pct,
            )
            adjusted_trades.append(adjusted_trade)

        return adjusted_trades
