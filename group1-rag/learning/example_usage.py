"""
Example Usage: Closed-Loop Learning System
===========================================

Demonstrates the complete cycle from observation through reporting.
"""

import json
import logging
from datetime import datetime

from observation_collector import ObservationCollector, MockObservationStream, TradeStatus
from analysis_engine import AnalysisEngine
from learning_engine import LearningEngine
from reporting_dashboard import ReportingDashboard

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"{title:^80}")
    print(f"{'=' * 80}\n")


def example_daily_cycle():
    """
    Example: Daily observation -> analysis -> learning -> report cycle.
    """
    print_section("DAILY LEARNING CYCLE")

    # Step 1: Collect observations
    print("1. COLLECTING OBSERVATIONS")
    print("-" * 80)

    collector = ObservationCollector()
    stream = MockObservationStream(seed=42)

    # Generate mock market activity
    stream.generate_mock_trades(collector, count=25)
    stream.generate_mock_regime_shifts(collector, count=2)
    stream.generate_mock_escalations(collector, count=1)

    summary = collector.get_summary()
    print(f"   Trades executed: {summary['total_trades']}")
    print(f"   Win rate: {summary['win_rate']:.1%}")
    print(f"   Net P&L: ${summary['total_pnl']:,.2f}")
    print(f"   Current regime: {summary['current_regime']}")
    print(f"   Active escalations: {summary['active_escalations']}")

    # Step 2: Analyze observations
    print("\n2. ANALYZING OBSERVATIONS")
    print("-" * 80)

    analysis_engine = AnalysisEngine()
    analysis = analysis_engine.generate_analysis_summary(
        collector.trades,
        collector.regime_shifts,
        collector.escalations
    )

    print(f"   Strategies analyzed: {len(analysis['strategy_performance_by_regime'])}")
    print(f"   Key insights found: {len(analysis['key_insights'])}")
    for insight in analysis['key_insights'][:3]:
        print(f"     • {insight}")

    # Step 3: Extract lessons
    print("\n3. EXTRACTING LESSONS")
    print("-" * 80)

    learning_engine = LearningEngine()
    lessons = learning_engine.extract_lessons_from_analysis(analysis)

    print(f"   Lessons extracted: {len(lessons)}")
    for i, lesson in enumerate(lessons[:5], 1):
        print(f"     {i}. {lesson.statement}")
        print(f"        Confidence: {lesson.confidence:.2f} | Evidence: {lesson.evidence_count}")

    # Step 4: Generate daily report
    print("\n4. GENERATING DAILY REPORT")
    print("-" * 80)

    dashboard = ReportingDashboard()
    daily_report = dashboard.generate_daily_report(
        summary,
        analysis,
        [l.lesson_id for l in lessons],
        len(learning_engine.contradiction_log)
    )

    print(f"   Report timestamp: {daily_report['timestamp']}")
    print(f"   Daily win rate: {daily_report['observation_summary']['daily_win_rate']:.1%}")
    print(f"   Action items: {len(daily_report['action_items'])}")
    for item in daily_report['action_items'][:3]:
        print(f"     [{item['priority'].upper()}] {item['action']}")

    return collector, analysis, learning_engine, dashboard


def example_weekly_aggregation():
    """
    Example: Aggregate daily reports into weekly summary.
    """
    print_section("WEEKLY AGGREGATION")

    # Simulate 5 days of data
    daily_reports = []
    dashboard = ReportingDashboard()

    for day in range(5):
        print(f"Day {day + 1}...")
        report = dashboard.generate_daily_report(
            {
                "total_trades": 15 + day * 2,
                "winning_trades": 9 + day,
                "losing_trades": 6 - day,
                "total_pnl": 1200.0 + day * 150,
                "active_escalations": max(0, 2 - day),
                "current_regime": "bull_low_vol"
            },
            {},
            [f"lesson_{day}_{i}" for i in range(3)],
            0
        )
        daily_reports.append(report)

    # Generate weekly summary
    learning_stats = {
        "lessons_created": 12,
        "lessons_promoted": 5,
        "lessons_demoted": 1,
        "contradictions_resolved": 1,
        "kb_updates": 3
    }

    weekly_report = dashboard.generate_weekly_report(daily_reports, learning_stats)

    print("\nWEEKLY PERFORMANCE METRICS:")
    print("-" * 80)
    metrics = weekly_report["aggregated_metrics"]
    print(f"   Total trades: {metrics['total_trades']}")
    print(f"   Weekly win rate: {metrics['weekly_win_rate']:.1%}")
    print(f"   Net P&L: ${metrics['net_pnl']:,.2f}")
    print(f"   Trend: {metrics['trend']}")

    print("\nLEARNING PROGRESS:")
    print("-" * 80)
    lp = weekly_report["learning_progress"]
    print(f"   Lessons created: {lp['lessons_created']}")
    print(f"   Lessons promoted to KB: {lp['lessons_promoted']}")
    print(f"   Contradictions resolved: {lp['contradictions_resolved']}")

    print("\nWEEKLY RECOMMENDATIONS:")
    print("-" * 80)
    for i, rec in enumerate(weekly_report['recommendations'], 1):
        print(f"   {i}. {rec}")

    return weekly_report


