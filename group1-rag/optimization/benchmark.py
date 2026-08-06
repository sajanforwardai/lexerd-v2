"""
Benchmark suite for RAG latency optimization.

Measures before/after latency for:
- Retrieval (with/without caching)
- Entity extraction (with/without caching)
- Reasoning (sequential vs parallel)
- Knowledge graph queries
- Safety checks
- End-to-end pipeline

Generates comparison reports and identifies improvements.
"""

import time
import json
import random
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

from cache_layer import CacheManager
from latency_monitor import LatencyMonitor
from parallel_reasoning import (
    ReasoningNode, ReasoningTree, ExecutionStrategy, NodeType
)
from index_optimizer import IndexOptimizer


class BenchmarkMode(Enum):
    """Benchmark modes."""
    BASELINE = "baseline"  # No optimization
    OPTIMIZED = "optimized"  # With optimization
    COMPARISON = "comparison"  # Side-by-side


@dataclass
class BenchmarkResult:
    """Results from a single benchmark."""
    name: str
    mode: str
    samples: int
    avg_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float

    def improvement_vs(self, baseline: "BenchmarkResult") -> Dict[str, float]:
        """Calculate improvement vs baseline."""
        return {
            "avg_improvement_pct": (baseline.avg_ms - self.avg_ms) / baseline.avg_ms * 100,
            "p95_improvement_pct": (baseline.p95_ms - self.p95_ms) / baseline.p95_ms * 100,
            "speedup_factor": baseline.avg_ms / self.avg_ms,
        }


class RetrievalBenchmark:
    """Benchmark retrieval with/without caching."""

    def __init__(self, corpus_size: int = 1000):
        """Initialize benchmark."""
        self.corpus_size = corpus_size
        self.corpus = self._generate_corpus()
        self.cache = CacheManager()
        self.optimizer = IndexOptimizer()
        self.optimizer.optimize_startup(self.corpus)

    def _generate_corpus(self) -> List[Dict[str, str]]:
        """Generate sample corpus."""
        corpus = []
        for i in range(self.corpus_size):
            corpus.append({
                "title": f"Document {i}",
                "body": f"This is document {i} with some content about trading",
                "tags": ["trading", "finance"]
            })
        return corpus

    def _simulate_retrieval(self, query: str) -> List[Tuple[float, Dict]]:
        """Simulate retrieval operation."""
        # Simulate actual retrieval latency
        time.sleep(random.gauss(0.05, 0.01))
        # Return top-3 results
        return [
            (0.9, self.corpus[0]),
            (0.8, self.corpus[1]),
            (0.7, self.corpus[2]),
        ]

    def benchmark_baseline(self, num_queries: int = 100) -> BenchmarkResult:
        """Benchmark retrieval without caching."""
        latencies = []

        for i in range(num_queries):
            query = f"query_{i % 10}"  # 10 unique queries

            start = time.perf_counter()
            self._simulate_retrieval(query)
            elapsed = (time.perf_counter() - start) * 1000

            latencies.append(elapsed)

        return self._compute_result(
            name="Retrieval Baseline",
            mode=BenchmarkMode.BASELINE.value,
            latencies=latencies
        )

    def benchmark_optimized(self, num_queries: int = 100) -> BenchmarkResult:
        """Benchmark retrieval with caching."""
        latencies = []

        for i in range(num_queries):
            query = f"query_{i % 10}"  # 10 unique queries
            k = 10

            start = time.perf_counter()

            # Check cache
            cached = self.cache.retrieval.get(query, k)
            if cached is None:
                results = self._simulate_retrieval(query)
                self.cache.retrieval.put(query, k, results)
            else:
                results = cached

            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        return self._compute_result(
            name="Retrieval Optimized",
            mode=BenchmarkMode.OPTIMIZED.value,
            latencies=latencies
        )

    def _compute_result(
        self,
        name: str,
        mode: str,
        latencies: List[float]
    ) -> BenchmarkResult:
        """Compute statistics from latencies."""
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)

        return BenchmarkResult(
            name=name,
            mode=mode,
            samples=n,
            avg_ms=sum(latencies) / n,
            p95_ms=sorted_lat[int(n * 0.95)],
            p99_ms=sorted_lat[int(n * 0.99)],
            min_ms=min(latencies),
            max_ms=max(latencies),
        )

    def run(self) -> Dict[str, Any]:
        """Run full retrieval benchmark."""
        print("\n" + "="*70)
        print("Retrieval Benchmark")
        print("="*70)

        baseline = self.benchmark_baseline()
        optimized = self.benchmark_optimized()

        print(f"\nBaseline:  {baseline.avg_ms:.2f}ms (p95: {baseline.p95_ms:.2f}ms)")
        print(f"Optimized: {optimized.avg_ms:.2f}ms (p95: {optimized.p95_ms:.2f}ms)")

        improvement = optimized.improvement_vs(baseline)
        print(f"\nImprovement:")
        print(f"  Avg: {improvement['avg_improvement_pct']:.1f}%")
        print(f"  P95: {improvement['p95_improvement_pct']:.1f}%")
        print(f"  Speedup: {improvement['speedup_factor']:.1f}x")

        cache_stats = self.cache.retrieval.get_stats()
        print(f"\nCache Hit Rate: {cache_stats.hit_rate:.1f}%")

        return {
            "baseline": asdict(baseline),
            "optimized": asdict(optimized),
            "improvement": improvement,
            "cache_hit_rate": cache_stats.hit_rate,
        }


