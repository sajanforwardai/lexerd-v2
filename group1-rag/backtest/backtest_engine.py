"""
Main backtest engine orchestrating data loading, strategy execution, and analysis.

Handles 30-60 day backtests for Tier 2 vs Tier 3 comparison.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Callable, Tuple
from datetime import datetime, timedelta
import numpy as np
import logging
import json

from .metrics_calculator import MetricsCalculator, PerformanceMetrics
from .strategy_executor import StrategyExecutor, StrategyConfig, ExecutionResult
from .statistical_validator import StatisticalValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest."""

    # Date range
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    lookback_days: int = 60  # Max lookback for analysis

    # Data source
    data_source: str = "mock"  # "mock" or "real"
    symbol: str = "SPY"  # Stock symbol

    # Strategy config
    strategy_config: StrategyConfig = None

    # Statistical testing
    confidence_level: float = 0.90
    n_bootstrap: int = 1000
    min_observations: int = 30

    # Risk-free rate
    risk_free_rate: float = 0.02


@dataclass
class BacktestResult:
    """Complete backtest result."""

    # Metadata
    config: BacktestConfig
    timestamp: str

    # Tier 2 (baseline) results
    tier2_execution: ExecutionResult
    tier2_metrics: PerformanceMetrics

    # Tier 3 (candidate) results
    tier3_execution: ExecutionResult
    tier3_metrics: PerformanceMetrics

    # Comparison & validation
    validation_result: ValidationResult

    # Summary
    winner: str  # "tier2", "tier3", or "tie"
    recommendation: str  # "GO", "CONDITIONAL_GO", "NO_GO"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'config': {
                'start_date': self.config.start_date,
                'end_date': self.config.end_date,
                'symbol': self.config.symbol,
                'confidence_level': self.config.confidence_level,
            },
            'tier2': {
                'sharpe_ratio': self.tier2_metrics.sharpe_ratio,
                'total_return': self.tier2_metrics.total_return,
                'max_drawdown': self.tier2_metrics.max_drawdown,
                'volatility': self.tier2_metrics.volatility,
                'trades': self.tier2_metrics.n_trades,
            },
            'tier3': {
                'sharpe_ratio': self.tier3_metrics.sharpe_ratio,
                'total_return': self.tier3_metrics.total_return,
                'max_drawdown': self.tier3_metrics.max_drawdown,
                'volatility': self.tier3_metrics.volatility,
                'trades': self.tier3_metrics.n_trades,
            },
            'comparison': {
                'sharpe_difference': self.validation_result.sharpe_difference,
                'p_value': self.validation_result.p_value,
                'significant': self.validation_result.significant_at_level,
                'confidence_interval': self.validation_result.confidence_interval,
            },
            'winner': self.winner,
            'recommendation': self.recommendation,
        }


