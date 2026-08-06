#!/usr/bin/env python3
"""
Example usage of Tier 3 Orchestrator with multi-step reasoning.

Demonstrates:
- Tier 3 reasoning-based mode (≤5s latency)
- Request parsing and reasoning depth determination
- Multi-tier integration (T1→T2→T3)
- Safety enforcement before execution
- Error recovery and fallback to Tier 2
- Escalation flags for edge cases
- Detailed latency breakdown
- Full reasoning chain visibility
"""

import json
from tier3_orchestrator import (
    Tier3Orchestrator,
    Tier3Response,
    ReasoningEngine,
    LatencyMonitor,
    EscalationLevel,
)
from orchestrator import VectorDBConnector, EntityExtractor, KnowledgeGraphConnector


def print_tier3_response(response: Tier3Response):
    """Pretty-print a Tier 3 response with full reasoning chain."""
    print(f"\n{'='*70}")
    print(f"Tier 3 Reasoning Response")
    print(f"{'='*70}")
    print(f"Query: {response.query}")
    print(f"Total Latency: {response.latency_ms:.1f}ms (limit: 5000ms)")

    # Status
    if response.fallback_used:
        print(f"⚠️  FALLBACK MODE: {response.fallback_reason}")
    print(f"Status: {'✓ Success' if not response.fallback_used else '✗ Failed, using Tier 2'}")

    # Recommendation
    print(f"\n{'─'*70}")
    print(f"RECOMMENDATION")
    print(f"{'─'*70}")
    print(response.recommendation)

    # Confidence & Escalation
    print(f"\n{'─'*70}")
    print(f"CONFIDENCE & ESCALATION")
    print(f"{'─'*70}")
    print(f"Confidence Score: {response.confidence_score:.0%}")
    print(f"Escalation Level: {response.escalation_level.value}")
    if response.escalation_reason:
        print(f"Escalation Reason: {response.escalation_reason}")

    # Safety Enforcement
    print(f"\n{'─'*70}")
    print(f"SAFETY ENFORCEMENT")
    print(f"{'─'*70}")
    print(f"All Checks Passed: {'✓ Yes' if response.safety_checks_passed else '✗ No'}")
    if response.safety_issues:
        print(f"Issues Found ({len(response.safety_issues)}):")
        for issue in response.safety_issues:
            print(f"  - {issue}")

    # Reasoning Chain
    if not response.fallback_used and response.reasoning_chain:
        print(f"\n{'─'*70}")
        print(f"REASONING CHAIN ({len(response.reasoning_chain)} steps)")
        print(f"{'─'*70}")
        for step in response.reasoning_chain:
            print(f"\nStep {step.step_number}: {step.description}")
            print(f"  Reasoning: {step.reasoning[:80]}...")
            print(f"  Confidence: {step.confidence:.0%}")
            print(f"  Latency: {step.latency_ms:.1f}ms")

    # Latency Breakdown
    if response.latency_breakdown:
        print(f"\n{'─'*70}")
        print(f"LATENCY BREAKDOWN")
        print(f"{'─'*70}")
        for phase, latency in response.latency_breakdown.items():
            pct = (latency / response.latency_ms * 100) if response.latency_ms > 0 else 0
            print(f"  {phase:30s}: {latency:7.1f}ms ({pct:5.1f}%)")

    # Retrieved Context (Tier 1)
    if response.cards:
        print(f"\n{'─'*70}")
        print(f"CONTEXT (from Tier 1 retrieval, {len(response.cards)} cards)")
        print(f"{'─'*70}")
        for i, card in enumerate(response.cards[:3], 1):
            print(f"{i}. {card.title} (score: {card.score:.2f})")
            print(f"   {card.content[:70]}...")

    # Entities (Tier 2)
    if response.entities:
        print(f"\n{'─'*70}")
        print(f"ENTITIES (from Tier 2 extraction, {len(response.entities)} found)")
        print(f"{'─'*70}")
        for entity in response.entities[:5]:
            print(f"  • {entity.name} ({entity.entity_type}, {entity.confidence:.0%})")

    print(f"\n{'='*70}\n")


def example_simple_query():
    """Example: Simple query auto-routing through all tiers."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Simple Query - Auto-routing through T1→T2→T3")
    print("="*70)

    orchestrator = Tier3Orchestrator()

    # Simple query that will be routed to Tier 3
    response = orchestrator.answer_with_tier3(
        "What are the recent market trends and their impact on stock performance?",
        use_tier3=True,
    )

    print_tier3_response(response)


def example_complex_analysis():
    """Example: Complex analytical query requiring deep reasoning."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Complex Analysis Query")
    print("="*70)

    orchestrator = Tier3Orchestrator()

    # Complex query requiring synthesis and analysis
    response = orchestrator.answer_with_tier3(
        "Analyze why market volatility affects different asset classes differently and what this means for portfolio management",
        use_tier3=True,
    )

    print_tier3_response(response)


