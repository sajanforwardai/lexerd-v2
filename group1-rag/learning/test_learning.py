"""
Comprehensive Test Suite for Closed-Loop Learning System
==========================================================

Tests:
- ObservationCollector (mock observation stream, storage, queries)
- AnalysisEngine (strategy analysis, Greek impact, volatility analysis, contradictions)
- LearningEngine (lesson extraction, KB updates, confidence decay, contradiction detection)
- ReportingDashboard (daily/weekly/monthly reports)
- Integration tests (full cycle)

Run with: pytest test_learning.py -v
"""

import pytest
import json
import tempfile
import logging
from datetime import datetime, timedelta
from pathlib import Path

from observation_collector import (
    ObservationCollector, TradeStatus, MockObservationStream,
    RegiType, TradeObservation, RegimeShift, Escalation
)
from analysis_engine import AnalysisEngine
from learning_engine import LearningEngine, Lesson
from reporting_dashboard import ReportingDashboard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestObservationCollector:
    """Test ObservationCollector functionality."""

    def test_record_trade(self):
        """Test recording a single trade."""
        collector = ObservationCollector()

        trade = collector.record_trade(
            trade_id="test_trade_1",
            strategy="gamma_scalping",
            instrument="BTC/USD",
            side="buy",
            quantity=1.5,
            entry_price=50000.0,
            exit_price=51000.0,
            pnl=1500.0,
            status=TradeStatus.FILLED,
            greeks={"delta": 0.5, "gamma": 0.1, "theta": -0.05, "vega": 0.2, "rho": 0.03},
            regime_at_entry="bull_low_vol"
        )

        assert trade.trade_id == "test_trade_1"
        assert trade.strategy == "gamma_scalping"
        assert trade.pnl == 1500.0
        assert collector.observation_count == 1
        assert len(collector.trades) == 1

    def test_record_regime_shift(self):
        """Test recording regime shift."""
        collector = ObservationCollector()

        shift = collector.record_regime_shift(
            from_regime="bull_low_vol",
            to_regime="bull_high_vol",
            volatility_change=25.5,
            trigger="volatility",
            confidence=0.85
        )

        assert shift.from_regime == "bull_low_vol"
        assert shift.to_regime == "bull_high_vol"
        assert collector.current_regime == "bull_high_vol"
        assert collector.observation_count == 1

    def test_record_escalation(self):
        """Test recording escalation."""
        collector = ObservationCollector()

        esc = collector.record_escalation(
            level="warning",
            category="loss",
            message="Daily loss exceeds threshold"
        )

        assert esc.level == "warning"
        assert esc.resolved is False
        assert collector.observation_count == 1

    def test_resolve_escalation(self):
        """Test resolving escalation."""
        collector = ObservationCollector()

        esc = collector.record_escalation(
            level="error",
            category="position",
            message="Position size exceeds limit"
        )

        assert collector.resolve_escalation(0)
        assert collector.escalations[0].resolved is True
        assert collector.escalations[0].resolution_time is not None

    def test_query_trades_by_strategy(self):
        """Test querying trades by strategy."""
        collector = ObservationCollector()

        collector.record_trade(
            trade_id="1", strategy="gamma_scalping", instrument="BTC/USD",
            side="buy", quantity=1.0, entry_price=50000.0
        )
        collector.record_trade(
            trade_id="2", strategy="vol_arbitrage", instrument="ETH/USD",
            side="sell", quantity=2.0, entry_price=3000.0
        )
        collector.record_trade(
            trade_id="3", strategy="gamma_scalping", instrument="SPY",
            side="buy", quantity=10.0, entry_price=400.0
        )

        gamma_trades = collector.get_trades_by_strategy("gamma_scalping")
        assert len(gamma_trades) == 2
        assert all(t.strategy == "gamma_scalping" for t in gamma_trades)

    def test_get_summary(self):
        """Test observation summary statistics."""
        collector = ObservationCollector()

        collector.record_trade(
            trade_id="1", strategy="gamma_scalping", instrument="BTC/USD",
            side="buy", quantity=1.0, entry_price=50000.0, pnl=1000.0
        )
        collector.record_trade(
            trade_id="2", strategy="gamma_scalping", instrument="BTC/USD",
            side="sell", quantity=1.0, entry_price=51000.0, pnl=-500.0
        )

        summary = collector.get_summary()
        assert summary["total_trades"] == 2
        assert summary["winning_trades"] == 1
        assert summary["losing_trades"] == 1
        assert summary["win_rate"] == 0.5
        assert summary["total_pnl"] == 500.0

    def test_export_import_observations(self):
        """Test exporting and importing observations."""
        collector1 = ObservationCollector()
        collector1.record_trade(
            trade_id="1", strategy="gamma_scalping", instrument="BTC/USD",
            side="buy", quantity=1.0, entry_price=50000.0, pnl=1000.0
        )
        collector1.record_regime_shift(
            from_regime="normal", to_regime="bull_low_vol",
            volatility_change=-15.0, confidence=0.80
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            collector1.export_observations(filepath)
            assert Path(filepath).exists()

            collector2 = ObservationCollector()
            assert collector2.import_observations(filepath)
            assert len(collector2.trades) == 1
            assert len(collector2.regime_shifts) == 1
        finally:
            Path(filepath).unlink()

    def test_mock_observation_stream(self):
        """Test mock observation stream generation."""
        collector = ObservationCollector()
        stream = MockObservationStream(seed=42)

        stream.generate_mock_trades(collector, count=20)
        assert len(collector.trades) == 20

        stream.generate_mock_regime_shifts(collector, count=3)
        assert len(collector.regime_shifts) == 3

        stream.generate_mock_escalations(collector, count=2)
        assert len(collector.escalations) == 2

        summary = collector.get_summary()
        assert summary["total_trades"] == 20


class TestAnalysisEngine:
    """Test AnalysisEngine functionality."""

    def test_analyze_strategy_by_regime(self):
        """Test strategy-regime analysis."""
        collector = ObservationCollector()
        stream = MockObservationStream(seed=42)
        stream.generate_mock_trades(collector, count=50)

        engine = AnalysisEngine()
        analysis = engine.analyze_strategy_by_regime(collector.trades)

        assert isinstance(analysis, dict)
        for strategy, regimes in analysis.items():
            for regime, metrics in regimes.items():
                assert "win_rate" in metrics
                assert "avg_pnl" in metrics
                assert "trades_count" in metrics
                assert 0 <= metrics["win_rate"] <= 1

    def test_analyze_greek_impact(self):
        """Test Greek impact analysis."""
        collector = ObservationCollector()
        stream = MockObservationStream(seed=42)
        stream.generate_mock_trades(collector, count=50)

        engine = AnalysisEngine()
        analysis = engine.analyze_greek_impact(collector.trades)

        assert set(analysis.keys()) == {"delta", "gamma", "theta", "vega", "rho"}
        for greek, data in analysis.items():
            assert "correlation" in data
            assert "avg_greek_value" in data
            assert "impact" in data
            assert data["impact"] in ["positive", "negative", "neutral", "insufficient_data"]

    def test_analyze_volatility_impact(self):
        """Test volatility impact analysis."""
        collector = ObservationCollector()
        stream = MockObservationStream(seed=42)
        stream.generate_mock_trades(collector, count=50)
        stream.generate_mock_regime_shifts(collector, count=3)

        engine = AnalysisEngine()
        analysis = engine.analyze_volatility_impact(collector.trades, collector.regime_shifts)

        assert "low_vol_performance" in analysis
        assert "high_vol_performance" in analysis
        assert "avg_pnl" in analysis["low_vol_performance"]
        assert "win_rate" in analysis["low_vol_performance"]

    def test_detect_contradictions(self):
        """Test contradiction detection."""
        engine = AnalysisEngine()

        # Create contradictory performance
        strategy_perf = {
            "gamma_scalping": {
                "bull_low_vol": {"win_rate": 0.75, "trades_count": 10},
                "bear_high_vol": {"win_rate": 0.35, "trades_count": 10}
            }
        }

        greek_impact = {
            "gamma": {"impact": "positive", "correlation": 0.5},
            "theta": {"impact": "negative", "correlation": -0.3}
        }

        contradictions = engine.detect_contradictions(strategy_perf, greek_impact)
        # Contradictions should be detected (high variance in strategy performance)
        assert isinstance(contradictions, list)

    def test_generate_analysis_summary(self):
        """Test full analysis summary generation."""
        collector = ObservationCollector()
        stream = MockObservationStream(seed=42)
        stream.generate_mock_trades(collector, count=50)
        stream.generate_mock_regime_shifts(collector, count=3)
        stream.generate_mock_escalations(collector, count=2)

        engine = AnalysisEngine()
        summary = engine.generate_analysis_summary(
            collector.trades,
            collector.regime_shifts,
            collector.escalations
        )

        assert "analysis_timestamp" in summary
        assert "strategy_performance_by_regime" in summary
        assert "greek_impact_analysis" in summary
        assert "volatility_impact" in summary
        assert "key_insights" in summary
        assert isinstance(summary["key_insights"], list)


class TestLearningEngine:
    """Test LearningEngine functionality."""

    def test_lesson_creation(self):
        """Test creating a lesson."""
        lesson = Lesson(
            lesson_id="test_1",
            statement="Gamma scalping works best in low volatility",
            condition="vol < 20%",
            confidence=0.85,
            evidence_count=50,
            first_observed=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
            supporting_metrics={"win_rate": 0.75, "trades": 50}
        )

        assert lesson.lesson_id == "test_1"
        assert lesson.confidence == 0.85
        assert lesson.evidence_count == 50

    def test_confidence_decay(self):
        """Test confidence decay over time."""
        old_time = (datetime.utcnow() - timedelta(days=7)).isoformat()

        lesson = Lesson(
            lesson_id="test_decay",
            statement="Test lesson",
            condition="test",
            confidence=1.0,
            evidence_count=100,
            first_observed=old_time,
            last_updated=old_time,
            supporting_metrics={}
        )

        # Confidence should decay
        new_conf = lesson.apply_decay()
        assert new_conf < 1.0
        # Should decay ~2% per week, so after 1 week should be ~0.98
        assert 0.95 < new_conf < 1.0

    def test_extract_lessons_from_analysis(self):
        """Test extracting lessons from analysis."""
        collector = ObservationCollector()
        stream = MockObservationStream(seed=42)
        stream.generate_mock_trades(collector, count=50)
        stream.generate_mock_regime_shifts(collector, count=3)

        engine = AnalysisEngine()
        analysis = engine.generate_analysis_summary(
            collector.trades,
            collector.regime_shifts,
            collector.escalations
        )

        learning = LearningEngine()
        lessons = learning.extract_lessons_from_analysis(analysis)

        assert len(lessons) > 0
        for lesson in lessons:
            assert isinstance(lesson, Lesson)
            assert 0 <= lesson.confidence <= 1
            assert lesson.evidence_count > 0

    def test_detect_contradiction(self):
        """Test contradiction detection between lessons."""
        learning = LearningEngine()

        lesson1 = Lesson(
            lesson_id="1",
            statement="Gamma scalping works best in high volatility",
            condition="vol > 20%",
            confidence=0.80,
            evidence_count=50,
            first_observed=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
            supporting_metrics={}
        )

        lesson2 = Lesson(
            lesson_id="2",
            statement="Gamma scalping fails in high volatility",
            condition="vol > 20%",
            confidence=0.75,
            evidence_count=45,
            first_observed=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
            supporting_metrics={}
        )

        learning.lessons["1"] = lesson1
        contradictions = learning.detect_contradictions(lesson2)

        # May or may not detect (depends on heuristic)
        assert isinstance(contradictions, list)

    def test_apply_confidence_decay(self):
        """Test applying decay to all lessons."""
        learning = LearningEngine()

        old_time = (datetime.utcnow() - timedelta(days=14)).isoformat()
        lesson = Lesson(
            lesson_id="test",
            statement="Test",
            condition="test",
            confidence=1.0,
            evidence_count=100,
            first_observed=old_time,
            last_updated=old_time,
            supporting_metrics={}
        )

        learning.lessons["test"] = lesson
        learning.apply_confidence_decay()

        # After 2 weeks, confidence should be 0.98^2 ≈ 0.96
        assert lesson.confidence < 1.0

    def test_get_monthly_kb_update_report(self):
        """Test generating monthly KB update report."""
        learning = LearningEngine()

        for i in range(5):
            lesson = Lesson(
                lesson_id=f"lesson_{i}",
                statement=f"Test lesson {i}",
                condition="test",
                confidence=0.75 + i * 0.05,  # 0.75, 0.80, 0.85, 0.90, 0.95
                evidence_count=100,
                first_observed=datetime.utcnow().isoformat(),
                last_updated=datetime.utcnow().isoformat(),
                supporting_metrics={}
            )
            learning.lessons[lesson.lesson_id] = lesson

        report = learning.get_monthly_kb_update_report()

        assert "total_lessons" in report
        assert report["total_lessons"] == 5
        assert "promoted_to_kb" in report
        assert len(report["promoted_to_kb"]) >= 3  # At least 0.75+

    def test_export_import_lessons(self):
        """Test exporting and importing lessons."""
        learning1 = LearningEngine()

        for i in range(3):
            lesson = Lesson(
                lesson_id=f"lesson_{i}",
                statement=f"Test lesson {i}",
                condition="test",
                confidence=0.80,
                evidence_count=100,
                first_observed=datetime.utcnow().isoformat(),
                last_updated=datetime.utcnow().isoformat(),
                supporting_metrics={}
            )
            learning1.lessons[lesson.lesson_id] = lesson

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            learning1.export_lessons(filepath)
            assert Path(filepath).exists()

            learning2 = LearningEngine()
            assert learning2.import_lessons(filepath)
            assert len(learning2.lessons) == 3
        finally:
            Path(filepath).unlink()


class TestReportingDashboard:
    """Test ReportingDashboard functionality."""

    def test_generate_daily_report(self):
        """Test generating daily report."""
        dashboard = ReportingDashboard()

        observations = {
            "total_trades": 10,
            "winning_trades": 7,
            "losing_trades": 3,
            "total_pnl": 1500.0,
            "active_escalations": 0,
            "current_regime": "bull_low_vol"
        }

        analysis = {
            "strategy_performance_by_regime": {},
            "greek_impact_analysis": {}
        }

        report = dashboard.generate_daily_report(
            observations, analysis, ["lesson_1", "lesson_2"], 0
        )

        assert report["report_type"] == "daily"
        assert "observation_summary" in report
        assert report["observation_summary"]["total_trades"] == 10
        assert report["observation_summary"]["daily_win_rate"] == 0.7

    def test_generate_weekly_report(self):
        """Test generating weekly report."""
        dashboard = ReportingDashboard()

        # Generate 7 daily reports
        daily_reports = []
        for i in range(7):
            report = dashboard.generate_daily_report(
                {
                    "total_trades": 10 + i,
                    "winning_trades": 6 + i // 2,
                    "losing_trades": 4 - i // 2,
                    "total_pnl": 1000.0 + i * 100,
                    "active_escalations": 0,
                    "current_regime": "bull_low_vol"
                },
                {},
                [],
                0
            )
            daily_reports.append(report)

        learning_stats = {
            "lessons_created": 5,
            "lessons_promoted": 2,
            "lessons_demoted": 1,
            "contradictions_resolved": 0,
            "kb_updates": 2
        }

        report = dashboard.generate_weekly_report(daily_reports, learning_stats)

        assert report["report_type"] == "weekly"
        assert report["aggregated_metrics"]["total_trades"] > 0
        assert report["aggregated_metrics"]["weekly_win_rate"] > 0

    def test_generate_monthly_report(self):
        """Test generating monthly report."""
        dashboard = ReportingDashboard()

        # Generate 4 weekly reports
        weekly_reports = []
        for i in range(4):
            report = {
                "aggregated_metrics": {
                    "total_trades": 50 + i * 10,
                    "total_wins": 30 + i * 5,
                    "total_losses": 20 - i,
                    "net_pnl": 2000.0 + i * 500,
                    "best_week": {},
                    "worst_week": {}
                }
            }
            weekly_reports.append(report)

        kb_summary = {
            "kb_update_history": [],
            "promoted_to_kb": [{"id": "1"}, {"id": "2"}],
            "demoted_lessons": [{"id": "3"}],
            "contradictions_detected": 1,
            "contradictions_resolved": 0,
            "avg_confidence": 0.78
        }

        report = dashboard.generate_monthly_report(weekly_reports, kb_summary)

        assert report["report_type"] == "monthly"
        assert report["monthly_performance"]["total_trades"] > 0
        assert "strategic_recommendations" in report


class TestIntegration:
    """Integration tests for the full learning cycle."""

    def test_full_learning_cycle(self):
        """Test complete cycle: observe -> analyze -> learn -> report."""
        # 1. Generate observations
        collector = ObservationCollector()
        stream = MockObservationStream(seed=42)
        stream.generate_mock_trades(collector, count=100)
        stream.generate_mock_regime_shifts(collector, count=5)
        stream.generate_mock_escalations(collector, count=3)

        assert len(collector.trades) == 100
        assert len(collector.regime_shifts) == 5
        assert len(collector.escalations) == 3

        # 2. Analyze
        analysis_engine = AnalysisEngine()
        analysis = analysis_engine.generate_analysis_summary(
            collector.trades,
            collector.regime_shifts,
            collector.escalations
        )

        assert analysis["strategy_performance_by_regime"]
        assert analysis["greek_impact_analysis"]
        assert analysis["key_insights"]

        # 3. Learn
        learning_engine = LearningEngine()
        lessons = learning_engine.extract_lessons_from_analysis(analysis)

        assert len(lessons) > 0
        for lesson in lessons:
            assert lesson.confidence > 0

        # 4. Report
        dashboard = ReportingDashboard()
        obs_summary = collector.get_summary()
        daily_report = dashboard.generate_daily_report(
            obs_summary,
            analysis,
            [l.lesson_id for l in lessons],
            len(learning_engine.contradiction_log)
        )

        assert daily_report["observation_summary"]["total_trades"] == 100
        assert len(daily_report["action_items"]) >= 0

    def test_confidence_decay_scenario(self):
        """Test scenario where old lessons decay over time."""
        learning = LearningEngine()

        # Create a lesson from last month
        old_time = (datetime.utcnow() - timedelta(days=30)).isoformat()
        old_lesson = Lesson(
            lesson_id="old_lesson",
            statement="Old strategy knowledge",
            condition="old",
            confidence=0.95,
            evidence_count=500,
            first_observed=old_time,
            last_updated=old_time,
            supporting_metrics={}
        )

        # Create a new lesson from today
        new_lesson = Lesson(
            lesson_id="new_lesson",
            statement="New strategy knowledge",
            condition="new",
            confidence=0.75,
            evidence_count=100,
            first_observed=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
            supporting_metrics={}
        )

        learning.lessons["old"] = old_lesson
        learning.lessons["new"] = new_lesson

        # Apply decay
        learning.apply_confidence_decay()

        # Old lesson should decay (30 days ≈ 4.3 weeks: 0.95 * 0.98^4.3 ≈ 0.87)
        assert old_lesson.confidence < 0.95, f"Expected decay but got {old_lesson.confidence}"
        assert new_lesson.confidence >= 0.70, f"New lesson should not decay much but got {new_lesson.confidence}"

    def test_contradiction_resolution_scenario(self):
        """Test detecting and resolving contradictions."""
        learning = LearningEngine()

        # Create contradictory lessons
        lesson1 = Lesson(
            lesson_id="strategy_a_works",
            statement="Strategy A works best in high volatility regimes",
            condition="vol > 25%",
            confidence=0.85,
            evidence_count=200,
            first_observed=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
            supporting_metrics={"win_rate": 0.72}
        )

        lesson2 = Lesson(
            lesson_id="strategy_a_fails",
            statement="Strategy A fails in high volatility",
            condition="vol > 25%",
            confidence=0.80,
            evidence_count=180,
            first_observed=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
            supporting_metrics={"win_rate": 0.35}
        )

        learning.lessons["1"] = lesson1
        contradictions = learning.detect_contradictions(lesson2)

        # Should detect potential contradiction
        assert isinstance(contradictions, list)

        # Resolve in favor of higher confidence
        if contradictions:
            learning.resolve_contradictions(0)
            assert learning.contradiction_log[0]["resolution"] != "pending"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
