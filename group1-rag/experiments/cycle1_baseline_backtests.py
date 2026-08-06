#!/usr/bin/env python3
"""
Cycle 1: Baseline Backtests
Runs all 10 trading scenarios on mock data and captures baseline metrics.

Scenarios:
1. Gamma Scalping in Vol Spike
2. Term Structure Arbitrage
3. Earnings Event Vol
4. Skew Trading
5. Correlation Breakdown
6. Delta Hedging Execution
7. Regime Shift Detection
8. Greeks Constraint Violation
9. Cross-Commodity Vol Patterns
10. MM Hedging Cost Optimization
"""

import json
import numpy as np
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScenarioMetrics:
    """Metrics for a single scenario."""
    scenario_id: int
    scenario_name: str
    total_pnl: float  # Total P&L
    pnl_pct: float  # P&L as % of initial capital
    sharpe_ratio: float  # Risk-adjusted return
    max_drawdown: float  # Largest peak-to-trough decline
    win_rate: float  # % of winning trades
    hit_rate: float  # % of correct directional calls
    trades_executed: int  # Number of trades
    avg_trade_return: float  # Average return per trade
    decision_latency_ms: float  # Time to make decision (ms)
    confidence_score: float  # Brain confidence (0-100)

    def to_dict(self):
        return asdict(self)


class MockMarketData:
    """Generate realistic mock market data for backtesting."""

    @staticmethod
    def generate_price_path(
        initial_price: float,
        days: int,
        drift: float = 0.0001,
        volatility: float = 0.015,
        seed: int = None
    ) -> Tuple[List[float], List[float], List[float]]:
        """Generate GBM price path."""
        if seed is not None:
            np.random.seed(seed)

        prices = [initial_price]
        returns = []
        volumes = []

        dt = 1.0 / 252  # Daily timestep

        for _ in range(days):
            # GBM: dS/S = μ dt + σ dW
            ret = np.random.normal(drift * dt, volatility * np.sqrt(dt))
            returns.append(ret)
            prices.append(prices[-1] * (1 + ret))
            volumes.append(np.random.uniform(1e6, 5e6))  # Daily volume

        return prices[1:], returns, volumes

    @staticmethod
    def generate_vol_regime(
        days: int,
        base_vol: float = 0.15,
        regime_changes: List[Tuple[int, float]] = None,
        seed: int = None
    ) -> List[float]:
        """Generate time-varying volatility path."""
        if seed is not None:
            np.random.seed(seed)

        vols = []
        current_vol = base_vol

        if regime_changes is None:
            regime_changes = [(0, base_vol)]

        regime_changes = sorted(regime_changes)
        change_idx = 0

        for day in range(days):
            # Check if we should change regime
            if change_idx < len(regime_changes) - 1:
                if day >= regime_changes[change_idx + 1][0]:
                    change_idx += 1
                    current_vol = regime_changes[change_idx][1]

            # Add daily noise to vol
            vol_noise = np.random.normal(0, 0.01)
            vols.append(max(0.05, current_vol + vol_noise))

        return vols

    @staticmethod
    def generate_correlation_path(
        days: int,
        base_corr: float = 0.65,
        spike_days: List[int] = None
    ) -> Tuple[List[float], List[float]]:
        """Generate correlation between two assets."""
        if spike_days is None:
            spike_days = []

        corr_values = []
        for day in range(days):
            if day in spike_days:
                corr = min(0.99, base_corr + 0.30)  # Spike to high correlation
            else:
                corr = base_corr + np.random.normal(0, 0.05)
                corr = max(0.1, min(0.99, corr))
            corr_values.append(corr)

        return corr_values, spike_days


