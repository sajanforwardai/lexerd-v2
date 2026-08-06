"""Group One Trading RAG — Tier 1 Hybrid Retrieval Engine.

Exports:
    HybridRetriever: Production-grade dense + BM25 hybrid retriever with optional
                     cross-encoder re-ranking. Designed for <100ms latency,
                     nDCG@10 >= 0.50 on trading corpus.
"""

from retrieval_engine import HybridRetriever

__all__ = ["HybridRetriever"]
__version__ = "1.0.0"
