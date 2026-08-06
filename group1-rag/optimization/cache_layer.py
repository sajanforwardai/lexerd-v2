"""
Multi-level caching system for Group One Trading RAG.

Implements LRU caches at strategic points:
- Retrieval results (query → top-K documents)
- Entity extraction results (text → entities)
- Knowledge graph query results
- Embedding cache (text → dense vectors)

Targets >70% cache hit rate on repeated queries.
"""

import hashlib
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
import threading


@dataclass
class CacheStats:
    """Statistics for a cache."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """Return hit rate as percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def __str__(self) -> str:
        return (
            f"Hits: {self.hits}, Misses: {self.misses}, "
            f"Hit Rate: {self.hit_rate:.1f}%, Evictions: {self.evictions}"
        )


class LRUCache:
    """
    Thread-safe LRU (Least Recently Used) cache.

    Maintains a fixed maximum size. When capacity is exceeded, least recently
    used items are evicted.
    """

    def __init__(self, capacity: int = 128):
        """
        Initialize LRU cache.

        Args:
            capacity: Maximum number of items to store
        """
        self.capacity = capacity
        self.cache: OrderedDict = OrderedDict()
        self.stats = CacheStats()
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value by key. Marks key as recently used.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        with self.lock:
            if key not in self.cache:
                self.stats.misses += 1
                return None

            # Move to end (mark as recently used)
            self.cache.move_to_end(key)
            self.stats.hits += 1
            return self.cache[key]

    def put(self, key: str, value: Any):
        """
        Put value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.capacity:
                    # Remove least recently used (first item)
                    removed_key = self.cache.popitem(last=False)
                    self.stats.evictions += 1

            self.cache[key] = value

    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()
            self.stats.hits = 0
            self.stats.misses = 0
            self.stats.evictions = 0

    def size(self) -> int:
        """Return current cache size."""
        with self.lock:
            return len(self.cache)

    def get_stats(self) -> CacheStats:
        """Return cache statistics."""
        with self.lock:
            return CacheStats(
                hits=self.stats.hits,
                misses=self.stats.misses,
                evictions=self.stats.evictions,
            )

    def __len__(self) -> int:
        return len(self.cache)

    def __contains__(self, key: str) -> bool:
        with self.lock:
            return key in self.cache


class RetrievalCache:
    """
    Caches retrieval results: query → (scores, documents).

    Keyed by query hash to handle semantic similarity while avoiding exact
    duplicate queries.
    """

    def __init__(self, capacity: int = 512):
        """
        Initialize retrieval cache.

        Args:
            capacity: Maximum number of cached results (default: 512)
        """
        self.cache = LRUCache(capacity)

    def _hash_query(self, query: str) -> str:
        """Hash a query for caching."""
        # Simple hash - in production could use semantic hashing
        return hashlib.md5(query.encode()).hexdigest()

    def get(
        self,
        query: str,
        k: int = 10
    ) -> Optional[List[Tuple[float, Dict]]]:
        """
        Get cached retrieval results.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of (score, document) tuples or None if not cached
        """
        key = f"{self._hash_query(query)}:k={k}"
        return self.cache.get(key)

    def put(
        self,
        query: str,
        k: int,
        results: List[Tuple[float, Dict]]
    ):
        """
        Cache retrieval results.

        Args:
            query: Search query
            k: Number of results
            results: List of (score, document) tuples
        """
        key = f"{self._hash_query(query)}:k={k}"
        self.cache.put(key, results)

    def get_stats(self) -> CacheStats:
        """Return cache statistics."""
        return self.cache.get_stats()

    def clear(self):
        """Clear cache."""
        self.cache.clear()


class EntityCache:
    """
    Caches entity extraction results: text → entities.

    Extracts entities are expensive (LLM calls). Caching common patterns
    can provide significant speedup.
    """

    def __init__(self, capacity: int = 512):
        """
        Initialize entity cache.

        Args:
            capacity: Maximum number of cached extractions (default: 512)
        """
        self.cache = LRUCache(capacity)

    def _hash_text(self, text: str) -> str:
        """Hash text for caching."""
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, text: str) -> Optional[Dict[str, List[str]]]:
        """
        Get cached entity extraction.

        Args:
            text: Input text

        Returns:
            Dict of entity type -> list of entities, or None if not cached
        """
        key = self._hash_text(text)
        return self.cache.get(key)

    def put(self, text: str, entities: Dict[str, List[str]]):
        """
        Cache entity extraction.

        Args:
            text: Input text
            entities: Dict of entity type -> list of entities
        """
        key = self._hash_text(text)
        self.cache.put(key, entities)

    def get_stats(self) -> CacheStats:
        """Return cache statistics."""
        return self.cache.get_stats()

    def clear(self):
        """Clear cache."""
        self.cache.clear()


class KGQueryCache:
    """
    Caches knowledge graph query results.

    KG queries are fast but frequent. Caching can reduce DB load.
    """

    def __init__(self, capacity: int = 512):
        """
        Initialize KG query cache.

        Args:
            capacity: Maximum number of cached queries (default: 512)
        """
        self.cache = LRUCache(capacity)

    def _hash_cypher(self, cypher: str, params: Optional[Dict] = None) -> str:
        """Hash a Cypher query and parameters."""
        query_str = cypher
        if params:
            query_str += json.dumps(params, sort_keys=True)
        return hashlib.md5(query_str.encode()).hexdigest()

    def get(
        self,
        cypher: str,
        params: Optional[Dict] = None
    ) -> Optional[List[Dict]]:
        """
        Get cached KG query results.

        Args:
            cypher: Cypher query string
            params: Query parameters

        Returns:
            Query results or None if not cached
        """
        key = self._hash_cypher(cypher, params)
        return self.cache.get(key)

    def put(
        self,
        cypher: str,
        params: Optional[Dict],
        results: List[Dict]
    ):
        """
        Cache KG query results.

        Args:
            cypher: Cypher query string
            params: Query parameters
            results: Query results
        """
        key = self._hash_cypher(cypher, params)
        self.cache.put(key, results)

    def get_stats(self) -> CacheStats:
        """Return cache statistics."""
        return self.cache.get_stats()

    def clear(self):
        """Clear cache."""
        self.cache.clear()


class EmbeddingCache:
    """
    Caches text embeddings: text → dense vector.

    Embedding calls are expensive. Caching prevents redundant encoder calls.
    """

    def __init__(self, capacity: int = 1024):
        """
        Initialize embedding cache.

        Args:
            capacity: Maximum number of cached embeddings (default: 1024)
        """
        self.cache = LRUCache(capacity)

    def _hash_text(self, text: str) -> str:
        """Hash text for caching."""
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, text: str) -> Optional[List[float]]:
        """
        Get cached embedding.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if not cached
        """
        key = self._hash_text(text)
        return self.cache.get(key)

    def put(self, text: str, embedding: List[float]):
        """
        Cache embedding.

        Args:
            text: Text
            embedding: Embedding vector
        """
        key = self._hash_text(text)
        self.cache.put(key, embedding)

    def get_stats(self) -> CacheStats:
        """Return cache statistics."""
        return self.cache.get_stats()

    def clear(self):
        """Clear cache."""
        self.cache.clear()


class CacheManager:
    """
    Unified cache management across all components.

    Provides single interface to manage all caches, clear on demand,
    and report aggregate statistics.
    """

    def __init__(
        self,
        retrieval_capacity: int = 512,
        entity_capacity: int = 512,
        kg_capacity: int = 512,
        embedding_capacity: int = 1024,
    ):
        """
        Initialize cache manager.

        Args:
            retrieval_capacity: Retrieval cache capacity
            entity_capacity: Entity cache capacity
            kg_capacity: KG cache capacity
            embedding_capacity: Embedding cache capacity
        """
        self.retrieval = RetrievalCache(retrieval_capacity)
        self.entities = EntityCache(entity_capacity)
        self.kg = KGQueryCache(kg_capacity)
        self.embeddings = EmbeddingCache(embedding_capacity)

    def clear_all(self):
        """Clear all caches."""
        self.retrieval.clear()
        self.entities.clear()
        self.kg.clear()
        self.embeddings.clear()

    def clear_retrieval(self):
        """Clear retrieval cache."""
        self.retrieval.clear()

    def clear_entities(self):
        """Clear entity cache."""
        self.entities.clear()

    def clear_kg(self):
        """Clear KG cache."""
        self.kg.clear()

    def clear_embeddings(self):
        """Clear embedding cache."""
        self.embeddings.clear()

    def get_stats(self) -> Dict[str, CacheStats]:
        """Get statistics for all caches."""
        return {
            "retrieval": self.retrieval.get_stats(),
            "entities": self.entities.get_stats(),
            "kg": self.kg.get_stats(),
            "embeddings": self.embeddings.get_stats(),
        }

    def report_stats(self) -> str:
        """Generate cache statistics report."""
        stats = self.get_stats()

        lines = ["\n" + "="*60]
        lines.append("Cache Statistics Report")
        lines.append("="*60 + "\n")

        total_hits = 0
        total_misses = 0

        for cache_name, cache_stats in stats.items():
            lines.append(f"{cache_name:15} - {cache_stats}")
            total_hits += cache_stats.hits
            total_misses += cache_stats.misses

        lines.append("-" * 60)
        total = total_hits + total_misses
        if total > 0:
            overall_hit_rate = (total_hits / total) * 100
            lines.append(f"{'OVERALL':15} - Hit Rate: {overall_hit_rate:.1f}% "
                        f"({total_hits} hits, {total_misses} misses)")
        lines.append("="*60 + "\n")

        return "\n".join(lines)

    def get_sizes(self) -> Dict[str, int]:
        """Get current size of each cache."""
        return {
            "retrieval": len(self.retrieval.cache),
            "entities": len(self.entities.cache),
            "kg": len(self.kg.cache),
            "embeddings": len(self.embeddings.cache),
        }


# ============================================================================
# Example usage and testing
# ============================================================================

if __name__ == "__main__":
    # Example LRU cache usage
    cache = LRUCache(capacity=3)

    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)

    print("Initial cache:", dict(cache.cache))
    print("Get 'a':", cache.get("a"))  # Hit
    print("Get 'd':", cache.get("d"))  # Miss
    print(cache.get_stats())

    cache.put("d", 4)  # Should evict 'b' (least recently used)
    print("After adding 'd':", dict(cache.cache))

    # Example CacheManager usage
    print("\n" + "="*60)
    manager = CacheManager()

    # Simulate retrievals
    manager.retrieval.put("bitcoin trading", 10, [(0.9, {"title": "Bitcoin"})])
    manager.retrieval.put("ethereum strategy", 10, [(0.8, {"title": "Ethereum"})])
    manager.retrieval.get("bitcoin trading", 10)  # Cache hit
    manager.retrieval.get("bitcoin trading", 10)  # Cache hit

    # Simulate entity extractions
    manager.entities.put(
        "Buy 100 BTC at market",
        {"entities": ["BTC"], "action": "Buy"}
    )
    manager.entities.get("Buy 100 BTC at market")  # Hit
    manager.entities.get("Unknown query")  # Miss

    print(manager.report_stats())
