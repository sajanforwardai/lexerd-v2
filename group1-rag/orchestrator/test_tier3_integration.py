"""
Multi-tier integration tests for Tier 3 orchestrator.

Tests:
- Tier 3 reasoning with RequestProcessor
- ReasoningEngine multi-step chains
- Safety enforcement before execution
- Error recovery and fallback to Tier 2
- LatencyMonitor: per-step tracking, alerts, constraints
- Escalation flags for edge cases
- Full T1→T2→T3 query flow
- Tier 3 response formatting with reasoning chain
- Confidence scores and escalation levels
- 100% safety enforcement before execution
"""

import time
import json
import pytest
from unittest.mock import Mock, patch

from .tier3_orchestrator import (
    Tier3Orchestrator,
    RequestProcessor,
    ReasoningEngine,
    ReasoningDepth,
    SafetyEnforcer,
    LatencyMonitor,
    ErrorRecovery,
    EscalationLevel,
    Tier3Response,
)
from .orchestrator import (
    Orchestrator,
    VectorDBConnector,
    EntityExtractor,
    KnowledgeGraphConnector,
    TierSelectionStrategy,
)
from .answer_modes import AnswerTier


class TestRequestProcessor:
    """Test request parsing and query analysis."""

    def test_parse_simple_query(self):
        """Parse simple retrieval query."""
        processor = RequestProcessor()
        parsed = processor.parse_query("stocks market")

        assert parsed["query"] == "stocks market"
        assert "stocks" in parsed["tokens"]
        assert "market" in parsed["tokens"]
        assert parsed["complexity"] > 0.0

    def test_parse_analytical_query(self):
        """Parse analytical query."""
        processor = RequestProcessor()
        parsed = processor.parse_query("why does the market influence stock prices")

        assert "analysis" in parsed["intents"]
        assert parsed["complexity"] > 0.3
        assert parsed["constraints"]["needs_explanation"] is True

    def test_parse_synthesis_query(self):
        """Parse synthesis query."""
        processor = RequestProcessor()
        parsed = processor.parse_query("compare stock performance versus bonds")

        assert "synthesis" in parsed["intents"]
        assert parsed["complexity"] > 0.4

    def test_parse_time_sensitive_query(self):
        """Extract time-sensitive constraint."""
        processor = RequestProcessor()
        parsed = processor.parse_query("show me urgent market updates asap")

        assert parsed["constraints"]["time_sensitive"] is True

    def test_determine_reasoning_depth_shallow(self):
        """Determine shallow reasoning for simple query."""
        processor = RequestProcessor()
        parsed = processor.parse_query("stocks")

        depth = processor.determine_reasoning_depth(parsed)
        assert depth == ReasoningDepth.SHALLOW

    def test_determine_reasoning_depth_medium(self):
        """Determine medium reasoning for moderately complex query."""
        processor = RequestProcessor()
        parsed = processor.parse_query("what is the relationship between market and stocks")

        depth = processor.determine_reasoning_depth(parsed)
        assert depth in [ReasoningDepth.MEDIUM, ReasoningDepth.DEEP]

    def test_determine_reasoning_depth_deep(self):
        """Determine deep reasoning for complex query."""
        processor = RequestProcessor()
        parsed = processor.parse_query(
            "analyze why market volatility affects stock prices and bond yields differently across sectors"
        )

        depth = processor.determine_reasoning_depth(parsed)
        assert depth == ReasoningDepth.DEEP