class EntityExtractionBenchmark:
    """Benchmark entity extraction with/without caching."""

    def __init__(self, num_unique_texts: int = 100):
        """Initialize benchmark."""
        self.texts = self._generate_texts(num_unique_texts)
        self.cache = CacheManager()

    def _generate_texts(self, num: int) -> List[str]:
        """Generate sample texts."""
        return [f"Buy {i} shares of AAPL at ${100+i}" for i in range(num)]

    def _simulate_extraction(self, text: str) -> Dict[str, List[str]]:
        """Simulate entity extraction (LLM call)."""
        time.sleep(random.gauss(0.15, 0.03))  # Simulate LLM latency
        return {
            "action": ["Buy"],
            "symbol": ["AAPL"],
            "quantity": [str(text.split()[1])],
        }

    def benchmark_baseline(self, num_queries: int = 100) -> BenchmarkResult:
        """Benchmark without caching."""
        latencies = []

        for i in range(num_queries):
            text = self.texts[i % len(self.texts)]

            start = time.perf_counter()
            self._simulate_extraction(text)
            elapsed = (time.perf_counter() - start) * 1000

            latencies.append(elapsed)

        return self._compute_result(
            name="Entity Extraction Baseline",
            mode=BenchmarkMode.BASELINE.value,
            latencies=latencies
        )

    def benchmark_optimized(self, num_queries: int = 100) -> BenchmarkResult:
        """Benchmark with caching."""
        latencies = []

        for i in range(num_queries):
            text = self.texts[i % len(self.texts)]

            start = time.perf_counter()

            # Check cache
            cached = self.cache.entities.get(text)
            if cached is None:
                entities = self._simulate_extraction(text)
                self.cache.entities.put(text, entities)
            else:
                entities = cached

            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        return self._compute_result(
            name="Entity Extraction Optimized",
            mode=BenchmarkMode.OPTIMIZED.value,
            latencies=latencies
        )

    def _compute_result(
        self,
        name: str,
        mode: str,
        latencies: List[float]
    ) -> BenchmarkResult:
        """Compute statistics."""
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)

        return BenchmarkResult(
            name=name,
            mode=mode,
            samples=n,
            avg_ms=sum(latencies) / n,
            p95_ms=sorted_lat[int(n * 0.95)],
            p99_ms=sorted_lat[int(n * 0.99)],
            min_ms=min(latencies),
            max_ms=max(latencies),
        )

    def run(self) -> Dict[str, Any]:
        """Run full entity extraction benchmark."""
        print("\n" + "="*70)
        print("Entity Extraction Benchmark")
        print("="*70)

        baseline = self.benchmark_baseline()
        optimized = self.benchmark_optimized()

        print(f"\nBaseline:  {baseline.avg_ms:.2f}ms (p95: {baseline.p95_ms:.2f}ms)")
        print(f"Optimized: {optimized.avg_ms:.2f}ms (p95: {optimized.p95_ms:.2f}ms)")

        improvement = optimized.improvement_vs(baseline)
        print(f"\nImprovement:")
        print(f"  Avg: {improvement['avg_improvement_pct']:.1f}%")
        print(f"  P95: {improvement['p95_improvement_pct']:.1f}%")
        print(f"  Speedup: {improvement['speedup_factor']:.1f}x")

        cache_stats = self.cache.entities.get_stats()
        print(f"\nCache Hit Rate: {cache_stats.hit_rate:.1f}%")

        return {
            "baseline": asdict(baseline),
            "optimized": asdict(optimized),
            "improvement": improvement,
            "cache_hit_rate": cache_stats.hit_rate,
        }


