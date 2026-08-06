#!/usr/bin/env python3
"""
Example usage of Tier 3 Agentic Reasoning Engine.

Demonstrates:
- ReasoningEngine with Tree-of-Thought
- State management and constraint validation
- RankingFunction for strategy evaluation
- Multi-agent coordination
- Latency budget enforcement
- Integration with Tier 1+2 outputs
"""

import json
import time
from typing import Dict, List

from reasoning_engine import (
    ReasoningEngine,
    MarketRegime,
    ConstraintType,
    Entity,
    Constraint,
)
from agent_coordinator import AgentCoordinator


def example_1_basic_reasoning():
    """Example 1: Basic reasoning with high volatility regime."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Tree-of-Thought Reasoning")
    print("="*70)

    # Initialize engine
    engine = ReasoningEngine(
        max_depth=3,
        max_branching_factor=3,
        max_total_latency_ms=5000.0,
    )

    # Market data
    market_regime = MarketRegime.HIGH_VOL
    entities = [
        {"entity_id": "e1", "entity_type": "Greek.gamma", "text": "gamma", "confidence": 0.95},
        {"entity_id": "e2", "entity_type": "Greek.vega", "text": "vega", "confidence": 0.90},
        {"entity_id": "e3", "entity_type": "Strategy", "text": "straddle", "confidence": 0.85},
    ]
    constraints = [
        {"constraint_type": ConstraintType.GREEK_EXPOSURE, "description": "Gamma limit", "value": 100},
        {"constraint_type": ConstraintType.NOTIONAL_LIMIT, "description": "Notional limit", "value": 1000},
    ]

    # Execute reasoning
    print(f"\nMarket Regime: {market_regime.value}")
    print(f"Entities: {len(entities)}")
    print(f"Constraints: {len(constraints)}")

    start = time.time()
    state = engine.reason(
        market_regime=market_regime,
        entities=entities,
        constraints=constraints,
        retrieved_documents=[],
    )
    elapsed = (time.time() - start) * 1000

    # Display results
    print(f"\nReasoning Results:")
    print(f"  Reasoning chain length: {len(state.reasoning_chain)} steps")
    print(f"  Tree size: {len(state.reasoning_tree)} nodes")
    print(f"  Max tree depth: {max(n.depth for n in state.reasoning_tree.values())}")
    print(f"  Latency: {elapsed:.1f}ms")

    # Show reasoning chain
    print(f"\nReasoning Chain:")
    for i, step in enumerate(state.reasoning_chain, 1):
        print(f"  {i}. [{step.step_type.value}] {step.description}")
        print(f"     Confidence: {step.confidence:.2f}, Duration: {step.duration_ms:.1f}ms")

    # Get best recommendation
    best = engine.get_best_recommendation(state)
    print(f"\nBest Recommendation:")
    print(f"  Strategy: {best['recommendation']}")
    print(f"  Confidence: {best['confidence']:.2f}")
    print(f"  Expected payoff: {best['expected_payoff']:.0f} bps")


def example_2_different_regimes():
    """Example 2: Compare reasoning across different market regimes."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Reasoning Across Market Regimes")
    print("="*70)

    engine = ReasoningEngine()

    # Test entities
    entities = [
        {"entity_id": "e1", "entity_type": "Greek.gamma", "text": "gamma", "confidence": 0.9},
        {"entity_id": "e2", "entity_type": "Strategy", "text": "scalping", "confidence": 0.85},
    ]

    # Test each regime
    regimes = [
        MarketRegime.HIGH_VOL,
        MarketRegime.LOW_VOL,
        MarketRegime.TREND,
        MarketRegime.MEAN_REVERT,
    ]

    results = {}
    for regime in regimes:
        state = engine.reason(regime, entities, [], [])
        best = engine.get_best_recommendation(state)
        results[regime.value] = best

        print(f"\n{regime.value.upper()}:")
        print(f"  Top strategy: {best['recommendation']}")
        print(f"  Confidence: {best['confidence']:.2f}")
        print(f"  Expected payoff: {best['expected_payoff']:.0f} bps")