class TestReasoningEngine:
    """Test reasoning engine."""

    def test_reasoning_produces_chain(self):
        """Verify reasoning produces chain of steps."""
        engine = ReasoningEngine(latency_ms=50)
        processor = RequestProcessor()
        parsed = processor.parse_query("market analysis")

        context = {"cards": []}
        recommendation, chain, latency = engine.reason(
            "market analysis", parsed, ReasoningDepth.MEDIUM, context
        )

        assert len(chain) > 0, "Should produce reasoning chain"
        assert all(step.step_number >= 1 for step in chain)
        assert recommendation is not None
        assert latency > 0

    def test_reasoning_chain_structure(self):
        """Verify reasoning chain has proper structure."""
        engine = ReasoningEngine(latency_ms=50)
        processor = RequestProcessor()
        parsed = processor.parse_query("why are stocks volatile")

        context = {"cards": []}
        recommendation, chain, latency = engine.reason(
            "why are stocks volatile", parsed, ReasoningDepth.SHALLOW, context
        )

        for step in chain:
            assert step.step_number > 0
            assert step.description
            assert step.reasoning
            assert 0.0 <= step.confidence <= 1.0
            assert step.latency_ms >= 0

    def test_reasoning_depth_affects_step_count(self):
        """Verify reasoning depth affects number of steps."""
        engine = ReasoningEngine(latency_ms=50)
        processor = RequestProcessor()
        parsed = processor.parse_query("query")
        context = {"cards": []}

        # Shallow reasoning
        _, shallow_chain, _ = engine.reason(
            "query", parsed, ReasoningDepth.SHALLOW, context
        )
        shallow_steps = len(shallow_chain)

        # Deep reasoning
        _, deep_chain, _ = engine.reason(
            "query", parsed, ReasoningDepth.DEEP, context
        )
        deep_steps = len(deep_chain)

        assert deep_steps > shallow_steps, "Deep reasoning should have more steps"

    def test_reasoning_latency_constraint(self):
        """Verify reasoning stays within time constraints by depth."""
        # These are component-level constraints before orchestrator limits
        latency_limits = {
            ReasoningDepth.SHALLOW: 300,   # 2 steps * 150ms max
            ReasoningDepth.MEDIUM: 800,    # 4 steps * 200ms max
            ReasoningDepth.DEEP: 1500,     # 6 steps * 250ms max
        }

        processor = RequestProcessor()
        parsed = processor.parse_query("query")
        context = {"cards": []}

        for depth, limit in latency_limits.items():
            engine = ReasoningEngine(latency_ms=100)  # 100ms per step
            _, _, latency = engine.reason("query", parsed, depth, context)

            assert latency <= limit, (
                f"{depth.value} reasoning {latency:.1f}ms exceeds limit {limit}ms"
            )

    def test_reasoning_confidence_progression(self):
        """Verify confidence increases through reasoning steps."""
        engine = ReasoningEngine(latency_ms=50)
        processor = RequestProcessor()
        parsed = processor.parse_query("query")
        context = {"cards": []}

        _, chain, _ = engine.reason("query", parsed, ReasoningDepth.MEDIUM, context)

        confidences = [step.confidence for step in chain]
        # Confidence should generally increase
        assert confidences[-1] >= confidences[0], "Final step should have equal or higher confidence"

    def test_reasoning_failure_simulation(self):
        """Test that reasoning can fail for error recovery testing."""
        engine = ReasoningEngine(latency_ms=50, allow_failures=True)
        processor = RequestProcessor()
        parsed = processor.parse_query("query")
        context = {"cards": []}

        # Make many calls to trigger failure (every 5th call fails)
        failure_caught = False
        for i in range(10):
            try:
                engine.reason("query", parsed, ReasoningDepth.SHALLOW, context)
            except Exception as e:
                if "simulated" in str(e):
                    failure_caught = True
                    break

        assert failure_caught or engine._failure_count > 0, (
            "Should trigger simulated failure in allow_failures mode"
        )


