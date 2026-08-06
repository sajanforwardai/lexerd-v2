"""
Analysis Engine for Trading System
===================================

Analyzes trading observations to extract patterns:
- What strategies work best in which regimes
- Correlation between Greeks and trade outcomes
- Volatility impact on performance
- Risk factor analysis
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from statistics import mean, stdev
from datetime import datetime

from observation_collector import TradeObservation, RegimeShift, Escalation

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """
    Analyzes trading observations to understand patterns and relationships.
    """

    def __init__(self):
        """Initialize analysis engine."""
        self.analysis_cache: Dict[str, Any] = {}
        self.last_analysis_time: Optional[str] = None

    def analyze_strategy_by_regime(
        self,
        trades: List[TradeObservation]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze strategy performance in each regime.

        Returns dict of {strategy: {regime: {metrics}}}
        Metrics: win_rate, avg_pnl, trades_count, avg_greeks
        """
        results = defaultdict(lambda: defaultdict(dict))

        strategy_regime_trades = defaultdict(lambda: defaultdict(list))
        for trade in trades:
            strategy_regime_trades[trade.strategy][trade.regime_at_entry].append(trade)

        for strategy, regimes in strategy_regime_trades.items():
            for regime, regime_trades in regimes.items():
                pnls = [t.pnl for t in regime_trades if t.pnl is not None]
                wins = sum(1 for p in pnls if p > 0)
                losses = sum(1 for p in pnls if p < 0)

                # Aggregate Greeks
                avg_greeks = {}
                for greek in ["delta", "gamma", "theta", "vega", "rho"]:
                    greek_values = [t.greeks.get(greek, 0) for t in regime_trades]
                    avg_greeks[greek] = mean(greek_values) if greek_values else 0.0

                results[strategy][regime] = {
                    "win_rate": wins / len(pnls) if pnls else 0.0,
                    "avg_pnl": mean(pnls) if pnls else 0.0,
                    "total_pnl": sum(pnls) if pnls else 0.0,
                    "trades_count": len(regime_trades),
                    "win_count": wins,
                    "loss_count": losses,
                    "std_dev": stdev(pnls) if len(pnls) > 1 else 0.0,
                    "avg_greeks": avg_greeks
                }

        return dict(results)

    def analyze_greek_impact(
        self,
        trades: List[TradeObservation]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze how each Greek correlates with trade outcomes.

        Returns dict of {greek: {analysis}}
        """
        results = {}
        greeks = ["delta", "gamma", "theta", "vega", "rho"]

        for greek in greeks:
            greek_vals = []
            pnl_vals = []

            for trade in trades:
                if trade.pnl is not None:
                    greek_vals.append(trade.greeks.get(greek, 0))
                    pnl_vals.append(trade.pnl)

            if not greek_vals or len(greek_vals) < 2:
                results[greek] = {
                    "correlation": 0.0,
                    "avg_greek_value": 0.0,
                    "impact": "insufficient_data"
                }
                continue

            # Simple correlation: high/low Greek groups
            avg_greek = mean(greek_vals)
            high_greek_trades = [pnl for g, pnl in zip(greek_vals, pnl_vals) if g > avg_greek]
            low_greek_trades = [pnl for g, pnl in zip(greek_vals, pnl_vals) if g <= avg_greek]

            high_greek_avg = mean(high_greek_trades) if high_greek_trades else 0.0
            low_greek_avg = mean(low_greek_trades) if low_greek_trades else 0.0

            # Correlation as difference in average performance
            correlation = high_greek_avg - low_greek_avg

            results[greek] = {
                "correlation": correlation,
                "avg_greek_value": avg_greek,
                "high_greek_avg_pnl": high_greek_avg,
                "low_greek_avg_pnl": low_greek_avg,
                "impact": "positive" if correlation > 0 else "negative" if correlation < 0 else "neutral"
            }

        return results

    def analyze_volatility_impact(
        self,
        trades: List[TradeObservation],
        regime_shifts: List[RegimeShift]
    ) -> Dict[str, Any]:
        """
        Analyze how volatility changes affect strategy performance.
        """
        vol_regimes = {
            "bull_low_vol": 1,
            "bull_high_vol": 3,
            "bear_low_vol": 1,
            "bear_high_vol": 3,
            "stress": 5
        }

        results = {
            "low_vol_performance": {"trades": [], "avg_pnl": 0.0, "win_rate": 0.0},
            "high_vol_performance": {"trades": [], "avg_pnl": 0.0, "win_rate": 0.0},
            "vol_sensitivity": {}
        }

        for trade in trades:
            vol_level = vol_regimes.get(trade.regime_at_entry, 2)
            if trade.pnl is not None:
                if vol_level <= 2:
                    results["low_vol_performance"]["trades"].append(trade.pnl)
                else:
                    results["high_vol_performance"]["trades"].append(trade.pnl)

        # Calculate metrics
        for key in ["low_vol_performance", "high_vol_performance"]:
            pnls = results[key]["trades"]
            if pnls:
                results[key]["avg_pnl"] = mean(pnls)
                results[key]["win_rate"] = sum(1 for p in pnls if p > 0) / len(pnls)

        return results

    def detect_contradictions(
        self,
        strategy_performance: Dict[str, Dict[str, Any]],
        greek_impact: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect contradictions in learned knowledge.

        Examples:
        - Strategy X works in regime A and B, but poorly in A vs B
        - Greek impact changed direction (vega positive now, was negative before)
        """
        contradictions = []

        # Check strategy consistency across regimes
        for strategy, regimes in strategy_performance.items():
            regime_list = list(regimes.items())
            if len(regime_list) >= 2:
                # Check for inconsistent performance
                win_rates = [r[1].get("win_rate", 0) for r in regime_list]
                if max(win_rates) > 0.6 and min(win_rates) < 0.4:
                    contradictions.append({
                        "type": "strategy_regime_inconsistency",
                        "strategy": strategy,
                        "description": f"Strategy {strategy} has inconsistent performance across regimes",
                        "high_wr": max(win_rates),
                        "low_wr": min(win_rates),
                        "severity": "medium"
                    })

        # Check Greek impact consistency
        greek_directions = {}
        for greek, impact_data in greek_impact.items():
            greek_directions[greek] = impact_data.get("impact")

        return contradictions

    def correlate_escalations_with_regime(
        self,
        escalations: List[Escalation],
        regime_shifts: List[RegimeShift]
    ) -> Dict[str, Any]:
        """
        Find correlations between escalations and regime shifts.
        """
        results = {
            "escalations_by_regime": defaultdict(list),
            "escalations_by_trigger": defaultdict(list),
            "temporal_proximity": []
        }

        for escalation in escalations:
            esc_time = datetime.fromisoformat(escalation.timestamp)

            # Find nearest regime shift
            nearest_shift = None
            min_time_diff = float('inf')

            for shift in regime_shifts:
                shift_time = datetime.fromisoformat(shift.timestamp)
                time_diff = abs((esc_time - shift_time).total_seconds())
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    nearest_shift = shift

            if nearest_shift and min_time_diff < 300:  # 5 minutes
                results["temporal_proximity"].append({
                    "escalation": escalation.message,
                    "regime_shift": f"{nearest_shift.from_regime} -> {nearest_shift.to_regime}",
                    "time_diff_seconds": min_time_diff,
                    "regime_trigger": nearest_shift.trigger
                })

        return dict(results)

    def extract_performance_by_greek_level(
        self,
        trades: List[TradeObservation]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract performance metrics grouped by Greek levels.

        Example: trades with delta > 0.5 have X% win rate and Y avg pnl
        """
        results = {}
        greek_thresholds = {
            "delta": [(-1.0, -0.5), (-0.5, 0.0), (0.0, 0.5), (0.5, 1.0)],
            "gamma": [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6)],
            "theta": [(-0.1, -0.05), (-0.05, 0.0), (0.0, 0.1)],
            "vega": [(-1.0, -0.5), (-0.5, 0.0), (0.0, 0.5), (0.5, 1.0)],
            "rho": [(-0.5, -0.25), (-0.25, 0.0), (0.0, 0.25), (0.25, 0.5)]
        }

        for greek, thresholds in greek_thresholds.items():
            results[greek] = {}

            for low, high in thresholds:
                range_key = f"[{low:.2f}, {high:.2f}]"
                range_trades = [
                    t for t in trades
                    if low <= t.greeks.get(greek, 0) <= high and t.pnl is not None
                ]

                if range_trades:
                    pnls = [t.pnl for t in range_trades]
                    results[greek][range_key] = {
                        "count": len(range_trades),
                        "avg_pnl": mean(pnls),
                        "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
                        "total_pnl": sum(pnls)
                    }

        return results

    def generate_analysis_summary(
        self,
        trades: List[TradeObservation],
        regime_shifts: List[RegimeShift],
        escalations: List[Escalation]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive analysis summary.
        """
        self.last_analysis_time = datetime.utcnow().isoformat()

        strategy_perf = self.analyze_strategy_by_regime(trades)
        greek_impact = self.analyze_greek_impact(trades)
        vol_impact = self.analyze_volatility_impact(trades, regime_shifts)
        contradictions = self.detect_contradictions(strategy_perf, greek_impact)
        esc_corr = self.correlate_escalations_with_regime(escalations, regime_shifts)
        greek_levels = self.extract_performance_by_greek_level(trades)

        summary = {
            "analysis_timestamp": self.last_analysis_time,
            "strategy_performance_by_regime": dict(strategy_perf),
            "greek_impact_analysis": greek_impact,
            "volatility_impact": vol_impact,
            "contradictions_detected": contradictions,
            "escalation_correlations": esc_corr,
            "greek_level_performance": greek_levels,
            "key_insights": self._extract_key_insights(
                strategy_perf, greek_impact, vol_impact, contradictions
            )
        }

        return summary

    def _extract_key_insights(
        self,
        strategy_perf: Dict[str, Dict[str, Any]],
        greek_impact: Dict[str, Dict[str, Any]],
        vol_impact: Dict[str, Any],
        contradictions: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract actionable insights from analysis."""
        insights = []

        # Strategy insights
        for strategy, regimes in strategy_perf.items():
            best_regime = max(regimes.items(), key=lambda x: x[1]["win_rate"], default=None)
            if best_regime and best_regime[1]["win_rate"] > 0.6:
                insights.append(
                    f"{strategy} performs best in {best_regime[0]} "
                    f"(win rate: {best_regime[1]['win_rate']:.1%})"
                )

        # Greek insights
        for greek, data in greek_impact.items():
            if data["impact"] == "positive" and data["correlation"] > 0.5:
                insights.append(
                    f"High {greek} correlates with better performance "
                    f"(correlation: {data['correlation']:.2f})"
                )

        # Volatility insights
        low_vol_wr = vol_impact["low_vol_performance"].get("win_rate", 0)
        high_vol_wr = vol_impact["high_vol_performance"].get("win_rate", 0)
        if low_vol_wr > 0 and high_vol_wr > 0:
            if low_vol_wr > high_vol_wr * 1.2:
                insights.append("Strategies perform better in low-volatility environments")
            elif high_vol_wr > low_vol_wr * 1.2:
                insights.append("Strategies perform better in high-volatility environments")

        # Contradiction insights
        if contradictions:
            insights.append(f"Detected {len(contradictions)} contradiction(s) in learned patterns")

        return insights
