"""
Multi-Agent Strategy Competition Framework
===========================================

Core components for dynamic strategy selection via Elo-rated agents.

Phase 3, Agent 2: Strategy Competition & Dynamic Selection
"""

from .strategy_agent import (
    StrategyAgent,
    ActionType,
    GreeksSnapshot,
    MarketState,
    StrategySelection,
    AgentPerformance,
)

from .agent_pool import (
    GammaScalpingAgent,
    VegaArbitrageAgent,
    MeanReversionAgent,
    EventDrivenAgent,
    MomentumAgent,
    CorrelationAgent,
    AgentPool,
)

from .competition_engine import (
    CompetitionEngine,
    EloRating,
)

from .regime_detector import (
    RegimeDetector,
    RegimeType,
)

__version__ = "1.0.0"
__author__ = "Group One Trading Quant"

__all__ = [
    # StrategyAgent
    "StrategyAgent",
    "ActionType",
    "GreeksSnapshot",
    "MarketState",
    "StrategySelection",
    "AgentPerformance",
    # Agent Pool
    "GammaScalpingAgent",
    "VegaArbitrageAgent",
    "MeanReversionAgent",
    "EventDrivenAgent",
    "MomentumAgent",
    "CorrelationAgent",
    "AgentPool",
    # Competition Engine
    "CompetitionEngine",
    "EloRating",
    # Regime Detector
    "RegimeDetector",
    "RegimeType",
]
