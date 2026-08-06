"""
RAG Orchestrator for combining retrieval and entity extraction.

Provides:
- Tier 1 (search-only, ≤100ms)
- Tier 2 (detail with entity extraction, ≤500ms)
- Tier 3 (multi-step reasoning with safety enforcement, ≤5s)

Automatic tier selection with graceful degradation across all tiers.
"""

from .orchestrator import (
    Orchestrator,
    VectorDBConnector,
    EntityExtractor,
    KnowledgeGraphConnector,
    TierSelectionStrategy,
    ComplexityDetector,
)
from .answer_modes import (
    AnswerTier,
    OrchestratorResponse,
    ResultCard,
    RetrievalResult,
    Entity,
    Relationship,
    TIER_CONFIGS,
)
from .tier3_orchestrator import (
    Tier3Orchestrator,
    Tier3Response,
    RequestProcessor,
    ReasoningEngine,
    ReasoningDepth,
    SafetyEnforcer,
    LatencyMonitor,
    ErrorRecovery,
    EscalationLevel,
    ReasoningStep,
)

__all__ = [
    # Tier 1 & 2
    "Orchestrator",
    "VectorDBConnector",
    "EntityExtractor",
    "KnowledgeGraphConnector",
    "TierSelectionStrategy",
    "ComplexityDetector",
    "AnswerTier",
    "OrchestratorResponse",
    "ResultCard",
    "RetrievalResult",
    "Entity",
    "Relationship",
    "TIER_CONFIGS",
    # Tier 3
    "Tier3Orchestrator",
    "Tier3Response",
    "RequestProcessor",
    "ReasoningEngine",
    "ReasoningDepth",
    "SafetyEnforcer",
    "LatencyMonitor",
    "ErrorRecovery",
    "EscalationLevel",
    "ReasoningStep",
]
