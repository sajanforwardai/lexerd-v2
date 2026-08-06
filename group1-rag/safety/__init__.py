"""
Group One RAG Tier 3 Safety Systems

Comprehensive risk management framework with:
- Position limits enforcement (multi-tier soft/warning/hard)
- Correlation regime detection (eigenvalue analysis)
- Circuit breaker (daily losses, vol spikes, black swan)
- Human escalation (alert logging and manual review triggers)
- Risk validation (pre/post-trade checks)
"""

from .safety_systems import (
    SafetySystems,
    PositionLimits,
    CorrelationDetector,
    CircuitBreaker,
    HumanEscalation,
    RiskValidator,
    GreeksSnapshot,
    PositionData,
    RiskAlert,
    LimitTier,
    RiskMetric,
    CircuitBreakerTrigger,
)

__all__ = [
    "SafetySystems",
    "PositionLimits",
    "CorrelationDetector",
    "CircuitBreaker",
    "HumanEscalation",
    "RiskValidator",
    "GreeksSnapshot",
    "PositionData",
    "RiskAlert",
    "LimitTier",
    "RiskMetric",
    "CircuitBreakerTrigger",
]

__version__ = "1.0.0"
