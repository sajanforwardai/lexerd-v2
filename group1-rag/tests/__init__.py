"""Group One RAG Testing Framework

Comprehensive testing suite for Group One Trading RAG system:
  - Tier 1: Hybrid dense + BM25 retrieval
  - Tier 2: Entity extraction and classification
  - E2E: Full pipeline evaluation
  - Regression: Baseline tracking and drift detection

Modules:
  - test_metrics.py: Evaluation metrics (Precision@k, nDCG, F1, latency)
  - conftest.py: Pytest fixtures and configuration
  - test_retrieval.py: Tier 1 retrieval tests
  - test_entity_extraction.py: Tier 2 entity extraction tests
  - test_end_to_end.py: E2E pipeline and integration tests
  - test_runner.py: Main test execution and reporting

Usage:
  pytest tests/                           # Run all tests
  pytest tests/ -m tier1                  # Run Tier 1 only
  pytest tests/ -m tier2                  # Run Tier 2 only
  pytest tests/ -m e2e                    # Run E2E tests
  pytest tests/ -m regression             # Run regression tests
  pytest tests/test_runner.py             # Run with custom reporting
"""

__version__ = "1.0.0"
__author__ = "Group One RAG Team"

from test_metrics import (
    precision_at_k,
    hit_at_one,
    ndcg_at_k,
    mean_reciprocal_rank,
    recall_at_k,
    entity_extraction_f1,
    compute_latency_stats,
    RetrievalResult,
    EntityExtractionResult,
    EvaluationReport,
    RegressionTracker,
    BenchmarkValidator,
    save_report,
    load_report,
)

__all__ = [
    "precision_at_k",
    "hit_at_one",
    "ndcg_at_k",
    "mean_reciprocal_rank",
    "recall_at_k",
    "entity_extraction_f1",
    "compute_latency_stats",
    "RetrievalResult",
    "EntityExtractionResult",
    "EvaluationReport",
    "RegressionTracker",
    "BenchmarkValidator",
    "save_report",
    "load_report",
]