def example_monthly_kb_update():
    """
    Example: Monthly knowledge base update with confidence scoring.
    """
    print_section("MONTHLY KB UPDATE")

    learning_engine = LearningEngine()

    # Simulate accumulation of lessons over a month
    print("Simulating 4 weeks of learning...")

    lesson_confidence_levels = [
        (0.95, "high_confidence"),
        (0.88, "medium_high_confidence"),
        (0.78, "medium_confidence"),
        (0.68, "low_medium_confidence"),
        (0.55, "low_confidence"),
        (0.45, "very_low_confidence")
    ]

    for conf, label in lesson_confidence_levels:
        learning_engine.lessons[label] = __import__('learning_engine').Lesson(
            lesson_id=label,
            statement=f"Test lesson {label}",
            condition="test",
            confidence=conf,
            evidence_count=100 + int(conf * 100),
            first_observed=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
            supporting_metrics={}
        )

    # Apply decay to simulate aging
    learning_engine.apply_confidence_decay()

    # Generate monthly report
    kb_report = learning_engine.get_monthly_kb_update_report()

    print("\nMONTHLY KB HEALTH:")
    print("-" * 80)
    print(f"   Total lessons: {kb_report['total_lessons']}")
    print(f"   High confidence lessons: {kb_report['high_confidence_lessons']}")
    print(f"   Low confidence lessons: {kb_report['low_confidence_lessons']}")
    print(f"   Average confidence: {kb_report['avg_confidence']:.3f}")

    print("\nLESSONS PROMOTED TO KB (confidence >= 0.75):")
    print("-" * 80)
    for lesson in kb_report['promoted_to_kb'][:3]:
        print(f"   • {lesson['statement'][:60]}...")
        print(f"     Confidence: {lesson['confidence']:.3f}")

    print("\nLESSONS DEMOTED (confidence < 0.60):")
    print("-" * 80)
    for lesson in kb_report['demoted_lessons'][:2]:
        print(f"   • {lesson['statement'][:60]}...")
        print(f"     Confidence: {lesson['confidence']:.3f}")

    return kb_report


def example_contradiction_detection():
    """
    Example: Detecting and resolving contradictions.
    """
    print_section("CONTRADICTION DETECTION")

    learning_engine = LearningEngine()

    # Create two contradictory lessons
    lesson1 = __import__('learning_engine').Lesson(
        lesson_id="strategy_works_high_vol",
        statement="Gamma scalping achieves 70% win rate in high volatility",
        condition="vol > 25%",
        confidence=0.82,
        evidence_count=150,
        first_observed=datetime.utcnow().isoformat(),
        last_updated=datetime.utcnow().isoformat(),
        supporting_metrics={"win_rate": 0.70, "trades": 150}
    )

    lesson2 = __import__('learning_engine').Lesson(
        lesson_id="strategy_fails_high_vol",
        statement="Gamma scalping fails with 35% win rate in high volatility",
        condition="vol > 25%",
        confidence=0.78,
        evidence_count=140,
        first_observed=datetime.utcnow().isoformat(),
        last_updated=datetime.utcnow().isoformat(),
        supporting_metrics={"win_rate": 0.35, "trades": 140}
    )

    learning_engine.lessons["1"] = lesson1

    print("Detecting contradictions...")
    contradictions = learning_engine.detect_contradictions(lesson2)

    print("\nCONTRADICTION ANALYSIS:")
    print("-" * 80)
    print(f"   Contradictions found: {len(contradictions)}")

    for i, esc in enumerate(learning_engine.contradiction_log, 1):
        print(f"\n   Contradiction {i}:")
        print(f"     Existing: {esc['existing_statement'][:50]}...")
        print(f"     New:      {esc['new_statement'][:50]}...")
        print(f"     Confidence: {esc['existing_confidence']:.2f} vs {esc['new_confidence']:.2f}")
        print(f"     Status: {esc['resolution']}")

    print("\nRESOLUTION STRATEGY:")
    print("-" * 80)
    print("   ✓ Favor higher-confidence lesson")
    print("   ✓ Require additional evidence for both lessons")
    print("   ✓ Investigate regime/market conditions differences")
    print("   ✓ Update KB only after contradiction resolved")


