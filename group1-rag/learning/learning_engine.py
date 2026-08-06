"""
Learning Engine for Trading System
===================================

Extracts lessons from analysis and updates knowledge graph.

Features:
- Conditional lesson extraction ("gamma scalping works best when vol < 20%")
- Confidence score management with temporal decay
- Contradiction detection and resolution
- Monthly KB updates with confidence thresholds
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class Lesson:
    """Represents a learned lesson from observations."""

    def __init__(
        self,
        lesson_id: str,
        statement: str,
        condition: str,
        confidence: float,
        evidence_count: int,
        first_observed: str,
        last_updated: str,
        supporting_metrics: Dict[str, Any],
        contradictions: Optional[List[str]] = None
    ):
        """
        Initialize lesson.

        Args:
            lesson_id: Unique identifier
            statement: Lesson statement (e.g., "gamma scalping works best when vol<20%")
            condition: Condition context (e.g., "vol<20%")
            confidence: Confidence score [0-1]
            evidence_count: Number of observations supporting this lesson
            first_observed: Timestamp when lesson was first extracted
            last_updated: Timestamp when lesson was last confirmed/updated
            supporting_metrics: Dict of metrics supporting this lesson
            contradictions: List of contradicting lessons
        """
        self.lesson_id = lesson_id
        self.statement = statement
        self.condition = condition
        self.confidence = max(0.0, min(1.0, confidence))
        self.evidence_count = evidence_count
        self.first_observed = first_observed
        self.last_updated = last_updated
        self.supporting_metrics = supporting_metrics
        self.contradictions = contradictions or []
        self.decay_rate = 0.98  # 2% decay per week if not reinforced

    def apply_decay(self) -> float:
        """
        Apply confidence decay if lesson hasn't been updated recently.

        Returns:
            Updated confidence after decay
        """
        last_update = datetime.fromisoformat(self.last_updated)
        weeks_elapsed = (datetime.utcnow() - last_update).days / 7.0

        if weeks_elapsed > 0:
            self.confidence *= (self.decay_rate ** weeks_elapsed)

        return self.confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert lesson to dictionary."""
        return {
            "lesson_id": self.lesson_id,
            "statement": self.statement,
            "condition": self.condition,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "first_observed": self.first_observed,
            "last_updated": self.last_updated,
            "supporting_metrics": self.supporting_metrics,
            "contradictions": self.contradictions,
            "decay_rate": self.decay_rate
        }


