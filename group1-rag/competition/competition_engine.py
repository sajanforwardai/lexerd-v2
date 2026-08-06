"""
Competition Engine: Elo Rating & Strategy Selection
=====================================================

Manages agent competition via Elo ratings. Selects best strategy
for current regime using weighted Elo scores and agent confidence.

Architecture:
- Elo rating per agent-regime pair
- Confidence-weighted selection
- Daily learning updates from ObservationCollector
- Dual-strategy A/B decision for hedging
- Confidence thresholds for escalation

Elo Formula:
- Standard Elo: Rating_new = Rating_old + K * (result - expected)
- K-factor: higher K (32-64) for newer ratings or high-vol regimes
- result: 1.0 for win (profitable trade), 0.0 for loss, 0.5 for breakeven
- expected: 1 / (1 + 10^((opponent_elo - player_elo) / 400))
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from strategy_agent import StrategyAgent, StrategySelection, ActionType
from agent_pool import AgentPool

logger = logging.getLogger(__name__)


@dataclass
class EloRating:
    """Elo rating for an agent-regime pair."""
    agent_name: str
    regime: str
    rating: float = 1600.0  # Standard starting Elo
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    last_updated: str = ""
    k_factor: int = 32  # Adjustment speed

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.utcnow().isoformat()

    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played

    def expected_score(self, opponent_rating: float) -> float:
        """Calculate expected score vs opponent rating."""
        return 1.0 / (1.0 + math.pow(10, (opponent_rating - self.rating) / 400.0))

    def update(self, result: float, opponent_rating: float = 1600.0):
        """
        Update rating based on game result.

        Args:
            result: 1.0 (win), 0.5 (draw), 0.0 (loss)
            opponent_rating: Rating of "opponent" (average pool rating)
        """
        expected = self.expected_score(opponent_rating)
        self.rating += self.k_factor * (result - expected)
        self.rating = max(0, self.rating)  # Clamp to non-negative

        self.games_played += 1
        if result == 1.0:
            self.wins += 1
        elif result == 0.0:
            self.losses += 1

        self.last_updated = datetime.utcnow().isoformat()


class CompetitionEngine:
    """
    Manages agent competition and strategy selection.

    Uses Elo ratings to track agent performance by regime, then
    selects best strategies via confidence-weighted voting.
    """

    def __init__(self, agent_pool: AgentPool):
        """
        Initialize competition engine.

        Args:
            agent_pool: AgentPool with strategy agents
        """
        self.agent_pool = agent_pool

        # Elo ratings by agent-regime pair
        self.elo_ratings: Dict[Tuple[str, str], EloRating] = {}

        # Selection history
        self.selection_history: List[Dict[str, Any]] = []

        # Current best agents per regime
        self.regime_leaders: Dict[str, str] = {}  # regime -> agent_name

        logger.info("Initialized CompetitionEngine")

    def _get_elo_key(self, agent_name: str, regime: str) -> Tuple[str, str]:
        """Get dictionary key for Elo rating."""
        return (agent_name, regime)

    def get_or_create_elo(self, agent_name: str, regime: str) -> EloRating:
        """Get or create Elo rating for agent-regime pair."""
        key = self._get_elo_key(agent_name, regime)

        if key not in self.elo_ratings:
            self.elo_ratings[key] = EloRating(agent_name=agent_name, regime=regime)

        return self.elo_ratings[key]

    def select_strategies(
        self,
        regime: str,
        agent_selections: Dict[str, StrategySelection],
        max_strategies: int = 2
    ) -> List[Tuple[str, StrategySelection]]:
        """
        Select top strategies from agent selections.

        Uses action_score = agent_elo[regime] * confidence to rank.

        Args:
            regime: Current market regime
            agent_selections: Dict of {agent_name: StrategySelection}
            max_strategies: How many top strategies to return

        Returns:
            List of (agent_name, StrategySelection) tuples, ranked by score
        """
        scored_strategies = []

        for agent_name, selection in agent_selections.items():
            elo = self.get_or_create_elo(agent_name, regime)

            # Action score combines Elo and agent confidence
            action_score = (elo.rating / 1600.0) * selection.confidence

            scored_strategies.append({
                "agent_name": agent_name,
                "selection": selection,
                "elo_rating": elo.rating,
                "confidence": selection.confidence,
                "action_score": action_score
            })

        # Sort by action score (descending)
        scored_strategies.sort(key=lambda x: x["action_score"], reverse=True)

        # Return top N
        selected = [
            (item["agent_name"], item["selection"])
            for item in scored_strategies[:max_strategies]
        ]

        return selected

    def get_winner_and_hedge(
        self,
        regime: str,
        agent_selections: Dict[str, StrategySelection],
        confidence_threshold: float = 0.60
    ) -> Tuple[Optional[Tuple[str, StrategySelection]], Optional[Tuple[str, StrategySelection]], str]:
        """
        Determine winning strategy and hedge strategy.

        Uses confidence thresholds for escalation decisions.

        Returns:
            (winner, hedge, decision_reason)
            - winner: (agent_name, StrategySelection) or None
            - hedge: backup strategy or None
            - decision_reason: explanation of decision
        """
        top_strategies = self.select_strategies(regime, agent_selections, max_strategies=3)

        if not top_strategies:
            return (None, None, "No valid strategies available")

        winner_agent, winner_selection = top_strategies[0]

        # Confidence escalation logic
        if winner_selection.confidence < 0.40:
            reason = (
                f"ESCALATE: Top agent {winner_agent} confidence {winner_selection.confidence:.2%} "
                f"below 40% threshold - human review required"
            )
            logger.warning(reason)
            return (None, None, reason)

        elif winner_selection.confidence < confidence_threshold:
            reason = (
                f"LOW_CONFIDENCE: Top agent {winner_agent} confidence {winner_selection.confidence:.2%} "
                f"below {confidence_threshold:.0%} - executing with hedge"
            )
            logger.info(reason)

            # Use second strategy as hedge
            hedge = top_strategies[1] if len(top_strategies) > 1 else None
            return ((winner_agent, winner_selection), hedge, reason)

        else:
            reason = f"CONFIDENT: {winner_agent} selected with {winner_selection.confidence:.2%} confidence"
            hedge = top_strategies[1] if len(top_strategies) > 1 else None
            return ((winner_agent, winner_selection), hedge, reason)

    def update_elo_from_trade(
        self,
        agent_name: str,
        regime: str,
        pnl: float,
        trade_outcome: str = "closed"  # "closed", "active", "cancelled"
    ):
        """
        Update Elo rating based on trade outcome.

        Called daily by learning loop with ObservationCollector results.

        Args:
            agent_name: Agent that made the decision
            regime: Regime where trade occurred
            pnl: P&L from trade (can be negative)
            trade_outcome: Status of trade
        """
        elo = self.get_or_create_elo(agent_name, regime)

        # Convert P&L to Elo result (1 = win, 0.5 = draw, 0 = loss)
        if pnl > 0:
            result = 1.0
        elif pnl == 0:
            result = 0.5
        else:
            result = 0.0

        # Get average pool rating for this regime (opponent strength)
        regime_ratings = [
            e.rating for (a, r), e in self.elo_ratings.items()
            if r == regime
        ]
        avg_rating = sum(regime_ratings) / len(regime_ratings) if regime_ratings else 1600.0

        # Adjust K-factor based on confidence
        if elo.games_played < 20:
            elo.k_factor = 64  # High K for new agents
        elif elo.games_played < 50:
            elo.k_factor = 48
        else:
            elo.k_factor = 32

        # Update rating
        elo.update(result, avg_rating)

        # Update agent's internal tracking
        agent = self.agent_pool.get_agent_by_name(agent_name)
        if agent:
            agent.update_performance(regime, pnl, trade_count=1, is_win=(pnl > 0))

        logger.debug(
            f"Updated Elo: {agent_name} in {regime}: "
            f"result={result}, new_rating={elo.rating:.0f}, k_factor={elo.k_factor}"
        )

    def update_regime_leader(self, regime: str):
        """Update the leading agent for this regime."""
        regime_elos = [
            (agent_name, e.rating)
            for (agent_name, r), e in self.elo_ratings.items()
            if r == regime
        ]

        if regime_elos:
            leader = max(regime_elos, key=lambda x: x[1])
            self.regime_leaders[regime] = leader[0]

    def get_regime_rankings(self, regime: str) -> List[Dict[str, Any]]:
        """Get ranked list of agents in a regime."""
        rankings = []

        for (agent_name, r), elo in self.elo_ratings.items():
            if r == regime:
                rankings.append({
                    "agent_name": agent_name,
                    "rating": elo.rating,
                    "games_played": elo.games_played,
                    "win_rate": elo.win_rate(),
                    "k_factor": elo.k_factor
                })

        rankings.sort(key=lambda x: x["rating"], reverse=True)
        return rankings

    def get_global_rankings(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get agent rankings across all regimes."""
        regimes = set(r for _, r in self.elo_ratings.keys())
        return {regime: self.get_regime_rankings(regime) for regime in regimes}

    def record_selection(
        self,
        regime: str,
        winner: Optional[Tuple[str, StrategySelection]],
        hedge: Optional[Tuple[str, StrategySelection]],
        reason: str
    ):
        """Record strategy selection decision."""
        self.selection_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "regime": regime,
            "winner": winner[0] if winner else None,
            "winner_strategy": winner[1].strategy_name if winner else None,
            "winner_confidence": winner[1].confidence if winner else None,
            "hedge": hedge[0] if hedge else None,
            "hedge_strategy": hedge[1].strategy_name if hedge else None,
            "reason": reason
        })

    def get_competition_stats(self) -> Dict[str, Any]:
        """Get overall competition statistics."""
        total_games = sum(e.games_played for e in self.elo_ratings.values())
        total_wins = sum(e.wins for e in self.elo_ratings.values())
        total_losses = sum(e.losses for e in self.elo_ratings.values())

        return {
            "total_games_played": total_games,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "overall_win_rate": total_wins / total_games if total_games > 0 else 0.0,
            "unique_regimes": len(set(r for _, r in self.elo_ratings.keys())),
            "unique_agents": len(set(a for a, _ in self.elo_ratings.keys())),
            "selection_decisions": len(self.selection_history),
            "regime_leaders": self.regime_leaders
        }

    def export_state(self, filepath: str) -> bool:
        """Export competition state to JSON."""
        import json

        try:
            export = {
                "exported_at": datetime.utcnow().isoformat(),
                "elo_ratings": [
                    {
                        "agent_name": elo.agent_name,
                        "regime": elo.regime,
                        "rating": elo.rating,
                        "games_played": elo.games_played,
                        "win_rate": elo.win_rate(),
                        "last_updated": elo.last_updated
                    }
                    for elo in self.elo_ratings.values()
                ],
                "regime_leaders": self.regime_leaders,
                "stats": self.get_competition_stats()
            }

            with open(filepath, 'w') as f:
                json.dump(export, f, indent=2)

            logger.info(f"Exported competition state to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export state: {e}")
            return False

    def __repr__(self) -> str:
        stats = self.get_competition_stats()
        return (
            f"CompetitionEngine("
            f"agents={stats['unique_agents']}, "
            f"regimes={stats['unique_regimes']}, "
            f"games={stats['total_games_played']}, "
            f"win_rate={stats['overall_win_rate']:.2%})"
        )
