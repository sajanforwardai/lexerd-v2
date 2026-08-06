"""
Comprehensive test harness for Tier 3 Reasoning Engine

Test categories:
1. Tree-of-Thought structure validation (depth, branching)
2. Latency enforcement (total and per-step budgets)
3. Constraint validation (detection and handling)
4. State management (entities, regimes, reasoning chains)
5. Ranking function correctness
6. Multi-agent coordination
7. Edge cases and error handling
"""

import unittest
import time
from typing import List, Dict

from reasoning_engine import (
    ReasoningEngine,
    ReasoningState,
    ReasoningNode,
    MarketRegime,
    Entity,
    Constraint,
    ConstraintType,
    ReasoningStepType,
    RankingFunction,
    RankingMetrics,
)
from agent_coordinator import (
    AgentCoordinator,
    MarketAnalyst,
    StrategySelector,
    Executor,
    AgentRole,
)


class TestReasoningEngineStructure(unittest.TestCase):
    """Test Tree-of-Thought structure."""

    def setUp(self):
        self.engine = ReasoningEngine(
            max_depth=3,
            max_branching_factor=3,
            max_total_latency_ms=5000.0,
            max_step_latency_ms=2000.0,
        )
        self.market_regime = MarketRegime.HIGH_VOL
        self.entities = [
            {"entity_id": f"ent_{i}", "entity_type": "Greek", "text": f"greek_{i}", "confidence": 0.8}
            for i in range(3)
        ]
        self.constraints = [
            {"constraint_type": ConstraintType.GREEK_EXPOSURE, "description": "Limit gamma", "value": 100}
        ]

    def test_tree_depth_limit(self):
        """Test that reasoning tree respects max depth."""
        state = self.engine.reason(
            self.market_regime,
            self.entities,
            self.constraints,
            [],
        )

        max_depth = max(node.depth for node in state.reasoning_tree.values()) if state.reasoning_tree else 0
        self.assertLessEqual(max_depth, self.engine.max_depth)

    def test_branching_factor_limit(self):
        """Test that each node has max branching factor children."""
        state = self.engine.reason(
            self.market_regime,
            self.entities,
            self.constraints,
            [],
        )

        for node in state.reasoning_tree.values():
            self.assertLessEqual(len(node.children_ids), self.engine.max_branching_factor)

    def test_tree_connectivity(self):
        """Test that tree is properly connected."""
        state = self.engine.reason(
            self.market_regime,
            self.entities,
            self.constraints,
            [],
        )

        if state.root_node_id:
            root = state.reasoning_tree.get(state.root_node_id)
            self.assertIsNotNone(root)
            self.assertIsNone(root.parent_id)

            # All non-root nodes should have a valid parent
            for node_id, node in state.reasoning_tree.items():
                if node.parent_id:
                    parent = state.reasoning_tree.get(node.parent_id)
                    self.assertIsNotNone(parent)

    def test_reasoning_chain_creation(self):
        """Test that reasoning chain is populated."""
        state = self.engine.reason(
            self.market_regime,
            self.entities,
            self.constraints,
            [],
        )

        # Should have at least 3 reasoning steps (regime, entity, constraint)
        self.assertGreaterEqual(len(state.reasoning_chain), 3)

        # Check step types
        step_types = [s.step_type for s in state.reasoning_chain]
        self.assertIn(ReasoningStepType.REGIME_ANALYSIS, step_types)
        self.assertIn(ReasoningStepType.ENTITY_ASSESSMENT, step_types)
        self.assertIn(ReasoningStepType.CONSTRAINT_VALIDATION, step_types)

    def test_node_id_uniqueness(self):
        """Test that all node IDs are unique."""
        state = self.engine.reason(
            self.market_regime,
            self.entities,
            self.constraints,
            [],
        )

        node_ids = list(state.reasoning_tree.keys())
        self.assertEqual(len(node_ids), len(set(node_ids)))