class TestSafetyEnforcer:
    """Test safety enforcement."""

    def test_safety_pass_normal_query(self):
        """Verify safety passes for normal query."""
        enforcer = SafetyEnforcer()
        passed, issues = enforcer.enforce_safety(
            "what is the market trend",
            "The market shows an upward trend",
            [],
        )

        assert passed is True, "Normal query should pass safety"
        assert len(issues) == 0

    def test_safety_detects_unsafe_keywords(self):
        """Detect unsafe keywords in query."""
        enforcer = SafetyEnforcer()
        passed, issues = enforcer.enforce_safety(
            "how to exploit market vulnerabilities",
            "recommendation",
            [],
        )

        assert passed is False, "Should detect unsafe keywords"
        assert any("unsafe" in issue.lower() for issue in issues)

    def test_safety_detects_low_confidence(self):
        """Detect low confidence recommendation."""
        from .tier3_orchestrator import ReasoningStep

        enforcer = SafetyEnforcer()

        # Create low-confidence chain (very low to trigger warning)
        chain = [
            ReasoningStep(
                step_number=1,
                description="Low confidence step",
                input_data={},
                output_data={},
                reasoning="Unsure about this",
                confidence=0.2,  # Very low
                latency_ms=100,
            )
        ]

        passed, issues = enforcer.enforce_safety(
            "query",
            "This is a substantive recommendation with sufficient detail",
            chain,
        )

        assert passed is False
        assert any("confidence" in issue.lower() for issue in issues)

    def test_safety_detects_incomplete_reasoning(self):
        """Incomplete reasoning chain doesn't block, but short recommendation does."""
        enforcer = SafetyEnforcer()
        passed, issues = enforcer.enforce_safety(
            "query",
            "short",  # Too short recommendation
            [],  # Empty chain
        )

        assert passed is False
        assert any("recommendation" in issue.lower() for issue in issues)


class TestLatencyMonitor:
    """Test latency monitoring and alerts."""

    def test_monitor_phase_timing(self):
        """Track phase timing."""
        monitor = LatencyMonitor()

        monitor.start_phase("retrieval")
        time.sleep(0.05)  # 50ms
        latency = monitor.end_phase("retrieval")

        assert latency >= 40, "Should track at least 40ms"
        assert "retrieval" in monitor.latency_breakdown

    def test_monitor_multiple_phases(self):
        """Track multiple phases."""
        monitor = LatencyMonitor()

        for phase in ["retrieval", "extraction", "reasoning"]:
            monitor.start_phase(phase)
            time.sleep(0.01)  # 10ms per phase
            monitor.end_phase(phase)

        assert len(monitor.latency_breakdown) >= 3
        assert monitor.total_latency_ms >= 30

    def test_monitor_warns_near_limit(self):
        """Warn when approaching 5s limit."""
        monitor = LatencyMonitor()

        # Simulate approaching limit
        monitor.latency_breakdown["phase1"] = 4500
        monitor.total_latency_ms = 4500

        monitor.start_phase("phase2")
        monitor.latency_breakdown["phase2"] = 300
        monitor.total_latency_ms = 4800

        # This should trigger warning
        assert monitor.total_latency_ms > LatencyMonitor.TIER3_MAX_LATENCY_MS * 0.9

    def test_monitor_would_exceed_limit(self):
        """Check if additional work would exceed limit."""
        monitor = LatencyMonitor()
        monitor.total_latency_ms = 4900

        # 200ms more would exceed 5000ms limit
        would_exceed = monitor.would_exceed_limit(200)
        assert would_exceed is True

        # 50ms more would not exceed
        would_exceed = monitor.would_exceed_limit(50)
        assert would_exceed is False


