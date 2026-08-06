"""
Tier 3: Agentic Reasoning Engine for Group One RAG

Tree-of-Thought reasoning with state management, multi-step validation,
and latency budget enforcement.

Exports:
- ReasoningEngine: Core reasoning engine with Tree-of-Thought
- ReasoningState: State management (regime, entities, constraints, chain)
- ReasoningNode: Tree-of-Thought node representation
- RankingFunction: Strategy ranking and evaluation
- AgentCoordinator: Multi-agent decomposition (Analyst, Selector, Executor)
- MarketAnalyst, StrategySelector, Executor: Individual agent implementations
"""

from reasoning_engine import (
    ReasoningEngine,
    ReasoningState,
    ReasoningNode,
    ReasoningStep,
    RankingFunction,
    RankingMetrics,
    MarketRegime,
    Entity,
    Constraint,
    ConstraintType,
    ReasoningStepType,
)

from agent_coordinator import (
    AgentCoordinator,
    MarketAnalyst,
    StrategySelector,
    Executor,
    AgentOutput,
    CoordinationResult,
    AgentRole,
)

__all__ = [
    # Core engine
    "ReasoningEngine",
    "ReasoningState",
    "ReasoningNode",
    "ReasoningStep",
    "RankingFunction",
    "RankingMetrics",
    # Data types
    "MarketRegime",
    "Entity",
    "Constraint",
    "ConstraintType",
    "ReasoningStepType",
    # Multi-agent
    "AgentCoordinator",
    "MarketAnalyst",
    "StrategySelector",
    "Executor",
    "AgentOutput",
    "CoordinationResult",
    "AgentRole",
]

__version__ = "1.0.0"
__description__ = "Tier 3 Agentic Reasoning Engine for Group One RAG"
