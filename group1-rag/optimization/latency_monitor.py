"""
Latency monitoring and SLA enforcement for Group One Trading RAG.

Tracks per-component latency, enforces SLA targets, and alerts on violations.

Target SLAs:
- Retrieval: 50-75ms
- Entity Extraction: 100-150ms
- Reasoning: 100-200ms
- KG Queries: <10ms
- Safety Checks: <5ms
- End-to-End: <2s (95%ile)
"""

import time
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import threading


class SLAStatus(Enum):
    """SLA status."""
    OK = "OK"
    WARNING = "WARNING"
    VIOLATED = "VIOLATED"


@dataclass
class SLATarget:
    """SLA target for a component."""
    component: str
    p95_ms: float  # 95%ile target
    p99_ms: float  # 99%ile target
    avg_ms: Optional[float] = None  # Optional average target


# Default SLA targets (from requirements)
DEFAULT_SLAS = {
    "retrieval": SLATarget("retrieval", p95_ms=75, p99_ms=150, avg_ms=50),
    "entity_extraction": SLATarget("entity_extraction", p95_ms=150, p99_ms=250, avg_ms=100),
    "reasoning": SLATarget("reasoning", p95_ms=200, p99_ms=400, avg_ms=100),
    "kg_queries": SLATarget("kg_queries", p95_ms=15, p99_ms=30, avg_ms=10),
    "safety_checks": SLATarget("safety_checks", p95_ms=10, p99_ms=20, avg_ms=5),
}

END_TO_END_SLA = SLATarget("end_to_end", p95_ms=2000, p99_ms=5000)


@dataclass
class SLAViolation:
    """An SLA violation event."""
    component: str
    latency_ms: float
    target_ms: float
    percentile: str  # "p95", "p99", "avg"
    timestamp: float
    query_id: Optional[str] = None


@dataclass
class ComponentLatency:
    """Latency metrics for a component."""
    component: str
    count: int
    sum_ms: float
    min_ms: float
    max_ms: float
    samples: deque = field(default_factory=lambda: deque(maxlen=1000))

    @property
    def avg_ms(self) -> float:
        return self.sum_ms / self.count if self.count > 0 else 0

    @property
    def p95_ms(self) -> float:
        if not self.samples:
            return 0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[idx] if idx < len(sorted_samples) else sorted_samples[-1]

    @property
    def p99_ms(self) -> float:
        if not self.samples:
            return 0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[idx] if idx < len(sorted_samples) else sorted_samples[-1]