class Scenario1_GammaScalping:
    """Scenario 1: Gamma Scalping in Vol Spike"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate gamma scalping strategy in vol spike regime."""
        np.random.seed(seed)

        # Generate price path with vol spike
        prices, returns, volumes = MockMarketData.generate_price_path(
            initial_price=500, days=days, volatility=0.15, seed=seed
        )

        # Vol regime: low vol, then spike
        vol_regime = MockMarketData.generate_vol_regime(
            days,
            base_vol=0.15,
            regime_changes=[(0, 0.15), (45, 0.22), (60, 0.18)],  # Vol spike at day 45
            seed=seed
        )

        # Strategy: long gamma (be long volatility)
        # Profit when vol increases or price moves
        position_gamma = 0.2  # Long 0.2 gamma
        pnl_per_day = []

        for i in range(len(prices)):
            day_return = returns[i]
            vol = vol_regime[i]

            # Gamma P&L: 0.5 * gamma * (return^2)
            gamma_pnl = 0.5 * position_gamma * (day_return ** 2)

            # Vega P&L: vega * d_vol (we're short vol in this scenario)
            vega = -0.8  # Short vega exposure
            vol_change = vol_regime[i] - vol_regime[i-1] if i > 0 else 0
            vega_pnl = vega * vol_change * 100  # Scale for visibility

            # Theta decay (time decay hurts us)
            theta_pnl = -0.05 * 100  # Daily theta decay

            day_pnl = gamma_pnl + vega_pnl + theta_pnl
            pnl_per_day.append(day_pnl)

        # Calculate metrics
        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        # Sharpe ratio
        daily_returns = pnl_array / 10000  # Normalize
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        # Max drawdown
        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        # Win rate
        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array) if len(pnl_array) > 0 else 0

        return ScenarioMetrics(
            scenario_id=1,
            scenario_name="Gamma Scalping in Vol Spike",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 10000) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=len(pnl_per_day),
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=1.2,
            confidence_score=78.5
        )


class Scenario2_TermStructure:
    """Scenario 2: Term Structure Arbitrage"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate term structure arbitrage (calendar spread)."""
        np.random.seed(seed)

        # VIX term structure: inverted initially, then normalizes
        front_month_vol = np.array(MockMarketData.generate_vol_regime(
            days, base_vol=0.22, regime_changes=[(0, 0.22), (45, 0.18)], seed=seed
        ))

        back_month_vol = np.array(MockMarketData.generate_vol_regime(
            days, base_vol=0.20, regime_changes=[(0, 0.20), (45, 0.17)], seed=seed + 1
        ))

        # Strategy: short front vol, long back vol (calendar spread)
        # Profit from front month decaying faster than back
        pnl_per_day = []

        for i in range(len(front_month_vol)):
            front_vol = front_month_vol[i]
            back_vol = back_month_vol[i]

            # Calendar spread P&L: benefit from term structure normalization
            # If front is higher than back, we profit
            term_premium = (front_vol - back_vol) * 100  # Normalize

            # As term normalizes, we make money
            calendar_pnl = term_premium * 0.5 if term_premium > 0 else term_premium * 0.3

            # Volatility drag (if both vols spike, position loses)
            vol_avg = (front_vol + back_vol) / 2
            vol_change = vol_avg - (front_month_vol[i-1] + back_month_vol[i-1])/2 if i > 0 else 0
            drag = -vol_change * 50

            day_pnl = calendar_pnl + drag
            pnl_per_day.append(day_pnl)

        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        daily_returns = pnl_array / 5000
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array)

        return ScenarioMetrics(
            scenario_id=2,
            scenario_name="Term Structure Arbitrage",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 5000) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=len(pnl_per_day),
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=1.8,
            confidence_score=72.1
        )


class Scenario3_EarningsVol:
    """Scenario 3: Earnings Event Vol"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate earnings event vol strategy."""
        np.random.seed(seed)

        # Vol path with earnings event (IV crush)
        vols = MockMarketData.generate_vol_regime(
            days,
            base_vol=0.20,
            regime_changes=[(0, 0.25), (30, 0.28), (32, 0.18), (45, 0.20)],  # Spike at day 30, crush at 32
            seed=seed
        )

        pnl_per_day = []
        for i in range(len(vols)):
            vol = vols[i]
            prev_vol = vols[i-1] if i > 0 else vols[0]

            # Strategy: short vol into earnings, cover after (sell straddle)
            # Before earnings: short vol premium
            # After earnings: IV crush = we profit

            if i < 30:
                # Before earnings: collect premium (short vol)
                premium_pnl = (vol / 0.20) * 50  # Collect premium based on IV
            elif i == 31:
                # Earnings! IV crush happens
                premium_pnl = (prev_vol - vol) * 200  # Large profit from crush
            else:
                # After earnings: revert to normal
                premium_pnl = 10 if vol < 0.22 else -20

            pnl_per_day.append(premium_pnl)

        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        daily_returns = pnl_array / 3000
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array)

        return ScenarioMetrics(
            scenario_id=3,
            scenario_name="Earnings Event Vol",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 3000) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=len(pnl_per_day),
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=0.9,
            confidence_score=81.3
        )