class TestLatencyEnforcement(unittest.TestCase):
    """Test latency budget enforcement."""

    def setUp(self):
        self.engine = ReasoningEngine(
            max_depth=3,
            max_branching_factor=3,
            max_total_latency_ms=5000.0,
            max_step_latency_ms=2000.0,
        )
        self.market_regime = MarketRegime.HIGH_VOL
        self.entities = [
            {"entity_id": f"ent_{i}", "entity_type": "Greek", "text": f"greek_{i}", "confidence": 0.8}
            for i in range(5)
        ]
        self.constraints = []

    def test_total_latency_budget(self):
        """Test that total reasoning latency respects budget."""
        start = time.time()
        state = self.engine.reason(
            self.market_regime,
            self.entities,
            self.constraints,
            [],
            latency_budget_ms=5000.0,
        )
        elapsed = (time.time() - start) * 1000

        self.assertLess(elapsed, 5000.0 * 1.2)  # Allow 20% overhead for timing
        self.assertLessEqual(state.accumulated_latency_ms, 5000.0 * 1.1)

    def test_step_latency_budget(self):
        """Test that individual reasoning steps respect step latency."""
        state = self.engine.reason(
            self.market_regime,
            self.entities,
            self.constraints,
            [],
        )

        for step in state.reasoning_chain:
            # Each step should be under max_step_latency_ms (with tolerance)
            self.assertLess(step.duration_ms, self.engine.max_step_latency_ms * 1.5)

    def test_early_termination_on_budget(self):
        """Test that reasoning terminates when budget is exhausted."""
        state = self.engine.reason(
            self.market_regime,
            self.entities,
            self.constraints,
            [],
            latency_budget_ms=100.0,  # Very tight budget
        )

        # Should still have at least basic reasoning
        self.assertGreater(len(state.reasoning_chain), 0)
        self.assertLess(state.accumulated_latency_ms, 500.0)


class TestConstraintValidation(unittest.TestCase):
    """Test constraint validation and handling."""

    def setUp(self):
        self.engine = ReasoningEngine()

    def test_constraint_detection_and_violation_flagging(self):
        """Test that constraints are properly validated."""
        regime = MarketRegime.HIGH_VOL
        entities = []
        constraints = [
            {"constraint_type": ConstraintType.GREEK_EXPOSURE, "description": "Greek limit", "value": 100},
            {"constraint_type": ConstraintType.NOTIONAL_LIMIT, "description": "Notional limit", "value": 1000},
        ]

        state = self.engine.reason(regime, entities, constraints, [])

        self.assertEqual(len(state.constraints), 2)
        for constraint in state.constraints:
            # Should be properly initialized
            self.assertIsNotNone(constraint.constraint_type)
            self.assertIsNotNone(constraint.description)

    def test_constraint_validation_step(self):
        """Test that constraint validation step is executed."""
        regime = MarketRegime.CRISIS  # Regime might trigger violations
        entities = []
        constraints = [
            {"constraint_type": ConstraintType.POSITION_LIMIT, "description": "Pos limit", "value": 50},
        ]

        state = self.engine.reason(regime, entities, constraints, [])

        # Should have constraint validation step
        constraint_steps = [s for s in state.reasoning_chain if s.step_type == ReasoningStepType.CONSTRAINT_VALIDATION]
        self.assertGreater(len(constraint_steps), 0)

        # Step should document constraints
        step = constraint_steps[0]
        self.assertIn("constraint", step.reasoning.lower())


class TestRankingFunction(unittest.TestCase):
    """Test ranking function for strategies."""

    def setUp(self):
        self.ranking_fn = RankingFunction()
        self.regime = MarketRegime.HIGH_VOL
        self.entities = [
            Entity(
                entity_id="e1",
                entity_type="Greek.gamma",
                text="gamma",
                confidence=0.9,
            ),
            Entity(
                entity_id="e2",
                entity_type="Strategy",
                text="gamma scalping",
                confidence=0.85,
            ),
        ]
        self.constraints = []

    def test_ranking_metrics_creation(self):
        """Test that ranking metrics are properly created."""
        metrics = self.ranking_fn.rank("gamma_scalping", self.regime, self.entities, self.constraints)

        self.assertIsInstance(metrics, RankingMetrics)
        self.assertGreaterEqual(metrics.edge_strength, 0.0)
        self.assertLessEqual(metrics.edge_strength, 1.0)
        self.assertGreaterEqual(metrics.historical_performance, 0.0)
        self.assertLessEqual(metrics.historical_performance, 1.0)

    def test_composite_score_calculation(self):
        """Test composite score calculation."""
        metrics = self.ranking_fn.rank("gamma_scalping", self.regime, self.entities, self.constraints)
        score = metrics.composite_score()

        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_regime_alignment_sensitivity(self):
        """Test that ranking is sensitive to regime."""
        high_vol_score = self.ranking_fn._compute_regime_alignment("gamma_scalping", MarketRegime.HIGH_VOL)
        low_vol_score = self.ranking_fn._compute_regime_alignment("gamma_scalping", MarketRegime.LOW_VOL)

        # Gamma scalping should score higher in high vol
        self.assertGreater(high_vol_score, low_vol_score)

    def test_constraint_impact_on_ranking(self):
        """Test that constraints impact ranking."""
        constraints_clean = []
        metrics_clean = self.ranking_fn.rank("delta_hedging", self.regime, self.entities, constraints_clean)

        constraints_violated = [
            Constraint(
                constraint_type=ConstraintType.GREEK_EXPOSURE,
                description="Gamma limit",
                value=50,
                severity=0.9,
                violated=True,
            ),
        ]
        metrics_violated = self.ranking_fn.rank("delta_hedging", self.regime, self.entities, constraints_violated)

        # Violated constraints should reduce alignment
        self.assertGreater(
            metrics_clean.constraint_alignment,
            metrics_violated.constraint_alignment,
        )