class LatencyMonitor:
    """
    Monitors per-component latency and enforces SLAs.

    Tracks latency for each component, computes percentiles, and
    detects SLA violations.
    """

    def __init__(self, slas: Dict[str, SLATarget] = None):
        """
        Initialize monitor.

        Args:
            slas: SLA targets (default: DEFAULT_SLAS)
        """
        self.slas = slas or DEFAULT_SLAS
        self.components: Dict[str, ComponentLatency] = {
            name: ComponentLatency(
                component=name,
                count=0,
                sum_ms=0,
                min_ms=float('inf'),
                max_ms=0,
            )
            for name in self.slas.keys()
        }
        self.violations: List[SLAViolation] = []
        self.lock = threading.RLock()
        self.end_to_end_samples: deque = deque(maxlen=1000)
        self.request_id_counter = 0

    def record_component_latency(
        self,
        component: str,
        latency_ms: float,
        query_id: Optional[str] = None
    ):
        """
        Record latency for a component.

        Args:
            component: Component name
            latency_ms: Measured latency
            query_id: Optional query ID
        """
        with self.lock:
            if component not in self.components:
                self.components[component] = ComponentLatency(
                    component=component,
                    count=0,
                    sum_ms=0,
                    min_ms=float('inf'),
                    max_ms=0,
                )

            comp = self.components[component]
            comp.count += 1
            comp.sum_ms += latency_ms
            comp.min_ms = min(comp.min_ms, latency_ms)
            comp.max_ms = max(comp.max_ms, latency_ms)
            comp.samples.append(latency_ms)

            # Check SLA
            self._check_sla(component, latency_ms, query_id)

    def record_end_to_end_latency(self, latency_ms: float, query_id: Optional[str] = None):
        """
        Record end-to-end latency.

        Args:
            latency_ms: Measured latency
            query_id: Optional query ID
        """
        with self.lock:
            self.end_to_end_samples.append(latency_ms)
            self._check_end_to_end_sla(latency_ms, query_id)

    def _check_sla(self, component: str, latency_ms: float, query_id: Optional[str]):
        """Check if latency violates SLA."""
        if component not in self.slas:
            return

        sla = self.slas[component]

        # Check against average if defined
        if sla.avg_ms and latency_ms > sla.avg_ms * 1.5:  # 50% margin
            self.violations.append(SLAViolation(
                component=component,
                latency_ms=latency_ms,
                target_ms=sla.avg_ms,
                percentile="avg",
                timestamp=time.time(),
                query_id=query_id,
            ))

    def _check_end_to_end_sla(self, latency_ms: float, query_id: Optional[str]):
        """Check end-to-end SLA."""
        if latency_ms > END_TO_END_SLA.p95_ms:
            self.violations.append(SLAViolation(
                component="end_to_end",
                latency_ms=latency_ms,
                target_ms=END_TO_END_SLA.p95_ms,
                percentile="p95",
                timestamp=time.time(),
                query_id=query_id,
            ))

    def get_component_metrics(self, component: str) -> Optional[ComponentLatency]:
        """Get metrics for a component."""
        with self.lock:
            return self.components.get(component)

    def get_all_metrics(self) -> Dict[str, ComponentLatency]:
        """Get metrics for all components."""
        with self.lock:
            return dict(self.components)

    def get_sla_status(self, component: str) -> SLAStatus:
        """Get current SLA status for component."""
        with self.lock:
            metrics = self.components.get(component)
            if not metrics or metrics.count == 0:
                return SLAStatus.OK

            sla = self.slas.get(component)
            if not sla:
                return SLAStatus.OK

            # Check p95
            if metrics.p95_ms > sla.p95_ms:
                return SLAStatus.VIOLATED

            # Check p99
            if metrics.p99_ms > sla.p99_ms:
                return SLAStatus.WARNING

            return SLAStatus.OK

    def get_end_to_end_sla_status(self) -> SLAStatus:
        """Get end-to-end SLA status."""
        with self.lock:
            if not self.end_to_end_samples:
                return SLAStatus.OK

            sorted_samples = sorted(self.end_to_end_samples)
            p95_idx = int(len(sorted_samples) * 0.95)
            p95 = sorted_samples[p95_idx] if p95_idx < len(sorted_samples) else sorted_samples[-1]

            if p95 > END_TO_END_SLA.p95_ms:
                return SLAStatus.VIOLATED

            return SLAStatus.OK

    def get_violations(self, limit: int = None) -> List[SLAViolation]:
        """Get recent SLA violations."""
        with self.lock:
            violations = self.violations[-limit:] if limit else self.violations
            return list(violations)

    def clear_violations(self):
        """Clear violation history."""
        with self.lock:
            self.violations.clear()

    def reset(self):
        """Reset all metrics."""
        with self.lock:
            for comp in self.components.values():
                comp.count = 0
                comp.sum_ms = 0
                comp.min_ms = float('inf')
                comp.max_ms = 0
                comp.samples.clear()

            self.end_to_end_samples.clear()
            self.violations.clear()

    def report(self, include_violations: bool = True) -> str:
        """Generate monitoring report."""
        lines = ["\n" + "="*90]
        lines.append("Latency Monitoring Report")
        lines.append("="*90 + "\n")

        # Component metrics table
        lines.append(f"{'Component':<20} {'Samples':>8} {'Avg':>8} {'Min':>8} "
                    f"{'P95':>8} {'P99':>8} {'Max':>8} {'SLA Status':>15}")
        lines.append("-" * 90)

        with self.lock:
            for name in sorted(self.components.keys()):
                comp = self.components[name]
                sla = self.slas.get(name)
                status = self.get_sla_status(name)

                lines.append(
                    f"{name:<20} {comp.count:>8} {comp.avg_ms:>7.1f}ms "
                    f"{comp.min_ms:>7.1f}ms {comp.p95_ms:>7.1f}ms {comp.p99_ms:>7.1f}ms "
                    f"{comp.max_ms:>7.1f}ms {status.value:>15}"
                )

                if sla:
                    target_str = f"(target: P95={sla.p95_ms:.0f}ms, P99={sla.p99_ms:.0f}ms)"
                    lines.append(f"  {target_str}")

        # End-to-end metrics
        lines.append("\n" + "-" * 90)
        if self.end_to_end_samples:
            sorted_e2e = sorted(self.end_to_end_samples)
            p95_idx = int(len(sorted_e2e) * 0.95)
            p99_idx = int(len(sorted_e2e) * 0.99)
            p95 = sorted_e2e[p95_idx] if p95_idx < len(sorted_e2e) else sorted_e2e[-1]
            p99 = sorted_e2e[p99_idx] if p99_idx < len(sorted_e2e) else sorted_e2e[-1]

            e2e_status = self.get_end_to_end_sla_status()

            lines.append(
                f"{'end_to_end':<20} {len(sorted_e2e):>8} {sum(sorted_e2e)/len(sorted_e2e):>7.1f}ms "
                f"{min(sorted_e2e):>7.1f}ms {p95:>7.1f}ms {p99:>7.1f}ms "
                f"{max(sorted_e2e):>7.1f}ms {e2e_status.value:>15}"
            )
            lines.append(f"  (target: P95={END_TO_END_SLA.p95_ms:.0f}ms, P99={END_TO_END_SLA.p99_ms:.0f}ms)")

        # Violations
        if include_violations:
            lines.append("\n" + "-" * 90)
            recent_violations = self.get_violations(10)
            if recent_violations:
                lines.append(f"Recent Violations (last {len(recent_violations)}):")
                for violation in recent_violations:
                    lines.append(
                        f"  {violation.component}: {violation.latency_ms:.1f}ms "
                        f"(target: {violation.target_ms:.1f}ms, {violation.percentile})"
                    )
            else:
                lines.append("No recent violations ✓")

        lines.append("="*90 + "\n")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, any]:
        """Export metrics as dictionary."""
        with self.lock:
            return {
                "components": {
                    name: {
                        "count": comp.count,
                        "avg_ms": comp.avg_ms,
                        "min_ms": comp.min_ms,
                        "max_ms": comp.max_ms,
                        "p95_ms": comp.p95_ms,
                        "p99_ms": comp.p99_ms,
                    }
                    for name, comp in self.components.items()
                },
                "end_to_end": {
                    "samples": len(self.end_to_end_samples),
                    "avg_ms": sum(self.end_to_end_samples) / len(self.end_to_end_samples)
                            if self.end_to_end_samples else 0,
                } if self.end_to_end_samples else None,
                "violations": len(self.violations),
            }


