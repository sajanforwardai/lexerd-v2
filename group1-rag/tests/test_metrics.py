"""test_metrics.py — Evaluation metrics for Group One Trading RAG system.

Implements comprehensive evaluation suite:
  1. Retrieval metrics: Precision@10, Hit@1, nDCG@10, MRR
  2. Entity extraction: F1, precision, recall
  3. Latency: p50, p99, mean
  4. Regression tracking: baseline snapshots and drift detection

Target benchmarks:
  - Tier 1 precision@10 ≥ 0.50
  - Tier 2 entity F1 ≥ 0.85
  - Tier 1 latency ≤ 100ms
  - Tier 2 latency ≤ 500ms
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---- Evaluation Metrics ----

def precision_at_k(retrieved_indices: list[int], relevant_indices: set[int], k: int = 10) -> float:
    """Precision@k: fraction of top-k results that are relevant.

    Args:
        retrieved_indices: List of retrieved document indices (in order)
        relevant_indices: Set of document indices known to be relevant
        k: Cutoff (default 10)

    Returns:
        Precision@k in [0, 1]
    """
    if not retrieved_indices:
        return 0.0
    top_k = set(retrieved_indices[:k])
    hits = len(top_k & relevant_indices)
    return hits / k if k > 0 else 0.0


def hit_at_one(retrieved_indices: list[int], relevant_indices: set[int]) -> bool:
    """Hit@1: whether the top-1 result is relevant.

    Args:
        retrieved_indices: List of retrieved document indices
        relevant_indices: Set of relevant indices

    Returns:
        True if top-1 is relevant, else False
    """
    return bool(retrieved_indices and retrieved_indices[0] in relevant_indices)


def ndcg_at_k(retrieved_indices: list[int], relevant_indices: set[int], k: int = 10) -> float:
    """Normalized Discounted Cumulative Gain@k.

    DCG@k = sum_{i=1}^k rel(i) / log2(i+1)
    nDCG@k = DCG@k / IDCG@k (ideal ranking)

    Args:
        retrieved_indices: Retrieved document indices
        relevant_indices: Relevant document indices
        k: Cutoff

    Returns:
        nDCG@k in [0, 1]
    """
    if not retrieved_indices or not relevant_indices:
        return 0.0

    # DCG: relevance is 1 if retrieved doc is relevant, 0 otherwise
    dcg = 0.0
    for i, doc_idx in enumerate(retrieved_indices[:k]):
        rel = 1.0 if doc_idx in relevant_indices else 0.0
        dcg += rel / np.log2(i + 2)  # i+2 because log2(1) = 0

    # Ideal DCG: first |relevant| results are all relevant
    ideal_hits = min(len(relevant_indices), k)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_hits))

    return dcg / idcg if idcg > 0 else 0.0


def mean_reciprocal_rank(retrieved_indices: list[int], relevant_indices: set[int]) -> float:
    """Mean Reciprocal Rank: 1 / position of first relevant result.

    Args:
        retrieved_indices: Retrieved document indices
        relevant_indices: Relevant document indices

    Returns:
        MRR in [0, 1], 0 if no relevant result found
    """
    for i, doc_idx in enumerate(retrieved_indices):
        if doc_idx in relevant_indices:
            return 1.0 / (i + 1)
    return 0.0


def recall_at_k(retrieved_indices: list[int], relevant_indices: set[int], k: int = 10) -> float:
    """Recall@k: fraction of all relevant items that appear in top-k.

    Args:
        retrieved_indices: Retrieved document indices
        relevant_indices: All relevant document indices
        k: Cutoff

    Returns:
        Recall@k in [0, 1]
    """
    if not relevant_indices:
        return 0.0
    top_k = set(retrieved_indices[:k])
    hits = len(top_k & relevant_indices)
    return hits / len(relevant_indices)


# ---- Entity Extraction Metrics ----

def entity_extraction_f1(
    predicted_entities: set[str],
    ground_truth_entities: set[str]
) -> tuple[float, float, float]:
    """Entity extraction evaluation: F1, precision, recall.

    Assumes exact string matching between predicted and ground truth.

    Args:
        predicted_entities: Set of extracted entity strings
        ground_truth_entities: Set of true entity strings

    Returns:
        (f1, precision, recall) tuple, each in [0, 1]
    """
    if not ground_truth_entities and not predicted_entities:
        return 1.0, 1.0, 1.0

    if not ground_truth_entities:
        precision = 0.0
    else:
        precision = len(predicted_entities & ground_truth_entities) / len(predicted_entities) \
            if predicted_entities else 0.0

    recall = len(predicted_entities & ground_truth_entities) / len(ground_truth_entities) \
        if ground_truth_entities else 0.0

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return f1, precision, recall


# ---- Latency Measurement ----

@dataclass
class LatencyStats:
    """Statistics for latency measurements."""
    mean_ms: float
    p50_ms: float
    p75_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    count: int


def compute_latency_stats(latencies_ms: list[float]) -> LatencyStats:
    """Compute latency percentiles and statistics.

    Args:
        latencies_ms: List of latency measurements in milliseconds

    Returns:
        LatencyStats dataclass with aggregated metrics
    """
    if not latencies_ms:
        return LatencyStats(
            mean_ms=0.0, p50_ms=0.0, p75_ms=0.0, p99_ms=0.0,
            min_ms=0.0, max_ms=0.0, count=0
        )

    sorted_lats = sorted(latencies_ms)
    return LatencyStats(
        mean_ms=float(np.mean(sorted_lats)),
        p50_ms=float(np.percentile(sorted_lats, 50)),
        p75_ms=float(np.percentile(sorted_lats, 75)),
        p99_ms=float(np.percentile(sorted_lats, 99)),
        min_ms=float(np.min(sorted_lats)),
        max_ms=float(np.max(sorted_lats)),
        count=len(sorted_lats)
    )


# ---- Result Aggregation & Tracking ----

@dataclass
class RetrievalResult:
    """Single retrieval evaluation result."""
    query_id: int
    query: str
    precision_at_10: float
    hit_at_1: bool
    ndcg_at_10: float
    mrr: float
    recall_at_10: float
    latency_ms: float
    tier: int


@dataclass
class EntityExtractionResult:
    """Single entity extraction result."""
    query_id: int
    query: str
    f1: float
    precision: float
    recall: float
    latency_ms: float
    tier: int


@dataclass
class EvaluationReport:
    """Aggregated evaluation results."""
    timestamp: str
    total_queries: int
    tier_1_results: list[RetrievalResult] = field(default_factory=list)
    tier_2_results: list[RetrievalResult] = field(default_factory=list)
    entity_results: list[EntityExtractionResult] = field(default_factory=list)

    # Aggregated metrics
    avg_precision_at_10: float = 0.0
    hit_at_1_rate: float = 0.0
    avg_ndcg_at_10: float = 0.0
    avg_mrr: float = 0.0
    avg_recall_at_10: float = 0.0

    # Latency stats by tier
    tier_1_latency: Optional[LatencyStats] = None
    tier_2_latency: Optional[LatencyStats] = None

    # Entity extraction aggregates
    entity_avg_f1: float = 0.0
    entity_avg_precision: float = 0.0
    entity_avg_recall: float = 0.0

    def compute_aggregates(self) -> None:
        """Compute aggregate metrics from individual results."""
        all_results = self.tier_1_results + self.tier_2_results

        if all_results:
            self.avg_precision_at_10 = np.mean([r.precision_at_10 for r in all_results])
            self.hit_at_1_rate = np.mean([float(r.hit_at_1) for r in all_results])
            self.avg_ndcg_at_10 = np.mean([r.ndcg_at_10 for r in all_results])
            self.avg_mrr = np.mean([r.mrr for r in all_results])
            self.avg_recall_at_10 = np.mean([r.recall_at_10 for r in all_results])

        # Tier-specific latency
        if self.tier_1_results:
            t1_lats = [r.latency_ms for r in self.tier_1_results]
            self.tier_1_latency = compute_latency_stats(t1_lats)

        if self.tier_2_results:
            t2_lats = [r.latency_ms for r in self.tier_2_results]
            self.tier_2_latency = compute_latency_stats(t2_lats)

        # Entity extraction aggregates
        if self.entity_results:
            self.entity_avg_f1 = np.mean([r.f1 for r in self.entity_results])
            self.entity_avg_precision = np.mean([r.precision for r in self.entity_results])
            self.entity_avg_recall = np.mean([r.recall for r in self.entity_results])

    def to_dict(self) -> dict:
        """Convert report to dictionary for JSON serialization."""
        d = asdict(self)
        # Convert LatencyStats to dict
        if self.tier_1_latency:
            d['tier_1_latency'] = asdict(self.tier_1_latency)
        if self.tier_2_latency:
            d['tier_2_latency'] = asdict(self.tier_2_latency)
        # Convert results to dicts
        d['tier_1_results'] = [asdict(r) for r in self.tier_1_results]
        d['tier_2_results'] = [asdict(r) for r in self.tier_2_results]
        d['entity_results'] = [asdict(r) for r in self.entity_results]
        return d


# ---- Regression Testing ----

class RegressionTracker:
    """Track performance baselines and detect regressions."""

    def __init__(self, baseline_path: Optional[Path] = None):
        """Initialize regression tracker.

        Args:
            baseline_path: Path to baseline results JSON (optional)
        """
        self.baseline_path = baseline_path
        self.baseline: Optional[dict] = None
        if baseline_path and baseline_path.exists():
            with open(baseline_path) as f:
                self.baseline = json.load(f)

    def check_regression(
        self,
        current_report: EvaluationReport,
        threshold_percent: float = 5.0
    ) -> dict[str, Any]:
        """Check if current results regress from baseline.

        Args:
            current_report: Current evaluation report
            threshold_percent: Regression threshold as percentage (default 5%)

        Returns:
            Dict with regression analysis:
            {
                "passed": bool,
                "regressions": [{"metric": ..., "baseline": ..., "current": ..., "change_pct": ...}],
                "improvements": [...]
            }
        """
        if not self.baseline:
            return {"passed": True, "message": "No baseline found, skipping regression check"}

        regressions = []
        improvements = []

        baseline_metrics = self.baseline.get("metrics", {})
        current_metrics = {
            "precision_at_10": current_report.avg_precision_at_10,
            "ndcg_at_10": current_report.avg_ndcg_at_10,
            "hit_at_1_rate": current_report.hit_at_1_rate,
            "mrr": current_report.avg_mrr,
            "entity_f1": current_report.entity_avg_f1,
            "tier_1_latency_p99": current_report.tier_1_latency.p99_ms if current_report.tier_1_latency else None,
            "tier_2_latency_p99": current_report.tier_2_latency.p99_ms if current_report.tier_2_latency else None,
        }

        for metric, current_val in current_metrics.items():
            if current_val is None:
                continue

            baseline_val = baseline_metrics.get(metric)
            if baseline_val is None:
                continue

            if baseline_val == 0:
                change_pct = 0.0 if current_val == 0 else 100.0
            else:
                change_pct = ((current_val - baseline_val) / abs(baseline_val)) * 100

            # For latency, lower is better; for others, higher is better
            is_latency = "latency" in metric
            regressed = (change_pct > threshold_percent and not is_latency) or \
                       (change_pct < -threshold_percent and is_latency)

            if regressed:
                regressions.append({
                    "metric": metric,
                    "baseline": baseline_val,
                    "current": current_val,
                    "change_pct": change_pct,
                    "threshold_pct": threshold_percent
                })
            elif change_pct * (-1 if is_latency else 1) > threshold_percent:
                improvements.append({
                    "metric": metric,
                    "baseline": baseline_val,
                    "current": current_val,
                    "change_pct": change_pct,
                })

        return {
            "passed": len(regressions) == 0,
            "regressions": regressions,
            "improvements": improvements
        }

    def save_baseline(self, report: EvaluationReport, path: Path) -> None:
        """Save current report as baseline for future regression checks.

        Args:
            report: Evaluation report to save as baseline
            path: Output path
        """
        baseline_data = {
            "timestamp": report.timestamp,
            "metrics": {
                "precision_at_10": report.avg_precision_at_10,
                "ndcg_at_10": report.avg_ndcg_at_10,
                "hit_at_1_rate": report.hit_at_1_rate,
                "mrr": report.avg_mrr,
                "entity_f1": report.entity_avg_f1,
                "entity_precision": report.entity_avg_precision,
                "entity_recall": report.entity_avg_recall,
            }
        }

        if report.tier_1_latency:
            baseline_data["metrics"]["tier_1_latency_p50"] = report.tier_1_latency.p50_ms
            baseline_data["metrics"]["tier_1_latency_p99"] = report.tier_1_latency.p99_ms

        if report.tier_2_latency:
            baseline_data["metrics"]["tier_2_latency_p50"] = report.tier_2_latency.p50_ms
            baseline_data["metrics"]["tier_2_latency_p99"] = report.tier_2_latency.p99_ms

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(baseline_data, f, indent=2)

        logger.info(f"Saved baseline to {path}")


# ---- Benchmark Validation ----

@dataclass
class BenchmarkTarget:
    """Target performance benchmarks."""
    metric: str
    tier: Optional[int]  # None = applies to all tiers
    target: float
    direction: str  # "higher" or "lower"


class BenchmarkValidator:
    """Validate results against target benchmarks."""

    # Default benchmarks from spec
    DEFAULT_BENCHMARKS = [
        BenchmarkTarget("precision_at_10", 1, 0.50, "higher"),
        BenchmarkTarget("entity_f1", 2, 0.85, "higher"),
        BenchmarkTarget("latency_p99", 1, 100.0, "lower"),
        BenchmarkTarget("latency_p99", 2, 500.0, "lower"),
    ]

    def __init__(self, benchmarks: Optional[list[BenchmarkTarget]] = None):
        """Initialize validator with benchmarks.

        Args:
            benchmarks: List of BenchmarkTarget objects (default: DEFAULT_BENCHMARKS)
        """
        self.benchmarks = benchmarks or self.DEFAULT_BENCHMARKS

    def validate(self, report: EvaluationReport) -> dict[str, Any]:
        """Validate report against benchmarks.

        Args:
            report: Evaluation report

        Returns:
            {
                "passed": bool,
                "results": [
                    {"benchmark": ..., "target": ..., "actual": ..., "passed": ..., "message": ...},
                    ...
                ]
            }
        """
        results = []

        for bench in self.benchmarks:
            actual = None
            message = ""

            if bench.metric == "precision_at_10" and bench.tier == 1:
                actual = report.avg_precision_at_10
            elif bench.metric == "entity_f1" and bench.tier == 2:
                actual = report.entity_avg_f1
            elif bench.metric == "latency_p99" and bench.tier == 1:
                actual = report.tier_1_latency.p99_ms if report.tier_1_latency else None
            elif bench.metric == "latency_p99" and bench.tier == 2:
                actual = report.tier_2_latency.p99_ms if report.tier_2_latency else None

            if actual is None:
                results.append({
                    "benchmark": f"{bench.metric} (tier {bench.tier})",
                    "target": bench.target,
                    "actual": None,
                    "passed": False,
                    "message": "No data available"
                })
                continue

            if bench.direction == "higher":
                passed = actual >= bench.target
                message = f"{actual:.4f} {'≥' if passed else '<'} {bench.target}"
            else:  # lower
                passed = actual <= bench.target
                message = f"{actual:.2f}ms {'≤' if passed else '>'} {bench.target}ms"

            results.append({
                "benchmark": f"{bench.metric} (tier {bench.tier})",
                "target": bench.target,
                "actual": actual,
                "passed": passed,
                "message": message
            })

        all_passed = all(r["passed"] for r in results)
        return {
            "passed": all_passed,
            "results": results
        }


# ---- Utility ----

def save_report(report: EvaluationReport, path: Path) -> None:
    """Save evaluation report to JSON file.

    Args:
        report: Evaluation report
        path: Output path
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    logger.info(f"Saved report to {path}")


def load_report(path: Path) -> dict:
    """Load evaluation report from JSON file.

    Args:
        path: Path to report JSON

    Returns:
        Report dictionary
    """
    with open(path) as f:
        return json.load(f)