class TestStateManagement(unittest.TestCase):
    """Test ReasoningState management."""

    def test_state_initialization(self):
        """Test state initialization."""
        entities = [
            Entity(entity_id="e1", entity_type="Greek", text="delta", confidence=0.9)
        ]
        constraints = [
            Constraint(
                constraint_type=ConstraintType.GREEK_EXPOSURE,
                description="Limit",
                value=100,
            )
        ]

        state = ReasoningState(
            market_regime=MarketRegime.HIGH_VOL,
            entities=entities,
            constraints=constraints,
        )

        self.assertEqual(state.market_regime, MarketRegime.HIGH_VOL)
        self.assertEqual(len(state.entities), 1)
        self.assertEqual(len(state.constraints), 1)
        self.assertEqual(len(state.reasoning_chain), 0)

    def test_state_serialization(self):
        """Test state can be serialized to dict."""
        state = ReasoningState(
            market_regime=MarketRegime.MEAN_REVERT,
            entities=[],
            constraints=[],
        )

        state_dict = state.to_dict()
        self.assertIsInstance(state_dict, dict)
        self.assertEqual(state_dict['market_regime'], 'mean_reverting')
        self.assertIn('timestamp', state_dict)

    def test_add_and_retrieve_node(self):
        """Test adding and retrieving nodes."""
        state = ReasoningState(
            market_regime=MarketRegime.HIGH_VOL,
            entities=[],
            constraints=[],
        )

        # Create a test node
        from reasoning_engine import ReasoningStep
        step = ReasoningStep(
            step_id="s1",
            step_type=ReasoningStepType.REGIME_ANALYSIS,
            description="Test",
            reasoning="Test reasoning",
            conclusion="Test conclusion",
            confidence=0.8,
            duration_ms=50.0,
        )
        metrics = RankingMetrics(
            edge_strength=0.8, historical_performance=0.7,
            risk_adjusted_score=0.75, expected_payoff=100.0,
            constraint_alignment=0.9, regime_alignment=0.85,
        )
        node = ReasoningNode(
            node_id="node_1",
            depth=0,
            parent_id=None,
            step=step,
            metrics=metrics,
        )

        state.add_node(node)
        retrieved = state.get_node("node_1")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.node_id, "node_1")


