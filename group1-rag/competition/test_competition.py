"""
Comprehensive Tests for Competition Framework
==============================================

Tests covering:
- StrategyAgent interface and implementations
- Agent pool management
- Competition engine with Elo ratings
- Regime detection and classification
- Strategy selection and scoring
- Learning loop integration

Targets:
- 25+ unit tests with 100% pass rate
- Elo update correctness
- Agent specialization in regimes
- Selection latency <50ms
"""

import pytest
import logging
import time
from typing import Dict, List, Any
from datetime import datetime

from strategy_agent import (
    StrategyAgent, ActionType, GreeksSnapshot, MarketState,
    StrategySelection, AgentPerformance
)
from agent_pool import (
    GammaScalpingAgent, VegaArbitrageAgent, MeanReversionAgent,
    EventDrivenAgent, MomentumAgent, CorrelationAgent, AgentPool
)
from competition_engine import CompetitionEngine, EloRating
from regime_detector import RegimeDetector, RegimeType

logger = logging.getLogger(__name__)


class TestStrategyAgent:
    """Tests for abstract StrategyAgent and implementations."""

    def test_agent_initialization(self):
        """Test agent initialization."""
        agent = GammaScalpingAgent()
        assert agent.name == "GammaScalpingAgent"
        assert len(agent.optimized_regimes) > 0
        assert agent.get_description()

    def test_greeks_snapshot(self):
        """Test GreeksSnapshot creation and serialization."""
        greeks = GreeksSnapshot(
            delta=0.5,
            gamma=0.1,
            theta=-0.01,
            vega=0.5,
            rho=0.05,
            vol_of_vol=0.2
        )
        assert greeks.delta == 0.5
        assert greeks.timestamp

        d = greeks.to_dict()
        assert d["delta"] == 0.5
        assert len(d) == 6

    def test_market_state(self):
        """Test MarketState creation."""
        state = MarketState(
            volatility=0.2,
            volatility_term_structure={"1m": 0.18, "3m": 0.22, "1y": 0.25},
            skew=-0.3,
            term_structure_slope=0.07,
            events=["earnings"],
            regime="bull_low_vol",
            price_momentum=0.5,
            correlation_regime="normal",
            liquidity_score=0.9
        )
        assert state.volatility == 0.2
        assert state.timestamp

    def test_strategy_selection_confidence_clamping(self):
        """Test that StrategySelection clamps confidence to [0, 1]."""
        sel1 = StrategySelection(
            strategy_name="test",
            action_type=ActionType.LONG,
            confidence=1.5,  # Should be clamped
            rationale="test",
            target_exposure=0.5
        )
        assert sel1.confidence == 1.0

        sel2 = StrategySelection(
            strategy_name="test",
            action_type=ActionType.LONG,
            confidence=-0.5,  # Should be clamped
            rationale="test",
            target_exposure=0.5
        )
        assert sel2.confidence == 0.0

    def test_agent_decision_recording(self):
        """Test that agents record decisions."""
        agent = GammaScalpingAgent()
        greeks = GreeksSnapshot(0.3, 0.2, -0.01, 0.4, 0.05, 0.1)
        state = MarketState(0.1, {}, 0.0, 0.0, [], "bull_low_vol", 0.5, "normal", 0.9)

        selection = agent.select_action("bull_low_vol", greeks, state)
        agent.record_decision(selection, state, greeks, pnl=100.0)

        assert len(agent.decision_history) == 1
        assert agent.decision_history[0]["strategy"] == "gamma_scalping"
        assert agent.decision_history[0]["pnl"] == 100.0

    def test_agent_performance_update(self):
        """Test performance tracking."""
        agent = GammaScalpingAgent()
        agent.update_performance("bull_low_vol", pnl=100.0, trade_count=1, is_win=True)
        agent.update_performance("bull_low_vol", pnl=-50.0, trade_count=1, is_win=False)

        perf = agent.get_performance("bull_low_vol")
        assert perf.total_pnl == 50.0
        assert perf.trade_count == 2

    def test_expertise_vector(self):
        """Test expertise vector calculation."""
        agent = GammaScalpingAgent()
        agent.update_performance("bull_low_vol", pnl=100.0, trade_count=1)
        agent.update_performance("bear_low_vol", pnl=50.0, trade_count=1)

        expertise = agent.get_expertise_vector()
        assert "bull_low_vol" in expertise
        assert "bear_low_vol" in expertise
        assert all(0 <= v <= 1 for v in expertise.values())