def example_confidence_decay():
    """
    Example: Confidence decay over time without reinforcement.
    """
    print_section("CONFIDENCE DECAY OVER TIME")

    from datetime import timedelta

    learning_engine = LearningEngine()

    # Create lessons at different ages
    ages_days = [0, 7, 14, 21, 30]
    initial_confidence = 0.95

    print("Creating lessons at different ages...")
    print("-" * 80)

    for days in ages_days:
        old_time = (datetime.utcnow() - timedelta(days=days)).isoformat()
        lesson = __import__('learning_engine').Lesson(
            lesson_id=f"lesson_age_{days}d",
            statement=f"Lesson created {days} days ago",
            condition="test",
            confidence=initial_confidence,
            evidence_count=100,
            first_observed=old_time,
            last_updated=old_time,
            supporting_metrics={}
        )
        learning_engine.lessons[lesson.lesson_id] = lesson

    # Apply decay
    print("\nApplying decay (2% per week)...")
    learning_engine.apply_confidence_decay()

    print("\nCONFIDENCE AFTER DECAY:")
    print("-" * 80)
    print(f"{'Age (days)':<15} {'Initial':<12} {'After Decay':<12} {'Decay %':<10}")
    print("-" * 80)

    for days in ages_days:
        lesson = learning_engine.lessons[f"lesson_age_{days}d"]
        decay_pct = (initial_confidence - lesson.confidence) / initial_confidence * 100
        print(
            f"{days:<15} {initial_confidence:<12.4f} {lesson.confidence:<12.4f} {decay_pct:<10.1f}%"
        )

    print("\nKEY OBSERVATIONS:")
    print("-" * 80)
    print("   • Lessons decay 2% per week if not reinforced")
    print("   • Older lessons (30 days) decay ~8.7%")
    print("   • System incentivizes regular evidence collection")
    print("   • Can be reset by new supporting evidence")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("CLOSED-LOOP LEARNING SYSTEM - COMPLETE WALKTHROUGH")
    print("=" * 80)

    # Example 1: Daily cycle
    collector, analysis, learning_engine, dashboard = example_daily_cycle()

    # Example 2: Weekly aggregation
    weekly_report = example_weekly_aggregation()

    # Example 3: Monthly KB update
    kb_report = example_monthly_kb_update()

    # Example 4: Contradiction detection
    example_contradiction_detection()

    # Example 5: Confidence decay
    example_confidence_decay()

    print_section("SUMMARY")
    print("""
The closed-loop learning system enables continuous improvement through:

1. DAILY OBSERVATIONS
   - Track every trade, outcome, regime shift, escalation
   - Identify patterns in real-time trading activity

2. WEEKLY ANALYSIS
   - Aggregate observations into patterns
   - Calculate strategy performance by regime
   - Correlate Greeks with outcomes
   - Detect contradictions in learned knowledge

3. MONTHLY KB UPDATES
   - Extract high-confidence lessons (≥ 0.75)
   - Update knowledge graph with new relationships
   - Demote low-confidence lessons (< 0.60)
   - Apply confidence decay (2% per week)

4. CONTINUOUS REPORTING
   - Daily: What happened, what changed, action items
   - Weekly: Trends, improvements, recommendations
   - Monthly: Strategic insights, KB health, evolution

Key Features:
✓ Conditional lessons ("works when vol < 20%")
✓ Confidence scoring with temporal decay
✓ Contradiction detection (old vs new knowledge)
✓ Mock observation stream for testing
✓ Full integration with knowledge graph
✓ Export/import for persistence

For production use:
- Connect to real trading system
- Use actual market regime detection
- Wire up to KG client for KB updates
- Deploy reporting dashboard
""")


if __name__ == "__main__":
    main()