class TestMultiAgentCoordination(unittest.TestCase):
    """Test multi-agent coordinator."""

    def setUp(self):
        self.coordinator = AgentCoordinator(max_latency_ms=5000.0)
        self.state = ReasoningState(
            market_regime=MarketRegime.HIGH_VOL,
            entities=[
                Entity(
                    entity_id="e1",
                    entity_type="Greek.gamma",
                    text="gamma",
                    confidence=0.9,
                )
            ],
            constraints=[],
        )

    def test_market_analyst_output(self):
        """Test MarketAnalyst produces output."""
        analyst = MarketAnalyst()
        output = analyst.analyze(
            self.state.market_regime,
            self.state.entities,
            self.state.constraints,
        )

        self.assertEqual(output.agent_role, AgentRole.MARKET_ANALYST)
        self.assertGreater(len(output.conclusions), 0)
        self.assertGreater(output.confidence, 0.0)
        self.assertLess(output.confidence, 1.0)

    def test_strategy_selector_output(self):
        """Test StrategySelector produces ranked output."""
        selector = StrategySelector()
        output = selector.select_strategies(
            self.state.market_regime,
            self.state.entities,
            self.state.constraints,
        )

        self.assertEqual(output.agent_role, AgentRole.STRATEGY_SELECTOR)
        self.assertGreater(len(output.recommendations), 0)

    def test_executor_output(self):
        """Test Executor produces execution plan."""
        executor = Executor()
        output = executor.plan_execution(
            "gamma_scalping",
            self.state.entities,
            self.state.constraints,
            expected_payoff=200.0,
        )

        self.assertEqual(output.agent_role, AgentRole.EXECUTOR)
        self.assertIn("gamma_scalping", output.analysis)

    def test_coordination_result(self):
        """Test full coordination produces result."""
        result = self.coordinator.coordinate(self.state)

        self.assertGreater(len(result.agent_outputs), 0)
        self.assertIsNotNone(result.final_recommendation)
        self.assertGreater(result.total_latency_ms, 0.0)
        self.assertLess(result.total_latency_ms, 5000.0 * 1.5)

    def test_coordination_latency(self):
        """Test coordination respects latency budget."""
        start = time.time()
        result = self.coordinator.coordinate(self.state)
        elapsed = (time.time() - start) * 1000

        self.assertLessEqual(result.total_latency_ms, 5000.0)
        self.assertLess(elapsed, 5000.0 * 1.5)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        self.engine = ReasoningEngine()

    def test_empty_entities_handling(self):
        """Test reasoning with no entities."""
        state = self.engine.reason(
            MarketRegime.HIGH_VOL,
            [],  # No entities
            [],
            [],
        )

        self.assertEqual(len(state.entities), 0)
        self.assertGreater(len(state.reasoning_chain), 0)

    def test_empty_constraints_handling(self):
        """Test reasoning with no constraints."""
        state = self.engine.reason(
            MarketRegime.HIGH_VOL,
            [{"entity_id": "e1", "entity_type": "Greek", "text": "gamma", "confidence": 0.8}],
            [],  # No constraints
            [],
        )

        self.assertEqual(len(state.constraints), 0)
        self.assertGreater(len(state.reasoning_chain), 0)

    def test_zero_confidence_entities(self):
        """Test handling of very low confidence entities."""
        entities = [
            {"entity_id": "e1", "entity_type": "Greek", "text": "gamma", "confidence": 0.1}
        ]
        state = self.engine.reason(
            MarketRegime.HIGH_VOL,
            entities,
            [],
            [],
        )

        self.assertGreater(len(state.reasoning_chain), 0)

    def test_all_regimes_supported(self):
        """Test that all market regimes are supported."""
        for regime in MarketRegime:
            state = self.engine.reason(regime, [], [], [])
            self.assertEqual(state.market_regime, regime)

    def test_very_tight_latency_budget(self):
        """Test reasoning with very tight latency budget."""
        state = self.engine.reason(
            MarketRegime.HIGH_VOL,
            [],
            [],
            [],
            latency_budget_ms=10.0,  # 10ms is very tight
        )

        # Should still complete
        self.assertGreater(len(state.reasoning_chain), 0)
        self.assertLess(state.accumulated_latency_ms, 200.0)


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple components."""

    def test_full_reasoning_pipeline(self):
        """Test complete reasoning pipeline from input to recommendation."""
        engine = ReasoningEngine()
        coordinator = AgentCoordinator()

        # Run reasoning
        state = engine.reason(
            market_regime=MarketRegime.HIGH_VOL,
            entities=[
                {"entity_id": "e1", "entity_type": "Greek.gamma", "text": "gamma", "confidence": 0.9},
                {"entity_id": "e2", "entity_type": "Strategy", "text": "straddle", "confidence": 0.85},
            ],
            constraints=[
                {"constraint_type": ConstraintType.GREEK_EXPOSURE, "description": "Gamma limit", "value": 100}
            ],
            retrieved_documents=[],
        )

        # Get recommendation from reasoning
        rec = engine.get_best_recommendation(state)

        # Run coordination
        result = coordinator.coordinate(
            state,
            recommended_strategy=rec.get("recommendation"),
            expected_payoff=rec.get("expected_payoff", 0.0),
        )

        # Verify results
        self.assertGreater(len(state.reasoning_chain), 0)
        self.assertGreater(len(result.agent_outputs), 0)
        self.assertLess(result.total_latency_ms, 5000.0)

    def test_end_to_end_latency_constraint(self):
        """Test complete pipeline respects end-to-end latency."""
        engine = ReasoningEngine(max_total_latency_ms=2000.0)
        coordinator = AgentCoordinator(max_latency_ms=2000.0)

        start = time.time()
        state = engine.reason(
            MarketRegime.HIGH_VOL,
            [{"entity_id": "e1", "entity_type": "Greek", "text": "gamma", "confidence": 0.8}],
            [],
            [],
            latency_budget_ms=1500.0,
        )
        reason_elapsed = (time.time() - start) * 1000

        result = coordinator.coordinate(state)
        coord_elapsed = (time.time() - start) * 1000

        self.assertLess(reason_elapsed, 1500.0 * 1.2)
        self.assertLess(coord_elapsed, 2000.0 * 1.5)


if __name__ == "__main__":
    # Run all tests
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    print("=" * 70)

    exit(0 if result.wasSuccessful() else 1)