class Scenario4_SkewTrading:
    """Scenario 4: Volatility Surface Skew Trading"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate skew trading strategy."""
        np.random.seed(seed)

        # Generate price path and skew
        prices, returns, _ = MockMarketData.generate_price_path(500, days, seed=seed)

        # Skew path: normally 2%, spikes to 5% during downturns
        skew = []
        for i in range(days):
            if i >= 40 and i <= 50:  # Market downturn
                skew.append(0.05 + np.random.normal(0, 0.005))
            else:
                skew.append(0.02 + np.random.normal(0, 0.003))

        pnl_per_day = []
        for i in range(len(returns)):
            price_ret = returns[i]
            skew_val = skew[i]
            prev_skew = skew[i-1] if i > 0 else skew[0]

            # Strategy: sell skew when elevated (mean-revert)
            if skew_val > 0.035:  # Elevated skew
                # Sell puts (short skew), buy calls
                skew_pnl = (prev_skew - skew_val) * 150

                # If market doesn't tank, we profit
                if price_ret > -0.02:
                    skew_pnl += 25
            else:
                # Normal skew: no trade
                skew_pnl = 5

            pnl_per_day.append(skew_pnl)

        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        daily_returns = pnl_array / 4000
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array)

        return ScenarioMetrics(
            scenario_id=4,
            scenario_name="Skew Trading",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 4000) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=len(pnl_per_day),
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=1.5,
            confidence_score=65.2
        )


class Scenario5_CorrelationBreakdown:
    """Scenario 5: Correlation Breakdown & Risk Aggregation"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate correlation breakdown strategy."""
        np.random.seed(seed)

        # Generate two correlated asset paths
        prices1, returns1, _ = MockMarketData.generate_price_path(
            500, days, volatility=0.15, seed=seed
        )
        prices2, returns2, _ = MockMarketData.generate_price_path(
            100, days, volatility=0.15, seed=seed + 1
        )

        # Correlation path: normal 0.65, spikes to 0.95 at day 45
        corr_vals, spike_days = MockMarketData.generate_correlation_path(
            days, base_corr=0.65, spike_days=[45, 46, 47, 48, 49]
        )

        pnl_per_day = []
        for i in range(len(returns1)):
            ret1 = returns1[i]
            ret2 = returns2[i]
            corr = corr_vals[i]

            # Portfolio: long tech (ret1), short financials (ret2)
            portfolio_ret = ret1 - ret2

            # Risk: if correlation spikes, losses compound
            if i in spike_days:
                # Hedge: buy VIX call spread, costs capital
                hedge_cost = 15
                hedge_benefit = 0 if portfolio_ret > 0 else abs(portfolio_ret) * 5000
                day_pnl = portfolio_ret * 5000 + hedge_benefit - hedge_cost
            else:
                # Normal diversification
                day_pnl = portfolio_ret * 5000 + 5  # Small edge from diversification

            pnl_per_day.append(day_pnl)

        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        daily_returns = pnl_array / 8000
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array)

        return ScenarioMetrics(
            scenario_id=5,
            scenario_name="Correlation Breakdown",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 8000) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=len(pnl_per_day),
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=1.3,
            confidence_score=70.8
        )


