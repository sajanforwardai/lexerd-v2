"""
Index optimization for Group One Trading RAG.

Implements:
- Pre-computation of BM25 index on startup (not on-demand)
- Compound indexes for hot queries (regime→strategy, Greeks)
- Lazy loading of non-critical relationships
- Index size optimization

Targets KG queries <10ms (from <20ms) and faster retrieval startup.
"""

import time
import json
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import pickle
import threading


@dataclass
class IndexMetadata:
    """Metadata about an index."""
    name: str
    size_bytes: int
    created_at: float
    last_accessed_at: float
    access_count: int = 0
    hit_count: int = 0


class BM25IndexManager:
    """
    Manages pre-computed BM25 indexes.

    Instead of computing BM25 on-demand, pre-compute at startup and cache.
    """

    def __init__(self):
        """Initialize BM25 index manager."""
        self.indexes: Dict[str, Any] = {}
        self.metadata: Dict[str, IndexMetadata] = {}
        self.lock = threading.RLock()

    def build_index(
        self,
        corpus: List[Dict[str, str]],
        index_name: str = "default",
        fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        Pre-build BM25 index from corpus.

        Args:
            corpus: List of documents
            index_name: Name for this index
            fields: Fields to index (default: title, body)

        Returns:
            BM25 index data structure
        """
        if fields is None:
            fields = ["title", "body"]

        start = time.perf_counter()

        # Build inverted index
        inverted_index: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        doc_frequencies: List[Dict[str, int]] = []
        doc_ids: Dict[int, Dict] = {}

        for doc_id, doc in enumerate(corpus):
            doc_freq = defaultdict(int)
            doc_ids[doc_id] = doc

            for field in fields:
                text = doc.get(field, "").lower()
                tokens = text.split()

                for token in tokens:
                    inverted_index[token][doc_id] += 1
                    doc_freq[token] += 1

            doc_frequencies.append(dict(doc_freq))

        # Build BM25 parameters
        N = len(corpus)
        avg_doc_length = sum(sum(f.values()) for f in doc_frequencies) / N

        index_data = {
            "inverted_index": dict(inverted_index),
            "doc_frequencies": doc_frequencies,
            "doc_ids": doc_ids,
            "N": N,
            "avg_doc_length": avg_doc_length,
            "fields": fields,
        }

        with self.lock:
            self.indexes[index_name] = index_data

            size_bytes = len(pickle.dumps(index_data))
            self.metadata[index_name] = IndexMetadata(
                name=index_name,
                size_bytes=size_bytes,
                created_at=time.perf_counter(),
                last_accessed_at=time.perf_counter(),
            )

        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"Built BM25 index '{index_name}' in {elapsed_ms:.2f}ms ({size_bytes} bytes)")

        return index_data

    def get_index(self, index_name: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get pre-built BM25 index.

        Args:
            index_name: Name of index

        Returns:
            Index data or None if not found
        """
        with self.lock:
            index = self.indexes.get(index_name)
            if index:
                self.metadata[index_name].access_count += 1
                self.metadata[index_name].last_accessed_at = time.perf_counter()
            return index

    def list_indexes(self) -> Dict[str, IndexMetadata]:
        """List all available indexes."""
        with self.lock:
            return dict(self.metadata)


class CompoundIndexBuilder:
    """
    Builds compound indexes for hot query patterns.

    Example: regime→strategy compound index allows fast lookup of all
    strategies for a given regime.
    """

    def __init__(self):
        """Initialize compound index builder."""
        self.indexes: Dict[str, Dict] = {}
        self.metadata: Dict[str, IndexMetadata] = {}

    def build_regime_strategy_index(
        self,
        kg_nodes: List[Dict[str, Any]],
        index_name: str = "regime_strategy"
    ) -> Dict[str, List[str]]:
        """
        Build regime→strategy compound index.

        Args:
            kg_nodes: Knowledge graph nodes
            index_name: Index name

        Returns:
            regime -> [strategies] mapping
        """
        start = time.perf_counter()

        index: Dict[str, Set[str]] = defaultdict(set)

        for node in kg_nodes:
            if node.get("type") == "regime":
                regime_id = node.get("id")
                # Find connected strategies
                if "strategies" in node:
                    for strategy in node["strategies"]:
                        index[regime_id].add(strategy)

        # Convert sets to lists
        index_final = {k: list(v) for k, v in index.items()}

        self.indexes[index_name] = index_final
        size_bytes = len(json.dumps(index_final).encode())
        self.metadata[index_name] = IndexMetadata(
            name=index_name,
            size_bytes=size_bytes,
            created_at=time.perf_counter(),
            last_accessed_at=time.perf_counter(),
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"Built compound index '{index_name}' in {elapsed_ms:.2f}ms")

        return index_final

    def build_greeks_index(
        self,
        positions: List[Dict[str, Any]],
        index_name: str = "greeks_lookup"
    ) -> Dict[str, Dict[str, float]]:
        """
        Build Greeks lookup index for fast risk calculations.

        Args:
            positions: List of positions with Greeks
            index_name: Index name

        Returns:
            symbol -> greeks mapping
        """
        start = time.perf_counter()

        index = {}

        for position in positions:
            symbol = position.get("symbol")
            if symbol:
                index[symbol] = {
                    "delta": position.get("delta", 0),
                    "gamma": position.get("gamma", 0),
                    "vega": position.get("vega", 0),
                    "theta": position.get("theta", 0),
                }

        self.indexes[index_name] = index
        size_bytes = len(json.dumps(index).encode())
        self.metadata[index_name] = IndexMetadata(
            name=index_name,
            size_bytes=size_bytes,
            created_at=time.perf_counter(),
            last_accessed_at=time.perf_counter(),
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"Built Greeks index in {elapsed_ms:.2f}ms ({len(index)} symbols)")

        return index

    def get_index(self, index_name: str) -> Optional[Dict]:
        """Get compound index."""
        if index_name in self.metadata:
            self.metadata[index_name].access_count += 1
            self.metadata[index_name].last_accessed_at = time.perf_counter()
        return self.indexes.get(index_name)


class LazyLoader:
    """
    Lazy loading strategy for non-critical data.

    Defers loading of non-essential relationships until needed.
    """

    def __init__(self):
        """Initialize lazy loader."""
        self.cache: Dict[str, Any] = {}
        self.loaders: Dict[str, callable] = {}

    def register_loader(self, key: str, loader_fn: callable):
        """
        Register a loader function for lazy data.

        Args:
            key: Data key
            loader_fn: Function that loads data (no args)
        """
        self.loaders[key] = loader_fn

    def get(self, key: str) -> Optional[Any]:
        """
        Get lazy-loaded data (loads if not cached).

        Args:
            key: Data key

        Returns:
            Data (loaded if necessary)
        """
        if key not in self.cache:
            if key in self.loaders:
                start = time.perf_counter()
                self.cache[key] = self.loaders[key]()
                elapsed_ms = (time.perf_counter() - start) * 1000
                print(f"Lazy loaded '{key}' in {elapsed_ms:.2f}ms")
            else:
                return None

        return self.cache[key]

    def preload(self, keys: List[str]):
        """
        Preload multiple keys.

        Args:
            keys: Keys to preload
        """
        for key in keys:
            self.get(key)

    def is_loaded(self, key: str) -> bool:
        """Check if data is cached."""
        return key in self.cache

    def clear(self, key: str = None):
        """Clear cache."""
        if key:
            self.cache.pop(key, None)
        else:
            self.cache.clear()


class IndexOptimizer:
    """
    Main index optimizer orchestrating all strategies.

    - Pre-computes BM25 indexes at startup
    - Builds compound indexes for hot queries
    - Manages lazy loading of non-critical data
    """

    def __init__(self):
        """Initialize optimizer."""
        self.bm25_manager = BM25IndexManager()
        self.compound_builder = CompoundIndexBuilder()
        self.lazy_loader = LazyLoader()
        self.startup_time_ms = 0

    def optimize_startup(
        self,
        corpus: List[Dict[str, str]],
        kg_nodes: List[Dict[str, Any]] = None,
        positions: List[Dict[str, Any]] = None,
    ):
        """
        Run optimization at startup.

        Pre-computes all indexes and sets up lazy loading.

        Args:
            corpus: Document corpus
            kg_nodes: KG nodes (optional)
            positions: Positions (optional)
        """
        start = time.perf_counter()

        print("\n" + "="*60)
        print("Startup Index Optimization")
        print("="*60)

        # Pre-compute BM25 index
        print("\n1. Building BM25 indexes...")
        self.bm25_manager.build_index(corpus, "retrieval")

        # Build compound indexes
        if kg_nodes:
            print("\n2. Building compound indexes...")
            self.compound_builder.build_regime_strategy_index(kg_nodes)

        if positions:
            self.compound_builder.build_greeks_index(positions)

        # Setup lazy loading
        print("\n3. Setting up lazy loading...")

        def load_market_data():
            time.sleep(0.001)  # Simulate load
            return {"SPX": 4500, "VIX": 15}

        def load_positions():
            time.sleep(0.001)
            return {}

        self.lazy_loader.register_loader("market_data", load_market_data)
        self.lazy_loader.register_loader("positions", load_positions)

        self.startup_time_ms = (time.perf_counter() - start) * 1000
        print(f"\nOptimization complete in {self.startup_time_ms:.2f}ms")
        print("="*60 + "\n")

    def report(self) -> str:
        """Generate index optimization report."""
        lines = ["\n" + "="*60]
        lines.append("Index Optimization Report")
        lines.append("="*60 + "\n")

        # BM25 indexes
        lines.append("BM25 Indexes:")
        bm25_indexes = self.bm25_manager.list_indexes()
        total_bm25_bytes = 0
        for name, metadata in bm25_indexes.items():
            lines.append(
                f"  {name}: {metadata.size_bytes / 1024:.1f} KB "
                f"(accessed {metadata.access_count}x)"
            )
            total_bm25_bytes += metadata.size_bytes

        if bm25_indexes:
            lines.append(f"  Total: {total_bm25_bytes / 1024 / 1024:.2f} MB")

        # Compound indexes
        lines.append("\nCompound Indexes:")
        total_compound_bytes = 0
        for name, metadata in self.compound_builder.metadata.items():
            lines.append(
                f"  {name}: {metadata.size_bytes / 1024:.1f} KB "
                f"(accessed {metadata.access_count}x)"
            )
            total_compound_bytes += metadata.size_bytes

        if self.compound_builder.metadata:
            lines.append(f"  Total: {total_compound_bytes / 1024:.1f} KB")

        # Lazy loading
        lines.append("\nLazy Loading:")
        lines.append(f"  Registered loaders: {len(self.lazy_loader.loaders)}")
        lines.append(f"  Loaded items: {len(self.lazy_loader.cache)}")

        # Startup time
        lines.append(f"\nStartup Optimization Time: {self.startup_time_ms:.2f}ms")

        lines.append("="*60 + "\n")
        return "\n".join(lines)


# ============================================================================
# Example usage
# ============================================================================

if __name__ == "__main__":
    # Create sample corpus
    corpus = [
        {
            "title": "Bitcoin Trading Strategy",
            "body": "A comprehensive guide to trading Bitcoin"
        },
        {
            "title": "Risk Management in Trading",
            "body": "Essential techniques for managing portfolio risk"
        },
        {
            "title": "Options Greeks Explained",
            "body": "Understanding delta, gamma, vega, and theta"
        },
    ]

    # Create sample KG nodes
    kg_nodes = [
        {
            "id": "regime_bullish",
            "type": "regime",
            "strategies": ["momentum", "trend_following"]
        },
        {
            "id": "regime_bearish",
            "type": "regime",
            "strategies": ["covered_call", "protective_put"]
        },
    ]

    # Create sample positions
    positions = [
        {"symbol": "AAPL", "delta": 0.6, "gamma": 0.02, "vega": 0.1, "theta": -0.01},
        {"symbol": "GOOG", "delta": 0.5, "gamma": 0.01, "vega": 0.08, "theta": -0.01},
    ]

    # Run optimizer
    optimizer = IndexOptimizer()
    optimizer.optimize_startup(corpus, kg_nodes, positions)

    # Get index
    bm25_index = optimizer.bm25_manager.get_index("retrieval")
    print(f"BM25 index documents: {bm25_index['N']}")

    # Get compound index
    regime_strat = optimizer.compound_builder.get_index("regime_strategy")
    print(f"Regime-Strategy index: {regime_strat}")

    # Test lazy loading
    market_data = optimizer.lazy_loader.get("market_data")
    print(f"Market data: {market_data}")

    print(optimizer.report())
