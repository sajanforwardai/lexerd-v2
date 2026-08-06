"""conftest.py — Pytest fixtures for Group One RAG tests.

Provides:
  - Golden query loading
  - Mock retriever/encoder fixtures
  - Baseline comparison fixtures
  - Report generation fixtures
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Generator

import numpy as np
import pytest

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ---- Fixture: Golden Query Set ----

@pytest.fixture(scope="session")
def golden_queries() -> dict[int, dict[str, Any]]:
    """Load golden query set from JSON.

    Returns:
        Dict mapping query_id -> query record
    """
    query_file = Path(__file__).parent / "golden_queries.json"
    if not query_file.exists():
        pytest.skip("golden_queries.json not found")

    with open(query_file) as f:
        data = json.load(f)

    queries_by_id = {}
    for q in data.get("queries", []):
        queries_by_id[q["id"]] = q

    for q in data.get("additional_queries", []):
        queries_by_id[q["id"]] = q

    logger.info(f"Loaded {len(queries_by_id)} golden queries")
    return queries_by_id


@pytest.fixture(scope="session")
def golden_queries_by_tier(golden_queries) -> dict[int, list[dict[str, Any]]]:
    """Group golden queries by tier.

    Returns:
        Dict mapping tier (1, 2) -> list of query records
    """
    by_tier = {1: [], 2: []}
    for query in golden_queries.values():
        tier = query.get("expected_tier", 1)
        by_tier[tier].append(query)

    logger.info(f"Tier 1 queries: {len(by_tier[1])}, Tier 2 queries: {len(by_tier[2])}")
    return by_tier


# ---- Fixture: Mock Encoder ----

class MockEncoder:
    """Mock encoder for testing without real embeddings."""

    def __init__(self, dim: int = 384, seed: int = 42):
        """Initialize mock encoder.

        Args:
            dim: Embedding dimension
            seed: Random seed for reproducibility
        """
        self.dim = dim
        self.rng = np.random.RandomState(seed)
        self.cache: dict[str, np.ndarray] = {}

    def query_embed(self, texts: list[str]) -> list[np.ndarray]:
        """Embed texts (deterministically for caching).

        Args:
            texts: List of text strings

        Returns:
            List of embeddings (normalized)
        """
        embeddings = []
        for text in texts:
            if text in self.cache:
                embeddings.append(self.cache[text])
            else:
                # Deterministic embedding based on text hash
                seed = hash(text) % (2**31)
                rng = np.random.RandomState(seed)
                vec = rng.randn(self.dim).astype(np.float32)
                vec /= (np.linalg.norm(vec) + 1e-9)
                self.cache[text] = vec
                embeddings.append(vec)

        return embeddings


@pytest.fixture
def mock_encoder() -> MockEncoder:
    """Fixture: Mock encoder for retrieval tests."""
    return MockEncoder()


# ---- Fixture: Mock Retriever ----

class MockRetriever:
    """Mock retriever that returns synthetic results."""

    def __init__(self, corpus: list[dict], relevance_fn: Callable = None):
        """Initialize mock retriever.

        Args:
            corpus: List of document dicts with "id", "title", "body"
            relevance_fn: Function(query, doc_id) -> relevance score [0, 1]
        """
        self.corpus = corpus
        self.relevance_fn = relevance_fn or self._default_relevance

    def _default_relevance(self, query: str, doc_id: str) -> float:
        """Default relevance: word overlap similarity.

        Args:
            query: Query string
            doc_id: Document ID

        Returns:
            Relevance score in [0, 1]
        """
        query_words = set(query.lower().split())
        doc = next((d for d in self.corpus if d.get("id") == doc_id), None)
        if not doc:
            return 0.0

        doc_text = (doc.get("title", "") + " " + doc.get("body", "")).lower()
        doc_words = set(doc_text.split())
        if not query_words or not doc_words:
            return 0.0

        overlap = len(query_words & doc_words)
        return overlap / max(len(query_words), len(doc_words))

    def search(self, query: str, k: int = 10) -> list[tuple[float, dict]]:
        """Retrieve top-k documents by relevance.

        Args:
            query: Query string
            k: Number of results

        Returns:
            List of (relevance_score, doc_dict) tuples
        """
        scores = []
        for doc in self.corpus:
            score = self.relevance_fn(query, doc.get("id", ""))
            scores.append((score, doc))

        # Sort by score descending
        scores.sort(key=lambda x: -x[0])
        return scores[:k]


@pytest.fixture
def sample_corpus() -> list[dict]:
    """Fixture: Sample trading document corpus.

    Returns:
        List of document records
    """
    return [
        {
            "id": "doc_1",
            "title": "Greeks in Options Trading",
            "body": "Gamma is the second derivative of option price with respect to underlying price. Delta is the first derivative."
        },
        {
            "id": "doc_2",
            "title": "Hedging Vega Exposure",
            "body": "Vega hedging can be done through calendar spreads or volatility swaps. Short-dated options have high vega decay."
        },
        {
            "id": "doc_3",
            "title": "Market Regime Detection",
            "body": "High volatility regimes vs mean reversion regimes require different strategies. Correlation breakdowns signal regime change."
        },
        {
            "id": "doc_4",
            "title": "Risk Management Basics",
            "body": "Value at Risk (VaR) measures potential losses. Position limits control concentration risk."
        },
        {
            "id": "doc_5",
            "title": "Futures and Basis",
            "body": "Basis is the difference between spot and futures price. Basis risk occurs when hedges are imperfect."
        },
    ]


@pytest.fixture
def mock_retriever(sample_corpus) -> MockRetriever:
    """Fixture: Mock retriever using sample corpus."""
    return MockRetriever(sample_corpus)


# ---- Fixture: Mock Entity Extractor ----

class MockEntityExtractor:
    """Mock entity extractor for testing."""

    def __init__(self, seed: int = 42):
        """Initialize mock extractor.

        Args:
            seed: Random seed for reproducibility
        """
        self.rng = np.random.RandomState(seed)

    def extract(self, text: str) -> set[str]:
        """Extract entities from text (mock: returns substrings matching patterns).

        Args:
            text: Text to extract from

        Returns:
            Set of entity strings
        """
        # Simple mock: extract capitalized words and known trading terms
        entities = set()

        # Known trading entities
        trading_terms = {
            "gamma", "delta", "vega", "theta", "rho",
            "volatility", "hedge", "options", "underlying",
            "regime", "correlation", "risk", "straddle",
            "spread", "calls", "puts", "bull", "bear"
        }

        words = text.lower().split()
        for word in words:
            word_clean = word.strip(".,!?;:")
            if word_clean in trading_terms:
                entities.add(word_clean)

        return entities


@pytest.fixture
def mock_entity_extractor() -> MockEntityExtractor:
    """Fixture: Mock entity extractor."""
    return MockEntityExtractor()


# ---- Fixture: Test Configuration ----

@pytest.fixture(scope="session")
def test_config() -> dict[str, Any]:
    """Fixture: Test configuration.

    Returns:
        Config dict with paths, timeouts, etc.
    """
    return {
        "tier_1_timeout_ms": 100,
        "tier_2_timeout_ms": 500,
        "min_queries_per_tier": 3,  # For testing, use fewer queries
        "baseline_regression_threshold_pct": 5.0,
        "results_dir": Path(__file__).parent / "results",
    }


# ---- Fixture: Report Output ----

@pytest.fixture(scope="session", autouse=True)
def setup_results_dir(test_config) -> Generator[None, None, None]:
    """Create results directory for test reports."""
    results_dir = test_config["results_dir"]
    results_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Results directory: {results_dir}")
    yield
    logger.info(f"Test results saved to {results_dir}")


# ---- Markers ----

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "tier1: Tier 1 retrieval tests"
    )
    config.addinivalue_line(
        "markers", "tier2: Tier 2 entity extraction tests"
    )
    config.addinivalue_line(
        "markers", "regression: Regression/benchmark tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests (skip with -m 'not slow')"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests"
    )