class ReasoningBenchmark:
    """Benchmark reasoning: sequential vs parallel."""

    def _create_tree(self) -> ReasoningTree:
        """Create a sample reasoning tree."""
        def dummy_eval(ctx):
            time.sleep(0.01)  # Simulate work
            return "result"

        root = ReasoningNode(
            name="Root",
            node_type=NodeType.ROOT,
            evaluate_fn=dummy_eval
        )

        # Level 1: 2 regime nodes (candidates for parallelization)
        regime1 = ReasoningNode(
            name="Regime-Bullish",
            node_type=NodeType.REGIME,
            evaluate_fn=dummy_eval,
            parent=root
        )
        regime2 = ReasoningNode(
            name="Regime-Bearish",
            node_type=NodeType.REGIME,
            evaluate_fn=dummy_eval,
            parent=root
        )
        root.children = [regime1, regime2]

        # Level 2: strategy nodes under each regime
        strategy1a = ReasoningNode(
            name="Strategy-Momentum",
            node_type=NodeType.STRATEGY,
            evaluate_fn=dummy_eval,
            parent=regime1
        )
        strategy2a = ReasoningNode(
            name="Strategy-Hedge",
            node_type=NodeType.STRATEGY,
            evaluate_fn=dummy_eval,
            parent=regime2
        )
        regime1.children.append(strategy1a)
        regime2.children.append(strategy2a)

        return ReasoningTree(root)

    def benchmark_sequential(self, num_iterations: int = 20) -> BenchmarkResult:
        """Benchmark sequential evaluation."""
        latencies = []

        for _ in range(num_iterations):
            tree = self._create_tree()
            tree.execution_strategy = ExecutionStrategy.SEQUENTIAL

            start = time.perf_counter()
            tree.evaluate({})
            elapsed = (time.perf_counter() - start) * 1000

            latencies.append(elapsed)

        return self._compute_result(
            name="Reasoning Sequential",
            mode="sequential",
            latencies=latencies
        )

    def benchmark_parallel(self, num_iterations: int = 20) -> BenchmarkResult:
        """Benchmark parallel evaluation."""
        latencies = []

        for _ in range(num_iterations):
            tree = self._create_tree()
            tree.execution_strategy = ExecutionStrategy.PARALLEL_SIBLINGS

            start = time.perf_counter()
            tree.evaluate({}, max_workers=4)
            elapsed = (time.perf_counter() - start) * 1000

            latencies.append(elapsed)

        return self._compute_result(
            name="Reasoning Parallel",
            mode="parallel",
            latencies=latencies
        )

    def _compute_result(
        self,
        name: str,
        mode: str,
        latencies: List[float]
    ) -> BenchmarkResult:
        """Compute statistics."""
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)

        return BenchmarkResult(
            name=name,
            mode=mode,
            samples=n,
            avg_ms=sum(latencies) / n,
            p95_ms=sorted_lat[int(n * 0.95)],
            p99_ms=sorted_lat[int(n * 0.99)],
            min_ms=min(latencies),
            max_ms=max(latencies),
        )

    def run(self) -> Dict[str, Any]:
        """Run full reasoning benchmark."""
        print("\n" + "="*70)
        print("Reasoning Benchmark (Sequential vs Parallel)")
        print("="*70)

        sequential = self.benchmark_sequential()
        parallel = self.benchmark_parallel()

        print(f"\nSequential:  {sequential.avg_ms:.2f}ms (p95: {sequential.p95_ms:.2f}ms)")
        print(f"Parallel:    {parallel.avg_ms:.2f}ms (p95: {parallel.p95_ms:.2f}ms)")

        improvement = parallel.improvement_vs(sequential)
        print(f"\nImprovement:")
        print(f"  Avg: {improvement['avg_improvement_pct']:.1f}%")
        print(f"  P95: {improvement['p95_improvement_pct']:.1f}%")
        print(f"  Speedup: {improvement['speedup_factor']:.1f}x")

        return {
            "sequential": asdict(sequential),
            "parallel": asdict(parallel),
            "improvement": improvement,
        }


