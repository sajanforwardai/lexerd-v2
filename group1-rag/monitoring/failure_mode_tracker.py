"""
Failure Mode Tracker and Pattern Matching

Collects every trade failure, execution issue, and safety escalation.
Categorizes failures and matches against known failure modes (RADAR library).
Generates weekly summaries and monthly deep-dive analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FailureCategory(Enum):
    """Failure mode categories."""
    EXECUTION_FAILURE = "execution_failure"  # Slippage, partial fill, rejected order
    SIGNAL_FAILURE = "signal_failure"  # False signal, timing error, parameter drift
    REGIME_SHIFT = "regime_shift"  # Unexpected market regime change
    CORRELATION_BREAKDOWN = "correlation_breakdown"  # Hedging failed
    RISK_VIOLATION = "risk_violation"  # Limit breach, leverage violation
    DATA_QUALITY = "data_quality"  # Missing/corrupt data
    SYSTEM_FAILURE = "system_failure"  # Crash, connection error


class FailureSeverity(Enum):
    """Failure severity levels."""
    MINOR = "minor"  # <$1k loss
    MODERATE = "moderate"  # $1k-$10k loss
    MAJOR = "major"  # $10k-$100k loss
    CRITICAL = "critical"  # >$100k loss or systemic risk


@dataclass
class FailureMode:
    """Known failure mode from RADAR library or historical patterns."""
    mode_id: str
    name: str
    category: FailureCategory
    description: str
    typical_loss: float  # Typical $ impact
    frequency: int  # Number of times seen
    mitigation_strategies: List[str]
    last_occurred: Optional[datetime] = None


@dataclass
class FailureEvent:
    """Single failure event."""
    timestamp: datetime
    category: FailureCategory
    severity: FailureSeverity
    strategy: str
    instrument: str
    description: str
    financial_impact: float  # Dollar impact
    matched_failure_modes: List[str] = field(default_factory=list)  # IDs of matched known modes
    is_known_mode: bool = False
    root_cause: Optional[str] = None
    remediation_taken: Optional[str] = None
    escalation_level: str = "INFO"  # "INFO", "WARNING", "CRITICAL"


@dataclass
class WeeklyFailureSummary:
    """Weekly failure summary report."""
    week_start: str  # YYYY-MM-DD
    week_end: str
    total_events: int
    events_by_category: Dict[str, int]
    events_by_severity: Dict[str, int]
    total_financial_impact: float
    known_mode_occurrences: Dict[str, int]  # mode_id -> count
    new_patterns_detected: List[str]
    top_recommendations: List[str]


@dataclass
class MonthlyFailureAnalysis:
    """Monthly deep-dive failure analysis."""
    month_year: str  # YYYY-MM
    total_events: int
    events_by_category: Dict[str, int]
    trend_analysis: Dict[str, int]  # "increasing", "stable", "decreasing"
    top_failure_modes: List[Tuple[str, int]]  # (mode_name, count)
    systemic_issues: List[str]
    process_improvements: List[str]
    risk_assessment: str  # "LOW", "MEDIUM", "HIGH"


class FailureModeTracker:
    """Track, categorize, and analyze trading failures."""

    def __init__(self):
        """Initialize failure tracker."""
        self.events: List[FailureEvent] = []
        self.known_modes: Dict[str, FailureMode] = self._load_known_modes()
        self.pattern_counts: Dict[str, int] = {}

    def record_failure(
        self,
        timestamp: datetime,
        category: FailureCategory,
        severity: FailureSeverity,
        strategy: str,
        instrument: str,
        description: str,
        financial_impact: float,
        root_cause: Optional[str] = None,
    ) -> FailureEvent:
        """Record a failure event.

        Args:
            timestamp: When failure occurred
            category: FailureCategory
            severity: FailureSeverity
            strategy: Strategy name
            instrument: Instrument affected
            description: Detailed description
            financial_impact: $ impact
            root_cause: Root cause analysis

        Returns:
            FailureEvent with pattern matching results
        """
        event = FailureEvent(
            timestamp=timestamp,
            category=category,
            severity=severity,
            strategy=strategy,
            instrument=instrument,
            description=description,
            financial_impact=financial_impact,
            root_cause=root_cause,
        )

        # Match against known modes
        matched_modes = self._match_failure_modes(event)
        event.matched_failure_modes = matched_modes
        event.is_known_mode = len(matched_modes) > 0

        # Determine escalation
        event.escalation_level = self._determine_escalation(event)

        self.events.append(event)

        # Log
        logger.warning(
            f"FAILURE RECORDED: {category.value} - {strategy}/{instrument} "
            f"${financial_impact:.0f} impact, "
            f"known_mode: {event.is_known_mode}"
        )

        return event

    def _match_failure_modes(self, event: FailureEvent) -> List[str]:
        """Match event against known failure modes.

        Args:
            event: FailureEvent to match

        Returns:
            List of matched mode IDs
        """
        matched = []

        for mode_id, mode in self.known_modes.items():
            # Category match
            if mode.category != event.category:
                continue

            # Description keyword matching
            description_lower = event.description.lower()
            keywords = [
                w for w in mode.description.lower().split()
                if len(w) > 4 and w not in ["failure", "error", "issue"]
            ]

            keyword_matches = sum(1 for kw in keywords if kw in description_lower)
            if keyword_matches >= len(keywords) * 0.5:  # 50% keyword match
                matched.append(mode_id)
                mode.last_occurred = event.timestamp
                mode.frequency += 1

        return matched

    def _determine_escalation(self, event: FailureEvent) -> str:
        """Determine escalation level for event.

        Args:
            event: FailureEvent

        Returns:
            Escalation level
        """
        if event.severity == FailureSeverity.CRITICAL:
            return "CRITICAL"
        elif event.severity == FailureSeverity.MAJOR:
            return "WARNING"
        elif event.is_known_mode:
            # Known modes are less urgent
            return "INFO"
        else:
            return "WARNING"  # Unknown modes warrant attention

    def get_weekly_summary(self, week_start: str) -> WeeklyFailureSummary:
        """Generate weekly failure summary.

        Args:
            week_start: YYYY-MM-DD start date

        Returns:
            WeeklyFailureSummary
        """
        # Parse dates
        start = datetime.strptime(week_start, "%Y-%m-%d")
        end = start + timedelta(days=7)

        # Filter to week
        week_events = [
            e for e in self.events
            if start <= e.timestamp < end
        ]

        # Count by category
        events_by_category = {}
        for cat in FailureCategory:
            count = sum(1 for e in week_events if e.category == cat)
            events_by_category[cat.value] = count

        # Count by severity
        events_by_severity = {}
        for sev in FailureSeverity:
            count = sum(1 for e in week_events if e.severity == sev)
            events_by_severity[sev.value] = count

        # Known modes
        known_mode_counts = {}
        for event in week_events:
            for mode_id in event.matched_failure_modes:
                known_mode_counts[mode_id] = known_mode_counts.get(mode_id, 0) + 1

        # Total impact
        total_impact = sum(e.financial_impact for e in week_events)

        # Recommendations
        recommendations = self._generate_recommendations(week_events)

        summary = WeeklyFailureSummary(
            week_start=week_start,
            week_end=end.strftime("%Y-%m-%d"),
            total_events=len(week_events),
            events_by_category=events_by_category,
            events_by_severity=events_by_severity,
            total_financial_impact=total_impact,
            known_mode_occurrences=known_mode_counts,
            new_patterns_detected=[],
            top_recommendations=recommendations[:5],
        )

        return summary

    def get_monthly_analysis(self, month_year: str) -> MonthlyFailureAnalysis:
        """Generate monthly deep-dive failure analysis.

        Args:
            month_year: YYYY-MM

        Returns:
            MonthlyFailureAnalysis
        """
        # Parse month
        start = datetime.strptime(month_year, "%Y-%m")
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

        # Filter to month
        month_events = [
            e for e in self.events
            if start <= e.timestamp < end
        ]

        # Count by category
        events_by_category = {}
        for cat in FailureCategory:
            count = sum(1 for e in month_events if e.category == cat)
            events_by_category[cat.value] = count

        # Top failure modes
        mode_counts = {}
        for event in month_events:
            for mode_id in event.matched_failure_modes:
                mode_name = self.known_modes[mode_id].name if mode_id in self.known_modes else mode_id
                mode_counts[mode_name] = mode_counts.get(mode_name, 0) + 1

        top_modes = sorted(mode_counts.items(), key=lambda x: x[1], reverse=True)

        # Systemic issues (patterns)
        systemic = self._identify_systemic_issues(month_events)

        # Risk assessment
        total_impact = sum(e.financial_impact for e in month_events)
        critical_count = sum(1 for e in month_events if e.severity == FailureSeverity.CRITICAL)
        risk_level = "HIGH" if (critical_count > 2 or total_impact > 100000) else (
            "MEDIUM" if (critical_count > 0 or total_impact > 10000) else "LOW"
        )

        analysis = MonthlyFailureAnalysis(
            month_year=month_year,
            total_events=len(month_events),
            events_by_category=events_by_category,
            trend_analysis={},
            top_failure_modes=top_modes[:10],
            systemic_issues=systemic,
            process_improvements=self._recommend_improvements(month_events),
            risk_assessment=risk_level,
        )

        return analysis

    def _generate_recommendations(self, events: List[FailureEvent]) -> List[str]:
        """Generate recommendations from events.

        Args:
            events: List of FailureEvent to analyze

        Returns:
            List of recommendations
        """
        recommendations = []

        # Count by category
        execution_failures = sum(1 for e in events if e.category == FailureCategory.EXECUTION_FAILURE)
        signal_failures = sum(1 for e in events if e.category == FailureCategory.SIGNAL_FAILURE)
        regime_shifts = sum(1 for e in events if e.category == FailureCategory.REGIME_SHIFT)

        if execution_failures > 2:
            recommendations.append(
                "Improve execution logic: review order routing and slippage models"
            )

        if signal_failures > 2:
            recommendations.append(
                "Backtest signal parameters: potential parameter drift detected"
            )

        if regime_shifts > 1:
            recommendations.append(
                "Enhance regime detection: consider faster adaptation strategies"
            )

        # Financial impact threshold
        total_impact = sum(e.financial_impact for e in events)
        if total_impact > 50000:
            recommendations.append(
                "Escalate to risk committee: cumulative weekly impact exceeds threshold"
            )

        return recommendations

    def _identify_systemic_issues(self, events: List[FailureEvent]) -> List[str]:
        """Identify systemic issues from event patterns.

        Args:
            events: List of FailureEvent

        Returns:
            List of systemic issue descriptions
        """
        issues = []

        # Same strategy multiple failures
        strategy_counts = {}
        for event in events:
            strategy_counts[event.strategy] = strategy_counts.get(event.strategy, 0) + 1

        for strategy, count in strategy_counts.items():
            if count >= 3:
                issues.append(f"Strategy '{strategy}' has {count} failures - may have systemic issue")

        # Recurring known mode
        mode_counts = {}
        for event in events:
            for mode_id in event.matched_failure_modes:
                mode_counts[mode_id] = mode_counts.get(mode_id, 0) + 1

        for mode_id, count in mode_counts.items():
            if count >= 2:
                mode = self.known_modes.get(mode_id)
                if mode:
                    issues.append(f"Known mode '{mode.name}' recurring {count} times")

        return issues

    def _recommend_improvements(self, events: List[FailureEvent]) -> List[str]:
        """Recommend process improvements.

        Args:
            events: List of FailureEvent

        Returns:
            List of improvement recommendations
        """
        improvements = []

        # Common themes
        major_events = [e for e in events if e.severity == FailureSeverity.MAJOR]
        if len(major_events) > 1:
            improvements.append("Implement pre-trade risk checks for major position changes")

        data_quality_issues = [e for e in events if e.category == FailureCategory.DATA_QUALITY]
        if len(data_quality_issues) > 0:
            improvements.append("Enhance data validation and monitoring pipelines")

        risk_violations = [e for e in events if e.category == FailureCategory.RISK_VIOLATION]
        if len(risk_violations) > 1:
            improvements.append("Review and tighten position limit enforcement")

        improvements.append("Conduct monthly failure mode review with trading team")

        return improvements

    def _load_known_modes(self) -> Dict[str, FailureMode]:
        """Load known failure modes from RADAR library.

        Returns:
            Dict of mode_id -> FailureMode
        """
        # Seed with common failure modes
        return {
            "slippage_regime": FailureMode(
                mode_id="slippage_regime",
                name="Regime-Dependent Slippage",
                category=FailureCategory.EXECUTION_FAILURE,
                description="Slippage increases dramatically in low-liquidity regimes",
                typical_loss=5000.0,
                frequency=0,
                mitigation_strategies=[
                    "Implement regime-aware order sizing",
                    "Use market-on-close orders in stress regimes",
                    "Reduce position sizes 25% during vol spikes",
                ],
            ),
            "correlation_hedge_failure": FailureMode(
                mode_id="correlation_hedge_failure",
                name="Correlation Hedge Breakdown",
                category=FailureCategory.CORRELATION_BREAKDOWN,
                description="Hedges fail when correlation structure changes",
                typical_loss=25000.0,
                frequency=0,
                mitigation_strategies=[
                    "Use dynamic correlation monitoring",
                    "Implement correlation breakeven monitoring",
                    "Reduce cross-correlated position sizes in stress regimes",
                ],
            ),
            "vol_spike_timing": FailureMode(
                mode_id="vol_spike_timing",
                name="Vol Spike Entry Timing",
                category=FailureCategory.SIGNAL_FAILURE,
                description="Signal timing fails to account for vol spike impact on Greeks",
                typical_loss=10000.0,
                frequency=0,
                mitigation_strategies=[
                    "Adjust Greeks calculations for realized vol",
                    "Add vol regime to entry filters",
                    "Pause entries during vol spikes >1.5x baseline",
                ],
            ),
        }

    def get_failure_report(self, n_recent: int = 100) -> Dict:
        """Get comprehensive failure report.

        Args:
            n_recent: Number of recent events to include

        Returns:
            Dict with failure analysis
        """
        recent_events = self.events[-n_recent:]

        return {
            "total_events": len(self.events),
            "recent_events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "category": e.category.value,
                    "severity": e.severity.value,
                    "strategy": e.strategy,
                    "instrument": e.instrument,
                    "financial_impact": e.financial_impact,
                    "is_known_mode": e.is_known_mode,
                    "matched_modes": e.matched_failure_modes,
                }
                for e in recent_events
            ],
            "known_modes": list(self.known_modes.keys()),
            "mode_frequencies": {
                mode_id: mode.frequency
                for mode_id, mode in self.known_modes.items()
            },
        }