class LearningEngine:
    """
    Manages lesson extraction, KB updates, and confidence scoring.
    """

    def __init__(self):
        """Initialize learning engine."""
        self.lessons: Dict[str, Lesson] = {}
        self.kb_update_history: List[Dict[str, Any]] = []
        self.contradiction_log: List[Dict[str, Any]] = []

    def extract_lessons_from_analysis(
        self,
        analysis: Dict[str, Any]
    ) -> List[Lesson]:
        """
        Extract conditional lessons from analysis output.

        Examples:
        - "Gamma scalping has 65% win rate when vol > 20%"
        - "Delta hedging works best in bull_high_vol regime"
        - "Theta decay is positive when vega is high"
        """
        lessons = []

        # Lesson 1: Strategy-regime combinations
        strategy_perf = analysis.get("strategy_performance_by_regime", {})
        for strategy, regimes in strategy_perf.items():
            for regime, metrics in regimes.items():
                if metrics.get("trades_count", 0) >= 5:  # Minimum evidence
                    win_rate = metrics.get("win_rate", 0)
                    if win_rate > 0.55:  # Significant performance
                        lesson = self._create_lesson(
                            f"{strategy}_in_{regime}",
                            f"{strategy.replace('_', ' ').title()} achieves {win_rate:.0%} win rate in {regime.replace('_', ' ')}",
                            f"regime={regime}",
                            confidence=min(0.95, 0.5 + win_rate * 0.5),  # confidence scales with win rate
                            evidence_count=metrics.get("trades_count", 0),
                            supporting_metrics=metrics
                        )
                        lessons.append(lesson)

        # Lesson 2: Greek impact
        greek_impact = analysis.get("greek_impact_analysis", {})
        for greek, data in greek_impact.items():
            impact = data.get("impact")
            if impact != "neutral":
                correlation = data.get("correlation", 0)
                confidence = min(0.90, 0.5 + abs(correlation) * 0.5)

                lesson = self._create_lesson(
                    f"greek_{greek}_impact",
                    f"High {greek} correlates with {'+' if correlation > 0 else '-'} performance "
                    f"(correlation: {correlation:.2f})",
                    f"{greek}>{data.get('avg_greek_value', 0):.2f}",
                    confidence=confidence,
                    evidence_count=100,  # Aggregate
                    supporting_metrics=data
                )
                lessons.append(lesson)

        # Lesson 3: Volatility environment lessons
        vol_impact = analysis.get("volatility_impact", {})
        low_vol_wr = vol_impact.get("low_vol_performance", {}).get("win_rate", 0)
        high_vol_wr = vol_impact.get("high_vol_performance", {}).get("win_rate", 0)

        if low_vol_wr > high_vol_wr * 1.15:
            lesson = self._create_lesson(
                "strategies_prefer_low_vol",
                f"Strategies perform better in low-volatility environments "
                f"({low_vol_wr:.0%} vs {high_vol_wr:.0%} win rate)",
                "vol < median",
                confidence=0.75,
                evidence_count=200,
                supporting_metrics=vol_impact
            )
            lessons.append(lesson)

        elif high_vol_wr > low_vol_wr * 1.15:
            lesson = self._create_lesson(
                "strategies_prefer_high_vol",
                f"Strategies perform better in high-volatility environments "
                f"({high_vol_wr:.0%} vs {low_vol_wr:.0%} win rate)",
                "vol > median",
                confidence=0.75,
                evidence_count=200,
                supporting_metrics=vol_impact
            )
            lessons.append(lesson)

        return lessons

    def _create_lesson(
        self,
        lesson_id: str,
        statement: str,
        condition: str,
        confidence: float,
        evidence_count: int,
        supporting_metrics: Dict[str, Any]
    ) -> Lesson:
        """Helper to create and store a lesson."""
        lesson = Lesson(
            lesson_id=lesson_id,
            statement=statement,
            condition=condition,
            confidence=confidence,
            evidence_count=evidence_count,
            first_observed=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
            supporting_metrics=supporting_metrics
        )
        self.lessons[lesson_id] = lesson
        return lesson

    def update_kb_relationships(
        self,
        kg_client: Any,  # KGClient from kg_client.py
        lessons: List[Lesson]
    ) -> Dict[str, Any]:
        """
        Update knowledge graph relationships based on learned lessons.

        For each high-confidence lesson, creates or updates KG relationships.
        """
        update_summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "lessons_processed": len(lessons),
            "relationships_created": 0,
            "relationships_updated": 0,
            "contradictions_detected": 0,
            "updates": []
        }

        for lesson in lessons:
            if lesson.confidence < 0.60:  # Minimum confidence threshold for KB update
                logger.info(f"Skipping lesson {lesson.lesson_id} (confidence too low: {lesson.confidence:.2f})")
                continue

            # Parse lesson to determine what nodes to create/link
            update_result = self._update_kg_from_lesson(kg_client, lesson)
            update_summary["updates"].append(update_result)

            if update_result["type"] == "created":
                update_summary["relationships_created"] += 1
            elif update_result["type"] == "updated":
                update_summary["relationships_updated"] += 1
            elif update_result["type"] == "contradiction":
                update_summary["contradictions_detected"] += 1

        self.kb_update_history.append(update_summary)
        return update_summary

    def _update_kg_from_lesson(
        self,
        kg_client: Any,
        lesson: Lesson
    ) -> Dict[str, Any]:
        """
        Update KG based on a single lesson.

        Returns dict describing the update.
        """
        result = {
            "lesson_id": lesson.lesson_id,
            "type": "skipped",
            "message": "",
            "source_id": None,
            "target_id": None,
            "relationship_type": None
        }

        try:
            # Parse lesson statement to extract entities
            if "gamma" in lesson.statement.lower() and "scalping" in lesson.statement.lower():
                # Create: Strategy (gamma_scalping) --applies_to--> MarketRegime (if vol < 20%)
                strategy = kg_client.add_node(
                    "Strategy", "Gamma Scalping",
                    {"description": "Profit from gamma while managing delta"}
                )

                if "vol" in lesson.condition.lower():
                    regime = kg_client.add_node(
                        "MarketRegime", "Low Volatility",
                        {"characteristics": "vol < 20%", "volatility_level": "low"}
                    )

                    if strategy and regime:
                        rel = kg_client.add_relationship(
                            strategy.id, "applies_to", regime.id,
                            confidence=lesson.confidence,
                            evidence=lesson.statement,
                            metadata={
                                "lesson_id": lesson.lesson_id,
                                "evidence_count": lesson.evidence_count,
                                "learned_at": lesson.last_updated
                            }
                        )
                        if rel:
                            result["type"] = "created"
                            result["source_id"] = strategy.id
                            result["target_id"] = regime.id
                            result["relationship_type"] = "applies_to"

            elif "greek" in lesson.lesson_id:
                # Create: Greeks --affects--> Position or Strategy
                greek_name = lesson.statement.split()[1].capitalize()
                greek = kg_client.add_node(
                    "Greeks", greek_name,
                    {"definition": f"Impact analysis for {greek_name}"}
                )

                if greek:
                    result["type"] = "created"
                    result["source_id"] = greek.id

            elif "strategies_prefer" in lesson.lesson_id:
                # Mark all strategies' volatility preference
                strategies = ["Gamma Scalping", "Vol Arbitrage", "Delta Hedging"]
                for strat_name in strategies:
                    strat = kg_client.get_node_by_name("Strategy", strat_name)
                    if not strat:
                        strat = kg_client.add_node(
                            "Strategy", strat_name,
                            {"description": f"{strat_name} strategy"}
                        )

                    vol_level = "Low Volatility" if "low-vol" in lesson.lesson_id else "High Volatility"
                    vol_regime = kg_client.add_node(
                        "MarketRegime", vol_level,
                        {"volatility_level": vol_level.lower().replace(" ", "_")}
                    )

                    if strat and vol_regime:
                        rel = kg_client.add_relationship(
                            strat.id, "applies_to", vol_regime.id,
                            confidence=lesson.confidence,
                            evidence=lesson.statement,
                            metadata={"lesson_id": lesson.lesson_id}
                        )
                        if rel:
                            result["type"] = "created"

        except Exception as e:
            logger.error(f"Failed to update KB for lesson {lesson.lesson_id}: {e}")
            result["type"] = "error"
            result["message"] = str(e)

        return result

    def detect_contradictions(self, new_lesson: Lesson) -> List[str]:
        """
        Detect if new lesson contradicts existing knowledge.

        Returns list of contradicting lesson IDs.
        """
        contradictions = []

        for existing_lesson_id, existing_lesson in self.lessons.items():
            # Check for direct contradictions
            if self._lessons_contradict(new_lesson, existing_lesson):
                contradictions.append(existing_lesson_id)
                # Log contradiction
                self.contradiction_log.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "new_lesson": new_lesson.lesson_id,
                    "existing_lesson": existing_lesson_id,
                    "new_statement": new_lesson.statement,
                    "existing_statement": existing_lesson.statement,
                    "new_confidence": new_lesson.confidence,
                    "existing_confidence": existing_lesson.confidence,
                    "resolution": "pending"
                })

        return contradictions

    def _lessons_contradict(self, lesson1: Lesson, lesson2: Lesson) -> bool:
        """
        Determine if two lessons contradict each other.

        Simple heuristic: contradictions if they mention same entities but opposite outcomes.
        """
        # Extract key entities
        entities1 = set(lesson1.statement.lower().split())
        entities2 = set(lesson2.statement.lower().split())

        overlap = entities1.intersection(entities2)

        if len(overlap) < 2:
            return False

        # Check for opposing sentiment
        positive_words = {"best", "good", "high", "better", "achieves", "correlates"}
        negative_words = {"worst", "bad", "low", "worse", "fails", "contradicts"}

        sentiment1_pos = bool(entities1.intersection(positive_words))
        sentiment2_pos = bool(entities2.intersection(positive_words))
        sentiment1_neg = bool(entities1.intersection(negative_words))
        sentiment2_neg = bool(entities2.intersection(negative_words))

        if (sentiment1_pos and sentiment2_neg) or (sentiment1_neg and sentiment2_pos):
            return True

        return False

    def resolve_contradictions(self, contradiction_id: int) -> bool:
        """
        Resolve a contradiction by favoring higher-confidence lesson.
        """
        if 0 <= contradiction_id < len(self.contradiction_log):
            entry = self.contradiction_log[contradiction_id]
            new_conf = self.lessons.get(entry["new_lesson"], Lesson(
                "", "", "", 0.0, 0, "", "", {}
            )).confidence
            existing_conf = self.lessons.get(entry["existing_lesson"], Lesson(
                "", "", "", 0.0, 0, "", "", {}
            )).confidence

            if new_conf > existing_conf:
                self.contradiction_log[contradiction_id]["resolution"] = "new_lesson_favored"
            else:
                self.contradiction_log[contradiction_id]["resolution"] = "existing_lesson_maintained"

            return True

        return False

    def apply_confidence_decay(self):
        """
        Apply decay to all lessons not recently reinforced.

        Decay = 2% per week if not updated.
        """
        for lesson in self.lessons.values():
            old_confidence = lesson.confidence
            new_confidence = lesson.apply_decay()
            if new_confidence != old_confidence:
                logger.info(
                    f"Lesson {lesson.lesson_id}: confidence {old_confidence:.3f} -> {new_confidence:.3f}"
                )

    def get_monthly_kb_update_report(self) -> Dict[str, Any]:
        """
        Generate monthly KB update report.

        Includes:
        - Lessons promoted to KB (confidence >= 0.75)
        - Lessons demoted (confidence < 0.60)
        - Contradictions resolved
        - KB statistics
        """
        high_confidence = [
            l for l in self.lessons.values()
            if l.confidence >= 0.75
        ]
        low_confidence = [
            l for l in self.lessons.values()
            if l.confidence < 0.60
        ]

        report = {
            "report_timestamp": datetime.utcnow().isoformat(),
            "total_lessons": len(self.lessons),
            "high_confidence_lessons": len(high_confidence),
            "low_confidence_lessons": len(low_confidence),
            "avg_confidence": sum(l.confidence for l in self.lessons.values()) / len(self.lessons) if self.lessons else 0.0,
            "promoted_to_kb": [l.to_dict() for l in high_confidence],
            "demoted_lessons": [l.to_dict() for l in low_confidence],
            "contradictions_detected": len(self.contradiction_log),
            "contradictions_resolved": sum(
                1 for c in self.contradiction_log
                if c.get("resolution") != "pending"
            ),
            "kb_update_history": self.kb_update_history[-4:]  # Last 4 updates
        }

        return report

    def export_lessons(self, filepath: str) -> bool:
        """Export all lessons to JSON."""
        try:
            export = {
                "exported_at": datetime.utcnow().isoformat(),
                "lessons": [l.to_dict() for l in self.lessons.values()],
                "contradictions": self.contradiction_log,
                "kb_update_history": self.kb_update_history
            }

            with open(filepath, 'w') as f:
                json.dump(export, f, indent=2)

            logger.info(f"Exported {len(self.lessons)} lessons to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to export lessons: {e}")
            return False

    def import_lessons(self, filepath: str) -> bool:
        """Import lessons from JSON."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            for lesson_dict in data.get("lessons", []):
                # Remove decay_rate if present (it's set in __init__, not constructor)
                lesson_dict_copy = lesson_dict.copy()
                lesson_dict_copy.pop("decay_rate", None)
                lesson = Lesson(**lesson_dict_copy)
                self.lessons[lesson.lesson_id] = lesson

            self.contradiction_log = data.get("contradictions", [])
            self.kb_update_history = data.get("kb_update_history", [])

            logger.info(f"Imported {len(self.lessons)} lessons from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to import lessons: {e}")
            return False