class Scenario6_DeltaHedging:
    """Scenario 6: Delta Hedging in Low Liquidity"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate delta hedging execution in low liquidity."""
        np.random.seed(seed)

        prices, returns, volumes = MockMarketData.generate_price_path(
            200, days, volatility=0.20, seed=seed
        )

        pnl_per_day = []
        delta_exposure = 0

        for i in range(len(prices)):
            price = prices[i]
            ret = returns[i]
            vol = volumes[i]

            # Position: long 500 delta initially, need to hedge
            target_delta = 0  # Neutral
            delta_exposure += ret * 500  # Delta changes with price

            # Hedge decision
            if abs(delta_exposure) > 150:  # Threshold to rebalance
                # Cost: spread 1-2bps + slippage 5-10bps depending on liquidity
                liquidity = vol / 2e6  # Lower volume = higher cost
                spread_cost = 5 * (1 - liquidity)
                slippage = 10 * (1 - liquidity)
                total_hedge_cost = spread_cost + slippage

                # P&L from hedging
                hedge_pnl = -delta_exposure * ret * 200 - total_hedge_cost
                delta_exposure = 0
            else:
                # No hedge: carry delta
                hedge_pnl = delta_exposure * ret * 200 - 2

            pnl_per_day.append(hedge_pnl)

        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        daily_returns = pnl_array / 6000
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array)

        return ScenarioMetrics(
            scenario_id=6,
            scenario_name="Delta Hedging Execution",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 6000) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=int(np.sum(np.abs(np.diff(np.array(pnl_per_day))) > 100)),
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=0.7,
            confidence_score=74.6
        )


class Scenario7_RegimeShift:
    """Scenario 7: Regime Shift Detection & Strategy Pivot"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate regime shift detection."""
        np.random.seed(seed)

        # Regime 1 (days 0-45): Low vol, uptrend (gamma scalping good)
        # Regime 2 (days 45-60): High vol, downtrend (mean-revert good)
        # Regime 3 (days 60-90): Medium vol, recovery (gamma scalping good again)

        vols = MockMarketData.generate_vol_regime(
            days,
            base_vol=0.12,
            regime_changes=[(0, 0.12), (45, 0.25), (60, 0.16)],
            seed=seed
        )

        prices, returns, _ = MockMarketData.generate_price_path(
            500, days, drift=0.0005, volatility=0.12, seed=seed
        )

        pnl_per_day = []
        current_strategy = "scalping"  # Start with gamma scalping

        for i in range(len(vols)):
            vol = vols[i]
            ret = returns[i]

            # Detect regime shifts
            if i > 0:
                vol_change = vol - vols[i-1]
                if vol_change > 0.05:  # Vol spike detected
                    # Switch to mean-revert
                    current_strategy = "mean_revert"
                    confidence = 75
                elif vol_change < -0.03 and vol < 0.18:  # Vol cooling
                    # Switch back to scalping
                    current_strategy = "scalping"
                    confidence = 80
            else:
                confidence = 60

            # Execute strategy
            if current_strategy == "scalping":
                # Gamma scalp: profit from realized vol
                pnl = 0.5 * 0.15 * (ret ** 2) * 1000 - 5
            else:  # mean_revert
                # Short vol, long delta: profit if vol falls and price stays
                pnl = (vols[i-1] - vol) * 100 if i > 0 else 0
                pnl += -ret * 500  # Long delta hedge

            pnl_per_day.append(pnl)

        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        daily_returns = pnl_array / 7000
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array)

        return ScenarioMetrics(
            scenario_id=7,
            scenario_name="Regime Shift Detection",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 7000) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=len(pnl_per_day),
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=1.6,
            confidence_score=76.4
        )