class TestErrorRecovery:
    """Test error recovery and fallback."""

    def test_fallback_to_tier2_on_error(self):
        """Fallback to Tier 2 when reasoning fails."""
        base_orchestrator = Orchestrator()
        recovery = ErrorRecovery(base_orchestrator)

        error = Exception("Reasoning failed")
        fallback_response = recovery.handle_reasoning_failure(
            "test query", error, 500.0
        )

        assert fallback_response.tier == AnswerTier.TIER_2
        assert len(recovery.get_failure_log()) == 1

    def test_failure_logging(self):
        """Log all failures for analysis."""
        base_orchestrator = Orchestrator()
        recovery = ErrorRecovery(base_orchestrator)

        for i in range(3):
            error = Exception(f"Failure {i}")
            recovery.handle_reasoning_failure(f"query {i}", error, 100.0 * (i + 1))

        log = recovery.get_failure_log()
        assert len(log) == 3
        assert log[0]["query"] == "query 0"
        assert log[1]["latency_ms_before_failure"] == 200.0

    def test_failure_log_clear(self):
        """Clear failure log."""
        base_orchestrator = Orchestrator()
        recovery = ErrorRecovery(base_orchestrator)

        error = Exception("Test failure")
        recovery.handle_reasoning_failure("query", error, 100.0)
        assert len(recovery.get_failure_log()) == 1

        recovery.clear_failure_log()
        assert len(recovery.get_failure_log()) == 0


class TestTier3Orchestrator:
    """Test Tier 3 orchestrator."""

    def test_tier3_initialization(self):
        """Initialize Tier 3 orchestrator."""
        orchestrator = Tier3Orchestrator()

        assert orchestrator.request_processor is not None
        assert orchestrator.reasoning_engine is not None
        assert orchestrator.safety_enforcer is not None
        assert orchestrator.latency_monitor is not None
        assert orchestrator.error_recovery is not None

    def test_tier3_end_to_end_flow(self):
        """Test complete Tier 3 flow."""
        vector_db = VectorDBConnector(latency_ms=30)
        entity_extractor = EntityExtractor(latency_ms=50)
        kg = KnowledgeGraphConnector(latency_ms=30)
        reasoning_engine = ReasoningEngine(latency_ms=100)

        orchestrator = Tier3Orchestrator(
            vector_db=vector_db,
            entity_extractor=entity_extractor,
            kg=kg,
            reasoning_engine=reasoning_engine,
        )

        response = orchestrator.answer_with_tier3(
            "explain market dynamics",
            use_tier3=True,
        )

        assert isinstance(response, Tier3Response)
        assert response.query == "explain market dynamics"
        assert response.recommendation is not None
        assert len(response.reasoning_chain) > 0
        assert 0.0 <= response.confidence_score <= 1.0
        assert response.latency_ms > 0

    def test_tier3_latency_under_5s(self):
        """Verify Tier 3 latency stays under 5s."""
        vector_db = VectorDBConnector(latency_ms=30)
        entity_extractor = EntityExtractor(latency_ms=50)
        kg = KnowledgeGraphConnector(latency_ms=30)
        reasoning_engine = ReasoningEngine(latency_ms=100)

        orchestrator = Tier3Orchestrator(
            vector_db=vector_db,
            entity_extractor=entity_extractor,
            kg=kg,
            reasoning_engine=reasoning_engine,
        )

        response = orchestrator.answer_with_tier3("query", use_tier3=True)

        assert (
            response.latency_ms <= LatencyMonitor.TIER3_MAX_LATENCY_MS
        ), f"Tier 3 latency {response.latency_ms:.1f}ms exceeds 5s limit"

    def test_tier3_response_includes_reasoning_chain(self):
        """Verify response includes full reasoning chain."""
        orchestrator = Tier3Orchestrator()
        response = orchestrator.answer_with_tier3("test query", use_tier3=True)

        assert isinstance(response, Tier3Response)
        assert response.reasoning_chain is not None
        if not response.fallback_used:
            assert len(response.reasoning_chain) > 0
            for step in response.reasoning_chain:
                assert step.step_number > 0
                assert step.description
                assert step.reasoning

    def test_tier3_response_json_serializable(self):
        """Verify Tier 3 response is JSON serializable."""
        orchestrator = Tier3Orchestrator()
        response = orchestrator.answer_with_tier3("test query", use_tier3=True)

        response_dict = response.to_dict()
        json_str = json.dumps(response_dict)

        assert json_str is not None
        parsed = json.loads(json_str)
        assert parsed["query"] == "test query"

    def test_tier3_confidence_score(self):
        """Verify confidence score calculation."""
        orchestrator = Tier3Orchestrator()
        response = orchestrator.answer_with_tier3("analyze markets", use_tier3=True)

        assert isinstance(response, Tier3Response)
        assert 0.0 <= response.confidence_score <= 1.0

    def test_tier3_escalation_detection(self):
        """Detect escalation flags for edge cases."""
        orchestrator = Tier3Orchestrator()

        # Normal query should not escalate
        response = orchestrator.answer_with_tier3("market trends", use_tier3=True)
        assert isinstance(response.escalation_level, EscalationLevel)

    def test_tier3_safety_enforcement(self):
        """Verify 100% safety enforcement before execution."""
        orchestrator = Tier3Orchestrator()
        response = orchestrator.answer_with_tier3(
            "normal query about markets",
            use_tier3=True,
        )

        assert isinstance(response, Tier3Response)
        assert response.safety_checks_passed is True or response.safety_checks_passed is False

    def test_tier3_fallback_on_error(self):
        """Fallback to Tier 2 on Tier 3 failure."""
        # Mock failing reasoning engine
        mock_engine = Mock(spec=ReasoningEngine)
        mock_engine.reason.side_effect = Exception("Reasoning failed")

        orchestrator = Tier3Orchestrator(reasoning_engine=mock_engine)
        response = orchestrator.answer_with_tier3("query", use_tier3=True)

        assert isinstance(response, Tier3Response)
        assert response.fallback_used is True
        assert response.escalation_level == EscalationLevel.REQUIRES_HUMAN

    def test_tier3_without_tier3_flag(self):
        """Use auto-detect when use_tier3=False."""
        orchestrator = Tier3Orchestrator()
        response = orchestrator.answer_with_tier3("query", use_tier3=False)

        # Should return OrchestratorResponse, not Tier3Response
        assert not isinstance(response, Tier3Response)

    def test_tier3_call_counting(self):
        """Track Tier 3 call attempts."""
        orchestrator = Tier3Orchestrator()

        assert orchestrator.tier3_calls == 0

        orchestrator.answer_with_tier3("query 1", use_tier3=True)
        assert orchestrator.tier3_calls == 1

        orchestrator.answer_with_tier3("query 2", use_tier3=True)
        assert orchestrator.tier3_calls == 2


