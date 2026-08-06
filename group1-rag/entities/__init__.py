"""
Tier 2: Entity Extraction Service for Group One Trading RAG
Extracts entities and relationships from retrieved text.
"""

from entity_extractor import (
    EntityExtractor,
    EntityType,
    RelationshipType,
    Entity,
    Relationship,
    ExtractionResult,
    extract_entities,
)

__version__ = "1.0.0"
__all__ = [
    "EntityExtractor",
    "EntityType",
    "RelationshipType",
    "Entity",
    "Relationship",
    "ExtractionResult",
    "extract_entities",
]
