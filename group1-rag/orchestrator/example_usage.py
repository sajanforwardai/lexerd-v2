#!/usr/bin/env python3
"""
Example usage of the RAG Orchestrator.

Demonstrates:
- Tier 1 (search-only mode)
- Tier 2 (detail mode with entity extraction)
- Auto-detect tier selection
- Error handling
- JSON response formatting
"""

import json
from orchestrator import (
    Orchestrator,
    VectorDBConnector,
    EntityExtractor,
    KnowledgeGraphConnector,
    AnswerTier,
    TierSelectionStrategy,
)


def print_response(response):
    """Pretty-print a response."""
    print(f"\n{'='*60}")
    print(f"Tier: {response.tier.value}")
    print(f"Query: {response.query}")
    print(f"Latency: {response.latency_ms:.1f}ms")
    print(f"Results: {len(response.cards)} cards")

    if response.error:
        print(f"Error: {response.error}")
    if response.fallback_used:
        print("⚠️  Fallback mode used")

    # Print cards
    print("\nResult Cards:")
    for i, card in enumerate(response.cards, 1):
        print(f"  {i}. {card.title} (score: {card.score:.2f})")
        print(f"     {card.content[:60]}...")

    # Print entities (if available)
    if response.entities:
        print(f"\nEntities ({len(response.entities)}):")
        for entity in response.entities[:3]:
            print(f"  - {entity.name} ({entity.entity_type}, {entity.confidence:.2f})")

    # Print relationships (if available)
    if response.relationships:
        print(f"\nRelationships ({len(response.relationships)}):")
        for rel in response.relationships[:3]:
            print(f"  - {rel.source_entity} → {rel.target_entity} ({rel.relation_type})")


def example_tier1_explicit():
    """Example 1: Explicitly request Tier 1 (search mode)."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Explicit Tier 1 (Search Mode)")
    print("="*60)

    orchestrator = Orchestrator()

    response = orchestrator.answer(
        query="stock market trends",
        tier=AnswerTier.TIER_1,
        strategy=TierSelectionStrategy.USER_SPECIFIED,
    )

    print_response(response)

    # Verify constraints
    assert response.tier == AnswerTier.TIER_1
    assert response.latency_ms <= 100, f"Latency {response.latency_ms}ms exceeds 100ms"
    assert response.entities is None, "Tier 1 should not have entities"
    assert response.relationships is None, "Tier 1 should not have relationships"
    assert orchestrator.claude_calls == 0, "Tier 1 should not call Claude"

    print("\n✓ All Tier 1 constraints verified")


def example_tier2_explicit():
    """Example 2: Explicitly request Tier 2 (detail mode)."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Explicit Tier 2 (Detail Mode)")
    print("="*60)

    orchestrator = Orchestrator()

    response = orchestrator.answer(
        query="financial markets and stock relationships",
        tier=AnswerTier.TIER_2,
        strategy=TierSelectionStrategy.USER_SPECIFIED,
    )

    print_response(response)

    # Verify constraints
    assert response.tier == AnswerTier.TIER_2
    assert response.latency_ms <= 500, f"Latency {response.latency_ms}ms exceeds 500ms"
    assert orchestrator.claude_calls == 0, "Tier 2 should not call Claude"

    print("\n✓ All Tier 2 constraints verified")


def example_auto_detect_simple():
    """Example 3: Auto-detect for simple query → Tier 1."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Auto-Detect Simple Query (→ Tier 1)")
    print("="*60)

    orchestrator = Orchestrator()

    response = orchestrator.answer(
        query="stocks",  # Simple 1-word query
        strategy=TierSelectionStrategy.AUTO_DETECT,
    )

    print_response(response)

    assert response.tier == AnswerTier.TIER_1
    print("\n✓ Auto-detect correctly selected Tier 1")


def example_auto_detect_complex():
    """Example 4: Auto-detect for complex query → Tier 2."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Auto-Detect Complex Query (→ Tier 2)")
    print("="*60)

    orchestrator = Orchestrator()

    response = orchestrator.answer(
        query="what is the relationship between market volatility and bond prices",
        strategy=TierSelectionStrategy.AUTO_DETECT,
    )

    print_response(response)

    assert response.tier == AnswerTier.TIER_2
    print("\n✓ Auto-detect correctly selected Tier 2")