class CircuitBreaker:
    """
    Circuit breaker for safety violations.

    Trips if too many safety check violations in short time.
    """

    def __init__(
        self,
        violation_threshold: int = 3,
        time_window_s: float = 60.0
    ):
        """
        Initialize circuit breaker.

        Args:
            violation_threshold: Number of violations to trip
            time_window_s: Time window for counting violations
        """
        self.violation_threshold = violation_threshold
        self.time_window_s = time_window_s
        self.violations: deque = deque()
        self.is_open = False
        self.lock = threading.RLock()

    def record_violation(self):
        """Record a safety violation."""
        with self.lock:
            now = time.time()
            self.violations.append(now)

            # Remove old violations outside window
            while self.violations and self.violations[0] < now - self.time_window_s:
                self.violations.popleft()

            # Check if tripped
            if len(self.violations) >= self.violation_threshold:
                self.is_open = True

    def is_healthy(self) -> bool:
        """Check if circuit is healthy."""
        with self.lock:
            return not self.is_open

    def reset(self):
        """Reset circuit breaker."""
        with self.lock:
            self.is_open = False
            self.violations.clear()


# ============================================================================
# Example usage
# ============================================================================

if __name__ == "__main__":
    import random

    monitor = LatencyMonitor()

    # Simulate latencies
    for _ in range(100):
        # Good retrieval
        monitor.record_component_latency("retrieval", random.gauss(60, 10))

        # Good entity extraction
        monitor.record_component_latency("entity_extraction", random.gauss(120, 15))

        # Good reasoning
        monitor.record_component_latency("reasoning", random.gauss(150, 20))

        # Good KG
        monitor.record_component_latency("kg_queries", random.gauss(8, 2))

        # Good safety
        monitor.record_component_latency("safety_checks", random.gauss(4, 1))

        # End-to-end
        e2e = (random.gauss(60, 10) + random.gauss(120, 15) +
               random.gauss(150, 20) + random.gauss(8, 2) +
               random.gauss(4, 1))
        monitor.record_end_to_end_latency(e2e)

    print(monitor.report())

    # Circuit breaker example
    breaker = CircuitBreaker(violation_threshold=2)
    breaker.record_violation()
    print(f"Circuit healthy after 1 violation: {breaker.is_healthy()}")
    breaker.record_violation()
    print(f"Circuit healthy after 2 violations: {breaker.is_healthy()}")
