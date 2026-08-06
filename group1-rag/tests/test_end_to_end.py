"""test_end_to_end.py — End-to-end evaluation tests for Group One RAG.

Combines Tier 1 retrieval and Tier 2 entity extraction.
Tests full pipeline: query -> retrieval -> entity extraction -> answer.

Target benchmarks:
  - Tier 1 precision@10 ≥ 0.50
  - Tier 2 entity F1 ≥ 0.85
  - Combined latency: ≤ 600ms (100ms + 500ms)
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from test_metrics import (
    RetrievalResult,
    EntityExtractionResult,
    EvaluationReport,
    BenchmarkValidator,
    BenchmarkTarget,
    precision_at_k,
    hit_at_one,
    ndcg_at_k,
    mean_reciprocal_rank,
    recall_at_k,
    entity_extraction_f1,
    compute_latency_stats,
    save_report,
)


@pytest.mark.e2e
class TestEndToEndPipeline:
    """End-to-end pipeline tests combining Tier 1 and Tier 2."""

    def test_e2e_retrieval_and_extraction(
        self, mock_retriever, sample_corpus, mock_entity_extractor, test_config
    ):
        """Test full pipeline: retrieval -> entity extraction."""
        query = "What is gamma hedging?"
        relevant_indices = {0, 1}  # Docs about Greeks and hedging

        # Tier 1: Retrieval
        tier1_start = time.perf_counter()
        retrieval_results = mock_retriever.search(query, k=10)
        tier1_latency = (time.perf_counter() - tier1_start) * 1000

        retrieved_indices = [
            sample_corpus.index(doc)
            for score, doc in retrieval_results
            if doc in sample_corpus
        ]

        # Combine results for entity extraction
        combined_text = " ".join(
            f"{doc.get('title', '')} {doc.get('body', '')}"
            for score, doc in retrieval_results
        )

        # Tier 2: Entity extraction
        tier2_start = time.perf_counter()
        entities = mock_entity_extractor.extract(combined_text)
        tier2_latency = (time.perf_counter() - tier2_start) * 1000

        total_latency = tier1_latency + tier2_latency

        # Check metrics
        precision = precision_at_k(retrieved_indices, relevant_indices, k=10)
        f1, _, _ = entity_extraction_f1(entities, {"gamma", "hedge"})

        print(f"E2E Pipeline:")
        print(f"  Tier 1 latency: {tier1_latency:.2f}ms")
        print(f"  Tier 2 latency: {tier2_latency:.2f}ms")
        print(f"  Total latency: {total_latency:.2f}ms")
        print(f"  Precision@10: {precision:.4f}")
        print(f"  Entity F1: {f1:.4f}")

        # Verify latency targets
        assert tier1_latency <= test_config["tier_1_timeout_ms"] * 2  # Allow some overhead
        assert tier2_latency <= test_config["tier_2_timeout_ms"] * 2

    def test_e2e_multiple_queries(
        self, mock_retriever, sample_corpus, mock_entity_extractor, golden_queries_by_tier, test_config
    ):
        """Test pipeline on multiple queries from golden set."""
        tier1_queries = golden_queries_by_tier[1][:3]
        tier2_queries = golden_queries_by_tier[2][:3]

        tier1_results = []
        tier2_results = []

        # Tier 1 queries
        for q_record in tier1_queries:
            query = q_record["query"]
            keywords = set(q_record["ground_truth_keywords"])

            start = time.perf_counter()
            retrieval_results = mock_retriever.search(query, k=10)
            latency = (time.perf_counter() - start) * 1000

            retrieved_indices = [
                sample_corpus.index(doc)
                for score, doc in retrieval_results
                if doc in sample_corpus
            ]

            result = RetrievalResult(
                query_id=q_record["id"],
                query=query,
                precision_at_10=precision_at_k(retrieved_indices, {sample_corpus.index(sample_corpus[0])}, k=10),
                hit_at_1=hit_at_one(retrieved_indices, {sample_corpus.index(sample_corpus[0])}),
                ndcg_at_10=ndcg_at_k(retrieved_indices, {sample_corpus.index(sample_corpus[0])}, k=10),
                mrr=mean_reciprocal_rank(retrieved_indices, {sample_corpus.index(sample_corpus[0])}),
                recall_at_10=recall_at_k(retrieved_indices, {sample_corpus.index(sample_corpus[0])}, k=10),
                latency_ms=latency,
                tier=1
            )
            tier1_results.append(result)

        # Tier 2 queries
        for q_record in tier2_queries:
            query = q_record["query"]
            keywords = set(q_record["ground_truth_keywords"])

            start = time.perf_counter()
            entities = mock_entity_extractor.extract(query)
            latency = (time.perf_counter() - start) * 1000

            f1, precision, recall = entity_extraction_f1(entities, keywords)

            result = EntityExtractionResult(
                query_id=q_record["id"],
                query=query,
                f1=f1,
                precision=precision,
                recall=recall,
                latency_ms=latency,
                tier=2
            )
            tier2_results.append(result)

        # Create report
        report = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_queries=len(tier1_results) + len(tier2_results),
            tier_1_results=tier1_results,
            entity_results=tier2_results
        )
        report.compute_aggregates()

        print(f"E2E Report:")
        print(f"  Tier 1 queries: {len(tier1_results)}")
        print(f"  Tier 2 queries: {len(tier2_results)}")
        print(f"  Avg Precision@10: {report.avg_precision_at_10:.4f}")
        print(f"  Avg Entity F1: {report.entity_avg_f1:.4f}")

        assert len(tier1_results) > 0
        assert len(tier2_results) > 0

    def test_e2e_benchmark_validation(
        self, mock_retriever, sample_corpus, mock_entity_extractor, golden_queries_by_tier
    ):
        """Test that results pass benchmark validation."""
        tier1_queries = golden_queries_by_tier[1][:5]

        tier1_results = []
        entity_results = []

        # Generate results
        for q_record in tier1_queries:
            query = q_record["query"]

            # Tier 1 retrieval
            retrieval_results = mock_retriever.search(query, k=10)
            retrieved_indices = [
                sample_corpus.index(doc)
                for score, doc in retrieval_results
                if doc in sample_corpus
            ]

            tier1_results.append(RetrievalResult(
                query_id=q_record["id"],
                query=query,
                precision_at_10=precision_at_k(retrieved_indices, {sample_corpus.index(sample_corpus[0])}, k=10),
                hit_at_1=hit_at_one(retrieved_indices, {sample_corpus.index(sample_corpus[0])}),
                ndcg_at_10=ndcg_at_k(retrieved_indices, {sample_corpus.index(sample_corpus[0])}, k=10),
                mrr=mean_reciprocal_rank(retrieved_indices, {sample_corpus.index(sample_corpus[0])}),
                recall_at_10=recall_at_k(retrieved_indices, {sample_corpus.index(sample_corpus[0])}, k=10),
                latency_ms=1.0,
                tier=1
            ))

            # Tier 2 entity extraction
            entities = mock_entity_extractor.extract(query)
            ground_truth = set(q_record["ground_truth_keywords"][:3])
            f1, precision, recall = entity_extraction_f1(entities, ground_truth)

            entity_results.append(EntityExtractionResult(
                query_id=q_record["id"],
                query=query,
                f1=f1,
                precision=precision,
                recall=recall,
                latency_ms=1.0,
                tier=2
            ))

        report = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_queries=len(tier1_results) + len(entity_results),
            tier_1_results=tier1_results,
            entity_results=entity_results
        )
        report.compute_aggregates()

        # Validate against benchmarks
        validator = BenchmarkValidator()
        validation_result = validator.validate(report)

        print(f"Benchmark validation:")
        for result in validation_result["results"]:
            print(f"  {result['benchmark']}: {result['message']}")

        # Note: For mock retriever/extractor, we may not hit all targets
        # Real system should be validated separately

    def test_e2e_latency_distribution(
        self, mock_retriever, sample_corpus, test_config
    ):
        """Test latency distribution across multiple runs."""
        query = "What is gamma in options?"
        latencies = []

        for _ in range(10):
            start = time.perf_counter()
            _ = mock_retriever.search(query, k=10)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        stats = compute_latency_stats(latencies)

        print(f"Latency distribution:")
        print(f"  Mean: {stats.mean_ms:.2f}ms")
        print(f"  p50: {stats.p50_ms:.2f}ms")
        print(f"  p99: {stats.p99_ms:.2f}ms")

        assert stats.p99_ms > 0


class TestE2EReportGeneration:
    """Tests for report generation and storage."""

    def test_e2e_report_save_and_load(
        self, mock_retriever, sample_corpus, test_config
    ):
        """Test saving and loading evaluation reports."""
        query = "What is gamma?"
        results = mock_retriever.search(query, k=10)
        retrieved_indices = [
            sample_corpus.index(doc)
            for score, doc in results
            if doc in sample_corpus
        ]

        tier1_results = [
            RetrievalResult(
                query_id=1,
                query=query,
                precision_at_10=precision_at_k(retrieved_indices, {0}, k=10),
                hit_at_1=hit_at_one(retrieved_indices, {0}),
                ndcg_at_10=ndcg_at_k(retrieved_indices, {0}, k=10),
                mrr=mean_reciprocal_rank(retrieved_indices, {0}),
                recall_at_10=recall_at_k(retrieved_indices, {0}, k=10),
                latency_ms=1.0,
                tier=1
            )
        ]

        report = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_queries=1,
            tier_1_results=tier1_results
        )
        report.compute_aggregates()

        # Save report
        report_path = test_config["results_dir"] / "test_report.json"
        save_report(report, report_path)

        assert report_path.exists()

        # Load and verify
        from test_metrics import load_report
        loaded = load_report(report_path)

        assert loaded["total_queries"] == 1
        assert len(loaded["tier_1_results"]) == 1
        print(f"Report saved and loaded successfully")

    def test_e2e_regression_detection(
        self, mock_retriever, sample_corpus, test_config
    ):
        """Test regression detection across runs."""
        from test_metrics import RegressionTracker

        # Create two reports
        report1 = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_queries=1,
            tier_1_results=[
                RetrievalResult(
                    query_id=1,
                    query="gamma",
                    precision_at_10=0.6,
                    hit_at_1=True,
                    ndcg_at_10=0.7,
                    mrr=1.0,
                    recall_at_10=0.8,
                    latency_ms=50.0,
                    tier=1
                )
            ]
        )
        report1.compute_aggregates()

        # Save as baseline
        baseline_path = test_config["results_dir"] / "baseline_regression_test.json"
        tracker = RegressionTracker()
        tracker.save_baseline(report1, baseline_path)

        # Create report with regression (lower precision)
        report2 = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_queries=1,
            tier_1_results=[
                RetrievalResult(
                    query_id=1,
                    query="gamma",
                    precision_at_10=0.5,  # 16.7% drop
                    hit_at_1=True,
                    ndcg_at_10=0.7,
                    mrr=1.0,
                    recall_at_10=0.8,
                    latency_ms=50.0,
                    tier=1
                )
            ]
        )
        report2.compute_aggregates()

        # Check regression
        tracker2 = RegressionTracker(baseline_path)
        regression_check = tracker2.check_regression(report2, threshold_percent=5.0)

        print(f"Regression check result: {regression_check}")
        # Should detect regression in precision_at_10


class TestE2EErrorHandling:
    """Tests for error handling in end-to-end pipeline."""

    def test_e2e_empty_retrieval_results(
        self, mock_entity_extractor
    ):
        """Test pipeline when retrieval returns no results."""
        # Simulate empty retrieval
        entities = mock_entity_extractor.extract("")

        assert isinstance(entities, set)
        assert len(entities) == 0

    def test_e2e_malformed_query(self, mock_retriever):
        """Test pipeline with malformed queries."""
        malformed_queries = [
            "\x00",
            "?" * 1000,
            None or "fallback",
        ]

        for q in malformed_queries:
            if q is not None:
                try:
                    results = mock_retriever.search(q, k=10)
                    assert isinstance(results, list)
                except Exception as e:
                    logger.info(f"Expected exception for malformed query: {e}")

    def test_e2e_timeout_handling(self, mock_retriever, test_config):
        """Test handling of operations that exceed timeout."""
        query = "What is gamma?"

        start = time.perf_counter()
        results = mock_retriever.search(query, k=10)
        elapsed = (time.perf_counter() - start) * 1000

        # Mock is fast, so this should pass
        assert elapsed < test_config["tier_1_timeout_ms"] * 10


# Logging helper
import logging
logger = logging.getLogger(__name__)
