"""
Financial metrics calculator for backtest analysis.

Computes Sharpe ratio, Sortino ratio, max drawdown, Information Ratio,
and p-values for strategy comparison.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for calculated performance metrics."""

    total_return: float  # Total return %
    annual_return: float  # Annualized return %
    sharpe_ratio: float  # Risk-adjusted return (daily-based)
    sortino_ratio: float  # Downside risk-adjusted return
    max_drawdown: float  # Maximum peak-to-trough %
    calmar_ratio: float  # Annual return / max drawdown
    win_rate: float  # % of positive days
    avg_win: float  # Average daily win %
    avg_loss: float  # Average daily loss %
    profit_factor: float  # Gross profit / gross loss
    volatility: float  # Daily volatility %

    # Additional metrics for comparison
    information_ratio: Optional[float] = None
    excess_return: Optional[float] = None  # vs benchmark
    tracking_error: Optional[float] = None  # vs benchmark

    # Statistical
    n_trades: int = 0
    n_days: int = 0
    sharpe_std_error: Optional[float] = None  # For confidence intervals


class MetricsCalculator:
    """Calculate financial performance metrics from returns data."""

    RISK_FREE_RATE = 0.02  # 2% annual risk-free rate
    TRADING_DAYS_PER_YEAR = 252

    def __init__(self, risk_free_rate: float = None):
        """Initialize calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
        """
        if risk_free_rate is not None:
            self.RISK_FREE_RATE = risk_free_rate

    def calculate_metrics(
        self,
        returns: List[float],
        trades: Optional[List[Tuple[float, bool]]] = None,
        benchmark_returns: Optional[List[float]] = None,
    ) -> PerformanceMetrics:
        """Calculate all metrics from daily returns.

        Args:
            returns: List of daily returns (as decimals, e.g., 0.01 = 1%)
            trades: List of (return, is_win) tuples for trade-level analysis
            benchmark_returns: Benchmark returns for Information Ratio calculation

        Returns:
            PerformanceMetrics dataclass with all calculated metrics
        """
        returns = np.array(returns)
        n_days = len(returns)

        # Basic calculations
        total_return = np.sum(returns)
        annual_return = self._annualize_return(total_return, n_days)
        volatility = np.std(returns) if n_days > 1 else 0

        # Ratio-based metrics
        sharpe = self._calculate_sharpe(returns)
        sortino = self._calculate_sortino(returns)
        max_dd, drawdown_duration = self._calculate_max_drawdown(returns)
        calmar = self._calculate_calmar(annual_return, max_dd)

        # Trade statistics
        win_rate, avg_win, avg_loss, pf = self._calculate_trade_stats(
            returns, trades
        )

        # Information Ratio (if benchmark provided)
        ir = None
        excess_return = None
        tracking_error = None
        if benchmark_returns is not None:
            excess, te = self._calculate_tracking_metrics(returns, benchmark_returns)
            excess_return = excess
            tracking_error = te
            ir = excess / te if te > 0 else 0

        # Sharpe standard error for significance testing
        sharpe_se = self._calculate_sharpe_std_error(returns)

        return PerformanceMetrics(
            total_return=total_return * 100,
            annual_return=annual_return * 100,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd * 100,
            calmar_ratio=calmar,
            win_rate=win_rate,
            avg_win=avg_win * 100,
            avg_loss=avg_loss * 100,
            profit_factor=pf,
            volatility=volatility * 100,
            information_ratio=ir,
            excess_return=excess_return * 100 if excess_return else None,
            tracking_error=tracking_error * 100 if tracking_error else None,
            n_trades=len(trades) if trades else 0,
            n_days=n_days,
            sharpe_std_error=sharpe_se,
        )

    def _annualize_return(self, total_return: float, n_days: int) -> float:
        """Annualize a return over N days."""
        if n_days == 0:
            return 0
        years = n_days / self.TRADING_DAYS_PER_YEAR
        return (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    def _calculate_sharpe(self, returns: np.ndarray, periods_per_year: int = 252) -> float:
        """Calculate Sharpe ratio.

        Sharpe = (annual_return - risk_free) / annual_volatility
        """
        if len(returns) == 0:
            return 0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Annualize
        annual_return = mean_return * periods_per_year

        if std_return == 0 or std_return < 1e-10:
            # No volatility - treat as flat (return 0)
            return 0

        annual_vol = std_return * np.sqrt(periods_per_year)

        sharpe = (annual_return - self.RISK_FREE_RATE) / annual_vol
        return sharpe

    def _calculate_sortino(self, returns: np.ndarray, periods_per_year: int = 252) -> float:
        """Calculate Sortino ratio (downside risk-adjusted return).

        Only penalizes downside volatility.
        """
        if len(returns) == 0:
            return 0

        mean_return = np.mean(returns)
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0:
            # No negative returns - infinite Sortino
            return mean_return * periods_per_year / 0.001

        downside_vol = np.std(downside_returns)

        if downside_vol == 0:
            return float('inf') if mean_return > 0 else 0

        annual_return = mean_return * periods_per_year
        annual_downside_vol = downside_vol * np.sqrt(periods_per_year)

        sortino = (annual_return - self.RISK_FREE_RATE) / annual_downside_vol
        return sortino

    def _calculate_max_drawdown(self, returns: np.ndarray) -> Tuple[float, int]:
        """Calculate maximum drawdown and its duration.

        Returns:
            Tuple of (max_drawdown, duration_in_days)
        """
        if len(returns) == 0:
            return 0, 0

        cumulative = np.cumprod(1 + returns) - 1
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / (1 + running_max)

        max_dd = np.min(drawdown)
        dd_idx = np.argmin(drawdown)

        # Find duration (from peak to recovery or end)
        duration = 1
        if dd_idx > 0:
            peak_idx = np.argmax(cumulative[:dd_idx])
        else:
            peak_idx = 0

        for i in range(dd_idx + 1, len(drawdown)):
            if drawdown[i] >= 0.99 * max_dd:  # Recovery threshold
                duration = i - peak_idx + 1
                break
            duration += 1

        return max_dd, duration

    def _calculate_calmar(self, annual_return: float, max_drawdown: float) -> float:
        """Calculate Calmar ratio (return / max drawdown)."""
        if max_drawdown >= 0 or abs(max_drawdown) < 0.001:
            return 0
        return annual_return / abs(max_drawdown)

    def _calculate_trade_stats(
        self,
        returns: np.ndarray,
        trades: Optional[List[Tuple[float, bool]]] = None,
    ) -> Tuple[float, float, float, float]:
        """Calculate win rate, avg win, avg loss, profit factor.

        Returns:
            (win_rate, avg_win, avg_loss, profit_factor)
        """
        if trades and len(trades) > 0:
            # Use provided trades
            wins = [t[0] for t in trades if t[1]]
            losses = [t[0] for t in trades if not t[1]]

            win_rate = len(wins) / len(trades) if trades else 0
            avg_win = np.mean(wins) if wins else 0
            avg_loss = np.mean(losses) if losses else 0

            gross_profit = sum(wins) if wins else 0
            gross_loss = abs(sum(losses)) if losses else 0
            pf = gross_profit / gross_loss if gross_loss > 0 else 0

            return win_rate, avg_win, avg_loss, pf

        # Calculate from daily returns
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]

        win_rate = len(positive_returns) / len(returns) if len(returns) > 0 else 0
        avg_win = np.mean(positive_returns) if len(positive_returns) > 0 else 0
        avg_loss = np.mean(negative_returns) if len(negative_returns) > 0 else 0

        gross_profit = np.sum(positive_returns) if len(positive_returns) > 0 else 0
        gross_loss = abs(np.sum(negative_returns)) if len(negative_returns) > 0 else 0
        pf = gross_profit / gross_loss if gross_loss > 0 else 0

        return win_rate, avg_win, avg_loss, pf

    def _calculate_tracking_metrics(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
    ) -> Tuple[float, float]:
        """Calculate excess return and tracking error vs benchmark.

        Returns:
            (excess_return, tracking_error)
        """
        if len(returns) != len(benchmark_returns):
            logger.warning(f"Returns length {len(returns)} != benchmark length {len(benchmark_returns)}")
            return 0, 0

        excess = returns - benchmark_returns
        excess_return = np.sum(excess)
        tracking_error = np.std(excess) * np.sqrt(self.TRADING_DAYS_PER_YEAR)

        return excess_return, tracking_error

    def _calculate_sharpe_std_error(self, returns: np.ndarray) -> float:
        """Calculate standard error of Sharpe ratio.

        Used for significance testing via bootstrap or t-tests.
        """
        if len(returns) < 2:
            return 0

        # Simplified: SE = sqrt((1 + 0.5*SR^2) / n) where SR is Sharpe
        sharpe = self._calculate_sharpe(returns)
        n = len(returns)

        se = np.sqrt((1 + 0.5 * sharpe**2) / n)
        return se

    def calculate_sharpe_p_value(
        self,
        strategy_sharpe: float,
        baseline_sharpe: float,
        strategy_se: float,
        n_obs: int,
    ) -> float:
        """Calculate p-value for Sharpe difference using t-test.

        H0: strategy_sharpe <= baseline_sharpe
        H1: strategy_sharpe > baseline_sharpe (one-tailed)

        Args:
            strategy_sharpe: Strategy's Sharpe ratio
            baseline_sharpe: Baseline's Sharpe ratio
            strategy_se: Standard error of strategy Sharpe
            n_obs: Number of observations

        Returns:
            P-value (lower = more significant)
        """
        from scipy import stats

        sharpe_diff = strategy_sharpe - baseline_sharpe
        # Conservative: use strategy SE for difference
        se_diff = strategy_se

        if se_diff == 0:
            return 1.0 if sharpe_diff <= 0 else 0.0

        t_stat = sharpe_diff / se_diff
        # One-tailed test: is strategy > baseline?
        p_value = 1 - stats.t.cdf(t_stat, n_obs - 1)

        return max(0, min(1, p_value))
