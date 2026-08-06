"""
Reporting Dashboard for Learning System
========================================

Generates daily and weekly reports showing:
- What changed in observations
- What improved in strategy performance
- What needs fixing (contradictions, low-confidence lessons)
- Key metrics trends
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class ReportingDashboard:
    """
    Generates comprehensive reports on learning system status.
    """

    def __init__(self):
        """Initialize dashboard."""
        self.daily_reports: List[Dict[str, Any]] = []
        self.weekly_reports: List[Dict[str, Any]] = []
        self.monthly_reports: List[Dict[str, Any]] = []

    def generate_daily_report(
        self,
        observations: Dict[str, Any],
        analysis: Dict[str, Any],
        lessons_extracted: List[str],
        contradictions_detected: int
    ) -> Dict[str, Any]:
        """
        Generate daily report summarizing observations and changes.

        Args:
            observations: Summary from ObservationCollector
            analysis: Analysis from AnalysisEngine
            lessons_extracted: List of new lessons
            contradictions_detected: Count of contradictions

        Returns:
            Daily report dict
        """
        report = {
            "report_type": "daily",
            "timestamp": datetime.utcnow().isoformat(),
            "date": datetime.utcnow().date().isoformat(),
            "observation_summary": {
                "total_trades": observations.get("total_trades", 0),
                "winning_trades": observations.get("winning_trades", 0),
                "losing_trades": observations.get("losing_trades", 0),
                "net_pnl": observations.get("total_pnl", 0.0),
                "daily_win_rate": (
                    observations.get("winning_trades", 0) /
                    observations.get("total_trades", 1)
                ) if observations.get("total_trades", 0) > 0 else 0.0,
                "current_regime": observations.get("current_regime", "unknown")
            },
            "escalations": {
                "active_count": observations.get("active_escalations", 0),
                "total_today": 0  # Filtered by date
            },
            "learning_activity": {
                "new_lessons": len(lessons_extracted),
                "contradictions_detected": contradictions_detected,
                "lessons_list": lessons_extracted
            },
            "strategy_highlights": self._extract_strategy_highlights(analysis),
            "greek_insights": self._extract_greek_insights(analysis),
            "action_items": self._generate_action_items(
                observations, analysis, contradictions_detected
            )
        }

        self.daily_reports.append(report)
        return report

    def generate_weekly_report(
        self,
        daily_reports: List[Dict[str, Any]],
        learning_engine_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate weekly summary from daily reports.

        Args:
            daily_reports: List of daily reports from past 7 days
            learning_engine_stats: Statistics from LearningEngine

        Returns:
            Weekly report dict
        """
        if not daily_reports:
            return {}

        # Aggregate metrics
        total_trades = sum(
            r["observation_summary"]["total_trades"]
            for r in daily_reports
        )
        total_pnl = sum(
            r["observation_summary"]["net_pnl"]
            for r in daily_reports
        )
        total_wins = sum(
            r["observation_summary"]["winning_trades"]
            for r in daily_reports
        )
        avg_daily_wr = (
            sum(r["observation_summary"]["daily_win_rate"] for r in daily_reports) /
            len(daily_reports)
        )

        # Identify trends
        pnls = [r["observation_summary"]["net_pnl"] for r in daily_reports]
        trend = "improving" if pnls[-1] > pnls[0] else "declining" if pnls[-1] < pnls[0] else "stable"

        report = {
            "report_type": "weekly",
            "timestamp": datetime.utcnow().isoformat(),
            "week_ending": (datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())).date().isoformat(),
            "aggregated_metrics": {
                "total_trades": total_trades,
                "total_wins": total_wins,
                "total_losses": total_trades - total_wins,
                "weekly_win_rate": total_wins / total_trades if total_trades > 0 else 0.0,
                "net_pnl": total_pnl,
                "avg_daily_pnl": total_pnl / len(daily_reports) if daily_reports else 0.0,
                "avg_daily_win_rate": avg_daily_wr,
                "trend": trend
            },
            "learning_progress": {
                "lessons_created": learning_engine_stats.get("lessons_created", 0),
                "lessons_promoted": learning_engine_stats.get("lessons_promoted", 0),
                "lessons_demoted": learning_engine_stats.get("lessons_demoted", 0),
                "contradictions_resolved": learning_engine_stats.get("contradictions_resolved", 0),
                "kb_updates": learning_engine_stats.get("kb_updates", 0)
            },
            "strategy_performance_changes": self._calculate_performance_changes(daily_reports),
            "best_performing_strategy": self._identify_best_strategy(daily_reports),
            "worst_performing_strategy": self._identify_worst_strategy(daily_reports),
            "key_findings": self._extract_weekly_findings(daily_reports, learning_engine_stats),
            "recommendations": self._generate_weekly_recommendations(
                learning_engine_stats, trend
            )
        }

        self.weekly_reports.append(report)
        return report

    def generate_monthly_report(
        self,
        weekly_reports: List[Dict[str, Any]],
        kb_update_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate monthly summary.

        Args:
            weekly_reports: List of weekly reports
            kb_update_summary: KB update summary from LearningEngine

        Returns:
            Monthly report dict
        """
        if not weekly_reports:
            return {}

        # Aggregate weekly data
        total_trades = sum(
            w["aggregated_metrics"]["total_trades"]
            for w in weekly_reports
        )
        total_pnl = sum(
            w["aggregated_metrics"]["net_pnl"]
            for w in weekly_reports
        )
        total_wins = sum(
            w["aggregated_metrics"]["total_wins"]
            for w in weekly_reports
        )
        monthly_wr = total_wins / total_trades if total_trades > 0 else 0.0

        report = {
            "report_type": "monthly",
            "timestamp": datetime.utcnow().isoformat(),
            "month": datetime.utcnow().strftime("%Y-%m"),
            "monthly_performance": {
                "total_trades": total_trades,
                "monthly_win_rate": monthly_wr,
                "net_pnl": total_pnl,
                "avg_trade_pnl": total_pnl / total_trades if total_trades > 0 else 0.0,
                "best_week": max(weekly_reports, key=lambda w: w["aggregated_metrics"]["net_pnl"]),
                "worst_week": min(weekly_reports, key=lambda w: w["aggregated_metrics"]["net_pnl"])
            },
            "kb_updates": kb_update_summary.get("kb_update_history", []),
            "lessons_matured": kb_update_summary.get("promoted_to_kb", []),
            "lessons_expired": kb_update_summary.get("demoted_lessons", []),
            "contradictions_summary": {
                "total_detected": kb_update_summary.get("contradictions_detected", 0),
                "total_resolved": kb_update_summary.get("contradictions_resolved", 0),
                "pending_resolution": (
                    kb_update_summary.get("contradictions_detected", 0) -
                    kb_update_summary.get("contradictions_resolved", 0)
                )
            },
            "strategy_evolution": self._track_strategy_evolution(weekly_reports),
            "regime_analysis": self._analyze_regime_performance(weekly_reports),
            "kb_health_check": self._kb_health_check(kb_update_summary),
            "strategic_recommendations": self._generate_monthly_strategic_recs(
                kb_update_summary
            )
        }

        self.monthly_reports.append(report)
        return report

    def _extract_strategy_highlights(self, analysis: Dict[str, Any]) -> List[str]:
        """Extract top strategy performers from analysis."""
        highlights = []
        strategy_perf = analysis.get("strategy_performance_by_regime", {})

        for strategy, regimes in strategy_perf.items():
            best_regime = max(
                regimes.items(),
                key=lambda x: x[1].get("win_rate", 0),
                default=None
            )
            if best_regime and best_regime[1].get("win_rate", 0) > 0.55:
                highlights.append(
                    f"{strategy.replace('_', ' ').title()} excels in "
                    f"{best_regime[0].replace('_', ' ')} "
                    f"({best_regime[1]['win_rate']:.0%} win rate)"
                )

        return highlights

    def _extract_greek_insights(self, analysis: Dict[str, Any]) -> List[str]:
        """Extract Greek impact insights."""
        insights = []
        greek_impact = analysis.get("greek_impact_analysis", {})

        for greek, data in greek_impact.items():
            if data.get("impact") == "positive" and data.get("correlation", 0) > 0.3:
                insights.append(
                    f"{greek.capitalize()} has positive correlation with returns "
                    f"({data['correlation']:.2f})"
                )

        return insights

    def _generate_action_items(
        self,
        observations: Dict[str, Any],
        analysis: Dict[str, Any],
        contradictions: int
    ) -> List[Dict[str, str]]:
        """Generate action items based on today's data."""
        items = []

        # Check for escalations
        if observations.get("active_escalations", 0) > 0:
            items.append({
                "priority": "high",
                "action": f"Review {observations['active_escalations']} active escalations",
                "category": "risk"
            })

        # Check for contradictions
        if contradictions > 0:
            items.append({
                "priority": "medium",
                "action": f"Resolve {contradictions} contradiction(s) in learned patterns",
                "category": "learning"
            })

        # Check for low win rate
        if observations.get("total_trades", 0) > 0:
            wr = observations.get("winning_trades", 0) / observations.get("total_trades", 1)
            if wr < 0.45:
                items.append({
                    "priority": "high",
                    "action": "Win rate below 45% - review strategy parameters",
                    "category": "strategy"
                })

        return items

    def _calculate_performance_changes(self, daily_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate week-over-week performance changes."""
        if len(daily_reports) < 2:
            return {}

        first_day = daily_reports[0]["observation_summary"]
        last_day = daily_reports[-1]["observation_summary"]

        wr_change = last_day["daily_win_rate"] - first_day["daily_win_rate"]
        pnl_change = last_day["net_pnl"] - first_day["net_pnl"]

        return {
            "win_rate_change": wr_change,
            "win_rate_trend": "improving" if wr_change > 0 else "declining" if wr_change < 0 else "flat",
            "pnl_change": pnl_change,
            "pnl_trend": "improving" if pnl_change > 0 else "declining" if pnl_change < 0 else "flat"
        }

    def _identify_best_strategy(self, daily_reports: List[Dict[str, Any]]) -> Optional[str]:
        """Identify best performing strategy across the week."""
        # Placeholder: would aggregate from all daily reports
        return None

    def _identify_worst_strategy(self, daily_reports: List[Dict[str, Any]]) -> Optional[str]:
        """Identify worst performing strategy across the week."""
        # Placeholder: would aggregate from all daily reports
        return None

    def _extract_weekly_findings(
        self,
        daily_reports: List[Dict[str, Any]],
        learning_stats: Dict[str, Any]
    ) -> List[str]:
        """Extract key findings from the week."""
        findings = []

        # Calculate aggregate stats
        total_trades = sum(
            r["observation_summary"]["total_trades"]
            for r in daily_reports
        )
        if total_trades > 0:
            findings.append(f"Executed {total_trades} trades this week")

        # Learning activity
        total_lessons = learning_stats.get("lessons_created", 0)
        if total_lessons > 0:
            findings.append(f"Extracted {total_lessons} new lessons from observations")

        return findings

    def _generate_weekly_recommendations(
        self,
        learning_stats: Dict[str, Any],
        trend: str
    ) -> List[str]:
        """Generate weekly action recommendations."""
        recs = []

        if trend == "declining":
            recs.append("Performance declining - consider parameter adjustments or strategy rotation")

        if learning_stats.get("contradictions_resolved", 0) > 0:
            recs.append("Review resolved contradictions to update strategy understanding")

        if learning_stats.get("kb_updates", 0) > 0:
            recs.append("Knowledge base was updated - validate new relationships")

        return recs

    def _track_strategy_evolution(self, weekly_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Track how strategy performance evolves over weeks."""
        return {"data": "placeholder"}

    def _analyze_regime_performance(self, weekly_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance in each market regime."""
        return {"data": "placeholder"}

    def _kb_health_check(self, kb_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Check health of knowledge base."""
        total_lessons = (
            len(kb_summary.get("promoted_to_kb", [])) +
            len(kb_summary.get("demoted_lessons", []))
        )

        return {
            "total_lessons": total_lessons,
            "active_lessons": len(kb_summary.get("promoted_to_kb", [])),
            "expired_lessons": len(kb_summary.get("demoted_lessons", [])),
            "avg_confidence": kb_summary.get("avg_confidence", 0.0),
            "health_status": "good" if kb_summary.get("avg_confidence", 0.0) > 0.70 else "fair"
        }

    def _generate_monthly_strategic_recs(
        self,
        kb_summary: Dict[str, Any]
    ) -> List[str]:
        """Generate strategic recommendations based on monthly summary."""
        recs = []

        avg_conf = kb_summary.get("avg_confidence", 0.0)
        if avg_conf < 0.65:
            recs.append("Average lesson confidence below target - increase evidence collection")

        contradictions = kb_summary.get("contradictions_detected", 0)
        if contradictions > len(kb_summary.get("promoted_to_kb", [])):
            recs.append("High contradiction rate - review knowledge extraction process")

        return recs

    def export_reports(self, filepath: str) -> bool:
        """Export all reports to JSON."""
        try:
            export = {
                "exported_at": datetime.utcnow().isoformat(),
                "daily_reports": self.daily_reports,
                "weekly_reports": self.weekly_reports,
                "monthly_reports": self.monthly_reports
            }

            with open(filepath, 'w') as f:
                json.dump(export, f, indent=2)

            logger.info(
                f"Exported {len(self.daily_reports)} daily, "
                f"{len(self.weekly_reports)} weekly, "
                f"{len(self.monthly_reports)} monthly reports to {filepath}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to export reports: {e}")
            return False

    def get_latest_daily_summary(self) -> Optional[Dict[str, Any]]:
        """Get the most recent daily report."""
        return self.daily_reports[-1] if self.daily_reports else None

    def get_latest_weekly_summary(self) -> Optional[Dict[str, Any]]:
        """Get the most recent weekly report."""
        return self.weekly_reports[-1] if self.weekly_reports else None

    def get_latest_monthly_summary(self) -> Optional[Dict[str, Any]]:
        """Get the most recent monthly report."""
        return self.monthly_reports[-1] if self.monthly_reports else None