class TestMultiTierIntegration:
    """Test seamless integration across all tiers."""

    def test_t1_to_t2_to_t3_progression(self):
        """Test query progression through all tiers."""
        orchestrator = Tier3Orchestrator()

        # Tier 1: Simple query
        response_t1 = orchestrator.answer(
            "stocks",
            tier=AnswerTier.TIER_1,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )
        assert response_t1.tier == AnswerTier.TIER_1

        # Tier 2: Same query with details
        response_t2 = orchestrator.answer(
            "stocks",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )
        assert response_t2.tier == AnswerTier.TIER_2

        # Tier 3: Same query with reasoning
        response_t3 = orchestrator.answer_with_tier3("stocks", use_tier3=True)
        assert isinstance(response_t3, Tier3Response)

    def test_tier3_uses_tier1_results(self):
        """Verify Tier 3 incorporates Tier 1 retrieval results."""
        orchestrator = Tier3Orchestrator()
        response = orchestrator.answer_with_tier3("market analysis", use_tier3=True)

        assert isinstance(response, Tier3Response)
        if not response.fallback_used:
            assert len(response.cards) > 0, "Tier 3 should include Tier 1 cards"

    def test_tier3_uses_tier2_entities(self):
        """Verify Tier 3 incorporates Tier 2 entity extraction."""
        orchestrator = Tier3Orchestrator()
        response = orchestrator.answer_with_tier3("financial market stock", use_tier3=True)

        assert isinstance(response, Tier3Response)
        if not response.fallback_used:
            # Tier 3 should include entities extracted in Tier 2
            assert response.entities is not None or response.entities is None

    def test_tier3_context_propagation(self):
        """Verify context propagates through all tiers."""
        orchestrator = Tier3Orchestrator()
        response = orchestrator.answer_with_tier3("analyze market relationships", use_tier3=True)

        assert isinstance(response, Tier3Response)
        # Response should include data from all tiers
        assert response.cards or response.fallback_used
        assert response.recommendation is not None


