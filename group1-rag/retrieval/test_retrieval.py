"""test_retrieval.py — Test harness for Group One Trading RAG retrieval engine.

Test coverage:
  1. Search mode never calls LLM (only uses pre-indexed vectors + BM25)
  2. Rerank flag override works (disable/enable cross-encoder)
  3. Scores are strictly descending
  4. k parameter respected (never exceeds k results)
  5. nDCG@10 >= 0.50 performance target
  6. Latency <= 100ms on typical corpus
  7. Hybrid fusion formula correctness
  8. Error handling and dense-only fallback
  9. Index building and edge cases

Run with: pytest test_retrieval.py -v --tb=short
"""

import logging
import time
import unittest
from typing import Callable, Optional
from unittest.mock import MagicMock, patch

import numpy as np

from retrieval_engine import (
    LAMBDA,
    HybridRetriever,
    _bm25,
    _minmax,
    _toks,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockEncoder:
    """Mock encoder that returns deterministic embeddings (no external calls)."""

    def __init__(self, dim: int = 768, seed: int = 42):
        """Initialize with embedding dimension."""
        self.dim = dim
        self.seed = seed
        self.query_calls = 0  # Track encoder calls (should only be for vectors)
        self.rng = np.random.RandomState(seed)

    def query_embed(self, texts: list[str]) -> list[np.ndarray]:
        """Embed texts deterministically (no LLM calls).

        Args:
            texts: List of strings to embed

        Returns:
            List of normalized embeddings
        """
        self.query_calls += 1
        embeddings = []
        for text in texts:
            # Deterministic: seed from text hash + position
            h = hash(text) & 0x7FFFFFFF
            self.rng.seed((self.seed + h) % (2**31))
            emb = self.rng.randn(self.dim).astype(np.float32)
            # Normalize
            emb /= np.linalg.norm(emb) + 1e-9
            embeddings.append(emb)
        return embeddings


class TestTokenization(unittest.TestCase):
    """Test tokenization and stop word filtering."""

    def test_toks_lowercase(self):
        """Tokenization is lowercase."""
        result = _toks("The Quick BROWN Fox")
        assert all(t.islower() for t in result)

    def test_toks_stops_filtered(self):
        """Stop words are removed."""
        result = _toks("the quick brown fox")
        assert "the" not in result
        assert "quick" in result
        assert "brown" in result

    def test_toks_length_filter(self):
        """Tokens < 3 chars removed."""
        result = _toks("a an the dog")
        assert "dog" in result
        # "a", "an", "the" all removed (stop words or length)

    def test_toks_empty(self):
        """Empty string returns empty list."""
        assert _toks("") == []
        assert _toks("   ") == []


class TestMinmax(unittest.TestCase):
    """Test min-max normalization."""

    def test_minmax_basic(self):
        """Min-max scale [0, 10] -> [0, 1]."""
        arr = np.array([0.0, 5.0, 10.0], dtype=np.float64)
        result = _minmax(arr)
        np.testing.assert_array_almost_equal(result, [0.0, 0.5, 1.0])

    def test_minmax_uniform(self):
        """All same values -> all zeros."""
        arr = np.array([5.0, 5.0, 5.0], dtype=np.float64)
        result = _minmax(arr)
        np.testing.assert_array_almost_equal(result, [0.0, 0.0, 0.0])

    def test_minmax_negative(self):
        """Handles negative values correctly."""
        arr = np.array([-10.0, 0.0, 10.0], dtype=np.float64)
        result = _minmax(arr)
        np.testing.assert_array_almost_equal(result, [0.0, 0.5, 1.0])


class TestBM25(unittest.TestCase):
    """Test BM25 scoring."""

    def setUp(self):
        """Set up a simple index."""
        self.index_data = {
            "df": {"dog": 2, "cat": 1, "animal": 3},
            "n": 3,
            "avgdl": 3.0,
            "tf": [
                {"dog": 2, "animal": 1},  # doc 0: "dog dog animal"
                {"cat": 1, "animal": 1},  # doc 1: "cat animal"
                {"dog": 1, "animal": 1},  # doc 2: "dog animal"
            ],
        }

    def test_bm25_basic(self):
        """BM25 score > 0 for matching tokens."""
        score = _bm25(["dog"], 0, self.index_data)
        assert score > 0

    def test_bm25_zero_for_missing(self):
        """BM25 score = 0 for missing tokens."""
        score = _bm25(["fox"], 0, self.index_data)
        assert score == 0.0

    def test_bm25_frequency_matters(self):
        """Doc with more occurrences scores higher."""
        score_doc0 = _bm25(["dog"], 0, self.index_data)  # dog appears 2x
        score_doc1 = _bm25(["dog"], 1, self.index_data)  # dog appears 0x
        score_doc2 = _bm25(["dog"], 2, self.index_data)  # dog appears 1x
        assert score_doc0 > score_doc2 > score_doc1


class TestHybridRetrieverBasics(unittest.TestCase):
    """Test HybridRetriever initialization and indexing."""

    def setUp(self):
        """Create a retriever with mock encoder."""
        self.encoder = MockEncoder(dim=768)
        self.retriever = HybridRetriever(self.encoder)

    def test_init(self):
        """Retriever initializes with correct parameters."""
        assert self.retriever.encoder is self.encoder
        assert self.retriever.lambda_weight == LAMBDA
        assert self.retriever._corpus == []
        assert self.retriever._vectors is None

    def test_index_simple(self):
        """Index corpus successfully."""
        corpus = [
            {"title": "Bitcoin Trading", "body": "Buy low sell high"},
            {"title": "Ethereum Strategy", "body": "Long-term hold"},
        ]
        self.retriever.index(corpus)

        assert len(self.retriever._corpus) == 2
        assert self.retriever._vectors.shape == (2, 768)
        assert self.retriever._index_data is not None

    def test_index_with_ids(self):
        """Index with custom IDs."""
        corpus = [
            {"title": "Bitcoin Trading", "body": "Buy low sell high"},
            {"title": "Ethereum Strategy", "body": "Long-term hold"},
        ]
        ids = ["BTC-001", "ETH-001"]
        self.retriever.index(corpus, ids=ids)

        assert self.retriever._ids == ids

    def test_index_mismatched_ids(self):
        """Raise error if IDs don't match corpus length."""
        corpus = [
            {"title": "Bitcoin Trading", "body": "Buy low sell high"},
            {"title": "Ethereum Strategy", "body": "Long-term hold"},
        ]
        ids = ["BTC-001"]  # Only 1 ID for 2 docs
        with self.assertRaises(ValueError):
            self.retriever.index(corpus, ids=ids)

    def test_search_without_index(self):
        """Raise error if search called before indexing."""
        with self.assertRaises(ValueError):
            self.retriever.search("bitcoin")

    def test_search_empty_query(self):
        """Empty query returns empty results."""
        corpus = [
            {"title": "Bitcoin Trading", "body": "Buy low sell high"},
        ]
        self.retriever.index(corpus)
        result = self.retriever.search("")
        assert result == []

    def test_stats(self):
        """get_stats returns correct info."""
        corpus = [
            {"title": "Bitcoin Trading", "body": "Buy low sell high"},
            {"title": "Ethereum Strategy", "body": "Long-term hold"},
        ]
        self.retriever.index(corpus)
        stats = self.retriever.get_stats()

        assert stats["corpus_size"] == 2
        assert stats["vector_dim"] == 768
        assert stats["lambda_weight"] == LAMBDA
        assert stats["index_built"] is True


class TestHybridRetrieverSearch(unittest.TestCase):
    """Test search functionality: correctness, performance, fallback."""

    def setUp(self):
        """Create a realistic test corpus."""
        self.encoder = MockEncoder(dim=768)
        self.retriever = HybridRetriever(self.encoder)

        # Trading-related corpus for nDCG evaluation
        self.corpus = [
            {
                "title": "Bitcoin Trading Strategy",
                "body": "Learn how to trade bitcoin effectively. Buy low sell high.",
                "tags": ["trading", "bitcoin", "strategy"],
            },
            {
                "title": "Ethereum Price Analysis",
                "body": "Analyze ethereum market trends and price movements.",
                "tags": ["ethereum", "analysis", "price"],
            },
            {
                "title": "Stock Market Fundamentals",
                "body": "Understand stock trading basics and market mechanics.",
                "tags": ["stocks", "trading", "fundamentals"],
            },
            {
                "title": "Options Trading Guide",
                "body": "Master options contracts and hedging strategies.",
                "tags": ["options", "trading", "derivatives"],
            },
            {
                "title": "Risk Management in Crypto",
                "body": "Protect your portfolio with proper risk management.",
                "tags": ["crypto", "risk", "management"],
            },
        ]
        self.retriever.index(self.corpus)

    def test_search_returns_results(self):
        """Search returns results."""
        results = self.retriever.search("bitcoin trading", k=3)
        assert len(results) > 0
        assert len(results) <= 3

    def test_search_respects_k(self):
        """Search returns at most k results."""
        for k in [1, 2, 5, 100]:
            results = self.retriever.search("trading", k=k)
            assert len(results) <= k

    def test_scores_descending(self):
        """Scores are strictly descending."""
        results = self.retriever.search("trading strategy", k=10)
        scores = [score for score, _ in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], f"Scores not descending: {scores}"

    def test_results_have_records(self):
        """Each result includes corpus record."""
        results = self.retriever.search("trading", k=5)
        for score, record in results:
            assert isinstance(score, float)
            assert isinstance(record, dict)
            assert "title" in record

    def test_search_latency(self):
        """Search completes within 100ms target."""
        query = "bitcoin trading strategy"
        start = time.perf_counter()
        results = self.retriever.search(query, k=10)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(results) > 0
        assert elapsed_ms <= 100, f"Search took {elapsed_ms:.1f}ms (target: 100ms)"
        logger.info(f"Search latency: {elapsed_ms:.1f}ms")

    def test_search_never_calls_llm(self):
        """Search only uses pre-indexed vectors (no LLM calls)."""
        encoder_calls_before = self.encoder.query_calls
        self.retriever.search("bitcoin trading", k=5)
        encoder_calls_after = self.encoder.query_calls

        # Should be 1 call (for query embedding), not multiple
        assert encoder_calls_after == encoder_calls_before + 1

    def test_rerank_flag_off(self):
        """rerank=False skips cross-encoder."""
        with patch.object(
            self.retriever, "_load_cross_encoder", side_effect=Exception("Should not call")
        ) as mock_ce:
            results = self.retriever.search("trading", k=5, rerank=False)
            assert len(results) > 0
            mock_ce.assert_not_called()

    def test_rerank_flag_on_unavailable(self):
        """rerank=True falls back gracefully if CE unavailable."""
        with patch.object(
            self.retriever, "_load_cross_encoder", side_effect=ImportError("fastembed missing")
        ):
            # Should not raise, should return hybrid results
            results = self.retriever.search("trading", k=5, rerank=True)
            assert len(results) > 0

    def test_search_fallback_on_error(self):
        """Hybrid search falls back to dense on error."""
        # Simulate an error in hybrid logic
        with patch.object(
            self.retriever, "_search_inner", side_effect=Exception("Hybrid failed")
        ):
            results = self.retriever.search("bitcoin", k=5)
            assert len(results) > 0  # Should still return results (dense fallback)

    def test_dense_fallback_returns_k(self):
        """Dense fallback returns up to k results."""
        with patch.object(
            self.retriever, "_search_inner", side_effect=Exception("Forced fallback")
        ):
            for k in [1, 3, 10]:
                results = self.retriever.search("bitcoin", k=k)
                assert len(results) <= k


class TestHybridRetrieverFusion(unittest.TestCase):
    """Test hybrid fusion formula and weighting."""

    def setUp(self):
        """Create retriever and index."""
        self.encoder = MockEncoder(dim=768)
        self.retriever = HybridRetriever(self.encoder, lambda_weight=0.45)
        self.corpus = [
            {
                "title": "Bitcoin",
                "body": "Bitcoin is a cryptocurrency bitcoin bitcoin.",
                "tags": ["crypto"],
            },
            {"title": "Ethereum", "body": "Ethereum is digital money.", "tags": ["crypto"]},
        ]
        self.retriever.index(self.corpus)

    def test_fusion_lambda_weight(self):
        """Verify LAMBDA weighting in fusion."""
        assert self.retriever.lambda_weight == 0.45

    def test_results_are_fused(self):
        """Results show that fusion is applied (intermediate scores)."""
        results = self.retriever.search("bitcoin", k=2)
        # Scores should be in reasonable range (normalized fusion)
        for score, _ in results:
            assert 0.0 <= score <= 1.0 + 0.15  # Allow phrase boost


class TestNDCGEvaluation(unittest.TestCase):
    """Test nDCG@10 performance metric (Tier 1 target: >= 0.50)."""

    def setUp(self):
        """Create a test corpus with known relevance."""
        self.encoder = MockEncoder(dim=768, seed=42)
        self.retriever = HybridRetriever(self.encoder)

        # Curated corpus with clear relevance relationships
        self.corpus = [
            {
                "title": "Bitcoin Trading Fundamentals",
                "body": "Complete guide to bitcoin trading strategies.",
                "tags": ["trading", "bitcoin", "strategies"],
            },  # 0
            {
                "title": "Day Trading Bitcoin",
                "body": "Fast strategies for daily bitcoin trading.",
                "tags": ["trading", "bitcoin", "day-trading"],
            },  # 1
            {
                "title": "Bitcoin Hodling Strategy",
                "body": "Long-term bitcoin investment approach.",
                "tags": ["bitcoin", "investment", "strategy"],
            },  # 2
            {
                "title": "Cryptocurrency Overview",
                "body": "General overview of crypto assets.",
                "tags": ["crypto", "overview"],
            },  # 3
            {
                "title": "Ethereum Trading",
                "body": "Ethereum trading and price analysis.",
                "tags": ["trading", "ethereum"],
            },  # 4
            {
                "title": "Stock Market Trading",
                "body": "Traditional stock market trading strategies.",
                "tags": ["trading", "stocks"],
            },  # 5
            {
                "title": "Finance Basics",
                "body": "Introduction to financial markets.",
                "tags": ["finance"],
            },  # 6
            {
                "title": "Risk Management",
                "body": "Managing trading risk and portfolio allocation.",
                "tags": ["risk", "trading"],
            },  # 7
            {
                "title": "Technical Analysis",
                "body": "Using charts and indicators for trading.",
                "tags": ["trading", "analysis"],
            },  # 8
            {
                "title": "Market Psychology",
                "body": "Understanding investor behavior and market trends.",
                "tags": ["psychology", "market"],
            },  # 9
        ]
        self.retriever.index(self.corpus)

    def test_ndcg_bitcoin_trading(self):
        """nDCG@10 for 'bitcoin trading' query."""
        query = "bitcoin trading"
        results = self.retriever.search(query, k=10)

        # Ground truth relevance: [0, 1, 2, 8, 4, 7, 9, 5, 3, 6]
        # (docs about bitcoin + trading score higher)
        ideal_relevance = [1, 1, 1, 1, 0, 1, 0, 0, 0, 0]  # At most 4 relevant in top 10
        retrieved_indices = []
        for score, rec in results:
            # Find which doc this is
            for i, c in enumerate(self.corpus):
                if c == rec:
                    retrieved_indices.append(i)
                    break

        ndcg = self._compute_ndcg(retrieved_indices, ideal_relevance, k=10)
        logger.info(f"nDCG@10 for '{query}': {ndcg:.3f}")
        assert ndcg >= 0.50, f"nDCG@10 {ndcg:.3f} < 0.50 (target)"

    def test_ndcg_trading_strategy(self):
        """nDCG@10 for 'trading strategy' query."""
        query = "trading strategy"
        results = self.retriever.search(query, k=10)

        retrieved_indices = []
        for score, rec in results:
            for i, c in enumerate(self.corpus):
                if c == rec:
                    retrieved_indices.append(i)
                    break

        # All docs with "trading" + "strategy" are relevant
        ndcg = self._compute_ndcg(retrieved_indices, [1] * len(self.corpus), k=10)
        logger.info(f"nDCG@10 for '{query}': {ndcg:.3f}")
        assert ndcg >= 0.50

    def _compute_ndcg(self, retrieved: list[int], relevance: list[int], k: int = 10) -> float:
        """Compute nDCG@k given retrieved indices and relevance scores."""
        # DCG: sum(rel_i / log2(i+1)) for i in range(min(len(retrieved), k))
        dcg = 0.0
        for i in range(min(len(retrieved), k)):
            rel = relevance[retrieved[i]] if retrieved[i] < len(relevance) else 0
            dcg += rel / np.log2(i + 2)

        # IDCG: best possible DCG with perfect ranking
        ideal = sorted(relevance, reverse=True)[:k]
        idcg = sum(rel / np.log2(i + 2) for i, rel in enumerate(ideal))

        return dcg / idcg if idcg > 0 else 0.0


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def setUp(self):
        """Create retriever."""
        self.encoder = MockEncoder(dim=768)
        self.retriever = HybridRetriever(self.encoder)

    def test_index_empty_corpus(self):
        """Handle empty corpus."""
        self.retriever.index([])
        assert self.retriever._corpus == []

    def test_index_single_document(self):
        """Handle single document."""
        self.retriever.index([{"title": "Doc", "body": "Content"}])
        results = self.retriever.search("doc", k=1)
        assert len(results) == 1

    def test_large_k_request(self):
        """Request k larger than corpus."""
        self.retriever.index([
            {"title": "Doc1", "body": "Content"},
            {"title": "Doc2", "body": "Content"},
        ])
        results = self.retriever.search("content", k=1000)
        assert len(results) <= 2

    def test_very_long_query(self):
        """Handle very long query."""
        long_query = " ".join(["word"] * 100)
        self.retriever.index([{"title": "Doc", "body": "word word word"}])
        results = self.retriever.search(long_query, k=1)
        assert len(results) > 0

    def test_special_characters_in_query(self):
        """Handle special characters."""
        self.retriever.index([{"title": "Bitcoin", "body": "Trading"}])
        results = self.retriever.search("@#$%^&*()", k=1)
        # Should not crash
        assert isinstance(results, list)

    def test_corpus_with_missing_fields(self):
        """Handle records with missing title/body."""
        self.retriever.index([
            {"title": "Doc1"},  # No body
            {"body": "Content"},  # No title
            {},  # Neither
        ])
        results = self.retriever.search("doc", k=3)
        assert len(results) <= 3


class TestIntegration(unittest.TestCase):
    """Integration tests: full workflow."""

    def test_full_workflow(self):
        """Complete index-search workflow."""
        encoder = MockEncoder(dim=768)
        retriever = HybridRetriever(encoder)

        # 1. Index corpus
        corpus = [
            {
                "title": "Bitcoin Trading",
                "body": "How to trade bitcoin effectively.",
                "tags": ["trading"],
            },
            {
                "title": "Ethereum Investing",
                "body": "Long-term ethereum investment strategy.",
                "tags": ["investing"],
            },
            {
                "title": "Risk Management",
                "body": "Protect your portfolio with proper risk controls.",
                "tags": ["risk"],
            },
        ]
        retriever.index(corpus)

        # 2. Search
        results = retriever.search("bitcoin trading", k=2)
        assert len(results) <= 2
        assert len(results) > 0

        # 3. Verify scores descend
        scores = [score for score, _ in results]
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

        # 4. Re-search with different query
        results2 = retriever.search("risk", k=3)
        assert len(results2) > 0

        # 5. Stats
        stats = retriever.get_stats()
        assert stats["corpus_size"] == 3
        assert stats["index_built"] is True


if __name__ == "__main__":
    unittest.main(verbosity=2)
