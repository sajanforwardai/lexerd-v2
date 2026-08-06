"""
RAG Orchestrator combining retrieval and entity extraction.

Implements Tier 1 (search mode) and Tier 2 (detail mode) with:
- Vector DB retrieval (≤100ms for Tier 1)
- Entity extraction + KG lookup (≤500ms for Tier 2)
- Tier selection logic (user-driven or auto-detect)
- Response formatting (JSON with cards, entities, relationships)
- Error handling with graceful degradation
"""

import time
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .answer_modes import (
    AnswerTier,
    OrchestratorResponse,
    ResultCard,
    RetrievalResult,
    Entity,
    Relationship,
    TIER_CONFIGS,
)

logger = logging.getLogger(__name__)


class TierSelectionStrategy(Enum):
    """Strategy for selecting answer tier."""
    USER_SPECIFIED = "user_specified"
    AUTO_DETECT = "auto_detect"


class VectorDBConnector:
    """Mock vector DB connector for testing.

    In production, this would connect to your actual vector DB
    (Pinecone, Weaviate, Milvus, etc.)
    """

    def __init__(self, latency_ms: float = 50):
        """Initialize connector with simulated latency."""
        self.latency_ms = latency_ms
        self.mock_db = {}

    def search(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """
        Search vector DB for top-k results.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of retrieval results with scores
        """
        # Simulate network latency
        time.sleep(self.latency_ms / 1000.0)

        # Return mock results for testing
        results = []
        for i in range(min(top_k, 5)):
            score = 1.0 - (i * 0.15)  # Decreasing scores
            result = RetrievalResult(
                content=f"Sample result {i+1} for query: {query}",
                score=max(score, 0.1),
                source_id=f"doc_{i+1}",
                metadata={"index": i, "query": query},
            )
            results.append(result)

        return results


class EntityExtractor:
    """Mock entity extractor for testing.

    In production, this would use:
    - Spacy, NLTK, or transformers for NER
    - Custom domain-specific models
    """

    def __init__(self, latency_ms: float = 200):
        """Initialize extractor with simulated latency."""
        self.latency_ms = latency_ms

    def extract(self, text: str) -> List[Entity]:
        """
        Extract entities from text.

        Args:
            text: Text to extract entities from

        Returns:
            List of extracted entities
        """
        # Simulate NER latency
        time.sleep(self.latency_ms / 1000.0)

        # Mock entities based on keywords in text
        entities = []

        keywords = {
            "financial": ("CONCEPT", 0.95),
            "market": ("CONCEPT", 0.92),
            "stock": ("ASSET", 0.90),
            "bond": ("ASSET", 0.89),
            "risk": ("CONCEPT", 0.88),
            "performance": ("METRIC", 0.87),
        }

        for keyword, (ent_type, confidence) in keywords.items():
            if keyword.lower() in text.lower():
                entity = Entity(
                    name=keyword.capitalize(),
                    entity_type=ent_type,
                    confidence=confidence,
                    source="text",
                    metadata={"keyword_match": True},
                )
                entities.append(entity)

        return entities


class KnowledgeGraphConnector:
    """Mock knowledge graph connector for testing.

    In production, this would connect to your KG
    (Neo4j, AWS Neptune, GraphQL API, etc.)
    """

    def __init__(self, latency_ms: float = 50):
        """Initialize KG connector with simulated latency."""
        self.latency_ms = latency_ms

    def lookup_entity(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """
        Look up entity in knowledge graph.

        Args:
            entity_name: Entity to look up

        Returns:
            Entity details or None if not found
        """
        # Simulate KG lookup latency
        time.sleep(self.latency_ms / 1000.0)

        # Mock lookup results
        mock_kg = {
            "Financial": {
                "description": "Related to money, banking, investments",
                "related_concepts": ["Market", "Risk", "Performance"],
            },
            "Market": {
                "description": "Place or system where trading occurs",
                "related_concepts": ["Stock", "Bond", "Risk"],
            },
            "Stock": {
                "description": "Equity security representing ownership",
                "related_concepts": ["Market", "Performance", "Risk"],
            },
        }

        return mock_kg.get(entity_name)

    def find_relationships(
        self, source_entity: str, target_entity: str
    ) -> Optional[Relationship]:
        """
        Find relationship between two entities in KG.

        Args:
            source_entity: Source entity
            target_entity: Target entity

        Returns:
            Relationship if found, None otherwise
        """
        # Simulate KG lookup
        time.sleep(self.latency_ms / 1000.0)

        # Mock relationships
        relationships_map = {
            ("Financial", "Market"): ("relates_to", 0.9),
            ("Market", "Stock"): ("contains", 0.95),
            ("Stock", "Risk"): ("has_attribute", 0.88),
            ("Market", "Risk"): ("influences", 0.85),
        }

        key = (source_entity, target_entity)
        if key in relationships_map:
            rel_type, confidence = relationships_map[key]
            return Relationship(
                source_entity=source_entity,
                target_entity=target_entity,
                relation_type=rel_type,
                confidence=confidence,
                metadata={"from_kg": True},
            )

        return None


class ComplexityDetector:
    """Detects query complexity for auto-tier selection."""

    @staticmethod
    def detect_complexity(query: str) -> AnswerTier:
        """
        Detect query complexity and recommend tier.

        Heuristics:
        - Simple queries (1-3 words): Tier 1
        - Multi-word with specific entities: Tier 2
        - Questions with "why", "how", "relationship": Tier 2

        Args:
            query: User query

        Returns:
            Recommended tier
        """
        # Simple word count heuristic
        word_count = len(query.split())

        # Keywords indicating complex queries
        complex_keywords = {
            "why",
            "how",
            "relationship",
            "related",
            "between",
            "analyze",
            "explain",
            "context",
            "background",
        }

        query_lower = query.lower()

        # If query asks about relationships or has complex keywords
        if any(keyword in query_lower for keyword in complex_keywords):
            return AnswerTier.TIER_2

        # If short query, use Tier 1
        if word_count <= 3:
            return AnswerTier.TIER_1

        # If medium-long query without complex keywords, use Tier 2
        if word_count >= 5:
            return AnswerTier.TIER_2

        # Default to Tier 1
        return AnswerTier.TIER_1


class Orchestrator:
    """Main orchestrator combining retrieval and extraction."""

    def __init__(
        self,
        vector_db: Optional[VectorDBConnector] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        kg: Optional[KnowledgeGraphConnector] = None,
    ):
        """Initialize orchestrator with connectors."""
        self.vector_db = vector_db or VectorDBConnector()
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.kg = kg or KnowledgeGraphConnector()
        self.complexity_detector = ComplexityDetector()

        # Track Claude calls for testing
        self._claude_calls = 0

    @property
    def claude_calls(self) -> int:
        """Get count of Claude API calls."""
        return self._claude_calls

    def select_tier(
        self,
        query: str,
        strategy: TierSelectionStrategy = TierSelectionStrategy.AUTO_DETECT,
        explicit_tier: Optional[AnswerTier] = None,
    ) -> AnswerTier:
        """
        Select answer tier based on strategy.

        Args:
            query: User query
            strategy: Selection strategy
            explicit_tier: Explicit tier if strategy is USER_SPECIFIED

        Returns:
            Selected tier
        """
        if strategy == TierSelectionStrategy.USER_SPECIFIED:
            if explicit_tier is None:
                raise ValueError(
                    "explicit_tier required when strategy is USER_SPECIFIED"
                )
            return explicit_tier

        # Auto-detect
        return self.complexity_detector.detect_complexity(query)

    def _retrieve(self, query: str, top_k: int = 5) -> Tuple[List[ResultCard], Optional[str]]:
        """
        Retrieve top-k results from vector DB.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Tuple of (list of result cards, error message or None)
        """
        try:
            results = self.vector_db.search(query, top_k)
            cards = []

            for i, result in enumerate(results):
                card = ResultCard(
                    title=f"Result {i+1}",
                    content=result.content,
                    score=result.score,
                    source_id=result.source_id,
                    metadata=result.metadata,
                )
                cards.append(card)

            return cards, None

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return [], str(e)

    def _extract_and_enrich(
        self, cards: List[ResultCard]
    ) -> Tuple[List[Entity], List[Relationship]]:
        """
        Extract entities and relationships from retrieval results.

        Args:
            cards: Result cards from retrieval

        Returns:
            Tuple of (entities, relationships)
        """
        all_entities = []
        all_relationships = []

        try:
            # Combine card contents
            combined_text = " ".join(card.content for card in cards)

            # Extract entities
            entities = self.entity_extractor.extract(combined_text)
            all_entities.extend(entities)

            # Look up entities in KG and find relationships
            entity_names = [e.name for e in entities]

            for i, entity1 in enumerate(entity_names):
                for entity2 in entity_names[i + 1 :]:
                    rel = self.kg.find_relationships(entity1, entity2)
                    if rel:
                        all_relationships.append(rel)

        except Exception as e:
            logger.error(f"Entity extraction/enrichment failed: {e}")
            # Graceful degradation: continue without extraction

        return all_entities, all_relationships

    def answer(
        self,
        query: str,
        tier: Optional[AnswerTier] = None,
        strategy: TierSelectionStrategy = TierSelectionStrategy.AUTO_DETECT,
    ) -> OrchestratorResponse:
        """
        Answer a query using orchestrator.

        Args:
            query: User query
            tier: Explicit tier (only if strategy=USER_SPECIFIED)
            strategy: Tier selection strategy

        Returns:
            OrchestratorResponse with cards, entities, relationships

        Raises:
            ValueError: If required parameters are missing (validation error)
        """
        start_time = time.time()
        error_msg = None
        fallback_used = False

        # Validate inputs first (let ValueError bubble up)
        selected_tier = self.select_tier(
            query,
            strategy=strategy,
            explicit_tier=tier,
        )

        try:
            # Enforce no-Claude constraint
            config = TIER_CONFIGS[selected_tier]
            if not config.get("allow_claude", False) and self._claude_calls > 0:
                logger.warning(
                    f"{selected_tier.value} mode does not allow Claude calls"
                )

            # Tier 1: Retrieval only
            if selected_tier == AnswerTier.TIER_1:
                cards, retrieval_error = self._retrieve(query)

                if retrieval_error:
                    error_msg = retrieval_error
                    fallback_used = True

                latency_ms = (time.time() - start_time) * 1000

                # Check latency constraint
                max_latency = config["max_latency_ms"]
                if latency_ms > max_latency:
                    logger.warning(
                        f"Tier 1 latency {latency_ms:.1f}ms exceeds limit "
                        f"{max_latency}ms"
                    )

                return OrchestratorResponse(
                    tier=selected_tier,
                    query=query,
                    cards=cards,
                    entities=None,
                    relationships=None,
                    latency_ms=latency_ms,
                    error=error_msg,
                    fallback_used=fallback_used,
                )

            # Tier 2: Retrieval + Entity Extraction + KG Lookup
            elif selected_tier == AnswerTier.TIER_2:
                # Retrieval phase
                cards, retrieval_error = self._retrieve(query)

                if retrieval_error:
                    error_msg = retrieval_error
                    fallback_used = True

                # Entity extraction + KG lookup phase
                entities, relationships = self._extract_and_enrich(cards)

                latency_ms = (time.time() - start_time) * 1000

                # Check latency constraints
                max_latency = config["max_latency_ms"]
                if latency_ms > max_latency:
                    logger.warning(
                        f"Tier 2 latency {latency_ms:.1f}ms exceeds limit "
                        f"{max_latency}ms"
                    )

                return OrchestratorResponse(
                    tier=selected_tier,
                    query=query,
                    cards=cards,
                    entities=entities if entities else None,
                    relationships=relationships if relationships else None,
                    latency_ms=latency_ms,
                    error=error_msg,
                    fallback_used=fallback_used,
                )

            else:
                raise ValueError(f"Unknown tier: {selected_tier}")

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"Orchestrator error: {e}", exc_info=True)

            # Graceful degradation: return Tier 1 results on error
            fallback_used = True
            try:
                cards, retrieval_error = self._retrieve(query)
                if retrieval_error and not error_msg:
                    error_msg = retrieval_error
            except Exception:
                cards = []

            return OrchestratorResponse(
                tier=AnswerTier.TIER_1,
                query=query,
                cards=cards,
                entities=None,
                relationships=None,
                latency_ms=latency_ms,
                error=error_msg,
                fallback_used=fallback_used,
            )