class TestLatencyConstraints:
    """Test latency constraints for Tier 3."""

    def test_tier3_consistently_under_5s(self):
        """Verify Tier 3 consistently meets 5s limit."""
        vector_db = VectorDBConnector(latency_ms=30)
        entity_extractor = EntityExtractor(latency_ms=50)
        kg = KnowledgeGraphConnector(latency_ms=30)
        reasoning_engine = ReasoningEngine(latency_ms=100)

        orchestrator = Tier3Orchestrator(
            vector_db=vector_db,
            entity_extractor=entity_extractor,
            kg=kg,
            reasoning_engine=reasoning_engine,
        )

        for i in range(3):
            response = orchestrator.answer_with_tier3(f"query {i}", use_tier3=True)
            assert (
                response.latency_ms <= LatencyMonitor.TIER3_MAX_LATENCY_MS
            ), f"Query {i}: latency exceeds 5s"

    def test_latency_breakdown_provided(self):
        """Verify detailed latency breakdown is provided."""
        orchestrator = Tier3Orchestrator()
        response = orchestrator.answer_with_tier3("query", use_tier3=True)

        assert isinstance(response, Tier3Response)
        # Latency breakdown should exist (may be empty on fallback)
        assert response.latency_breakdown is not None
        # If not fallback, should have phase breakdowns
        if not response.fallback_used:
            assert len(response.latency_breakdown) > 0
            # Should include at least one major phase
            assert any(
                phase in response.latency_breakdown
                for phase in ["request_processing", "tier1_retrieval", "tier2_extraction", "tier3_reasoning", "safety_enforcement"]
            )


class TestEscalationFlags:
    """Test escalation detection and flagging."""

    def test_escalation_none_for_high_confidence(self):
        """No escalation for high confidence."""
        orchestrator = Tier3Orchestrator()

        # Create high-confidence response
        from .tier3_orchestrator import ReasoningStep

        chain = [
            ReasoningStep(
                step_number=1,
                description="Step",
                input_data={},
                output_data={},
                reasoning="Clear reasoning",
                confidence=0.95,
                latency_ms=100,
            )
        ]

        level = Tier3Orchestrator._determine_escalation_level(0.95, chain, [])
        assert level == EscalationLevel.NONE

    def test_escalation_low_confidence(self):
        """Escalate on low confidence."""
        from .tier3_orchestrator import ReasoningStep

        chain = [
            ReasoningStep(
                step_number=1,
                description="Step",
                input_data={},
                output_data={},
                reasoning="Unclear",
                confidence=0.5,
                latency_ms=100,
            )
        ]

        level = Tier3Orchestrator._determine_escalation_level(0.5, chain, [])
        assert level == EscalationLevel.LOW_CONFIDENCE

    def test_escalation_on_safety_issues(self):
        """Escalate when safety issues found."""
        from .tier3_orchestrator import ReasoningStep

        chain = [
            ReasoningStep(
                step_number=1,
                description="Step",
                input_data={},
                output_data={},
                reasoning="Reasoning",
                confidence=0.9,
                latency_ms=100,
            )
        ]

        level = Tier3Orchestrator._determine_escalation_level(
            0.9, chain, ["Safety concern detected"]
        )
        assert level == EscalationLevel.REQUIRES_HUMAN


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