def example_error_handling():
    """Example 5: Error handling and graceful degradation."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Error Handling & Graceful Degradation")
    print("="*60)

    from unittest.mock import Mock

    # Create orchestrator with mocked failing vector DB
    mock_db = Mock(spec=VectorDBConnector)
    mock_db.search.side_effect = Exception("Database connection failed")

    orchestrator = Orchestrator(vector_db=mock_db)

    response = orchestrator.answer(
        query="test query",
        tier=AnswerTier.TIER_1,
        strategy=TierSelectionStrategy.USER_SPECIFIED,
    )

    print(f"Error occurred: {response.error}")
    print(f"Fallback used: {response.fallback_used}")
    print(f"Cards returned: {len(response.cards)}")

    # Response is still valid
    assert response.error is not None or response.fallback_used
    print("\n✓ Graceful degradation working")


def example_json_serialization():
    """Example 6: JSON serialization for API responses."""
    print("\n" + "="*60)
    print("EXAMPLE 6: JSON Serialization")
    print("="*60)

    orchestrator = Orchestrator()

    response = orchestrator.answer(
        query="market analysis",
        tier=AnswerTier.TIER_2,
        strategy=TierSelectionStrategy.USER_SPECIFIED,
    )

    # Convert to JSON-serializable dict
    response_dict = response.to_dict()
    json_str = json.dumps(response_dict, indent=2)

    print("Response as JSON:")
    print(json_str[:500] + "...\n")

    # Verify JSON is valid and deserializable
    parsed = json.loads(json_str)
    assert parsed["tier"] in ["tier_1", "tier_2"]
    assert isinstance(parsed["cards"], list)

    print("✓ JSON serialization verified")


def example_latency_measurement():
    """Example 7: Measure latency for multiple queries."""
    print("\n" + "="*60)
    print("EXAMPLE 7: Latency Measurement")
    print("="*60)

    # Create orchestrator with specific latency parameters
    vector_db = VectorDBConnector(latency_ms=30)
    entity_extractor = EntityExtractor(latency_ms=100)
    kg = KnowledgeGraphConnector(latency_ms=20)

    orchestrator = Orchestrator(
        vector_db=vector_db,
        entity_extractor=entity_extractor,
        kg=kg,
    )

    print("Tier 1 (Search) Latencies:")
    for i in range(3):
        response = orchestrator.answer(
            query=f"query {i}",
            tier=AnswerTier.TIER_1,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )
        print(f"  Query {i}: {response.latency_ms:.1f}ms (≤100ms ✓)" if response.latency_ms <= 100 else f"  Query {i}: {response.latency_ms:.1f}ms ✗")

    print("\nTier 2 (Detail) Latencies:")
    for i in range(3):
        response = orchestrator.answer(
            query=f"complex query {i}",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )
        print(f"  Query {i}: {response.latency_ms:.1f}ms (≤500ms ✓)" if response.latency_ms <= 500 else f"  Query {i}: {response.latency_ms:.1f}ms ✗")


def example_tier_progression():
    """Example 8: Progression from Tier 1 to Tier 2."""
    print("\n" + "="*60)
    print("EXAMPLE 8: Tier Progression")
    print("="*60)

    orchestrator = Orchestrator()

    # Start with Tier 1
    print("Starting with Tier 1...")
    response1 = orchestrator.answer(
        query="stocks",
        tier=AnswerTier.TIER_1,
        strategy=TierSelectionStrategy.USER_SPECIFIED,
    )
    print(f"  Tier: {response1.tier.value}")
    print(f"  Entities: {response1.entities}")

    # Upgrade to Tier 2
    print("\nUpgrading to Tier 2...")
    response2 = orchestrator.answer(
        query="stocks",
        tier=AnswerTier.TIER_2,
        strategy=TierSelectionStrategy.USER_SPECIFIED,
    )
    print(f"  Tier: {response2.tier.value}")
    print(f"  Entities: {len(response2.entities) if response2.entities else 0}")

    print("\n✓ Tier progression successful")


def example_production_pattern():
    """Example 9: Production usage pattern."""
    print("\n" + "="*60)
    print("EXAMPLE 9: Production Usage Pattern")
    print("="*60)

    # Initialize orchestrator with production settings
    orchestrator = Orchestrator()

    # User query
    user_query = "how do interest rates affect stock valuations"

    # Auto-select tier based on query
    response = orchestrator.answer(
        query=user_query,
        strategy=TierSelectionStrategy.AUTO_DETECT,
    )

    # Handle response
    if response.error:
        print(f"❌ Error: {response.error}")
        # Return degraded response to user
    elif response.fallback_used:
        print("⚠️  Partial results (some enrichment unavailable)")
    else:
        print("✓ Full results")

    # Log metrics
    print(f"📊 Latency: {response.latency_ms:.1f}ms")
    print(f"📊 Tier: {response.tier.value}")
    print(f"📊 Results: {len(response.cards)} cards")

    if response.entities:
        print(f"📊 Entities: {len(response.entities)}")
    if response.relationships:
        print(f"📊 Relationships: {len(response.relationships)}")

    # Return JSON to API client
    api_response = json.dumps(response.to_dict())
    print(f"\n✓ Returning {len(api_response)} bytes to client")


if __name__ == "__main__":
    print("="*60)
    print("RAG Orchestrator Examples")
    print("="*60)

    example_tier1_explicit()
    example_tier2_explicit()
    example_auto_detect_simple()
    example_auto_detect_complex()
    example_error_handling()
    example_json_serialization()
    example_latency_measurement()
    example_tier_progression()
    example_production_pattern()

    print("\n" + "="*60)
    print("All examples completed successfully! ✓")
    print("="*60)
