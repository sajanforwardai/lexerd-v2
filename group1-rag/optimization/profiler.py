"""
Profiler for Group One Trading RAG system.

Instruments each component (retrieval, entity extraction, reasoning, KG, safety)
to identify latency bottlenecks and measure per-component performance.
"""

import cProfile
import pstats
import io
import time
import json
from contextlib import contextmanager
from typing import Dict, List, Any, Callable
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class ComponentMetrics:
    """Metrics for a single component."""
    name: str
    call_count: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p95_time_ms: float
    p99_time_ms: float


class LatencyProfiler:
    """
    Profiles RAG system components to identify bottlenecks.

    Tracks per-component latency, call counts, and statistical percentiles.
    Designed to measure production-like workloads with minimal overhead.
    """

    def __init__(self, name: str = "RAG System"):
        """Initialize profiler."""
        self.name = name
        self.measurements: Dict[str, List[float]] = defaultdict(list)
        self.call_counts: Dict[str, int] = defaultdict(int)
        self.active_timers: Dict[str, float] = {}

    @contextmanager
    def timer(self, component_name: str):
        """Context manager for timing a component."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.measurements[component_name].append(elapsed_ms)
            self.call_counts[component_name] += 1

    def start_timer(self, component_name: str):
        """Manually start a timer (paired with stop_timer)."""
        self.active_timers[component_name] = time.perf_counter()

    def stop_timer(self, component_name: str):
        """Manually stop a timer."""
        if component_name not in self.active_timers:
            raise ValueError(f"Timer for {component_name} was not started")

        elapsed_ms = (time.perf_counter() - self.active_timers[component_name]) * 1000
        del self.active_timers[component_name]
        self.measurements[component_name].append(elapsed_ms)
        self.call_counts[component_name] += 1

    def get_metrics(self, component_name: str) -> ComponentMetrics:
        """Get metrics for a component."""
        times = self.measurements.get(component_name, [])

        if not times:
            raise ValueError(f"No measurements for {component_name}")

        times_sorted = sorted(times)
        n = len(times_sorted)

        return ComponentMetrics(
            name=component_name,
            call_count=self.call_counts[component_name],
            total_time_ms=sum(times),
            avg_time_ms=sum(times) / n,
            min_time_ms=min(times),
            max_time_ms=max(times),
            p95_time_ms=times_sorted[int(n * 0.95)],
            p99_time_ms=times_sorted[int(n * 0.99)],
        )

    def get_all_metrics(self) -> Dict[str, ComponentMetrics]:
        """Get metrics for all measured components."""
        return {
            name: self.get_metrics(name)
            for name in self.measurements.keys()
        }

    def reset(self):
        """Reset all measurements."""
        self.measurements.clear()
        self.call_counts.clear()
        self.active_timers.clear()

    def report(self, include_raw: bool = False) -> str:
        """Generate a formatted latency report."""
        if not self.measurements:
            return "No measurements recorded."

        metrics = self.get_all_metrics()

        # Sort by total time descending
        sorted_metrics = sorted(
            metrics.values(),
            key=lambda m: m.total_time_ms,
            reverse=True
        )

        lines = [f"\n{'='*80}"]
        lines.append(f"Latency Profile: {self.name}")
        lines.append(f"{'='*80}\n")

        # Summary table
        lines.append(f"{'Component':<30} {'Calls':>8} {'Total (ms)':>12} "
                    f"{'Avg (ms)':>10} {'Min':>8} {'Max':>8} {'P95':>8} {'P99':>8}")
        lines.append("-" * 96)

        total_time = sum(m.total_time_ms for m in sorted_metrics)
        for metric in sorted_metrics:
            pct = (metric.total_time_ms / total_time * 100) if total_time > 0 else 0
            lines.append(
                f"{metric.name:<30} {metric.call_count:>8} "
                f"{metric.total_time_ms:>11.2f}  "
                f"{metric.avg_time_ms:>9.2f} "
                f"{metric.min_time_ms:>7.2f} "
                f"{metric.max_time_ms:>7.2f} "
                f"{metric.p95_time_ms:>7.2f} "
                f"{metric.p99_time_ms:>7.2f}  "
                f"({pct:.1f}%)"
            )

        lines.append("-" * 96)
        lines.append(f"{'TOTAL':<30} {sum(m.call_count for m in sorted_metrics):>8} "
                    f"{total_time:>11.2f} ms")
        lines.append(f"{'='*80}\n")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary (for JSON serialization)."""
        metrics = self.get_all_metrics()
        return {
            name: asdict(metric)
            for name, metric in metrics.items()
        }

    def to_json(self) -> str:
        """Export metrics as JSON."""
        return json.dumps(self.to_dict(), indent=2)

    def bottleneck_analysis(self) -> Dict[str, Any]:
        """
        Identify optimization opportunities.

        Returns analysis of bottlenecks, opportunities, and recommendations.
        """
        if not self.measurements:
            return {}

        metrics = self.get_all_metrics()
        total_time = sum(m.total_time_ms for m in metrics.values())

        # Components with high variance (opportunity for caching)
        high_variance = {}
        for metric in metrics.values():
            if metric.avg_time_ms > 0:
                cv = (metric.max_time_ms - metric.min_time_ms) / metric.avg_time_ms
                if cv > 2.0:  # Coefficient of variation > 2
                    high_variance[metric.name] = {
                        "variance": cv,
                        "opportunity": "High variance suggests caching could help"
                    }

        # Hot path components (>20% of total time)
        hot_path = {}
        for metric in metrics.values():
            pct = (metric.total_time_ms / total_time) * 100
            if pct > 20:
                hot_path[metric.name] = {
                    "percentage": pct,
                    "opportunity": "Focus optimization effort here"
                }

        # Frequently called components (opportunity for batching)
        high_frequency = {}
        avg_call_count = sum(m.call_count for m in metrics.values()) / len(metrics)
        for metric in metrics.values():
            if metric.call_count > avg_call_count * 1.5:
                high_frequency[metric.name] = {
                    "call_count": metric.call_count,
                    "opportunity": "Batching or caching could reduce overhead"
                }

        return {
            "total_time_ms": total_time,
            "component_count": len(metrics),
            "high_variance_candidates": high_variance,
            "hot_path_candidates": hot_path,
            "high_frequency_candidates": high_frequency,
        }


