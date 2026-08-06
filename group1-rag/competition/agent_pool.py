"""
Agent Pool: Specialized Trading Strategy Agents
================================================

Concrete implementations of 5+ specialized strategy agents, each optimized
for particular market regimes and trading approaches.

Pool Components:
1. GammaScalpingAgent - optimized for low-vol, high-gamma regimes
2. VegaArbitrageAgent - vol surface mispricings and term structure
3. MeanReversionAgent - skew mean reversion when elevated
4. EventDrivenAgent - earnings, economic events, volatility spikes
5. MomentumAgent - trend-following, regime persistence bets
6. CorrelationAgent - correlation regime changes
7. LiquidityProvisionAgent - market microstructure, order flow
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from strategy_agent import (
    StrategyAgent, ActionType, GreeksSnapshot, MarketState,
    StrategySelection, AgentPerformance
)

logger = logging.getLogger(__name__)


class GammaScalpingAgent(StrategyAgent):
    """
    Gamma Scalping Agent

    Specializes in low-volatility, high-gamma environments.
    Executes delta-hedged option trades that profit from realized volatility
    exceeding implied volatility.

    Optimized Regimes:
    - bull_low_vol, bear_low_vol: high gamma profitability
    - Normal regimes: baseline strategy

    Decision Logic:
    - High gamma (>0.3) and low vol (<15%) → strong signal
    - Theta decay helps in these conditions
    - Vega negative (short vol): use for hedging
    """

    def __init__(self):
        super().__init__("GammaScalpingAgent")
        self.optimized_regimes = ["bull_low_vol", "bear_low_vol", "normal"]

    def select_action(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> StrategySelection:
        """Select gamma scalping action."""

        # Base confidence from regime match
        regime_confidence = 0.85 if regime in self.optimized_regimes else 0.55

        # Gamma signal: scalp high gamma
        gamma_signal = min(greeks.gamma / 0.5, 1.0)  # Normalize to 0-0.5 range
        gamma_confidence = 0.9 if gamma_signal > 0.6 else 0.7 if gamma_signal > 0.3 else 0.4

        # Vol signal: lower vol is better for gamma scalping
        vol_signal = 1.0 - market_state.volatility  # Higher when vol is low
        vol_confidence = 0.85 if vol_signal > 0.7 else 0.5 if vol_signal > 0.4 else 0.2

        # Theta signal: positive theta contributes
        theta_signal = max(greeks.theta / 0.1, 0.0)  # Normalize
        theta_confidence = 0.7 if theta_signal > 0.5 else 0.4

        # Combine signals
        combined_confidence = (
            regime_confidence * 0.3 +
            gamma_confidence * 0.35 +
            vol_confidence * 0.2 +
            theta_confidence * 0.15
        )

        # Determine action
        if combined_confidence > 0.7 and gamma_signal > 0.4:
            action = ActionType.LONG
            exposure = min(gamma_signal, 0.8)  # Cap exposure
        elif combined_confidence > 0.6:
            action = ActionType.HEDGE
            exposure = 0.3
        else:
            action = ActionType.NEUTRAL
            exposure = 0.0

        rationale = (
            f"Gamma scalping in {regime}: "
            f"gamma={greeks.gamma:.3f}, vol={market_state.volatility:.2%}, "
            f"theta={greeks.theta:.3f}. "
            f"{'Favorable conditions' if combined_confidence > 0.7 else 'Suboptimal conditions'}"
        )

        return StrategySelection(
            strategy_name="gamma_scalping",
            action_type=action,
            confidence=combined_confidence,
            rationale=rationale,
            target_exposure=exposure,
            metadata={
                "gamma_signal": float(gamma_signal),
                "vol_signal": float(vol_signal),
                "theta_signal": float(theta_signal)
            }
        )

    def get_description(self) -> str:
        return (
            "Delta-hedged gamma scalping. Profits from realized vol exceeding implied. "
            "Optimized for low-vol regimes with high gamma. Position-neutral strategy."
        )


class VegaArbitrageAgent(StrategyAgent):
    """
    Vega Arbitrage Agent

    Specializes in volatility surface mispricings and term structure trades.
    Exploits differences between implied volatility levels across strikes and tenors.

    Optimized Regimes:
    - Any regime with term structure dislocations
    - High vol-of-vol environments (volatility is volatile)

    Decision Logic:
    - Term structure slope abnormal → trade it
    - Vol-of-vol high → mean reversion opportunity
    - Skew extremes → arb opportunities
    """

    def __init__(self):
        super().__init__("VegaArbitrageAgent")
        self.optimized_regimes = ["bull_high_vol", "bear_high_vol", "stress"]

    def select_action(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> StrategySelection:
        """Select vega arbitrage action."""

        # Term structure signal
        ts_signal = abs(market_state.term_structure_slope)
        ts_confidence = 0.8 if ts_signal > 0.15 else 0.5 if ts_signal > 0.05 else 0.2

        # Vol-of-vol signal: high vol-of-vol = arbitrage opportunity
        vol_of_vol_signal = min(greeks.vol_of_vol / 0.5, 1.0)
        vol_of_vol_confidence = 0.9 if vol_of_vol_signal > 0.6 else 0.6

        # Skew signal: extreme skew offers mean reversion
        skew_signal = abs(market_state.skew)
        skew_confidence = 0.75 if skew_signal > 0.7 else 0.4 if skew_signal > 0.3 else 0.1

        # Vega sensitivity
        vega_signal = abs(greeks.vega) / 1.0  # Normalize
        vega_confidence = 0.8 if vega_signal > 0.6 else 0.5

        # Combine signals
        combined_confidence = (
            ts_confidence * 0.3 +
            vol_of_vol_confidence * 0.3 +
            skew_confidence * 0.2 +
            vega_confidence * 0.2
        )

        # Determine action
        if combined_confidence > 0.7:
            action = ActionType.LONG
            exposure = min((ts_signal + vol_of_vol_signal) / 2, 0.7)
        elif combined_confidence > 0.5:
            action = ActionType.HEDGE
            exposure = 0.4
        else:
            action = ActionType.NEUTRAL
            exposure = 0.0

        rationale = (
            f"Vol arb in {regime}: "
            f"ts_slope={market_state.term_structure_slope:.3f}, "
            f"vol_of_vol={greeks.vol_of_vol:.3f}, skew={market_state.skew:.2f}. "
            f"Signal strength: {combined_confidence:.2f}"
        )

        return StrategySelection(
            strategy_name="vega_arbitrage",
            action_type=action,
            confidence=combined_confidence,
            rationale=rationale,
            target_exposure=exposure,
            metadata={
                "term_structure_slope": float(market_state.term_structure_slope),
                "vol_of_vol": float(greeks.vol_of_vol),
                "skew": float(market_state.skew)
            }
        )

    def get_description(self) -> str:
        return (
            "Vol surface and term structure arbitrage. Exploits term structure dislocations "
            "and skew mean reversion. Directionally neutral vol trades."
        )


class MeanReversionAgent(StrategyAgent):
    """
    Mean Reversion Agent

    Specializes in skew mean reversion when skew is elevated.
    Fades extremes when market conditions are stretched.

    Optimized Regimes:
    - High-vol regimes where skew extremes are common
    - Post-event regimes (after volatility spike)

    Decision Logic:
    - High skew (>0.8) → sell put skew
    - Low skew (<-0.8) → sell call skew
    - Vol-of-vol declining → mean reversion favored
    """

    def __init__(self):
        super().__init__("MeanReversionAgent")
        self.optimized_regimes = ["bear_high_vol", "stress"]

    def select_action(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> StrategySelection:
        """Select mean reversion action."""

        # Skew extremeness
        skew_extremeness = abs(market_state.skew)
        skew_confidence = 0.9 if skew_extremeness > 0.8 else 0.7 if skew_extremeness > 0.5 else 0.3

        # Vol-of-vol declining suggests mean reversion
        vol_of_vol_signal = min(greeks.vol_of_vol / 0.3, 1.0)
        vol_of_vol_confidence = 0.8 if vol_of_vol_signal < 0.4 else 0.4

        # Gamma helps mean reversion (short gamma when skew extreme)
        gamma_signal = max(0, 1.0 - greeks.gamma / 0.2)  # Higher when gamma low
        gamma_confidence = 0.7 if gamma_signal > 0.5 else 0.4

        # Vega reversal play
        vega_signal = 1.0 - (abs(greeks.vega) / 2.0)  # Neutral vega is best
        vega_confidence = 0.6

        combined_confidence = (
            skew_confidence * 0.4 +
            vol_of_vol_confidence * 0.25 +
            gamma_confidence * 0.2 +
            vega_confidence * 0.15
        )

        # Determine action
        if combined_confidence > 0.75 and skew_extremeness > 0.7:
            action = ActionType.SHORT  # Fade the extreme
            exposure = min(skew_extremeness, 0.7)
        elif combined_confidence > 0.6:
            action = ActionType.HEDGE
            exposure = 0.3
        else:
            action = ActionType.NEUTRAL
            exposure = 0.0

        rationale = (
            f"Mean reversion in {regime}: "
            f"skew={market_state.skew:.2f} (extremeness={skew_extremeness:.2f}), "
            f"vol_of_vol={greeks.vol_of_vol:.3f}. "
            f"{'Favors fading' if skew_extremeness > 0.7 else 'Conditions unclear'}"
        )

        return StrategySelection(
            strategy_name="mean_reversion",
            action_type=action,
            confidence=combined_confidence,
            rationale=rationale,
            target_exposure=exposure,
            metadata={
                "skew_extremeness": float(skew_extremeness),
                "vol_of_vol": float(greeks.vol_of_vol)
            }
        )

    def get_description(self) -> str:
        return (
            "Skew mean reversion. Fades extremes when skew is stretched. "
            "Profits from skew normalization in high-vol regimes."
        )


class EventDrivenAgent(StrategyAgent):
    """
    Event-Driven Agent

    Specializes in trading around known events (earnings, economic releases, etc.)
    and reacting to unexpected volatility spikes.

    Optimized Regimes:
    - Any regime with active events
    - Immediate post-event periods

    Decision Logic:
    - Events in market_state.events → activate
    - Liquidity high → enable larger positions
    - Vol spike detected → opportunity
    """

    def __init__(self):
        super().__init__("EventDrivenAgent")
        self.optimized_regimes = ["stress", "bull_high_vol", "bear_high_vol"]

    def select_action(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> StrategySelection:
        """Select event-driven action."""

        # Event presence signal
        event_signal = len(market_state.events) > 0
        event_confidence = 0.9 if event_signal else 0.3

        # Volatility spike signal
        vol_signal = market_state.volatility
        vol_spike_confidence = 0.85 if vol_signal > 0.5 else 0.6 if vol_signal > 0.3 else 0.2

        # Liquidity availability
        liquidity_signal = market_state.liquidity_score
        liquidity_confidence = 0.8 if liquidity_signal > 0.7 else 0.5

        # Vega sensitivity in events
        vega_signal = abs(greeks.vega)
        vega_event_confidence = 0.7 if vega_signal > 0.5 else 0.4

        combined_confidence = (
            event_confidence * 0.35 +
            vol_spike_confidence * 0.35 +
            liquidity_confidence * 0.2 +
            vega_event_confidence * 0.1
        )

        # Determine action
        if event_signal and combined_confidence > 0.8:
            action = ActionType.LONG
            exposure = min(0.8, liquidity_signal)
        elif vol_signal > 0.5 and combined_confidence > 0.6:
            action = ActionType.HEDGE
            exposure = 0.5
        else:
            action = ActionType.NEUTRAL
            exposure = 0.0

        event_names = ", ".join(market_state.events) if market_state.events else "none"
        rationale = (
            f"Event-driven in {regime}: "
            f"events=[{event_names}], vol={market_state.volatility:.2%}, "
            f"liquidity={liquidity_signal:.1%}"
        )

        return StrategySelection(
            strategy_name="event_driven",
            action_type=action,
            confidence=combined_confidence,
            rationale=rationale,
            target_exposure=exposure,
            metadata={
                "events": market_state.events,
                "vol_spike": float(vol_signal),
                "liquidity": float(liquidity_signal)
            }
        )

    def get_description(self) -> str:
        return (
            "Event-driven trading. Activates on earnings, economic releases, "
            "and volatility spikes. Capitalizes on vol expansion around events."
        )


class MomentumAgent(StrategyAgent):
    """
    Momentum Agent

    Trend-following strategy that bets on regime persistence.
    Profits from momentum and trend continuation.

    Optimized Regimes:
    - Bull regimes (momentum positive)
    - High-vol regimes (momentum tends to persist)

    Decision Logic:
    - Price momentum positive → go long
    - Delta exposed in direction of momentum
    - Low gamma (avoid fighting trends)
    """

    def __init__(self):
        super().__init__("MomentumAgent")
        self.optimized_regimes = ["bull_low_vol", "bull_high_vol"]

    def select_action(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> StrategySelection:
        """Select momentum action."""

        # Momentum signal: positive momentum in market_state
        momentum_signal = max(market_state.price_momentum, 0)
        momentum_confidence = 0.85 if momentum_signal > 0.6 else 0.65 if momentum_signal > 0.2 else 0.2

        # Delta exposure in momentum direction
        delta_signal = greeks.delta
        delta_alignment = 1.0 if (momentum_signal > 0 and delta_signal > 0.3) or (momentum_signal < 0 and delta_signal < -0.3) else 0.4
        delta_confidence = 0.8 if delta_alignment > 0.7 else 0.4

        # Regime match
        regime_confidence = 0.9 if "bull" in regime else 0.5

        # Low gamma in trends
        gamma_for_trend = 1.0 - min(greeks.gamma / 0.2, 1.0)
        gamma_confidence = 0.7 if gamma_for_trend > 0.6 else 0.3

        combined_confidence = (
            momentum_confidence * 0.4 +
            delta_confidence * 0.3 +
            regime_confidence * 0.2 +
            gamma_confidence * 0.1
        )

        # Determine action
        if momentum_signal > 0.5 and combined_confidence > 0.75:
            action = ActionType.LONG
            exposure = min(momentum_signal, 0.8)
        elif momentum_signal < -0.3 and combined_confidence > 0.6:
            action = ActionType.SHORT
            exposure = min(abs(momentum_signal), 0.6)
        elif combined_confidence > 0.5:
            action = ActionType.HEDGE
            exposure = 0.3
        else:
            action = ActionType.NEUTRAL
            exposure = 0.0

        rationale = (
            f"Momentum trading in {regime}: "
            f"momentum={market_state.price_momentum:.2f}, "
            f"delta={greeks.delta:.2f}. "
            f"{'Following trend' if momentum_signal > 0.5 else 'Waiting for signal'}"
        )

        return StrategySelection(
            strategy_name="momentum",
            action_type=action,
            confidence=combined_confidence,
            rationale=rationale,
            target_exposure=exposure,
            metadata={
                "momentum": float(market_state.price_momentum),
                "delta_alignment": float(delta_alignment)
            }
        )

    def get_description(self) -> str:
        return (
            "Trend-following momentum strategy. Bets on regime persistence. "
            "Long in bullish regimes, flat/short in bearish. Exploits continuation."
        )


class CorrelationAgent(StrategyAgent):
    """
    Correlation Regime Agent

    Specializes in correlation trading and pair strategies.
    Exploits correlation dislocations and regime changes.

    Optimized Regimes:
    - Stress regimes (correlations spike)
    - Normal to high-vol transitions

    Decision Logic:
    - Correlation abnormal → trade it
    - Vol-of-vol guides correlation vol expectations
    - Diversification deterioration → opportunity
    """

    def __init__(self):
        super().__init__("CorrelationAgent")
        self.optimized_regimes = ["stress", "bear_high_vol"]

    def select_action(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> StrategySelection:
        """Select correlation action."""

        # Correlation regime signal
        corr_stress = market_state.correlation_regime == "stress"
        corr_confidence = 0.85 if corr_stress else 0.5

        # Vol-of-vol signals correlation vol expectations
        vol_of_vol_signal = min(greeks.vol_of_vol / 0.5, 1.0)
        vol_of_vol_confidence = 0.8 if vol_of_vol_signal > 0.6 else 0.4

        # Regime match
        regime_confidence = 0.9 if "stress" in regime else 0.5 if "high_vol" in regime else 0.2

        # Rho (interest rate sensitivity) for correlation moves
        rho_signal = abs(greeks.rho / 0.3)
        rho_confidence = 0.6

        combined_confidence = (
            corr_confidence * 0.35 +
            vol_of_vol_confidence * 0.3 +
            regime_confidence * 0.25 +
            rho_confidence * 0.1
        )

        # Determine action
        if combined_confidence > 0.75 and corr_stress:
            action = ActionType.LONG
            exposure = min(0.7, vol_of_vol_signal)
        elif combined_confidence > 0.6:
            action = ActionType.HEDGE
            exposure = 0.4
        else:
            action = ActionType.NEUTRAL
            exposure = 0.0

        rationale = (
            f"Correlation strategy in {regime}: "
            f"corr_regime={market_state.correlation_regime}, "
            f"vol_of_vol={greeks.vol_of_vol:.3f}. "
            f"{'Correlation dislocations present' if corr_stress else 'Waiting'}"
        )

        return StrategySelection(
            strategy_name="correlation_pairs",
            action_type=action,
            confidence=combined_confidence,
            rationale=rationale,
            target_exposure=exposure,
            metadata={
                "correlation_regime": market_state.correlation_regime,
                "vol_of_vol": float(greeks.vol_of_vol)
            }
        )

    def get_description(self) -> str:
        return (
            "Correlation and pair trading. Exploits correlation dislocations "
            "and diversification breakdown in stress regimes."
        )


class AgentPool:
    """
    Manages pool of strategy agents.

    Provides access to agents, tracks performance, and enables
    agent-level queries for competition engine.
    """

    def __init__(self, agents: Optional[List[StrategyAgent]] = None):
        """
        Initialize agent pool.

        Args:
            agents: List of agents to include. If None, creates default pool.
        """
        if agents is None:
            # Default pool
            self.agents = [
                GammaScalpingAgent(),
                VegaArbitrageAgent(),
                MeanReversionAgent(),
                EventDrivenAgent(),
                MomentumAgent(),
                CorrelationAgent(),
            ]
        else:
            self.agents = agents

        logger.info(f"Initialized AgentPool with {len(self.agents)} agents")

    def add_agent(self, agent: StrategyAgent):
        """Add a new agent to the pool."""
        self.agents.append(agent)
        logger.info(f"Added agent: {agent.name}")

    def get_agent_by_name(self, name: str) -> Optional[StrategyAgent]:
        """Get agent by name."""
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None

    def get_agents_for_regime(self, regime: str) -> List[StrategyAgent]:
        """Get agents optimized for a specific regime."""
        return [a for a in self.agents if regime in a.optimized_regimes]

    def select_actions(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> Dict[str, StrategySelection]:
        """
        Get action selections from all agents.

        Returns:
            Dict of {agent_name: StrategySelection}
        """
        selections = {}
        for agent in self.agents:
            try:
                selection = agent.select_action(regime, greeks, market_state)
                selections[agent.name] = selection
            except Exception as e:
                logger.error(f"Error getting action from {agent.name}: {e}")
                # Create neutral selection on error
                selections[agent.name] = StrategySelection(
                    strategy_name="error",
                    action_type=ActionType.NEUTRAL,
                    confidence=0.0,
                    rationale=f"Error in agent: {str(e)}",
                    target_exposure=0.0
                )

        return selections

    def get_pool_summary(self) -> Dict[str, Any]:
        """Get summary of pool performance."""
        return {
            "pool_size": len(self.agents),
            "agents": [
                {
                    "name": agent.name,
                    "elo": agent.get_performance().elo_rating,
                    "trades": agent.get_performance().trade_count,
                    "win_rate": agent.get_performance().win_rate,
                    "total_pnl": agent.get_performance().total_pnl
                }
                for agent in self.agents
            ]
        }

    def __repr__(self) -> str:
        return f"AgentPool({len(self.agents)} agents)"