def example_3_constraint_validation():
    """Example 3: Constraint validation and impact on reasoning."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Constraint Validation and Impact")
    print("="*70)

    engine = ReasoningEngine()

    entities = [
        {"entity_id": "e1", "entity_type": "Greek.gamma", "text": "gamma", "confidence": 0.9},
    ]

    # Scenario 1: No constraints
    print("\nScenario 1: No constraints")
    state1 = engine.reason(MarketRegime.HIGH_VOL, entities, [], [])
    best1 = engine.get_best_recommendation(state1)
    print(f"  Recommendation: {best1['recommendation']}")
    print(f"  Confidence: {best1['confidence']:.2f}")

    # Scenario 2: With constraints
    print("\nScenario 2: With constraints")
    constraints = [
        {"constraint_type": ConstraintType.GREEK_EXPOSURE, "description": "Gamma limit", "value": 50},
        {"constraint_type": ConstraintType.POSITION_LIMIT, "description": "Pos limit", "value": 100},
    ]
    state2 = engine.reason(MarketRegime.HIGH_VOL, entities, constraints, [])
    best2 = engine.get_best_recommendation(state2)
    print(f"  Recommendation: {best2['recommendation']}")
    print(f"  Confidence: {best2['confidence']:.2f}")

    # Validate constraints in state
    valid, violations = state2.validate_constraints()
    print(f"\n  Constraint validation: {'PASS' if valid else 'FAIL'}")
    if violations:
        print(f"  Violations: {violations}")


def example_4_multi_agent_coordination():
    """Example 4: Multi-agent coordination."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Multi-Agent Coordination")
    print("="*70)

    # Setup
    engine = ReasoningEngine()
    coordinator = AgentCoordinator(max_latency_ms=5000.0)

    # Run reasoning first
    state = engine.reason(
        market_regime=MarketRegime.HIGH_VOL,
        entities=[
            {"entity_id": "e1", "entity_type": "Greek.gamma", "text": "gamma", "confidence": 0.9},
            {"entity_id": "e2", "entity_type": "Strategy", "text": "straddle", "confidence": 0.85},
        ],
        constraints=[],
        retrieved_documents=[],
    )

    # Get recommendation from reasoning
    best = engine.get_best_recommendation(state)

    # Run coordination
    print(f"\nRecommended strategy: {best['recommendation']}")
    print(f"Expected payoff: {best['expected_payoff']:.0f} bps")

    start = time.time()
    result = coordinator.coordinate(
        state,
        recommended_strategy=best['recommendation'],
        expected_payoff=best['expected_payoff'],
    )
    elapsed = (time.time() - start) * 1000

    # Display coordination results
    print(f"\nCoordination Results:")
    print(f"  Agents executed: {len(result.agent_outputs)}")
    print(f"  Total latency: {elapsed:.1f}ms")

    for i, output in enumerate(result.agent_outputs, 1):
        print(f"\n  Agent {i}: {output.agent_role.value}")
        print(f"    Confidence: {output.confidence:.2f}")
        print(f"    Latency: {output.latency_ms:.1f}ms")
        print(f"    Conclusions: {len(output.conclusions)}")
        if output.recommendations:
            print(f"    Recommendations: {', '.join(output.recommendations[:2])}")