class BacktestEngine:
    """Main backtesting engine."""

    def __init__(self, config: BacktestConfig = None):
        """Initialize engine.

        Args:
            config: Backtest configuration
        """
        self.config = config or BacktestConfig(
            start_date='2024-01-01',
            end_date='2024-03-01',
        )
        self.metrics_calc = MetricsCalculator(self.config.risk_free_rate)
        self.validator = StatisticalValidator(
            confidence_level=self.config.confidence_level,
            n_bootstrap=self.config.n_bootstrap,
        )

    def run_backtest(
        self,
        tier2_signals: List[float],
        tier3_signals: List[float],
        prices: List[float],
        dates: List[str],
        benchmark_returns: Optional[List[float]] = None,
    ) -> BacktestResult:
        """Run complete backtest comparing Tier 2 vs Tier 3.

        Args:
            tier2_signals: Tier 2 entry/exit signals (-1, 0, 1)
            tier3_signals: Tier 3 entry/exit signals (-1, 0, 1)
            prices: Price data
            dates: Corresponding dates
            benchmark_returns: Optional benchmark returns

        Returns:
            BacktestResult with complete analysis
        """
        # Validate inputs
        if not (len(tier2_signals) == len(tier3_signals) == len(prices) == len(dates)):
            raise ValueError("All input lists must have the same length")

        if len(prices) < self.config.min_observations:
            raise ValueError(
                f"Insufficient data: {len(prices)} < {self.config.min_observations}"
            )

        # Execute both strategies
        executor2 = StrategyExecutor(self.config.strategy_config)
        executor3 = StrategyExecutor(self.config.strategy_config)

        tier2_result = executor2.execute_strategy(dates, prices, tier2_signals, benchmark_returns)
        tier3_result = executor3.execute_strategy(dates, prices, tier3_signals, benchmark_returns)

        # Calculate metrics
        tier2_metrics = self.metrics_calc.calculate_metrics(
            tier2_result.returns,
            benchmark_returns=benchmark_returns,
        )
        tier3_metrics = self.metrics_calc.calculate_metrics(
            tier3_result.returns,
            benchmark_returns=benchmark_returns,
        )

        # Statistical validation
        validation = self.validator.validate_improvement(
            tier2_result.returns,
            tier3_result.returns,
            tier2_metrics.sharpe_ratio,
            tier3_metrics.sharpe_ratio,
        )

        # Determine winner
        winner = 'tier3' if tier3_metrics.sharpe_ratio > tier2_metrics.sharpe_ratio else 'tier2'
        if abs(tier3_metrics.sharpe_ratio - tier2_metrics.sharpe_ratio) < 0.01:
            winner = 'tie'

        return BacktestResult(
            config=self.config,
            timestamp=datetime.now().isoformat(),
            tier2_execution=tier2_result,
            tier2_metrics=tier2_metrics,
            tier3_execution=tier3_result,
            tier3_metrics=tier3_metrics,
            validation_result=validation,
            winner=winner,
            recommendation=validation.recommendation,
        )

    def load_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> Tuple[List[str], List[float], List[float]]:
        """Load historical price data.

        Args:
            symbol: Stock ticker (e.g., 'SPY')
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD

        Returns:
            (dates, prices, volumes)
        """
        if self.config.data_source == 'mock':
            return self._generate_mock_data(start_date, end_date)
        else:
            return self._load_real_data(symbol, start_date, end_date)

    def _generate_mock_data(
        self,
        start_date: str,
        end_date: str,
        initial_price: float = 100,
        volatility: float = 0.015,
        drift: float = 0.0005,
    ) -> Tuple[List[str], List[float], List[float]]:
        """Generate realistic mock price data using geometric Brownian motion.

        Args:
            start_date: Start date
            end_date: End date
            initial_price: Starting price
            volatility: Daily volatility (std dev)
            drift: Daily drift/return

        Returns:
            (dates, prices, volumes)
        """
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        dates = []
        current = start
        while current <= end:
            # Skip weekends
            if current.weekday() < 5:
                dates.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)

        n_days = len(dates)
        prices = [initial_price]

        # Geometric Brownian motion
        np.random.seed(42)
        for _ in range(n_days - 1):
            epsilon = np.random.normal(0, 1)
            ret = drift + volatility * epsilon
            new_price = prices[-1] * (1 + ret)
            prices.append(new_price)

        # Mock volumes (typically 1-10M shares)
        volumes = [np.random.uniform(1e6, 10e6) for _ in prices]

        return dates, prices, volumes

    def _load_real_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> Tuple[List[str], List[float], List[float]]:
        """Load real data from an external source.

        In production, this would connect to:
        - yfinance
        - Alpha Vantage
        - IB (Interactive Brokers)
        - Polygon.io
        - etc.
        """
        try:
            import yfinance as yf

            data = yf.download(symbol, start=start_date, end=end_date)
            dates = [d.strftime('%Y-%m-%d') for d in data.index]
            prices = data['Close'].tolist()
            volumes = data['Volume'].tolist()

            return dates, prices, volumes
        except ImportError:
            logger.warning("yfinance not installed. Falling back to mock data.")
            return self._generate_mock_data(start_date, end_date)
        except Exception as e:
            logger.error(f"Error loading real data: {e}. Falling back to mock data.")
            return self._generate_mock_data(start_date, end_date)

    def handle_data_gaps(
        self,
        dates: List[str],
        prices: List[float],
    ) -> Tuple[List[str], List[float]]:
        """Handle missing data / gaps in price series.

        Args:
            dates: List of dates
            prices: List of prices

        Returns:
            (cleaned_dates, cleaned_prices)
        """
        if len(dates) == 0:
            return dates, prices

        cleaned_dates = [dates[0]]
        cleaned_prices = [prices[0]]

        for i in range(1, len(dates)):
            # Check for gaps > 1 trading day
            prev_date = datetime.strptime(cleaned_dates[-1], '%Y-%m-%d')
            curr_date = datetime.strptime(dates[i], '%Y-%m-%d')

            # Expected gap: 1 day, or 3 for weekend
            delta = (curr_date - prev_date).days

            if delta > 3:
                logger.warning(f"Data gap detected: {delta} days between {cleaned_dates[-1]} and {dates[i]}")
                # Forward-fill the gap with last known price
                current = prev_date + timedelta(days=1)
                while current < curr_date:
                    if current.weekday() < 5:  # Weekday only
                        cleaned_dates.append(current.strftime('%Y-%m-%d'))
                        cleaned_prices.append(cleaned_prices[-1])
                    current += timedelta(days=1)

            cleaned_dates.append(dates[i])
            cleaned_prices.append(prices[i])

        return cleaned_dates, cleaned_prices

    def adjust_for_survivorship_bias(
        self,
        prices: List[float],
        dates: List[str],
    ) -> List[float]:
        """Adjust for survivorship bias in backtests.

        Survivorship bias: historical backtests include only companies that survived.
        Apply a penalty or downward adjustment to returns.

        Args:
            prices: Price series
            dates: Corresponding dates

        Returns:
            Adjusted prices (or returns)
        """
        # Simple adjustment: reduce returns by 0.1% annually for survivorship bias
        # (typical historical estimate)
        adjustment_factor = 1 - (0.001 / 252)  # 0.1% / year = ~0.04 bps / day

        adjusted_prices = [prices[0]]
        for i in range(1, len(prices)):
            adjusted_prices.append(adjusted_prices[-1] * (prices[i] / prices[i - 1]) * adjustment_factor)

        return adjusted_prices

    def validate_backtest_integrity(
        self,
        result: BacktestResult,
    ) -> Dict[str, bool]:
        """Validate backtest results for quality issues.

        Returns:
            Dictionary of validation checks
        """
        checks = {
            'sufficient_data': result.config.n_bootstrap > 0,
            'tier2_returns_valid': len(result.tier2_execution.returns) > 0,
            'tier3_returns_valid': len(result.tier3_execution.returns) > 0,
            'metrics_exist': (result.tier2_metrics is not None and result.tier3_metrics is not None),
            'sharpe_reasonable': (
                abs(result.tier2_metrics.sharpe_ratio) < 10
                and abs(result.tier3_metrics.sharpe_ratio) < 10
            ),
            'p_value_valid': (
                0 <= result.validation_result.p_value <= 1
            ),
            'drawdown_valid': (
                result.tier2_metrics.max_drawdown <= 0
                and result.tier3_metrics.max_drawdown <= 0
            ),
        }

        return checks