class TestAgentPool:
    """Tests for AgentPool."""

    def test_default_pool_creation(self):
        """Test creation of default agent pool."""
        pool = AgentPool()
        assert len(pool.agents) == 6  # Default pool size
        assert all(isinstance(a, StrategyAgent) for a in pool.agents)

    def test_pool_agent_by_name(self):
        """Test retrieving agent by name."""
        pool = AgentPool()
        agent = pool.get_agent_by_name("GammaScalpingAgent")
        assert agent is not None
        assert agent.name == "GammaScalpingAgent"

    def test_pool_agents_for_regime(self):
        """Test getting agents optimized for regime."""
        pool = AgentPool()
        gamma_agents = pool.get_agents_for_regime("bull_low_vol")
        assert len(gamma_agents) > 0

    def test_pool_select_actions(self):
        """Test getting actions from all agents in pool."""
        pool = AgentPool()
        greeks = GreeksSnapshot(0.3, 0.2, -0.01, 0.4, 0.05, 0.1)
        state = MarketState(0.1, {}, 0.0, 0.0, [], "bull_low_vol", 0.5, "normal", 0.9)

        selections = pool.select_actions("bull_low_vol", greeks, state)

        assert len(selections) == len(pool.agents)
        assert all(isinstance(s, StrategySelection) for s in selections.values())
        assert all(0 <= s.confidence <= 1 for s in selections.values())

    def test_pool_add_custom_agent(self):
        """Test adding custom agent to pool."""
        pool = AgentPool(agents=[])
        assert len(pool.agents) == 0

        agent = GammaScalpingAgent()
        pool.add_agent(agent)
        assert len(pool.agents) == 1
        assert pool.get_agent_by_name("GammaScalpingAgent") == agent


