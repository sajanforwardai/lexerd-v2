"""
Multi-Agent Coordinator for Tier 3 Reasoning

Decomposes complex reasoning into specialized agents:
- Market Analyst: Analyzes market regime and conditions
- Strategy Selector: Evaluates and ranks strategy options
- Executor: Plans execution and risk management
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum

from reasoning_engine import (
    ReasoningState,
    ReasoningStep,
    ReasoningStepType,
    MarketRegime,
    Entity,
    Constraint,
)


class AgentRole(str, Enum):
    """Agent role types."""
    MARKET_ANALYST = "market_analyst"
    STRATEGY_SELECTOR = "strategy_selector"
    EXECUTOR = "executor"


@dataclass
class AgentOutput:
    """Output from an agent."""
    agent_role: AgentRole
    task_description: str
    analysis: str
    conclusions: List[str]
    recommendations: List[str]
    confidence: float
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['agent_role'] = self.agent_role.value
        return data


@dataclass
class CoordinationResult:
    """Result of multi-agent coordination."""
    agent_outputs: List[AgentOutput]
    final_recommendation: str
    reasoning_summary: str
    total_latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            'agent_outputs': [o.to_dict() for o in self.agent_outputs],
            'final_recommendation': self.final_recommendation,
            'reasoning_summary': self.reasoning_summary,
            'total_latency_ms': self.total_latency_ms,
            'timestamp': self.timestamp,
        }


class MarketAnalyst:
    """Agent: Analyzes market regime and conditions."""

    def analyze(
        self,
        regime: MarketRegime,
        entities: List[Entity],
        constraints: List[Constraint],
    ) -> AgentOutput:
        """Analyze market regime and conditions.

        Args:
            regime: Current market regime
            entities: Extracted entities
            constraints: Active constraints

        Returns:
            AgentOutput with market analysis
        """
        start_time = time.time()

        # Analyze regime characteristics
        regime_analysis = self._analyze_regime(regime)
        entity_analysis = self._analyze_entities(entities)
        constraint_analysis = self._analyze_constraints(constraints)

        analysis = f"""
        MARKET ANALYST ASSESSMENT
        ==========================

        Market Regime: {regime.value}
        {regime_analysis}

        Entity Distribution:
        {entity_analysis}

        Constraint Environment:
        {constraint_analysis}
        """

        conclusions = [
            f"Current regime is {regime.value}",
            f"Entity quality average: {self._avg_entity_confidence(entities):.2f}",
            f"Constraints: {len(constraints)} active ({sum(1 for c in constraints if c.violated)} violated)",
        ]

        recommendations = [
            "Monitor regime shifts in volatility",
            "Prioritize low-latency execution",
            "Ensure compliance with all constraints",
        ]

        latency = (time.time() - start_time) * 1000

        return AgentOutput(
            agent_role=AgentRole.MARKET_ANALYST,
            task_description="Analyze market regime and conditions",
            analysis=analysis.strip(),
            conclusions=conclusions,
            recommendations=recommendations,
            confidence=0.80,
            latency_ms=latency,
        )

    def _analyze_regime(self, regime: MarketRegime) -> str:
        """Analyze regime characteristics."""
        regime_chars = {
            MarketRegime.HIGH_VOL: "High volatility regime - favor volatility-sensitive strategies",
            MarketRegime.LOW_VOL: "Low volatility regime - emphasize carry and term structure",
            MarketRegime.TREND: "Trending regime - directional strategies aligned with trend",
            MarketRegime.MEAN_REVERT: "Mean-reverting regime - favor reversion strategies",
            MarketRegime.EVENT_DRIVEN: "Event-driven regime - concentrate on catalyst events",
            MarketRegime.CRISIS: "Crisis regime - defensive positioning essential",
            MarketRegime.STRESSED: "Stressed regime - liquidity premium elevated",
        }
        return regime_chars.get(regime.value, "Unknown regime characteristics")

    def _analyze_entities(self, entities: List[Entity]) -> str:
        """Analyze entity distribution."""
        if not entities:
            return "No entities extracted"
        type_counts = {}
        for e in entities:
            type_counts[e.entity_type] = type_counts.get(e.entity_type, 0) + 1
        analysis = "\n        ".join(f"{t}: {c}" for t, c in sorted(type_counts.items()))
        return analysis

    def _analyze_constraints(self, constraints: List[Constraint]) -> str:
        """Analyze constraints."""
        if not constraints:
            return "No active constraints"
        active = [c for c in constraints if not c.violated]
        violated = [c for c in constraints if c.violated]
        analysis = f"Active: {len(active)}, Violated: {len(violated)}"
        if violated:
            analysis += f" (violations: {', '.join(c.constraint_type.value for c in violated[:2])})"
        return analysis

    def _avg_entity_confidence(self, entities: List[Entity]) -> float:
        """Calculate average entity confidence."""
        if not entities:
            return 0.0
        return sum(e.confidence for e in entities) / len(entities)


class StrategySelector:
    """Agent: Evaluates and ranks strategy options."""

    def __init__(self):
        self.strategy_scores = {}

    def select_strategies(
        self,
        regime: MarketRegime,
        entities: List[Entity],
        constraints: List[Constraint],
        num_recommendations: int = 3,
    ) -> AgentOutput:
        """Select and rank strategy options.

        Args:
            regime: Current market regime
            entities: Extracted entities
            constraints: Active constraints
            num_recommendations: Number of top strategies to recommend

        Returns:
            AgentOutput with ranked strategies
        """
        start_time = time.time()

        # Evaluate strategies
        strategies = self._get_candidate_strategies(regime)
        ranked = self._rank_strategies(strategies, regime, entities, constraints)

        # Build analysis
        analysis = self._build_analysis(ranked, num_recommendations)
        conclusions = self._build_conclusions(ranked)
        recommendations = [s[0] for s in ranked[:num_recommendations]]

        latency = (time.time() - start_time) * 1000

        return AgentOutput(
            agent_role=AgentRole.STRATEGY_SELECTOR,
            task_description="Evaluate and rank strategy options",
            analysis=analysis,
            conclusions=conclusions,
            recommendations=recommendations,
            confidence=self._avg_rank_confidence(ranked),
            latency_ms=latency,
        )

    def _get_candidate_strategies(self, regime: MarketRegime) -> List[str]:
        """Get candidate strategies for regime."""
        all_strategies = [
            "gamma_scalping",
            "vol_arbitrage",
            "delta_hedging",
            "straddle",
            "strangle",
            "iron_butterfly",
            "calendar_spread",
            "skew_trading",
        ]
        # Filter by regime
        if regime == MarketRegime.HIGH_VOL:
            return [s for s in all_strategies if s in ["gamma_scalping", "straddle", "strangle"]]
        elif regime == MarketRegime.LOW_VOL:
            return [s for s in all_strategies if s in ["calendar_spread", "skew_trading"]]
        elif regime == MarketRegime.TREND:
            return [s for s in all_strategies if s in ["delta_hedging", "directional_spread"]]
        elif regime == MarketRegime.MEAN_REVERT:
            return [s for s in all_strategies if s in ["calendar_spread", "delta_hedging"]]
        else:
            return all_strategies[:3]

    def _rank_strategies(
        self,
        strategies: List[str],
        regime: MarketRegime,
        entities: List[Entity],
        constraints: List[Constraint],
    ) -> List[tuple]:
        """Rank strategies by suitability.

        Returns:
            List of (strategy, score) tuples, sorted descending
        """
        ranked = []
        for strategy in strategies:
            score = self._score_strategy(strategy, regime, entities, constraints)
            ranked.append((strategy, score))
            self.strategy_scores[strategy] = score
        return sorted(ranked, key=lambda x: x[1], reverse=True)

    def _score_strategy(
        self,
        strategy: str,
        regime: MarketRegime,
        entities: List[Entity],
        constraints: List[Constraint],
    ) -> float:
        """Score a strategy for the given regime."""
        regime_score = self._regime_compatibility(strategy, regime)
        entity_score = self._entity_alignment(strategy, entities)
        constraint_score = self._constraint_compatibility(strategy, constraints)

        return 0.4 * regime_score + 0.35 * entity_score + 0.25 * constraint_score

    def _regime_compatibility(self, strategy: str, regime: MarketRegime) -> float:
        """Score regime compatibility."""
        compatibility = {
            "gamma_scalping": {
                MarketRegime.HIGH_VOL: 0.95,
                MarketRegime.TREND: 0.70,
                MarketRegime.MEAN_REVERT: 0.75,
            },
            "vol_arbitrage": {
                MarketRegime.HIGH_VOL: 0.90,
                MarketRegime.LOW_VOL: 0.60,
            },
            "delta_hedging": {
                MarketRegime.TREND: 0.85,
                MarketRegime.CRISIS: 0.70,
            },
            "straddle": {
                MarketRegime.HIGH_VOL: 0.88,
                MarketRegime.LOW_VOL: 0.50,
            },
        }
        return compatibility.get(strategy, {}).get(regime, 0.50)

    def _entity_alignment(self, strategy: str, entities: List[Entity]) -> float:
        """Score entity alignment with strategy."""
        if not entities:
            return 0.50
        # Count matching entities
        matches = sum(
            1 for e in entities
            if any(kw in e.text.lower() for kw in self._strategy_keywords(strategy))
        )
        return min(1.0, (matches + 1) / len(entities) + 0.30)

    def _constraint_compatibility(self, strategy: str, constraints: List[Constraint]) -> float:
        """Score constraint compatibility."""
        if not constraints:
            return 1.0
        violations = sum(1 for c in constraints if c.violated)
        return max(0.0, 1.0 - violations / len(constraints))

    def _strategy_keywords(self, strategy: str) -> List[str]:
        """Get keywords for a strategy."""
        keywords = {
            "gamma_scalping": ["gamma", "scalp", "rehedge"],
            "vol_arbitrage": ["vol", "volatility", "arb"],
            "delta_hedging": ["delta", "hedge", "directional"],
            "straddle": ["straddle", "atm", "both sides"],
            "calendar_spread": ["calendar", "term", "structure"],
            "skew_trading": ["skew", "smile", "volatility"],
        }
        return keywords.get(strategy, [])

    def _build_analysis(self, ranked: List[tuple], num_recs: int) -> str:
        """Build analysis of ranked strategies."""
        analysis = "STRATEGY SELECTOR EVALUATION\n===========================\n\nRanked Strategies:\n"
        for i, (strategy, score) in enumerate(ranked[:5], 1):
            analysis += f"{i}. {strategy}: {score:.2f}\n"
        return analysis

    def _build_conclusions(self, ranked: List[tuple]) -> List[str]:
        """Build conclusions."""
        if not ranked:
            return ["No suitable strategies identified"]
        top_strategy, top_score = ranked[0]
        return [
            f"Top recommendation: {top_strategy} ({top_score:.2f})",
            f"Strategy count evaluated: {len(ranked)}",
        ]

    def _avg_rank_confidence(self, ranked: List[tuple]) -> float:
        """Average confidence across rankings."""
        if not ranked:
            return 0.0
        return sum(s for _, s in ranked) / len(ranked)


class Executor:
    """Agent: Plans execution and risk management."""

    def plan_execution(
        self,
        recommended_strategy: str,
        entities: List[Entity],
        constraints: List[Constraint],
        expected_payoff: float = 0.0,
    ) -> AgentOutput:
        """Plan execution for recommended strategy.

        Args:
            recommended_strategy: Strategy to execute
            entities: Extracted entities
            constraints: Active constraints
            expected_payoff: Expected payoff estimate

        Returns:
            AgentOutput with execution plan
        """
        start_time = time.time()

        # Create execution plan
        execution_steps = self._create_execution_steps(recommended_strategy)
        risk_plan = self._create_risk_plan(recommended_strategy, entities, constraints)
        monitoring_plan = self._create_monitoring_plan(recommended_strategy)

        analysis = f"""
        EXECUTION PLAN
        ==============

        Strategy: {recommended_strategy}
        Expected Payoff: {expected_payoff:.0f} bps

        Execution Steps:
        {self._format_steps(execution_steps)}

        Risk Management:
        {risk_plan}

        Monitoring:
        {monitoring_plan}
        """

        conclusions = [
            f"Execution plan created for {recommended_strategy}",
            f"Risk controls: {len(execution_steps)} checkpoints",
            "Ready for deployment" if self._all_constraints_met(constraints) else "Constraint violations present",
        ]

        recommendations = [
            "Execute in stages with risk monitoring",
            "Set stop-loss at -100 bps",
            "Monitor Greeks continuously",
        ]

        latency = (time.time() - start_time) * 1000

        return AgentOutput(
            agent_role=AgentRole.EXECUTOR,
            task_description="Plan execution and risk management",
            analysis=analysis.strip(),
            conclusions=conclusions,
            recommendations=recommendations,
            confidence=0.85,
            latency_ms=latency,
        )

    def _create_execution_steps(self, strategy: str) -> List[str]:
        """Create execution steps for strategy."""
        steps = [
            "1. Validate market conditions",
            "2. Prepare order parameters",
            "3. Set risk limits and alerts",
            "4. Execute initial position",
            "5. Monitor P&L and Greeks",
        ]
        return steps

    def _create_risk_plan(self, strategy: str, entities: List[Entity], constraints: List[Constraint]) -> str:
        """Create risk management plan."""
        greek_exposures = [e.text for e in entities if "greek" in e.entity_type.lower()]
        constraints_str = ", ".join(c.constraint_type.value for c in constraints[:2])

        plan = f"""
        Greeks to monitor: {', '.join(greek_exposures) if greek_exposures else 'Delta, Gamma, Theta, Vega'}
        Stop loss: -100 bps
        Take profit: +200 bps
        Active constraints: {constraints_str if constraints_str else 'None'}
        """
        return plan.strip()

    def _create_monitoring_plan(self, strategy: str) -> str:
        """Create monitoring plan."""
        return """
        Real-time monitoring:
        - P&L tracking every minute
        - Greek rebalancing as needed
        - Market regime monitoring
        - Constraint violation alerts
        """

    def _format_steps(self, steps: List[str]) -> str:
        """Format execution steps."""
        return "\n        ".join(steps)

    def _all_constraints_met(self, constraints: List[Constraint]) -> bool:
        """Check if all constraints are met."""
        return all(not c.violated for c in constraints)


class AgentCoordinator:
    """Coordinates multi-agent reasoning and recommendation."""

    def __init__(self, max_latency_ms: float = 5000.0):
        """Initialize coordinator.

        Args:
            max_latency_ms: Total latency budget for all agents
        """
        self.max_latency_ms = max_latency_ms
        self.market_analyst = MarketAnalyst()
        self.strategy_selector = StrategySelector()
        self.executor = Executor()

    def coordinate(
        self,
        reasoning_state: ReasoningState,
        recommended_strategy: Optional[str] = None,
        expected_payoff: float = 0.0,
    ) -> CoordinationResult:
        """Coordinate multi-agent reasoning.

        Args:
            reasoning_state: State from ReasoningEngine
            recommended_strategy: Optional pre-selected strategy
            expected_payoff: Optional expected payoff estimate

        Returns:
            CoordinationResult with all agent outputs and recommendation
        """
        start_time = time.time()
        agent_outputs = []

        # Step 1: Market Analysis (budget: 2s)
        analyst_output = self.market_analyst.analyze(
            reasoning_state.market_regime,
            reasoning_state.entities,
            reasoning_state.constraints,
        )
        agent_outputs.append(analyst_output)
        remaining_budget = self.max_latency_ms - (time.time() - start_time) * 1000

        # Step 2: Strategy Selection (budget: 2s)
        if remaining_budget > 500:
            selector_output = self.strategy_selector.select_strategies(
                reasoning_state.market_regime,
                reasoning_state.entities,
                reasoning_state.constraints,
            )
            agent_outputs.append(selector_output)
            # Use selected strategy if not provided
            if not recommended_strategy and selector_output.recommendations:
                recommended_strategy = selector_output.recommendations[0]
        remaining_budget = self.max_latency_ms - (time.time() - start_time) * 1000

        # Step 3: Execution Planning (budget: 1s)
        if remaining_budget > 300 and recommended_strategy:
            executor_output = self.executor.plan_execution(
                recommended_strategy,
                reasoning_state.entities,
                reasoning_state.constraints,
                expected_payoff,
            )
            agent_outputs.append(executor_output)

        # Generate final summary
        final_recommendation = recommended_strategy or "Unable to generate recommendation"
        reasoning_summary = self._generate_summary(agent_outputs)
        total_latency = (time.time() - start_time) * 1000

        return CoordinationResult(
            agent_outputs=agent_outputs,
            final_recommendation=final_recommendation,
            reasoning_summary=reasoning_summary,
            total_latency_ms=total_latency,
        )

    def _generate_summary(self, outputs: List[AgentOutput]) -> str:
        """Generate summary of all agent outputs."""
        if not outputs:
            return "No agent outputs"

        summary = "MULTI-AGENT COORDINATION SUMMARY\n"
        summary += "=" * 40 + "\n\n"

        for output in outputs:
            summary += f"{output.agent_role.value.upper()}\n"
            summary += f"Confidence: {output.confidence:.2f}\n"
            summary += f"Conclusions: {'; '.join(output.conclusions[:2])}\n\n"

        return summary
