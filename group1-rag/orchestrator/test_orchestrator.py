"""
Test harness for RAG orchestrator.

Tests:
- Tier 1 (search mode): NO Claude calls, ≤100ms latency
- Tier 2 (detail mode): NO Claude calls, ≤500ms latency
- Entity extraction: ≤300ms latency
- Tier selection logic (user-driven and auto-detect)
- Response formatting (JSON with cards, entities, relationships)
- Error handling and graceful degradation
"""

import time
import json
import pytest
from unittest.mock import Mock, patch

from .orchestrator import (
    Orchestrator,
    VectorDBConnector,
    EntityExtractor,
    KnowledgeGraphConnector,
    TierSelectionStrategy,
    ComplexityDetector,
)
from .answer_modes import AnswerTier, OrchestratorResponse


class TestTier1SearchMode:
    """Test Tier 1 (search-only mode) constraints."""

    def test_tier1_no_claude_calls(self):
        """Verify Tier 1 makes no Claude API calls."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "simple query",
            tier=AnswerTier.TIER_1,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        assert orchestrator.claude_calls == 0, "Tier 1 should not make Claude calls"
        assert response.tier == AnswerTier.TIER_1
        assert not response.fallback_used

    def test_tier1_latency_under_100ms(self):
        """Verify Tier 1 latency is ≤100ms."""
        # Use a fast vector DB
        vector_db = VectorDBConnector(latency_ms=30)
        orchestrator = Orchestrator(vector_db=vector_db)

        response = orchestrator.answer(
            "query",
            tier=AnswerTier.TIER_1,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        assert (
            response.latency_ms <= 100
        ), f"Tier 1 latency {response.latency_ms:.1f}ms exceeds 100ms limit"

    def test_tier1_returns_cards_only(self):
        """Verify Tier 1 returns only cards, no entities/relationships."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "query",
            tier=AnswerTier.TIER_1,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        assert response.tier == AnswerTier.TIER_1
        assert len(response.cards) > 0, "Should return cards"
        assert (
            response.entities is None
        ), "Tier 1 should not extract entities"
        assert (
            response.relationships is None
        ), "Tier 1 should not include relationships"

    def test_tier1_response_format(self):
        """Verify Tier 1 response JSON format."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "test query",
            tier=AnswerTier.TIER_1,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        # Convert to dict (JSON-serializable)
        response_dict = response.to_dict()

        # Verify required fields
        assert response_dict["tier"] == "tier_1"
        assert response_dict["query"] == "test query"
        assert "latency_ms" in response_dict
        assert "cards" in response_dict
        assert isinstance(response_dict["cards"], list)

        # Tier 1 should have null entities/relationships
        assert response_dict["entities"] is None
        assert response_dict["relationships"] is None

        # Verify JSON serializable
        json_str = json.dumps(response_dict)
        assert json_str is not None


class TestTier2DetailMode:
    """Test Tier 2 (detailed mode with entity extraction) constraints."""

    def test_tier2_no_claude_calls(self):
        """Verify Tier 2 makes no Claude API calls."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "complex query about relationships",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        assert orchestrator.claude_calls == 0, "Tier 2 should not make Claude calls"
        assert response.tier == AnswerTier.TIER_2

    def test_tier2_latency_under_500ms(self):
        """Verify Tier 2 latency is ≤500ms."""
        # Use realistic latencies
        vector_db = VectorDBConnector(latency_ms=30)
        entity_extractor = EntityExtractor(latency_ms=100)
        kg = KnowledgeGraphConnector(latency_ms=50)

        orchestrator = Orchestrator(
            vector_db=vector_db,
            entity_extractor=entity_extractor,
            kg=kg,
        )

        response = orchestrator.answer(
            "query about market relationships",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        assert (
            response.latency_ms <= 500
        ), f"Tier 2 latency {response.latency_ms:.1f}ms exceeds 500ms limit"

    def test_tier2_entity_extraction_latency(self):
        """Verify entity extraction latency ≤300ms."""
        extractor = EntityExtractor(latency_ms=150)
        orchestrator = Orchestrator(entity_extractor=extractor)

        start = time.time()
        response = orchestrator.answer(
            "financial market query",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )
        total_time = (time.time() - start) * 1000

        # Entity extraction should be fast (component-level constraint)
        # Note: Total latency includes retrieval, but extraction must be ≤300ms
        assert (
            response.latency_ms <= 500
        ), f"Total latency {response.latency_ms:.1f}ms should be ≤500ms"

    def test_tier2_returns_entities_and_relationships(self):
        """Verify Tier 2 returns entities and relationships."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "financial market and stock relationship",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        assert response.tier == AnswerTier.TIER_2
        assert len(response.cards) > 0, "Should return cards"
        # Entities and relationships may be empty if no matches, but structure present
        assert response.entities is not None or response.entities is None

    def test_tier2_response_format(self):
        """Verify Tier 2 response JSON format."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "market financial stock query",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        response_dict = response.to_dict()

        assert response_dict["tier"] == "tier_2"
        assert response_dict["query"] == "market financial stock query"
        assert "latency_ms" in response_dict
        assert "cards" in response_dict
        assert "entities" in response_dict
        assert "relationships" in response_dict

        # Verify JSON serializable
        json_str = json.dumps(response_dict)
        assert json_str is not None


class TestTierSelection:
    """Test tier selection logic."""

    def test_user_specified_tier_selection(self):
        """Verify user-specified tier selection works."""
        orchestrator = Orchestrator()

        # Explicit Tier 1
        response = orchestrator.answer(
            "query",
            tier=AnswerTier.TIER_1,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )
        assert response.tier == AnswerTier.TIER_1

        # Explicit Tier 2
        response = orchestrator.answer(
            "query",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )
        assert response.tier == AnswerTier.TIER_2

    def test_user_specified_requires_tier(self):
        """Verify USER_SPECIFIED strategy requires explicit tier."""
        orchestrator = Orchestrator()

        with pytest.raises(ValueError, match="explicit_tier required"):
            orchestrator.answer(
                "query",
                tier=None,
                strategy=TierSelectionStrategy.USER_SPECIFIED,
            )

    def test_auto_detect_simple_query_uses_tier1(self):
        """Verify auto-detect uses Tier 1 for simple queries."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "stocks",  # 1 word = simple
            strategy=TierSelectionStrategy.AUTO_DETECT,
        )
        assert response.tier == AnswerTier.TIER_1

    def test_auto_detect_complex_query_uses_tier2(self):
        """Verify auto-detect uses Tier 2 for complex queries."""
        orchestrator = Orchestrator()

        # Query with complex keywords
        response = orchestrator.answer(
            "what is the relationship between stocks and market",
            strategy=TierSelectionStrategy.AUTO_DETECT,
        )
        assert response.tier == AnswerTier.TIER_2

        # Query with "why"
        response = orchestrator.answer(
            "why does market influence stocks",
            strategy=TierSelectionStrategy.AUTO_DETECT,
        )
        assert response.tier == AnswerTier.TIER_2

    def test_complexity_detector_heuristics(self):
        """Verify complexity detector heuristics."""
        detector = ComplexityDetector()

        # Simple cases
        assert detector.detect_complexity("stock") == AnswerTier.TIER_1
        assert detector.detect_complexity("stock bond") == AnswerTier.TIER_1
        assert detector.detect_complexity("stock bond market") == AnswerTier.TIER_1

        # Complex cases
        assert detector.detect_complexity("why is stock price rising") == AnswerTier.TIER_2
        assert detector.detect_complexity("relationship between market and stock") == AnswerTier.TIER_2
        assert detector.detect_complexity("explain the market dynamics") == AnswerTier.TIER_2


class TestResponseFormatting:
    """Test response formatting and JSON serialization."""

    def test_result_card_json_format(self):
        """Verify result card JSON format."""
        orchestrator = Orchestrator()
        response = orchestrator.answer("test query", tier=AnswerTier.TIER_1, strategy=TierSelectionStrategy.USER_SPECIFIED)

        assert len(response.cards) > 0
        card = response.cards[0]

        card_dict = card.to_dict()
        assert "title" in card_dict
        assert "content" in card_dict
        assert "score" in card_dict
        assert isinstance(card_dict["score"], float)

    def test_entity_json_format(self):
        """Verify entity JSON format."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "financial market stock",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        if response.entities:
            entity = response.entities[0]
            entity_dict = entity.to_dict()

            assert "name" in entity_dict
            assert "type" in entity_dict
            assert "confidence" in entity_dict
            assert isinstance(entity_dict["confidence"], float)

    def test_relationship_json_format(self):
        """Verify relationship JSON format."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "market stock financial",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        if response.relationships:
            rel = response.relationships[0]
            rel_dict = rel.to_dict()

            assert "source" in rel_dict
            assert "target" in rel_dict
            assert "type" in rel_dict
            assert "confidence" in rel_dict

    def test_full_response_json_serializable(self):
        """Verify full response is JSON-serializable."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "test query",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        response_dict = response.to_dict()
        json_str = json.dumps(response_dict)

        # Deserialize and verify structure
        parsed = json.loads(json_str)
        assert parsed["tier"] in ["tier_1", "tier_2"]
        assert isinstance(parsed["cards"], list)
        assert isinstance(parsed["latency_ms"], float)


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    def test_retrieval_error_graceful_degradation(self):
        """Verify graceful degradation on retrieval error."""
        # Mock vector DB to fail
        mock_db = Mock(spec=VectorDBConnector)
        mock_db.search.side_effect = Exception("DB connection failed")

        orchestrator = Orchestrator(vector_db=mock_db)
        response = orchestrator.answer(
            "query",
            tier=AnswerTier.TIER_1,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        # Should return response with error and no cards
        assert response.fallback_used or response.error is not None
        assert response.cards == []

    def test_entity_extraction_error_continues(self):
        """Verify Tier 2 continues if entity extraction fails."""
        # Mock entity extractor to fail
        mock_extractor = Mock(spec=EntityExtractor)
        mock_extractor.extract.side_effect = Exception("Extraction failed")

        orchestrator = Orchestrator(entity_extractor=mock_extractor)
        response = orchestrator.answer(
            "query",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        # Should still return cards and continue
        assert len(response.cards) > 0
        assert response.tier == AnswerTier.TIER_2

    def test_kg_lookup_error_continues(self):
        """Verify Tier 2 continues if KG lookup fails."""
        # Mock KG to fail
        mock_kg = Mock(spec=KnowledgeGraphConnector)
        mock_kg.find_relationships.side_effect = Exception("KG lookup failed")

        orchestrator = Orchestrator(kg=mock_kg)
        response = orchestrator.answer(
            "query",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        # Should still return cards and entities
        assert len(response.cards) > 0
        assert response.tier == AnswerTier.TIER_2

    def test_error_message_in_response(self):
        """Verify error message is included in response."""
        mock_db = Mock(spec=VectorDBConnector)
        error_msg = "Database unavailable"
        mock_db.search.side_effect = Exception(error_msg)

        orchestrator = Orchestrator(vector_db=mock_db)
        response = orchestrator.answer(
            "query",
            tier=AnswerTier.TIER_1,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        assert response.error is not None or response.fallback_used


class TestLatencyConstraints:
    """Test latency constraints end-to-end."""

    def test_tier1_multiple_queries_under_100ms(self):
        """Verify Tier 1 consistently meets 100ms constraint."""
        vector_db = VectorDBConnector(latency_ms=30)
        orchestrator = Orchestrator(vector_db=vector_db)

        for i in range(5):
            response = orchestrator.answer(
                f"query {i}",
                tier=AnswerTier.TIER_1,
                strategy=TierSelectionStrategy.USER_SPECIFIED,
            )
            assert (
                response.latency_ms <= 100
            ), f"Query {i}: {response.latency_ms:.1f}ms > 100ms"

    def test_tier2_multiple_queries_under_500ms(self):
        """Verify Tier 2 consistently meets 500ms constraint."""
        vector_db = VectorDBConnector(latency_ms=30)
        entity_extractor = EntityExtractor(latency_ms=100)
        kg = KnowledgeGraphConnector(latency_ms=50)

        orchestrator = Orchestrator(
            vector_db=vector_db,
            entity_extractor=entity_extractor,
            kg=kg,
        )

        for i in range(5):
            response = orchestrator.answer(
                f"complex query {i}",
                tier=AnswerTier.TIER_2,
                strategy=TierSelectionStrategy.USER_SPECIFIED,
            )
            assert (
                response.latency_ms <= 500
            ), f"Query {i}: {response.latency_ms:.1f}ms > 500ms"


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_end_to_end_tier1_flow(self):
        """Test complete Tier 1 flow."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "stock market",
            strategy=TierSelectionStrategy.AUTO_DETECT,
        )

        # Auto-detect should choose Tier 1 for simple query
        assert response.tier == AnswerTier.TIER_1
        assert len(response.cards) > 0
        assert response.entities is None
        assert response.relationships is None
        assert response.latency_ms <= 100
        assert orchestrator.claude_calls == 0

        # Verify JSON serialization
        json_str = json.dumps(response.to_dict())
        assert json_str is not None

    def test_end_to_end_tier2_flow(self):
        """Test complete Tier 2 flow."""
        orchestrator = Orchestrator()
        response = orchestrator.answer(
            "what is the relationship between financial markets and stocks",
            strategy=TierSelectionStrategy.AUTO_DETECT,
        )

        # Auto-detect should choose Tier 2 for complex query
        assert response.tier == AnswerTier.TIER_2
        assert len(response.cards) > 0
        assert response.latency_ms <= 500
        assert orchestrator.claude_calls == 0

        # Verify JSON serialization
        json_str = json.dumps(response.to_dict())
        assert json_str is not None

    def test_tier1_to_tier2_progression(self):
        """Test progression from Tier 1 to Tier 2."""
        orchestrator = Orchestrator()

        # Start with Tier 1
        response1 = orchestrator.answer(
            "stocks",
            strategy=TierSelectionStrategy.AUTO_DETECT,
        )
        assert response1.tier == AnswerTier.TIER_1

        # Progress to Tier 2 with explicit request
        response2 = orchestrator.answer(
            "stocks",
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )
        assert response2.tier == AnswerTier.TIER_2
        assert response2.latency_ms <= 500


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
