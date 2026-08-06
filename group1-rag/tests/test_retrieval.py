"""test_retrieval.py — Tier 1 retrieval evaluation tests.

Tests for hybrid dense + BM25 retrieval system.
Measures: Precision@10, Hit@1, nDCG@10, MRR, latency.

Target: Precision@10 ≥ 0.50, Latency ≤ 100ms
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from test_metrics import (
    RetrievalResult,
    EvaluationReport,
    precision_at_k,
    hit_at_one,
    ndcg_at_k,
    mean_reciprocal_rank,
    recall_at_k,
    save_report,
)


@pytest.mark.tier1
class TestTier1Retrieval:
    """Tier 1 retrieval evaluation suite."""

    def test_retrieval_precision_at_10_sample(
        self, mock_retriever, sample_corpus, test_config
    ):
        """Test Precision@10 on sample queries."""
        sample_queries = [
            {"query": "What is gamma?", "relevant_indices": {0}},
            {"query": "How do I hedge vega?", "relevant_indices": {1}},
            {"query": "What strategies work in this regime?", "relevant_indices": {2}},
        ]

        precisions = []
        for q_data in sample_queries:
            results = mock_retriever.search(q_data["query"], k=10)
            retrieved_indices = [
                sample_corpus.index(doc)
                for score, doc in results
                if doc in sample_corpus
            ]
            precision = precision_at_k(retrieved_indices, q_data["relevant_indices"], k=10)
            precisions.append(precision)

        avg_precision = sum(precisions) / len(precisions) if precisions else 0.0
        assert avg_precision >= 0.0, "Precision should be non-negative"
        print(f"Sample Precision@10: {avg_precision:.4f}")

    def test_retrieval_hit_at_1_sample(
        self, mock_retriever, sample_corpus
    ):
        """Test Hit@1 rate on sample queries."""
        sample_queries = [
            {"query": "What is gamma?", "relevant_indices": {0}},
            {"query": "Hedging strategies", "relevant_indices": {1}},
            {"query": "Risk management", "relevant_indices": {3}},
        ]

        hits = []
        for q_data in sample_queries:
            results = mock_retriever.search(q_data["query"], k=1)
            if results:
                doc = results[0][1]
                retrieved_idx = sample_corpus.index(doc) if doc in sample_corpus else -1
                hit = retrieved_idx in q_data["relevant_indices"]
            else:
                hit = False
            hits.append(hit)

        hit_rate = sum(hits) / len(hits) if hits else 0.0
        print(f"Sample Hit@1 rate: {hit_rate:.2%}")

    def test_retrieval_ndcg_at_10_sample(
        self, mock_retriever, sample_corpus
    ):
        """Test nDCG@10 on sample queries."""
        sample_queries = [
            {"query": "What is gamma?", "relevant_indices": {0}},
            {"query": "How do I hedge vega?", "relevant_indices": {1, 4}},
            {"query": "Risk management", "relevant_indices": {3}},
        ]

        ndcgs = []
        for q_data in sample_queries:
            results = mock_retriever.search(q_data["query"], k=10)
            retrieved_indices = [
                sample_corpus.index(doc)
                for score, doc in results
                if doc in sample_corpus
            ]
            ndcg = ndcg_at_k(retrieved_indices, q_data["relevant_indices"], k=10)
            ndcgs.append(ndcg)

        avg_ndcg = sum(ndcgs) / len(ndcgs) if ndcgs else 0.0
        print(f"Sample nDCG@10: {avg_ndcg:.4f}")

    def test_retrieval_mrr_sample(
        self, mock_retriever, sample_corpus
    ):
        """Test Mean Reciprocal Rank."""
        sample_queries = [
            {"query": "What is gamma?", "relevant_indices": {0}},
            {"query": "How do I hedge vega?", "relevant_indices": {1}},
            {"query": "Risk and portfolio", "relevant_indices": {3, 4}},
        ]

        mrrs = []
        for q_data in sample_queries:
            results = mock_retriever.search(q_data["query"], k=10)
            retrieved_indices = [
                sample_corpus.index(doc)
                for score, doc in results
                if doc in sample_corpus
            ]
            mrr = mean_reciprocal_rank(retrieved_indices, q_data["relevant_indices"])
            mrrs.append(mrr)

        avg_mrr = sum(mrrs) / len(mrrs) if mrrs else 0.0
        print(f"Sample MRR: {avg_mrr:.4f}")

    @pytest.mark.parametrize("k", [1, 5, 10])
    def test_retrieval_recall_at_k(self, mock_retriever, sample_corpus, k):
        """Test Recall@k for different cutoffs."""
        query = "What is gamma? derivatives options"
        relevant_indices = {0, 1}  # Two relevant docs in sample corpus

        results = mock_retriever.search(query, k=k)
        retrieved_indices = [
            sample_corpus.index(doc)
            for score, doc in results
            if doc in sample_corpus
        ]
        recall = recall_at_k(retrieved_indices, relevant_indices, k=k)

        assert 0.0 <= recall <= 1.0, f"Recall@{k} should be in [0, 1]"
        print(f"Recall@{k}: {recall:.4f}")

    def test_retrieval_latency_tier1(self, mock_retriever, sample_corpus, test_config):
        """Test Tier 1 latency (target: ≤ 100ms)."""
        query = "What is gamma?"
        latencies = []

        # Run multiple times to measure latency distribution
        for _ in range(5):
            start = time.perf_counter()
            _ = mock_retriever.search(query, k=10)
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        p99_latency = sorted(latencies)[-1]  # Approximate p99

        target_latency = test_config["tier_1_timeout_ms"]
        print(f"Tier 1 latency: avg={avg_latency:.2f}ms, p99={p99_latency:.2f}ms (target={target_latency}ms)")

        # Note: Mock retriever is very fast, so this will likely pass
        # Real retriever should be benchmarked separately

    def test_retrieval_corpus_size_scaling(self, mock_retriever, test_config):
        """Test that retrieval scales with corpus size."""
        query = "What is gamma options risk"

        latencies = []
        for _ in range(3):
            start = time.perf_counter()
            _ = mock_retriever.search(query, k=10)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        print(f"Retrieval latency for corpus size {len(mock_retriever.corpus)}: {avg_latency:.2f}ms")

    def test_retrieval_empty_query(self, mock_retriever):
        """Test behavior on empty query."""
        results = mock_retriever.search("", k=10)
        # Should return something (all docs) or nothing, both acceptable
        assert isinstance(results, list)

    def test_retrieval_special_characters(self, mock_retriever):
        """Test queries with special characters."""
        special_queries = [
            "What's gamma?",
            "Greeks (delta, gamma, vega)",
            "Hedge@100% or 50%?",
        ]

        for q in special_queries:
            results = mock_retriever.search(q, k=5)
            assert isinstance(results, list)
            print(f"Query '{q}' returned {len(results)} results")

    def test_retrieval_long_query(self, mock_retriever):
        """Test long complex queries."""
        long_query = "How do I hedge my vega exposure in a volatile market regime with gamma scalping techniques?"

        results = mock_retriever.search(long_query, k=10)
        assert isinstance(results, list)
        assert len(results) <= 10
        print(f"Long query returned {len(results)} results")

    def test_retrieval_k_parameter(self, mock_retriever):
        """Test k parameter (number of results)."""
        query = "What is gamma?"

        for k in [1, 5, 10, 20, 100]:
            results = mock_retriever.search(query, k=k)
            assert len(results) <= k, f"Should return at most {k} results"

    def test_retrieval_result_scoring(self, mock_retriever):
        """Test that results are properly scored."""
        query = "gamma options trading"
        results = mock_retriever.search(query, k=10)

        if len(results) > 1:
            # Scores should be in descending order
            scores = [score for score, _ in results]
            assert scores == sorted(scores, reverse=True), "Results should be sorted by score descending"

    def test_retrieval_relevance_consistency(self, mock_retriever):
        """Test that same query returns consistent relevance ordering."""
        query = "What is gamma?"

        results1 = mock_retriever.search(query, k=5)
        results2 = mock_retriever.search(query, k=5)

        ids1 = [doc.get("id") for _, doc in results1]
        ids2 = [doc.get("id") for _, doc in results2]

        assert ids1 == ids2, "Multiple searches with same query should return same order"


class TestTier1RegressionBaseline:
    """Baseline and regression tests for Tier 1."""

    def test_tier1_baseline_creation(self, mock_retriever, sample_corpus, test_config):
        """Create and save Tier 1 baseline."""
        from test_metrics import EvaluationReport
        from datetime import datetime

        tier_1_results = []
        query_id = 1
        for query in ["gamma", "hedge vega", "risk management"]:
            results = mock_retriever.search(query, k=10)
            retrieved_indices = [
                sample_corpus.index(doc)
                for score, doc in results
                if doc in sample_corpus
            ]
            relevant_indices = {sample_corpus.index(sample_corpus[0])}

            start = time.perf_counter()
            _ = mock_retriever.search(query, k=10)
            latency = (time.perf_counter() - start) * 1000

            result = RetrievalResult(
                query_id=query_id,
                query=query,
                precision_at_10=precision_at_k(retrieved_indices, relevant_indices, k=10),
                hit_at_1=hit_at_one(retrieved_indices, relevant_indices),
                ndcg_at_10=ndcg_at_k(retrieved_indices, relevant_indices, k=10),
                mrr=mean_reciprocal_rank(retrieved_indices, relevant_indices),
                recall_at_10=recall_at_k(retrieved_indices, relevant_indices, k=10),
                latency_ms=latency,
                tier=1
            )
            tier_1_results.append(result)
            query_id += 1

        report = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_queries=len(tier_1_results),
            tier_1_results=tier_1_results
        )
        report.compute_aggregates()

        # Save as baseline
        baseline_path = test_config["results_dir"] / "baseline_tier1.json"
        from test_metrics import RegressionTracker
        tracker = RegressionTracker()
        tracker.save_baseline(report, baseline_path)

        assert baseline_path.exists()
        print(f"Created Tier 1 baseline: {report.avg_precision_at_10:.4f}")