class TestCompetitionEngine:
    """Tests for CompetitionEngine."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)
        assert engine.agent_pool == pool
        assert len(engine.elo_ratings) == 0

    def test_elo_rating_creation(self):
        """Test Elo rating creation."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)

        elo = engine.get_or_create_elo("GammaScalpingAgent", "bull_low_vol")
        assert elo.rating == 1600.0
        assert elo.games_played == 0

    def test_elo_expected_score(self):
        """Test Elo expected score calculation."""
        elo1 = EloRating("agent1", "regime1", rating=1600.0)
        elo2 = EloRating("agent2", "regime1", rating=1600.0)

        # Equal ratings -> 0.5 expected score
        assert abs(elo1.expected_score(elo2.rating) - 0.5) < 0.01

    def test_elo_update_win(self):
        """Test Elo update for win."""
        elo = EloRating("agent", "regime", rating=1600.0, k_factor=32)
        elo.update(result=1.0, opponent_rating=1600.0)

        assert elo.rating > 1600.0
        assert elo.wins == 1
        assert elo.games_played == 1

    def test_elo_update_loss(self):
        """Test Elo update for loss."""
        elo = EloRating("agent", "regime", rating=1600.0, k_factor=32)
        elo.update(result=0.0, opponent_rating=1600.0)

        assert elo.rating < 1600.0
        assert elo.losses == 1
        assert elo.games_played == 1

    def test_select_strategies_scoring(self):
        """Test strategy selection with Elo scoring."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)

        # Set up Elo ratings
        engine.get_or_create_elo("GammaScalpingAgent", "bull_low_vol").rating = 1800.0
        engine.get_or_create_elo("MomentumAgent", "bull_low_vol").rating = 1400.0

        # Create selections
        gamma_sel = StrategySelection(
            strategy_name="gamma_scalping",
            action_type=ActionType.LONG,
            confidence=0.8,
            rationale="",
            target_exposure=0.5
        )
        momentum_sel = StrategySelection(
            strategy_name="momentum",
            action_type=ActionType.LONG,
            confidence=0.9,
            rationale="",
            target_exposure=0.7
        )

        selections = {
            "GammaScalpingAgent": gamma_sel,
            "MomentumAgent": momentum_sel
        }

        ranked = engine.select_strategies("bull_low_vol", selections, max_strategies=2)

        # Gamma should rank higher due to Elo despite lower confidence
        assert ranked[0][0] == "GammaScalpingAgent"

    def test_winner_and_hedge_selection(self):
        """Test winner and hedge selection logic."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)

        engine.get_or_create_elo("GammaScalpingAgent", "bull_low_vol").rating = 1800.0
        engine.get_or_create_elo("MomentumAgent", "bull_low_vol").rating = 1400.0

        gamma_sel = StrategySelection(
            strategy_name="gamma_scalping",
            action_type=ActionType.LONG,
            confidence=0.75,
            rationale="",
            target_exposure=0.5
        )
        momentum_sel = StrategySelection(
            strategy_name="momentum",
            action_type=ActionType.LONG,
            confidence=0.65,
            rationale="",
            target_exposure=0.7
        )

        selections = {
            "GammaScalpingAgent": gamma_sel,
            "MomentumAgent": momentum_sel
        }

        winner, hedge, reason = engine.get_winner_and_hedge(
            "bull_low_vol", selections, confidence_threshold=0.60
        )

        assert winner is not None
        assert winner[0] == "GammaScalpingAgent"
        assert hedge is not None

    def test_escalation_low_confidence(self):
        """Test escalation when confidence is too low."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)

        sel = StrategySelection(
            strategy_name="test",
            action_type=ActionType.NEUTRAL,
            confidence=0.35,  # Below escalation threshold
            rationale="",
            target_exposure=0.0
        )

        selections = {"GammaScalpingAgent": sel}

        winner, hedge, reason = engine.get_winner_and_hedge(
            "bull_low_vol", selections, confidence_threshold=0.60
        )

        assert winner is None
        assert "ESCALATE" in reason

    def test_regime_rankings(self):
        """Test regime-specific rankings."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)

        engine.get_or_create_elo("GammaScalpingAgent", "bull_low_vol").rating = 1700.0
        engine.get_or_create_elo("MomentumAgent", "bull_low_vol").rating = 1600.0

        rankings = engine.get_regime_rankings("bull_low_vol")

        assert len(rankings) == 2
        assert rankings[0]["agent_name"] == "GammaScalpingAgent"

    def test_competition_stats(self):
        """Test competition statistics."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)

        engine.get_or_create_elo("GammaScalpingAgent", "bull_low_vol").update(1.0)
        engine.get_or_create_elo("GammaScalpingAgent", "bull_low_vol").update(0.0)

        stats = engine.get_competition_stats()

        assert stats["total_games_played"] == 2
        assert stats["total_wins"] == 1
        assert stats["total_losses"] == 1


class TestRegimeDetector:
    """Tests for RegimeDetector."""

    def test_detector_initialization(self):
        """Test detector initialization."""
        detector = RegimeDetector(use_kg=False)
        assert detector.current_regime == RegimeType.NORMAL.value

    def test_bull_low_vol_detection(self):
        """Test bull low vol regime detection."""
        detector = RegimeDetector(use_kg=False)

        regime, conf = detector.detect_regime(
            volatility=0.10,  # Low vol
            skew=0.0,
            term_structure_slope=0.05,
            price_momentum=0.6,  # Bullish
            vol_of_vol=0.1,
            events=[],
            correlation_regime="normal"
        )

        assert regime == RegimeType.BULL_LOW_VOL.value
        assert conf > 0.7

    def test_bear_high_vol_detection(self):
        """Test bear high vol regime detection."""
        detector = RegimeDetector(use_kg=False)

        regime, conf = detector.detect_regime(
            volatility=0.50,  # High vol
            skew=-0.7,  # Bearish skew
            term_structure_slope=0.02,
            price_momentum=-0.4,  # Bearish
            vol_of_vol=0.2,
            events=[],
            correlation_regime="normal"
        )

        assert regime == RegimeType.BEAR_HIGH_VOL.value
        assert conf > 0.6

    def test_stress_detection_high_vol(self):
        """Test stress regime detection from high vol."""
        detector = RegimeDetector(use_kg=False)

        regime, conf = detector.detect_regime(
            volatility=0.70,  # Extreme vol
            skew=-0.8,  # Extreme skew
            term_structure_slope=0.02,
            price_momentum=-0.5,
            vol_of_vol=0.5,  # High vol-of-vol
            events=[],
            correlation_regime="stress"
        )

        assert regime == RegimeType.STRESS.value
        assert conf > 0.75

    def test_normal_regime_detection(self):
        """Test normal regime in between conditions."""
        detector = RegimeDetector(use_kg=False)

        regime, conf = detector.detect_regime(
            volatility=0.25,  # Middle range
            skew=0.0,
            term_structure_slope=0.05,
            price_momentum=0.0,  # No clear trend
            vol_of_vol=0.15,
            events=[],
            correlation_regime="normal"
        )

        assert regime == RegimeType.NORMAL.value

    def test_regime_shift_recording(self):
        """Test recording of regime shifts."""
        detector = RegimeDetector(use_kg=False)

        regime1, _ = detector.detect_regime(0.1, 0.0, 0.05, 0.5, 0.1, [], "normal")
        regime2, _ = detector.detect_regime(0.5, -0.7, 0.02, -0.5, 0.5, [], "stress")

        assert len(detector.regime_history) == 2
        assert detector.regime_history[0][0] == regime1
        assert detector.regime_history[1][0] == regime2

    def test_regime_stability(self):
        """Test regime stability calculation."""
        detector = RegimeDetector(use_kg=False)

        # Stable regime (no changes in detected regime)
        for _ in range(5):
            detector.detect_regime(0.1, 0.0, 0.05, 0.5, 0.1, [], "normal")

        # With only one entry in regime history (initial regime), stability is 0.5
        stability = detector.get_regime_strength()["regime_stability"]
        assert stability >= 0.5  # Default when limited history

        # Now create a regime with more history and varied changes
        detector2 = RegimeDetector(use_kg=False)
        # Use varying volatility to trigger regime changes
        vol_sequence = [0.1, 0.1, 0.1, 0.5, 0.5]  # Change vol to trigger regime shift
        for i, vol in enumerate(vol_sequence):
            detector2.detect_regime(vol, 0.0, 0.05, 0.5, 0.1, [], "normal")

        stability2 = detector2.get_regime_strength()["regime_stability"]
        # One regime change into 2 entries: 1 change / 2 entries = 0.5 stability
        assert stability2 >= 0.5


class TestSelectionLatency:
    """Tests for real-time performance requirements."""

    def test_selection_latency_under_50ms(self):
        """Test that strategy selection completes in <50ms."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)

        greeks = GreeksSnapshot(0.3, 0.2, -0.01, 0.4, 0.05, 0.1)
        state = MarketState(0.1, {}, 0.0, 0.0, [], "bull_low_vol", 0.5, "normal", 0.9)

        # Prime caches
        for _ in range(2):
            pool.select_actions("bull_low_vol", greeks, state)

        # Measure actual selection
        start = time.time()
        selections = pool.select_actions("bull_low_vol", greeks, state)
        elapsed = (time.time() - start) * 1000  # Convert to ms

        assert elapsed < 50.0
        logger.info(f"Selection latency: {elapsed:.2f}ms")


