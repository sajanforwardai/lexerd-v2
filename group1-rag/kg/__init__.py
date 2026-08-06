"""
Group One RAG Knowledge Graph Package
======================================

A Neo4j-based knowledge graph for trading strategies, market regimes,
Greeks, volatility surfaces, and risk metrics.

Main Components:
- kg_client: Core KG client for node/relationship management
- corpus_ingestion: Corpus parsing and entity linking
- queries: Pre-built Cypher queries
- test_kg: Comprehensive test suite

Entity Types (9):
- MarketRegime
- Strategy
- Greeks
- VolSurface
- TradingOpportunity
- Event
- OrderFlow
- RiskMetric
- Position

Usage:
    from kg import KGClient, ingest_corpus_files

    # Create client
    client = KGClient(use_mock=True)

    # Ingest corpus
    stats = ingest_corpus_files(client)

    # Query the graph
    strategies = client.query_strategies_by_regime("High-Vol Market")
"""

from kg_client import (
    KGClient,
    KGNode,
    KGRelationship,
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    create_client,
)

from corpus_ingestion import (
    CorpusParser,
    EntityLinker,
    ingest_corpus_files,
    export_ingestion_report,
)

__version__ = "1.0.0"
__all__ = [
    "KGClient",
    "KGNode",
    "KGRelationship",
    "ENTITY_TYPES",
    "RELATIONSHIP_TYPES",
    "create_client",
    "CorpusParser",
    "EntityLinker",
    "ingest_corpus_files",
    "export_ingestion_report",
]
