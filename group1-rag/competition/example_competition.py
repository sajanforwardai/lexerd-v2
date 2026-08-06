"""
Example: Full Daily Competition Cycle
======================================

Demonstrates end-to-end workflow:
1. Initialize agent pool, competition engine, regime detector
2. Simulate 30 days of market data
3. Daily: detect regime, collect agent selections, pick winner
4. Weekly: calculate performance by regime
5. Export results and agent rankings

Shows integration with ObservationCollector and learning loop.
"""

import logging
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any

from agent_pool import AgentPool
from competition_engine import CompetitionEngine
from regime_detector import RegimeDetector
from strategy_agent import GreeksSnapshot, MarketState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockMarketDataStream:
    """Generate mock market data for simulation."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.current_vol = 0.15
        self.current_momentum = 0.3
        self.vol_trend = 0.01  # Increasing/decreasing vol

    def get_next_day(self) -> Dict[str, Any]:
        """Get market data for next day."""
        # Vol evolves via random walk
        self.current_vol += random.gauss(0, self.vol_trend)
        self.current_vol = max(0.08, min(0.60, self.current_vol))

        # Momentum mean-reverts
        self.current_momentum = self.current_momentum * 0.7 + random.gauss(0, 0.2)

        # Generate Greeks
        greeks = GreeksSnapshot(
            delta=0.3 + self.current_momentum,
            gamma=0.15 - (self.current_vol * 0.3),
            theta=-0.01,
            vega=self.current_vol,
            rho=0.05,
            vol_of_vol=0.1 + (abs(self.current_vol - 0.15) * 0.5)
        )

        # Generate market state
        market_state = MarketState(
            volatility=self.current_vol,
            volatility_term_structure={
                "1m": self.current_vol * 0.9,
                "3m": self.current_vol,
                "1y": self.current_vol * 1.1
            },
            skew=-0.2 if self.current_momentum < 0 else 0.1,
            term_structure_slope=0.05,
            events=self._generate_events(),
            regime="",  # Will be detected
            price_momentum=self.current_momentum,
            correlation_regime="normal" if self.current_vol < 0.40 else "stress",
            liquidity_score=0.9 if self.current_vol < 0.40 else 0.7
        )

        return {
            "greeks": greeks,
            "market_state": market_state
        }

    def _generate_events(self) -> List[str]:
        """Generate random events with 10% probability."""
        events = []
        event_types = ["earnings", "econ_data", "fomc", "vol_spike"]

        for event_type in event_types:
            if random.random() < 0.05:  # 5% chance each
                events.append(event_type)

        return events


class DailyCompetition:
    """Runs daily competition and tracks results."""

    def __init__(self):
        """Initialize competition components."""
        self.agent_pool = AgentPool()
        self.competition_engine = CompetitionEngine(self.agent_pool)
        self.regime_detector = RegimeDetector(use_kg=False)
        self.market_data = MockMarketDataStream()

        # Results tracking
        self.daily_results: List[Dict[str, Any]] = []
        self.trade_log: List[Dict[str, Any]] = []

        logger.info("Initialized DailyCompetition")

    def run_day(self, day_num: int) -> Dict[str, Any]:
        """Run a single trading day."""
        # Get market data
        data = self.market_data.get_next_day()
        greeks = data["greeks"]
        market_state = data["market_state"]

        # Detect regime
        regime, regime_conf = self.regime_detector.detect_regime(
            volatility=market_state.volatility,
            skew=market_state.skew,
            term_structure_slope=market_state.term_structure_slope,
            price_momentum=market_state.price_momentum,
            vol_of_vol=greeks.vol_of_vol,
            events=market_state.events,
            correlation_regime=market_state.correlation_regime
        )

        market_state.regime = regime

        # Get agent selections
        selections = self.agent_pool.select_actions(regime, greeks, market_state)

        # Select winner and hedge
        winner, hedge, reason = self.competition_engine.get_winner_and_hedge(
            regime, selections, confidence_threshold=0.60
        )

        # Simulate trade outcome
        if winner:
            agent_name, strategy = winner

            # P&L depends on strategy quality in regime
            agent = self.agent_pool.get_agent_by_name(agent_name)
            base_pnl = 50 if agent_name in self.regime_detector.regime_history[0][0] else 20

            # Perturb with randomness
            pnl = base_pnl * random.gauss(1.0, 0.3)

            # Update Elo
            self.competition_engine.update_elo_from_trade(agent_name, regime, pnl)

            # Log trade
            trade = {
                "day": day_num,
                "date": (datetime.utcnow() - timedelta(days=30-day_num)).isoformat(),
                "regime": regime,
                "agent": agent_name,
                "strategy": strategy.strategy_name,
                "confidence": strategy.confidence,
                "pnl": pnl,
                "status": "executed"
            }
            self.trade_log.append(trade)
        else:
            pnl = 0
            trade = {
                "day": day_num,
                "date": (datetime.utcnow() - timedelta(days=30-day_num)).isoformat(),
                "regime": regime,
                "status": "escalated",
                "reason": reason
            }
            self.trade_log.append(trade)

        # Record selection
        self.competition_engine.record_selection(regime, winner, hedge, reason)

        # Store daily result
        result = {
            "day": day_num,
            "regime": regime,
            "regime_confidence": regime_conf,
            "volatility": market_state.volatility,
            "momentum": market_state.price_momentum,
            "winner": winner[0] if winner else None,
            "pnl": pnl,
            "escalated": winner is None,
            "events": market_state.events
        }

        self.daily_results.append(result)

        logger.info(
            f"Day {day_num}: regime={regime} ({regime_conf:.2%}), "
            f"winner={winner[0] if winner else 'ESCALATED'}, "
            f"pnl={pnl:.1f}"
        )

        return result

    def run_period(self, num_days: int = 30):
        """Run competition for N days."""
        logger.info(f"Starting {num_days}-day competition")

        for day in range(1, num_days + 1):
            self.run_day(day)

        logger.info(f"Completed {num_days}-day competition")

    def get_weekly_summary(self, week_num: int) -> Dict[str, Any]:
        """Get summary for a week."""
        start_day = (week_num - 1) * 7 + 1
        end_day = week_num * 7

        week_trades = [t for t in self.trade_log if start_day <= t.get("day", 0) <= end_day]
        week_results = [r for r in self.daily_results if start_day <= r.get("day", 0) <= end_day]

        # Calculate metrics by agent
        agent_metrics = {}
        for trade in week_trades:
            if "agent" in trade:
                agent = trade["agent"]
                if agent not in agent_metrics:
                    agent_metrics[agent] = {
                        "trades": 0,
                        "total_pnl": 0.0,
                        "win_count": 0,
                        "selection_count": 0
                    }

                agent_metrics[agent]["trades"] += 1
                agent_metrics[agent]["total_pnl"] += trade.get("pnl", 0)
                if trade.get("pnl", 0) > 0:
                    agent_metrics[agent]["win_count"] += 1

        # Add selection counts from competition
        for trade in week_trades:
            if "agent" in trade:
                agent = trade["agent"]
                agent_metrics[agent]["selection_count"] += 1

        return {
            "week": week_num,
            "trading_days": len(week_results),
            "total_pnl": sum(r.get("pnl", 0) for r in week_results),
            "win_rate": sum(1 for r in week_results if r.get("pnl", 0) > 0) / len(week_results) if week_results else 0,
            "avg_volatility": sum(r.get("volatility", 0) for r in week_results) / len(week_results) if week_results else 0,
            "escalations": sum(1 for r in week_results if r.get("escalated", False)),
            "agent_metrics": agent_metrics
        }

    def get_final_report(self) -> Dict[str, Any]:
        """Generate final competition report."""
        total_days = len(self.daily_results)
        total_pnl = sum(r.get("pnl", 0) for r in self.daily_results)
        winning_days = sum(1 for r in self.daily_results if r.get("pnl", 0) > 0)
        escalations = sum(1 for r in self.daily_results if r.get("escalated", False))

        # Regime analysis
        regime_analysis = {}
        for result in self.daily_results:
            regime = result["regime"]
            if regime not in regime_analysis:
                regime_analysis[regime] = {
                    "days": 0,
                    "total_pnl": 0.0,
                    "avg_vol": 0.0,
                    "winning_days": 0
                }

            regime_analysis[regime]["days"] += 1
            regime_analysis[regime]["total_pnl"] += result.get("pnl", 0)
            regime_analysis[regime]["avg_vol"] += result.get("volatility", 0)
            if result.get("pnl", 0) > 0:
                regime_analysis[regime]["winning_days"] += 1

        # Finalize regime stats
        for regime in regime_analysis:
            days = regime_analysis[regime]["days"]
            regime_analysis[regime]["avg_vol"] /= days
            regime_analysis[regime]["win_rate"] = regime_analysis[regime]["winning_days"] / days

        # Get final rankings
        final_rankings = self.competition_engine.get_global_rankings()

        return {
            "period": "30-day simulation",
            "total_trading_days": total_days,
            "total_pnl": total_pnl,
            "win_rate": winning_days / total_days if total_days > 0 else 0,
            "sharpe_ratio": self._calculate_sharpe(),
            "max_drawdown": self._calculate_max_drawdown(),
            "escalations": escalations,
            "regime_analysis": regime_analysis,
            "final_rankings": final_rankings,
            "competition_stats": self.competition_engine.get_competition_stats()
        }

    def _calculate_sharpe(self) -> float:
        """Calculate Sharpe ratio of daily returns."""
        import statistics

        returns = [r.get("pnl", 0) for r in self.daily_results]
        if not returns or len(returns) < 2:
            return 0.0

        mean_return = statistics.mean(returns)
        std_dev = statistics.stdev(returns) if len(returns) > 1 else 1.0

        if std_dev == 0:
            return 0.0

        # Annualize (252 trading days)
        return (mean_return / std_dev) * (252 ** 0.5)

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        cumulative = 0
        peak = 0
        max_dd = 0

        for result in self.daily_results:
            cumulative += result.get("pnl", 0)
            peak = max(peak, cumulative)
            dd = peak - cumulative
            max_dd = max(max_dd, dd)

        return max_dd

    def save_results(self, filepath: str):
        """Save results to JSON."""
        report = self.get_final_report()

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Saved results to {filepath}")


def main():
    """Run full 30-day competition example."""
    logger.info("Starting example competition...")

    # Initialize and run
    competition = DailyCompetition()
    competition.run_period(num_days=30)

    # Generate weekly summaries
    logger.info("\n=== WEEKLY SUMMARIES ===")
    for week in range(1, 5):
        summary = competition.get_weekly_summary(week)
        logger.info(
            f"\nWeek {week}: {summary['total_pnl']:.1f} PnL, "
            f"{summary['win_rate']:.1%} win rate, "
            f"{summary['escalations']} escalations"
        )

        # Show top agents
        if summary["agent_metrics"]:
            logger.info("  Top agents:")
            sorted_agents = sorted(
                summary["agent_metrics"].items(),
                key=lambda x: x[1]["total_pnl"],
                reverse=True
            )
            for agent_name, metrics in sorted_agents[:3]:
                logger.info(
                    f"    {agent_name}: {metrics['total_pnl']:.1f} PnL "
                    f"({metrics['win_count']}/{metrics['trades']} wins)"
                )

    # Final report
    logger.info("\n=== FINAL REPORT ===")
    report = competition.get_final_report()

    logger.info(f"Total P&L: {report['total_pnl']:.1f}")
    logger.info(f"Win Rate: {report['win_rate']:.1%}")
    logger.info(f"Sharpe Ratio: {report['sharpe_ratio']:.2f}")
    logger.info(f"Max Drawdown: {report['max_drawdown']:.1f}")
    logger.info(f"Escalations: {report['escalations']} / {report['total_trading_days']}")

    logger.info("\n=== REGIME PERFORMANCE ===")
    for regime, stats in report["regime_analysis"].items():
        logger.info(
            f"{regime}: {stats['days']} days, "
            f"{stats['total_pnl']:.1f} PnL, "
            f"{stats['win_rate']:.1%} win rate"
        )

    logger.info("\n=== FINAL RANKINGS ===")
    for regime, rankings in report["final_rankings"].items():
        logger.info(f"\n{regime}:")
        for i, agent in enumerate(rankings[:3], 1):
            logger.info(
                f"  {i}. {agent['agent_name']}: "
                f"Elo={agent['rating']:.0f}, "
                f"Games={agent['games_played']}, "
                f"WR={agent['win_rate']:.1%}"
            )

    # Save to file
    import tempfile
    import os

    # Save to competition directory if it exists
    results_path = "/workspace/group1-rag/competition/competition_results.json"
    try:
        competition.save_results(results_path)
    except Exception as e:
        logger.error(f"Could not save to {results_path}: {e}")
        # Try temp directory
        temp_path = os.path.join(tempfile.gettempdir(), "competition_results.json")
        competition.save_results(temp_path)
        logger.info(f"Saved to {temp_path} instead")

    logger.info("\nCompetition complete!")


if __name__ == "__main__":
    main()