def example_with_custom_connectors():
    """Example: Tier 3 with custom-configured connectors."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Custom Configuration with Optimized Latency")
    print("="*70)

    # Configure fast connectors to stay under 5s limit
    vector_db = VectorDBConnector(latency_ms=30)      # Fast retrieval
    entity_extractor = EntityExtractor(latency_ms=50)  # Medium extraction
    kg = KnowledgeGraphConnector(latency_ms=30)       # Fast KG lookup
    reasoning_engine = ReasoningEngine(latency_ms=100)  # Fast reasoning steps

    orchestrator = Tier3Orchestrator(
        vector_db=vector_db,
        entity_extractor=entity_extractor,
        kg=kg,
        reasoning_engine=reasoning_engine,
    )

    response = orchestrator.answer_with_tier3(
        "Compare bonds and stocks as investment vehicles",
        use_tier3=True,
    )

    print_tier3_response(response)


def example_error_recovery():
    """Example: Error recovery and fallback to Tier 2."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Error Recovery - Fallback to Tier 2")
    print("="*70)

    from unittest.mock import Mock

    # Create orchestrator with failing reasoning engine
    mock_engine = Mock(spec=ReasoningEngine)
    mock_engine.reason.side_effect = Exception("Simulated reasoning engine failure")

    orchestrator = Tier3Orchestrator(reasoning_engine=mock_engine)

    response = orchestrator.answer_with_tier3(
        "Query that will trigger error recovery",
        use_tier3=True,
    )

    print_tier3_response(response)
    print(f"Failure Log: {len(orchestrator.get_failure_log())} failure(s) logged")
    if orchestrator.get_failure_log():
        for log in orchestrator.get_failure_log():
            print(f"  - {log['query']}: {log['error']}")


def example_escalation_scenarios():
    """Example: Various escalation scenarios."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Escalation Scenarios")
    print("="*70)

    orchestrator = Tier3Orchestrator()

    # Query 1: Low confidence scenario (complex analytical query)
    print("\nScenario A: Complex query that may have low confidence")
    response_a = orchestrator.answer_with_tier3(
        "Predict future market movements based on historical patterns",
        use_tier3=True,
    )
    print(f"Escalation: {response_a.escalation_level.value}")
    if response_a.escalation_level != EscalationLevel.NONE:
        print(f"Reason: {response_a.escalation_reason}")

    # Query 2: Normal query
    print("\nScenario B: Straightforward factual query")
    response_b = orchestrator.answer_with_tier3(
        "What is the definition of a stock market index?",
        use_tier3=True,
    )
    print(f"Escalation: {response_b.escalation_level.value}")
    if response_b.escalation_level == EscalationLevel.NONE:
        print("No escalation needed - high confidence response")


def example_json_output():
    """Example: JSON output for API integration."""
    print("\n" + "="*70)
    print("EXAMPLE 6: JSON Output for API Integration")
    print("="*70)

    orchestrator = Tier3Orchestrator()
    response = orchestrator.answer_with_tier3(
        "Explain market efficiency hypothesis",
        use_tier3=True,
    )

    # Convert to JSON-serializable dict
    response_dict = response.to_dict()

    print("JSON Output (first 500 chars):")
    json_str = json.dumps(response_dict, indent=2)
    print(json_str[:500] + "...")

    # Show structure
    print("\nJSON Structure:")
    print(f"  Root keys: {', '.join(response_dict.keys())}")
    print(f"  Reasoning chain: {len(response_dict.get('reasoning_chain', []))} steps")
    print(f"  Context cards: {len(response_dict.get('cards', []))}")


def example_tier_comparison():
    """Example: Compare all three tiers on same query."""
    print("\n" + "="*70)
    print("EXAMPLE 7: Multi-tier Comparison")
    print("="*70)

    from orchestrator import AnswerTier, TierSelectionStrategy

    orchestrator = Tier3Orchestrator()
    query = "What factors drive market volatility?"

    # Tier 1: Fast retrieval only
    print(f"\nTier 1 (Search-only, ≤100ms):")
    response_t1 = orchestrator.answer(
        query,
        tier=AnswerTier.TIER_1,
        strategy=TierSelectionStrategy.USER_SPECIFIED,
    )
    print(f"  Latency: {response_t1.latency_ms:.1f}ms")
    print(f"  Results: {len(response_t1.cards)} cards")
    print(f"  Entities: {response_t1.entities}")

    # Tier 2: With entity extraction
    print(f"\nTier 2 (Detail+extraction, ≤500ms):")
    response_t2 = orchestrator.answer(
        query,
        tier=AnswerTier.TIER_2,
        strategy=TierSelectionStrategy.USER_SPECIFIED,
    )
    print(f"  Latency: {response_t2.latency_ms:.1f}ms")
    print(f"  Results: {len(response_t2.cards)} cards")
    print(f"  Entities: {len(response_t2.entities) if response_t2.entities else 0}")
    print(f"  Relationships: {len(response_t2.relationships) if response_t2.relationships else 0}")

    # Tier 3: With reasoning
    print(f"\nTier 3 (Reasoning, ≤5000ms):")
    response_t3 = orchestrator.answer_with_tier3(query, use_tier3=True)
    print(f"  Latency: {response_t3.latency_ms:.1f}ms")
    print(f"  Results: {len(response_t3.cards)} cards")
    print(f"  Reasoning steps: {len(response_t3.reasoning_chain)}")
    print(f"  Confidence: {response_t3.confidence_score:.0%}")
    print(f"  Recommendation: {response_t3.recommendation[:60]}...")


if __name__ == "__main__":
    # Run examples
    example_simple_query()
    example_complex_analysis()
    example_with_custom_connectors()
    example_error_recovery()
    example_escalation_scenarios()
    example_json_output()
    example_tier_comparison()

    print("\n" + "="*70)
    print("All examples completed!")
    print("="*70)
