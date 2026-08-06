"""
Closed-Loop Learning System for Trading
========================================

A comprehensive learning system that enables continuous improvement through:
1. Observation Collection - track trades, outcomes, regime shifts
2. Analysis Engine - extract patterns and correlations
3. Learning Engine - generate conditional lessons with confidence scores
4. Knowledge Updater - maintain and update knowledge graph
5. Reporting Dashboard - daily/weekly/monthly summaries

Cycle time: Daily observations → Weekly analysis → Monthly KB updates

Key features:
- Confidence scoring with temporal decay (2% per week)
- Contradiction detection (old vs new knowledge)
- Conditional lessons ("works when X < threshold")
- Mock observation stream for testing
"""

from observation_collector import (
    ObservationCollector,
    TradeObservation,
    RegimeShift,
    Escalation,
    MockObservationStream,
    TradeStatus,
    RegiType
)

from analysis_engine import AnalysisEngine

from learning_engine import LearningEngine, Lesson

from reporting_dashboard import ReportingDashboard

__all__ = [
    "ObservationCollector",
    "TradeObservation",
    "RegimeShift",
    "Escalation",
    "MockObservationStream",
    "TradeStatus",
    "RegiType",
    "AnalysisEngine",
    "LearningEngine",
    "Lesson",
    "ReportingDashboard"
]

__version__ = "1.0.0"