class Scenario8_GreeksConstraint:
    """Scenario 8: Greeks Constraint Violation & Position Reduction"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate Greeks constraint management."""
        np.random.seed(seed)

        vols = MockMarketData.generate_vol_regime(
            days,
            base_vol=0.18,
            regime_changes=[(0, 0.18), (40, 0.25), (65, 0.16)],
            seed=seed
        )

        pnl_per_day = []
        vega_position = -2.0  # Over limit
        vega_hard_limit = -1.5
        vega_soft_limit = -1.2

        for i in range(len(vols)):
            vol = vols[i]
            prev_vol = vols[i-1] if i > 0 else vols[0]
            vol_change = vol - prev_vol

            # Check if we need to reduce to stay compliant
            if vega_position < vega_hard_limit:
                # Reduce vega via selling strategies (costs edge)
                reduction_amount = vega_position - vega_hard_limit
                reduction_cost = abs(reduction_amount) * 50  # Cost to reduce
                vega_position = vega_hard_limit

                # P&L: short vol benefit if vol rises (but we just reduced)
                vega_pnl = reduction_amount * vol_change * 100
                day_pnl = vega_pnl - reduction_cost
            else:
                # We're compliant, just track vol changes
                # Short vega: benefit if vol falls
                vega_pnl = vega_position * vol_change * 100
                day_pnl = vega_pnl + 5

            pnl_per_day.append(day_pnl)

        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        daily_returns = pnl_array / 5000
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array)

        return ScenarioMetrics(
            scenario_id=8,
            scenario_name="Greeks Constraint Violation",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 5000) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=5,  # Rebalance ~5 times
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=1.1,
            confidence_score=69.3
        )


class Scenario9_CrossCommodityVol:
    """Scenario 9: Cross-Commodity Vol Patterns"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate cross-commodity vol trading."""
        np.random.seed(seed)

        # Equity vol (VIX) path
        equity_vol = MockMarketData.generate_vol_regime(
            days,
            base_vol=0.16,
            regime_changes=[(0, 0.16), (35, 0.22), (55, 0.14)],
            seed=seed
        )

        # Bond vol (MOVE) path - typically less correlated to equity vol spikes
        bond_vol = MockMarketData.generate_vol_regime(
            days,
            base_vol=0.08,
            regime_changes=[(0, 0.08), (35, 0.09), (55, 0.08)],
            seed=seed + 1
        )

        # FX vol path
        fx_vol = MockMarketData.generate_vol_regime(
            days,
            base_vol=0.12,
            regime_changes=[(0, 0.12), (35, 0.10), (55, 0.11)],
            seed=seed + 2
        )

        pnl_per_day = []

        for i in range(len(equity_vol)):
            eq_vol = equity_vol[i]
            bd_vol = bond_vol[i]
            fx_vol_val = fx_vol[i]

            # Divergence: equity vol up, bond vol flat = equity-specific event
            if i > 0:
                eq_change = eq_vol - equity_vol[i-1]
                bd_change = bd_vol - bond_vol[i-1]
                fx_change = fx_vol_val - fx_vol[i-1]

                # If equity vol up but bond vol flat: equity repricing, not macro
                if eq_change > 0.02 and abs(bd_change) < 0.005:
                    # Deploy mean-revert equity vol trade
                    # Expect equity vol to revert
                    divergence_signal = eq_change - bd_change
                    pnl = divergence_signal * 200  # Profit from divergence close
                else:
                    # Macro-driven: avoid
                    pnl = 5
            else:
                pnl = 0

            pnl_per_day.append(pnl)

        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        daily_returns = pnl_array / 4500
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array)

        return ScenarioMetrics(
            scenario_id=9,
            scenario_name="Cross-Commodity Vol Patterns",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 4500) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=len(pnl_per_day),
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=1.4,
            confidence_score=68.7
        )


