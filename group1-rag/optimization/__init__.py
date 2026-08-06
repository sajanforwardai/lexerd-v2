"""
Group One Trading RAG — Latency Optimization System

Provides production-grade optimization components for reducing end-to-end
latency from 200-400ms to <2s (95%ile).

Components:
  - profiler: Latency profiling and bottleneck analysis
  - cache_layer: Multi-level LRU caching
  - parallel_reasoning: Thread-pool parallel tree evaluation
  - index_optimizer: Pre-computed index management
  - latency_monitor: SLA monitoring and circuit breaker
  - benchmark: Before/after latency comparison

Quick Start:
  >>> from optimization.cache_layer import CacheManager
  >>> cache = CacheManager()
  >>> results = cache.retrieval.get(query, k=10)
  >>> if results is None:
  ...     results = retriever.search(query, k=10)
  ...     cache.retrieval.put(query, k=10, results)

See README.md for full documentation.
"""

from profiler import LatencyProfiler, CPUProfiler, MemoryProfiler
from cache_layer import (
    LRUCache, RetrievalCache, EntityCache, KGQueryCache,
    EmbeddingCache, CacheManager
)
from parallel_reasoning import (
    ReasoningNode, ReasoningTree, ReasoningAccelerator,
    NodeType, ExecutionStrategy
)
from index_optimizer import (
    BM25IndexManager, CompoundIndexBuilder, LazyLoader, IndexOptimizer
)
from latency_monitor import (
    LatencyMonitor, SLAStatus, CircuitBreaker,
    SLATarget, DEFAULT_SLAS
)

__version__ = "1.0.0"
__all__ = [
    # Profiling
    "LatencyProfiler",
    "CPUProfiler",
    "MemoryProfiler",
    # Caching
    "LRUCache",
    "RetrievalCache",
    "EntityCache",
    "KGQueryCache",
    "EmbeddingCache",
    "CacheManager",
    # Reasoning
    "ReasoningNode",
    "ReasoningTree",
    "ReasoningAccelerator",
    "ExecutionStrategy",
    "NodeType",
    # Index Optimization
    "BM25IndexManager",
    "CompoundIndexBuilder",
    "LazyLoader",
    "IndexOptimizer",
    # Monitoring
    "LatencyMonitor",
    "SLAStatus",
    "CircuitBreaker",
    "SLATarget",
    "DEFAULT_SLAS",
]