class CPUProfiler:
    """
    CPU-level profiler using cProfile.

    For detailed function-level profiling. Output can be large; use for
    targeted analysis of hot functions.
    """

    def __init__(self):
        """Initialize CPU profiler."""
        self.profiler = cProfile.Profile()
        self.is_running = False

    def start(self):
        """Start CPU profiling."""
        self.profiler.enable()
        self.is_running = True

    def stop(self):
        """Stop CPU profiling."""
        self.profiler.disable()
        self.is_running = False

    def report(self, sort_by: str = "cumulative", limit: int = 20) -> str:
        """Generate CPU profile report."""
        if self.is_running:
            self.stop()

        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s)
        ps.sort_stats(sort_by)
        ps.print_stats(limit)
        return s.getvalue()

    def reset(self):
        """Reset profiler."""
        self.profiler = cProfile.Profile()
        self.is_running = False


class MemoryProfiler:
    """
    Simple memory usage tracker.

    Tracks peak memory and allocation size for components.
    """

    def __init__(self):
        """Initialize memory profiler."""
        self.snapshots = {}

    def snapshot(self, name: str, data_size_bytes: int):
        """Record memory snapshot."""
        self.snapshots[name] = {
            "size_bytes": data_size_bytes,
            "size_mb": data_size_bytes / (1024 * 1024),
        }

    def report(self) -> str:
        """Generate memory report."""
        if not self.snapshots:
            return "No memory measurements recorded."

        total_bytes = sum(s["size_bytes"] for s in self.snapshots.values())

        lines = [f"\n{'='*60}"]
        lines.append("Memory Profile")
        lines.append(f"{'='*60}\n")
        lines.append(f"{'Component':<30} {'Size (MB)':>15}")
        lines.append("-" * 48)

        for name, snap in sorted(
            self.snapshots.items(),
            key=lambda x: x[1]["size_bytes"],
            reverse=True
        ):
            lines.append(f"{name:<30} {snap['size_mb']:>14.2f}")

        lines.append("-" * 48)
        lines.append(f"{'TOTAL':<30} {total_bytes / (1024*1024):>14.2f} MB")
        lines.append(f"{'='*60}\n")

        return "\n".join(lines)


def profile_function(profiler: LatencyProfiler, component_name: str) -> Callable:
    """
    Decorator to automatically profile a function.

    Usage:
        @profile_function(profiler, "my_component")
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            with profiler.timer(component_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# Example usage and testing
# ============================================================================

if __name__ == "__main__":
    # Demonstrate profiler
    profiler = LatencyProfiler("Example RAG Profile")

    # Simulate component measurements
    import random

    # Retrieval (varies a lot - caching opportunity)
    for _ in range(100):
        profiler.measurements["retrieval"].append(random.gauss(75, 25))
    profiler.call_counts["retrieval"] = 100

    # Entity extraction (consistent high cost)
    for _ in range(50):
        profiler.measurements["entity_extraction"].append(random.gauss(120, 15))
    profiler.call_counts["entity_extraction"] = 50

    # Reasoning (hot path)
    for _ in range(100):
        profiler.measurements["reasoning"].append(random.gauss(150, 30))
    profiler.call_counts["reasoning"] = 100

    # KG queries (fast, frequent)
    for _ in range(500):
        profiler.measurements["kg_queries"].append(random.gauss(15, 5))
    profiler.call_counts["kg_queries"] = 500

    # Safety checks (fast)
    for _ in range(100):
        profiler.measurements["safety_checks"].append(random.gauss(8, 2))
    profiler.call_counts["safety_checks"] = 100

    print(profiler.report())
    print("\nBottleneck Analysis:")
    import json
    print(json.dumps(profiler.bottleneck_analysis(), indent=2))

    # Memory profile example
    mem_profiler = MemoryProfiler()
    mem_profiler.snapshot("embeddings", 1024 * 1024 * 150)  # 150 MB
    mem_profiler.snapshot("kg_index", 1024 * 1024 * 50)      # 50 MB
    mem_profiler.snapshot("bm25_index", 1024 * 1024 * 30)    # 30 MB
    mem_profiler.snapshot("cache", 1024 * 1024 * 20)         # 20 MB

    print(mem_profiler.report())