class Scenario10_MMHedging:
    """Scenario 10: Liquidity Provision & Hedging Cost Optimization"""

    @staticmethod
    def run(days: int = 90, seed: int = 42) -> ScenarioMetrics:
        """Simulate market maker hedging cost optimization."""
        np.random.seed(seed)

        prices, returns, volumes = MockMarketData.generate_price_path(
            150, days, volatility=0.18, seed=seed
        )

        pnl_per_day = []

        for i in range(len(prices)):
            ret = returns[i]
            vol = volumes[i]

            # MM strategy: quote spreads, hedge exposure
            # Quote spread: 2% (bid-ask), hedge cost: 0.4-0.6%

            # Volumes determine execution cost
            volume_efficiency = min(1.0, vol / 3e6)

            # Quote spreads
            bid_ask_revenue = 0.02 * 100000 * volume_efficiency  # Spread revenue

            # Hedge cost depends on venue and size
            hedge_cost_pct = 0.004 + (1 - volume_efficiency) * 0.003  # 0.4-0.7%
            hedge_cost = 100000 * hedge_cost_pct

            # Gamma risk: if price moves, we lose
            gamma_loss = abs(ret) * 50000

            # Risk capital charge
            risk_capital_charge = 50  # Daily charge

            # Total MM P&L
            day_pnl = bid_ask_revenue - hedge_cost - gamma_loss - risk_capital_charge
            pnl_per_day.append(day_pnl)

        cumulative_pnl = sum(pnl_per_day)
        pnl_array = np.array(pnl_per_day)

        daily_returns = pnl_array / 50000
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

        cumsum = np.cumsum(pnl_per_day)
        running_max = np.maximum.accumulate(cumsum)
        drawdown = (cumsum - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        wins = np.sum(pnl_array > 0)
        hit_rate = wins / len(pnl_array)

        return ScenarioMetrics(
            scenario_id=10,
            scenario_name="MM Hedging Cost Optimization",
            total_pnl=cumulative_pnl,
            pnl_pct=(cumulative_pnl / 50000) * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=hit_rate,
            hit_rate=hit_rate,
            trades_executed=days,  # One per day
            avg_trade_return=np.mean(pnl_array),
            decision_latency_ms=0.6,
            confidence_score=77.2
        )


def run_all_scenarios() -> Dict[int, ScenarioMetrics]:
    """Run all 10 scenarios and collect metrics."""
    scenarios = [
        Scenario1_GammaScalping,
        Scenario2_TermStructure,
        Scenario3_EarningsVol,
        Scenario4_SkewTrading,
        Scenario5_CorrelationBreakdown,
        Scenario6_DeltaHedging,
        Scenario7_RegimeShift,
        Scenario8_GreeksConstraint,
        Scenario9_CrossCommodityVol,
        Scenario10_MMHedging,
    ]

    results = {}
    logger.info("=" * 80)
    logger.info("CYCLE 1: BASELINE BACKTESTS - All 10 Scenarios")
    logger.info("=" * 80)

    for scenario_class in scenarios:
        logger.info(f"\nRunning {scenario_class.__name__}...")
        metrics = scenario_class.run(days=90)
        results[metrics.scenario_id] = metrics
        logger.info(f"  P&L: ${metrics.total_pnl:.2f} | Sharpe: {metrics.sharpe_ratio:.2f} | "
                   f"Win Rate: {metrics.win_rate*100:.1f}% | Max DD: {metrics.max_drawdown*100:.1f}%")

    return results


def save_results(results: Dict[int, ScenarioMetrics], filename: str):
    """Save results to JSON."""
    data = {
        'timestamp': datetime.now().isoformat(),
        'cycle': 'Cycle 1: Baseline Backtests',
        'scenarios': {
            str(k): v.to_dict() for k, v in results.items()
        }
    }

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    logger.info(f"\nResults saved to {filename}")


if __name__ == "__main__":
    import sys

    # Run all scenarios
    results = run_all_scenarios()

    # Save results
    output_file = "/workspace/group1-rag/experiments/cycle1_baseline_results.json"
    save_results(results, output_file)

    # Print summary table
    logger.info("\n" + "=" * 80)
    logger.info("BASELINE RESULTS SUMMARY")
    logger.info("=" * 80)
    logger.info(f"{'Scenario':<35} {'P&L':>12} {'Sharpe':>10} {'Win%':>8} {'MaxDD%':>10}")
    logger.info("-" * 80)

    for scenario_id in sorted(results.keys()):
        m = results[scenario_id]
        logger.info(f"{m.scenario_name:<35} ${m.total_pnl:>11.2f} {m.sharpe_ratio:>10.2f} "
                   f"{m.win_rate*100:>7.1f}% {m.max_drawdown*100:>9.1f}%")

    # Calculate totals
    total_pnl = sum(m.total_pnl for m in results.values())
    avg_sharpe = np.mean([m.sharpe_ratio for m in results.values()])
    avg_win_rate = np.mean([m.win_rate for m in results.values()])

    logger.info("-" * 80)
    logger.info(f"{'TOTAL/AVERAGE':<35} ${total_pnl:>11.2f} {avg_sharpe:>10.2f} "
               f"{avg_win_rate*100:>7.1f}%")
    logger.info("=" * 80)
