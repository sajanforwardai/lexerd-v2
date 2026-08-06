"""
Parallel reasoning evaluation for Group One Trading RAG.

Implements thread pool-based parallel evaluation of reasoning nodes.
Evaluates sibling nodes concurrently to reduce reasoning latency from
200-400ms to target 100-200ms.

Key optimization: evaluate 2 branches in parallel instead of sequential.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time


class NodeType(Enum):
    """Types of reasoning nodes."""
    ROOT = "root"
    REGIME = "regime"
    STRATEGY = "strategy"
    ACTION = "action"
    EVALUATION = "evaluation"


class ExecutionStrategy(Enum):
    """Execution strategy for reasoning trees."""
    SEQUENTIAL = "sequential"  # Evaluate nodes one-by-one
    PARALLEL_SIBLINGS = "parallel_siblings"  # Evaluate siblings in parallel
    PARALLEL_FULL = "parallel_full"  # Evaluate all nodes in parallel


@dataclass
class ReasoningNode:
    """
    A node in the reasoning tree.

    Represents a decision point or evaluation in the reasoning process.
    """
    name: str
    node_type: NodeType
    evaluate_fn: Callable[..., Any]
    children: List["ReasoningNode"] = field(default_factory=list)
    parent: Optional["ReasoningNode"] = None
    result: Optional[Any] = None
    latency_ms: float = 0.0

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """
        Evaluate this node.

        Args:
            context: Context dictionary for evaluation

        Returns:
            Node result
        """
        start = time.perf_counter()
        self.result = self.evaluate_fn(context)
        self.latency_ms = (time.perf_counter() - start) * 1000
        return self.result


@dataclass
class ReasoningTree:
    """
    A tree of reasoning nodes.

    Represents the full reasoning process from root to leaf decisions.
    """
    root: ReasoningNode
    execution_strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL_SIBLINGS

    def get_all_nodes(self) -> List[ReasoningNode]:
        """Get all nodes in tree (breadth-first)."""
        nodes = []
        queue = [self.root]

        while queue:
            node = queue.pop(0)
            nodes.append(node)
            queue.extend(node.children)

        return nodes

    def get_nodes_by_level(self) -> List[List[ReasoningNode]]:
        """
        Get nodes grouped by level (depth).

        Returns:
            List of lists, where each inner list contains nodes at that depth
        """
        levels = []
        queue = [(self.root, 0)]
        current_level = 0

        while queue:
            node, level = queue.pop(0)

            if level > current_level:
                current_level = level
                levels.append([])

            if level == len(levels):
                levels.append([])

            levels[level].append(node)

            for child in node.children:
                queue.append((child, level + 1))

        return levels

    def evaluate_sequential(self, context: Dict[str, Any]) -> Tuple[Any, float]:
        """
        Evaluate tree sequentially (baseline).

        Args:
            context: Evaluation context

        Returns:
            (result, total_latency_ms)
        """
        start = time.perf_counter()

        def _evaluate_node(node: ReasoningNode):
            node.evaluate(context)
            # Recursively evaluate children
            for child in node.children:
                _evaluate_node(child)

        _evaluate_node(self.root)
        total_ms = (time.perf_counter() - start) * 1000
        return self.root.result, total_ms

    def evaluate_parallel_siblings(
        self,
        context: Dict[str, Any],
        max_workers: int = 4
    ) -> Tuple[Any, float]:
        """
        Evaluate siblings in parallel.

        Siblings at the same level are evaluated concurrently.
        Reduces latency by parallelizing sibling evaluation.

        Args:
            context: Evaluation context
            max_workers: Maximum thread pool size

        Returns:
            (result, total_latency_ms)
        """
        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            levels = self.get_nodes_by_level()

            # Evaluate level by level
            for level_nodes in levels:
                # Submit all nodes at this level
                futures = {
                    executor.submit(node.evaluate, context): node
                    for node in level_nodes
                }

                # Wait for all to complete
                for future in as_completed(futures):
                    future.result()

        total_ms = (time.perf_counter() - start) * 1000
        return self.root.result, total_ms

    def evaluate_parallel_full(
        self,
        context: Dict[str, Any],
        max_workers: int = 4
    ) -> Tuple[Any, float]:
        """
        Fully parallel evaluation (with dependency ordering).

        Evaluates nodes in parallel while respecting parent-child dependencies.

        Args:
            context: Evaluation context
            max_workers: Maximum thread pool size

        Returns:
            (result, total_latency_ms)
        """
        start = time.perf_counter()
        evaluated = set()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures_to_nodes = {}

            def _submit_node(node: ReasoningNode):
                """Submit node for evaluation if dependencies are met."""
                if node in evaluated:
                    return

                # Check if parent is evaluated
                if node.parent and node.parent not in evaluated:
                    return False  # Can't evaluate yet

                # Submit this node
                future = executor.submit(node.evaluate, context)
                futures_to_nodes[future] = node
                return True

            # Submit root first
            _submit_node(self.root)

            # Process futures as they complete
            while futures_to_nodes:
                for future in as_completed(futures_to_nodes):
                    node = futures_to_nodes.pop(future)
                    future.result()
                    evaluated.add(node)

                    # Try to submit children
                    for child in node.children:
                        _submit_node(child)

        total_ms = (time.perf_counter() - start) * 1000
        return self.root.result, total_ms

    def evaluate(self, context: Dict[str, Any], max_workers: int = 4) -> Tuple[Any, float]:
        """
        Evaluate tree using configured strategy.

        Args:
            context: Evaluation context
            max_workers: Thread pool size (for parallel strategies)

        Returns:
            (result, total_latency_ms)
        """
        if self.execution_strategy == ExecutionStrategy.SEQUENTIAL:
            return self.evaluate_sequential(context)
        elif self.execution_strategy == ExecutionStrategy.PARALLEL_SIBLINGS:
            return self.evaluate_parallel_siblings(context, max_workers)
        elif self.execution_strategy == ExecutionStrategy.PARALLEL_FULL:
            return self.evaluate_parallel_full(context, max_workers)
        else:
            raise ValueError(f"Unknown strategy: {self.execution_strategy}")

    def get_total_latency(self) -> float:
        """Get sum of all node latencies."""
        return sum(node.latency_ms for node in self.get_all_nodes())

    def get_critical_path(self) -> List[ReasoningNode]:
        """Get nodes on the critical path (longest branch)."""
        def _get_critical_path(node: ReasoningNode) -> Tuple[float, List[ReasoningNode]]:
            if not node.children:
                return node.latency_ms, [node]

            max_latency = node.latency_ms
            best_path = [node]

            for child in node.children:
                child_latency, child_path = _get_critical_path(child)
                total = node.latency_ms + child_latency

                if total > max_latency:
                    max_latency = total
                    best_path = [node] + child_path

            return max_latency, best_path

        _, path = _get_critical_path(self.root)
        return path

    def report(self) -> str:
        """Generate evaluation report."""
        lines = ["\n" + "="*70]
        lines.append("Reasoning Tree Evaluation Report")
        lines.append("="*70 + "\n")

        # Tree structure
        lines.append("Tree Structure:")
        lines.append("-" * 70)

        def _print_node(node: ReasoningNode, indent: int = 0):
            prefix = "  " * indent + "├─ "
            lines.append(
                f"{prefix}{node.name:<20} ({node.node_type.value:<12}) "
                f"{node.latency_ms:>8.2f} ms"
            )
            for child in node.children:
                _print_node(child, indent + 1)

        _print_node(self.root)

        # Statistics
        lines.append("\n" + "-" * 70)
        total_nodes = len(self.get_all_nodes())
        total_latency = self.get_total_latency()
        critical_path = self.get_critical_path()

        lines.append(f"Total Nodes: {total_nodes}")
        lines.append(f"Total Latency (sum): {total_latency:.2f} ms")
        lines.append(f"Root Latency: {self.root.latency_ms:.2f} ms")

        if critical_path:
            critical_latency = sum(n.latency_ms for n in critical_path)
            lines.append(f"Critical Path Length: {len(critical_path)}")
            lines.append(f"Critical Path Latency: {critical_latency:.2f} ms")

        lines.append(f"Execution Strategy: {self.execution_strategy.value}")
        lines.append("="*70 + "\n")

        return "\n".join(lines)


class ReasoningAccelerator:
    """
    Optimizes reasoning performance through tree pruning and caching.

    - Reduces tree depth for common patterns (2 levels instead of 3)
    - Caches common evaluation results
    - Identifies and skips unnecessary branches
    """

    def __init__(self, cache_capacity: int = 128):
        """Initialize accelerator."""
        self.cache_capacity = cache_capacity
        self.evaluation_cache: Dict[str, Any] = {}
        self.hit_count = 0
        self.miss_count = 0

    def prune_tree(self, tree: ReasoningTree, max_depth: int = 2) -> ReasoningTree:
        """
        Prune tree to max depth.

        For common queries, depth 2 (regime → strategy → action) is sufficient.

        Args:
            tree: Original tree
            max_depth: Maximum depth to keep

        Returns:
            Pruned tree
        """
        def _prune_node(node: ReasoningNode, depth: int):
            if depth >= max_depth:
                node.children = []
            else:
                for child in node.children:
                    _prune_node(child, depth + 1)

        _prune_node(tree.root, 0)
        return tree

    def cache_result(self, key: str, result: Any):
        """Cache evaluation result."""
        if len(self.evaluation_cache) >= self.cache_capacity:
            # Simple eviction: remove first (FIFO)
            self.evaluation_cache.pop(next(iter(self.evaluation_cache)))

        self.evaluation_cache[key] = result

    def get_cached(self, key: str) -> Optional[Any]:
        """Get cached result."""
        result = self.evaluation_cache.get(key)
        if result is not None:
            self.hit_count += 1
        else:
            self.miss_count += 1
        return result

    def should_evaluate_branch(
        self,
        branch_name: str,
        confidence_threshold: float = 0.8
    ) -> bool:
        """
        Decide whether to evaluate a branch.

        Skips low-confidence branches to save time.

        Args:
            branch_name: Name of branch
            confidence_threshold: Skip if confidence below this

        Returns:
            True if branch should be evaluated
        """
        # Placeholder: could track branch success rates
        return True

    def report(self) -> str:
        """Generate performance report."""
        lines = ["\nReasoning Accelerator Report"]
        lines.append("-" * 50)
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0
        lines.append(f"Cache Hits: {self.hit_count}")
        lines.append(f"Cache Misses: {self.miss_count}")
        lines.append(f"Hit Rate: {hit_rate:.1f}%")
        lines.append(f"Cache Size: {len(self.evaluation_cache)}")
        return "\n".join(lines)


# ============================================================================
# Example usage and testing
# ============================================================================

if __name__ == "__main__":
    # Create a sample reasoning tree
    def dummy_evaluate(context: Dict) -> str:
        """Dummy evaluation function."""
        import time
        time.sleep(0.01)  # Simulate work
        return "result"

    # Build tree
    root = ReasoningNode(
        name="Root",
        node_type=NodeType.ROOT,
        evaluate_fn=lambda ctx: "root_result"
    )

    regime = ReasoningNode(
        name="Regime",
        node_type=NodeType.REGIME,
        evaluate_fn=dummy_evaluate,
        parent=root
    )
    root.children.append(regime)

    # Regime children (parallel candidates)
    strategy1 = ReasoningNode(
        name="Strategy-Bullish",
        node_type=NodeType.STRATEGY,
        evaluate_fn=dummy_evaluate,
        parent=regime
    )
    strategy2 = ReasoningNode(
        name="Strategy-Bearish",
        node_type=NodeType.STRATEGY,
        evaluate_fn=dummy_evaluate,
        parent=regime
    )
    regime.children = [strategy1, strategy2]

    # Action nodes
    action1 = ReasoningNode(
        name="Action-Buy",
        node_type=NodeType.ACTION,
        evaluate_fn=dummy_evaluate,
        parent=strategy1
    )
    strategy1.children.append(action1)

    action2 = ReasoningNode(
        name="Action-Sell",
        node_type=NodeType.ACTION,
        evaluate_fn=dummy_evaluate,
        parent=strategy2
    )
    strategy2.children.append(action2)

    # Test different strategies
    context = {"market": "bullish"}

    for strategy in [ExecutionStrategy.SEQUENTIAL,
                     ExecutionStrategy.PARALLEL_SIBLINGS]:
        tree = ReasoningTree(root, strategy)
        result, latency = tree.evaluate(context)
        print(f"\n{strategy.value}: {latency:.2f}ms")
        print(tree.report())
