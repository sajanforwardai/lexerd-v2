"""
Answer modes for RAG orchestrator.

Defines Tier 1 (search/retrieval-only) and Tier 2 (detailed with entity extraction)
modes with their respective response structures and constraints.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any, List, Dict, Optional
from pydantic import BaseModel


class AnswerTier(Enum):
    """Answer tiers with performance characteristics."""
    TIER_1 = "tier_1"  # Search mode: retrieval only, ≤100ms, no Claude calls
    TIER_2 = "tier_2"  # Detail mode: retrieval + entity extraction + KG, ≤500ms
    TIER_3 = "tier_3"  # Reasoning mode: multi-step reasoning with safety enforcement, ≤5s


class ResponseFormat(BaseModel):
    """Response format specification."""
    include_cards: bool = True
    include_entities: bool = False
    include_relationships: bool = False
    include_metadata: bool = True


@dataclass
class RetrievalResult:
    """Single retrieval result with score."""
    content: str
    score: float
    source_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Entity:
    """Extracted entity from text."""
    name: str
    entity_type: str
    confidence: float
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.entity_type,
            "confidence": self.confidence,
            "source": self.source,
            "metadata": self.metadata or {},
        }


@dataclass
class Relationship:
    """Relationship between entities."""
    source_entity: str
    target_entity: str
    relation_type: str
    confidence: float
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_entity,
            "target": self.target_entity,
            "type": self.relation_type,
            "confidence": self.confidence,
            "metadata": self.metadata or {},
        }


@dataclass
class ResultCard:
    """A single result card for display."""
    title: str
    content: str
    score: float
    source_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "score": self.score,
            "source_id": self.source_id,
            "metadata": self.metadata or {},
        }


@dataclass
class OrchestratorResponse:
    """Response from orchestrator combining retrieval and extraction."""
    tier: AnswerTier
    query: str
    cards: List[ResultCard]
    entities: Optional[List[Entity]] = None
    relationships: Optional[List[Relationship]] = None
    latency_ms: float = 0.0
    error: Optional[str] = None
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to JSON-serializable dict."""
        return {
            "tier": self.tier.value,
            "query": self.query,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "fallback_used": self.fallback_used,
            "cards": [card.to_dict() for card in self.cards],
            "entities": (
                [entity.to_dict() for entity in self.entities]
                if self.entities
                else None
            ),
            "relationships": (
                [rel.to_dict() for rel in self.relationships]
                if self.relationships
                else None
            ),
        }


# Tier-specific configurations
TIER_CONFIGS = {
    AnswerTier.TIER_1: {
        "name": "Search",
        "description": "Fast retrieval-only mode",
        "max_latency_ms": 100,
        "allow_claude": False,
        "response_format": ResponseFormat(
            include_cards=True,
            include_entities=False,
            include_relationships=False,
        ),
    },
    AnswerTier.TIER_2: {
        "name": "Detail",
        "description": "Comprehensive mode with entity extraction and KG lookup",
        "max_latency_ms": 500,
        "allow_claude": False,  # No Claude calls at all
        "entity_extraction_max_ms": 300,
        "response_format": ResponseFormat(
            include_cards=True,
            include_entities=True,
            include_relationships=True,
        ),
    },
    AnswerTier.TIER_3: {
        "name": "Reasoning",
        "description": "Deep reasoning mode with multi-step analysis and safety enforcement",
        "max_latency_ms": 5000,  # 5 second limit
        "allow_claude": True,  # Allows reasoning engine calls
        "reasoning_max_ms": 1500,  # Reasoning step budget
        "safety_enforcement": True,  # 100% safety checks before execution
        "response_format": ResponseFormat(
            include_cards=True,
            include_entities=True,
            include_relationships=True,
        ),
    },
}