class TestIntegration:
    """Integration tests for full competition cycle."""

    def test_daily_competition_cycle(self):
        """Test a full day of competition."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)
        detector = RegimeDetector(use_kg=False)

        # Simulate 10 hours of trading
        for hour in range(10):
            # Detect regime (changes during day)
            if hour < 4:
                vol = 0.1 + (hour * 0.01)
                momentum = 0.4
            elif hour < 8:
                vol = 0.15 + (hour * 0.02)
                momentum = 0.2
            else:
                vol = 0.3
                momentum = -0.3

            regime, regime_conf = detector.detect_regime(
                volatility=vol,
                skew=-0.2 if momentum < 0 else 0.1,
                term_structure_slope=0.05,
                price_momentum=momentum,
                vol_of_vol=0.15,
                events=[],
                correlation_regime="normal"
            )

            # Get agent selections
            greeks = GreeksSnapshot(
                delta=0.3 + momentum,
                gamma=0.2 - (vol * 0.5),
                theta=-0.01,
                vega=vol,
                rho=0.05,
                vol_of_vol=0.15
            )
            state = MarketState(vol, {}, 0.0, 0.0, [], regime, momentum, "normal", 0.9)

            selections = pool.select_actions(regime, greeks, state)

            # Select winner
            winner, hedge, reason = engine.get_winner_and_hedge(regime, selections)

            if winner:
                # Simulate trade outcome
                pnl = (10 if winner[1].confidence > 0.7 else 5) if hour % 2 == 0 else -3
                engine.update_elo_from_trade(winner[0], regime, pnl)

            engine.record_selection(regime, winner, hedge, reason)

        # Verify competition ran
        stats = engine.get_competition_stats()
        assert stats["total_games_played"] > 0
        assert stats["selection_decisions"] == 10
        assert len(detector.regime_history) > 0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_agent_pool_selection(self):
        """Test handling of empty pool."""
        pool = AgentPool(agents=[])
        greeks = GreeksSnapshot(0.3, 0.2, -0.01, 0.4, 0.05, 0.1)
        state = MarketState(0.1, {}, 0.0, 0.0, [], "bull_low_vol", 0.5, "normal", 0.9)

        selections = pool.select_actions("bull_low_vol", greeks, state)
        assert len(selections) == 0

    def test_agent_error_handling(self):
        """Test handling of agent errors."""
        pool = AgentPool()
        engine = CompetitionEngine(pool)

        # Mock agent that throws error
        class ErrorAgent(StrategyAgent):
            def __init__(self):
                super().__init__("ErrorAgent")

            def select_action(self, regime, greeks, market_state):
                raise ValueError("Intentional error")

            def get_description(self):
                return "Error agent"

        pool.agents.append(ErrorAgent())

        greeks = GreeksSnapshot(0.3, 0.2, -0.01, 0.4, 0.05, 0.1)
        state = MarketState(0.1, {}, 0.0, 0.0, [], "bull_low_vol", 0.5, "normal", 0.9)

        selections = pool.select_actions("bull_low_vol", greeks, state)

        # Should have selection for error agent with neutral action
        assert "ErrorAgent" in selections
        assert selections["ErrorAgent"].action_type == ActionType.NEUTRAL

    def test_nan_values_handling(self):
        """Test handling of NaN values in inputs."""
        agent = GammaScalpingAgent()
        greeks = GreeksSnapshot(
            delta=float('nan'),
            gamma=0.2,
            theta=-0.01,
            vega=0.4,
            rho=0.05,
            vol_of_vol=0.1
        )
        state = MarketState(0.1, {}, 0.0, 0.0, [], "bull_low_vol", 0.5, "normal", 0.9)

        # Should not crash
        selection = agent.select_action("bull_low_vol", greeks, state)
        assert selection is not None


def run_all_tests():
    """Run all tests with logging."""
    logging.basicConfig(level=logging.DEBUG)
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_all_tests()