def example_5_latency_budget():
    """Example 5: Latency budget enforcement."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Latency Budget Enforcement")
    print("="*70)

    engine = ReasoningEngine()

    entities = [
        {"entity_id": f"e{i}", "entity_type": "Greek", "text": f"greek_{i}", "confidence": 0.8}
        for i in range(5)
    ]

    # Test different budgets
    budgets = [500.0, 1000.0, 2000.0, 5000.0]

    print(f"\nTesting different latency budgets:")
    for budget in budgets:
        start = time.time()
        state = engine.reason(
            MarketRegime.HIGH_VOL,
            entities,
            [],
            [],
            latency_budget_ms=budget,
        )
        elapsed = (time.time() - start) * 1000

        print(f"\n  Budget: {budget:.0f}ms")
        print(f"    Actual latency: {elapsed:.1f}ms")
        print(f"    Reasoning steps: {len(state.reasoning_chain)}")
        print(f"    Tree nodes: {len(state.reasoning_tree)}")
        print(f"    Status: {'PASS' if elapsed < budget * 1.2 else 'FAIL'}")


def example_6_state_serialization():
    """Example 6: State serialization to JSON."""
    print("\n" + "="*70)
    print("EXAMPLE 6: State Serialization to JSON")
    print("="*70)

    engine = ReasoningEngine()

    state = engine.reason(
        market_regime=MarketRegime.HIGH_VOL,
        entities=[
            {"entity_id": "e1", "entity_type": "Greek", "text": "gamma", "confidence": 0.9},
        ],
        constraints=[
            {"constraint_type": ConstraintType.GREEK_EXPOSURE, "description": "Limit", "value": 100}
        ],
        retrieved_documents=[],
    )

    # Serialize to dict
    state_dict = state.to_dict()

    print(f"\nSerialized State:")
    print(f"  Market regime: {state_dict['market_regime']}")
    print(f"  Entities: {len(state_dict['entities'])}")
    print(f"  Constraints: {len(state_dict['constraints'])}")
    print(f"  Reasoning steps: {len(state_dict['reasoning_chain'])}")
    print(f"  Tree size: {state_dict['reasoning_tree_size']}")
    print(f"  Latency: {state_dict['accumulated_latency_ms']:.1f}ms")

    # Convert to JSON
    json_str = json.dumps(state_dict, indent=2)
    print(f"\nJSON (truncated):")
    print(json_str[:500] + "...")


def example_7_full_pipeline():
    """Example 7: Full pipeline from query to recommendation."""
    print("\n" + "="*70)
    print("EXAMPLE 7: Full Pipeline (Query → Reasoning → Recommendation)")
    print("="*70)

    # Simulate Tier 1+2 outputs
    print("\nStep 1: Tier 1 Retrieval")
    retrieved_docs = [
        {"title": "Trading gamma scalping", "text": "Scalp gamma in high vol regimes..."},
        {"title": "Vol arbitrage", "text": "Trade volatility misalignments..."},
    ]
    print(f"  Retrieved: {len(retrieved_docs)} documents")

    print("\nStep 2: Tier 2 Entity Extraction")
    entities = [
        {"entity_id": "e1", "entity_type": "Greek.gamma", "text": "gamma", "confidence": 0.95},
        {"entity_id": "e2", "entity_type": "Strategy", "text": "scalping", "confidence": 0.88},
        {"entity_id": "e3", "entity_type": "VolSurface", "text": "volatility surface", "confidence": 0.82},
    ]
    print(f"  Extracted: {len(entities)} entities")

    print("\nStep 3: Tier 3 Reasoning")
    engine = ReasoningEngine()
    start = time.time()
    state = engine.reason(
        market_regime=MarketRegime.HIGH_VOL,
        entities=entities,
        constraints=[],
        retrieved_documents=retrieved_docs,
    )
    reasoning_time = (time.time() - start) * 1000
    print(f"  Reasoning time: {reasoning_time:.1f}ms")

    print("\nStep 4: Multi-Agent Coordination")
    coordinator = AgentCoordinator()
    best = engine.get_best_recommendation(state)
    start = time.time()
    result = coordinator.coordinate(state, recommended_strategy=best['recommendation'])
    coord_time = (time.time() - start) * 1000
    print(f"  Coordination time: {coord_time:.1f}ms")

    print("\nStep 5: Final Recommendation")
    print(f"  Strategy: {result.final_recommendation}")
    print(f"  Expected payoff: {best['expected_payoff']:.0f} bps")
    print(f"  Confidence: {best['confidence']:.2f}")
    print(f"  Total latency: {reasoning_time + coord_time:.1f}ms")

    print("\nAgent Outputs:")
    for output in result.agent_outputs:
        print(f"  - {output.agent_role.value}: confidence {output.confidence:.2f}")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("TIER 3 AGENTIC REASONING ENGINE - EXAMPLES")
    print("="*70)

    # Run examples
    example_1_basic_reasoning()
    example_2_different_regimes()
    example_3_constraint_validation()
    example_4_multi_agent_coordination()
    example_5_latency_budget()
    example_6_state_serialization()
    example_7_full_pipeline()

    print("\n" + "="*70)
    print("ALL EXAMPLES COMPLETED")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