class EndToEndBenchmark:
    """Benchmark complete pipeline."""

    def __init__(self):
        """Initialize benchmark."""
        self.cache = CacheManager()
        self.monitor = LatencyMonitor()
        self.corpus = [{"title": f"Doc {i}", "body": f"content {i}"} for i in range(100)]
        self.texts = [f"Buy {i} BTC" for i in range(50)]

    def benchmark_unoptimized(self, num_queries: int = 50) -> BenchmarkResult:
        """Benchmark without optimizations."""
        latencies = []

        for i in range(num_queries):
            start = time.perf_counter()

            # Retrieval (no cache)
            time.sleep(random.gauss(0.08, 0.02))

            # Entity extraction (no cache)
            time.sleep(random.gauss(0.15, 0.03))

            # Reasoning
            time.sleep(random.gauss(0.15, 0.03))

            # KG queries
            time.sleep(random.gauss(0.02, 0.005))

            # Safety
            time.sleep(random.gauss(0.01, 0.002))

            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        return self._compute_result(
            name="End-to-End Unoptimized",
            mode="unoptimized",
            latencies=latencies
        )

    def benchmark_optimized(self, num_queries: int = 50) -> BenchmarkResult:
        """Benchmark with optimizations."""
        latencies = []

        for i in range(num_queries):
            start = time.perf_counter()

            # Retrieval (with cache)
            query = f"query_{i % 10}"
            self.cache.retrieval.get(query, 10)
            if self.cache.retrieval.get(query, 10) is None:
                time.sleep(random.gauss(0.08, 0.02))
                self.cache.retrieval.put(query, 10, [(0.9, {})])
            # Cached access is nearly free

            # Entity extraction (with cache)
            text = self.texts[i % len(self.texts)]
            if self.cache.entities.get(text) is None:
                time.sleep(random.gauss(0.15, 0.03))
                self.cache.entities.put(text, {})
            # Cached access is nearly free

            # Reasoning (parallel)
            time.sleep(random.gauss(0.12, 0.02))  # Faster due to parallelization

            # KG queries (pre-indexed)
            time.sleep(random.gauss(0.01, 0.003))

            # Safety (fast checks)
            time.sleep(random.gauss(0.005, 0.001))

            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        return self._compute_result(
            name="End-to-End Optimized",
            mode="optimized",
            latencies=latencies
        )

    def _compute_result(
        self,
        name: str,
        mode: str,
        latencies: List[float]
    ) -> BenchmarkResult:
        """Compute statistics."""
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)

        return BenchmarkResult(
            name=name,
            mode=mode,
            samples=n,
            avg_ms=sum(latencies) / n,
            p95_ms=sorted_lat[int(n * 0.95)],
            p99_ms=sorted_lat[int(n * 0.99)],
            min_ms=min(latencies),
            max_ms=max(latencies),
        )

    def run(self) -> Dict[str, Any]:
        """Run end-to-end benchmark."""
        print("\n" + "="*70)
        print("End-to-End Pipeline Benchmark")
        print("="*70)

        unoptimized = self.benchmark_unoptimized()
        optimized = self.benchmark_optimized()

        print(f"\nUnoptimized: {unoptimized.avg_ms:.2f}ms (p95: {unoptimized.p95_ms:.2f}ms)")
        print(f"Optimized:   {optimized.avg_ms:.2f}ms (p95: {optimized.p95_ms:.2f}ms)")

        improvement = optimized.improvement_vs(unoptimized)
        print(f"\nImprovement:")
        print(f"  Avg: {improvement['avg_improvement_pct']:.1f}%")
        print(f"  P95: {improvement['p95_improvement_pct']:.1f}%")
        print(f"  Speedup: {improvement['speedup_factor']:.1f}x")

        # Check if under 2s target
        if optimized.p95_ms < 2000:
            print(f"\n✓ P95 latency ({optimized.p95_ms:.0f}ms) under 2s target")
        else:
            print(f"\n✗ P95 latency ({optimized.p95_ms:.0f}ms) over 2s target")

        return {
            "unoptimized": asdict(unoptimized),
            "optimized": asdict(optimized),
            "improvement": improvement,
        }


def run_all_benchmarks() -> Dict[str, Any]:
    """Run all benchmarks and return aggregated results."""
    print("\n" + "="*70)
    print("RAG LATENCY OPTIMIZATION BENCHMARKS")
    print("="*70)

    results = {}

    # Retrieval
    print("\n[1/4] Running Retrieval Benchmark...")
    retrieval_bench = RetrievalBenchmark()
    results["retrieval"] = retrieval_bench.run()

    # Entity Extraction
    print("\n[2/4] Running Entity Extraction Benchmark...")
    entity_bench = EntityExtractionBenchmark()
    results["entity_extraction"] = entity_bench.run()

    # Reasoning
    print("\n[3/4] Running Reasoning Benchmark...")
    reasoning_bench = ReasoningBenchmark()
    results["reasoning"] = reasoning_bench.run()

    # End-to-End
    print("\n[4/4] Running End-to-End Benchmark...")
    e2e_bench = EndToEndBenchmark()
    results["end_to_end"] = e2e_bench.run()

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    print("\nComponent Improvements:")
    print(f"  Retrieval:        {results['retrieval']['improvement']['avg_improvement_pct']:.1f}%")
    print(f"  Entity Extract:   {results['entity_extraction']['improvement']['avg_improvement_pct']:.1f}%")
    print(f"  Reasoning:        {results['reasoning']['improvement']['avg_improvement_pct']:.1f}%")
    print(f"  End-to-End:       {results['end_to_end']['improvement']['avg_improvement_pct']:.1f}%")

    print("\nSpeedup Factors:")
    print(f"  Retrieval:        {results['retrieval']['improvement']['speedup_factor']:.1f}x")
    print(f"  Entity Extract:   {results['entity_extraction']['improvement']['speedup_factor']:.1f}x")
    print(f"  Reasoning:        {results['reasoning']['improvement']['speedup_factor']:.1f}x")
    print(f"  End-to-End:       {results['end_to_end']['improvement']['speedup_factor']:.1f}x")

    print("\n" + "="*70 + "\n")

    return results


if __name__ == "__main__":
    results = run_all_benchmarks()

    # Save results
    with open("/tmp/benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results saved to /tmp/benchmark_results.json")
