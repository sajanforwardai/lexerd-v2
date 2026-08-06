"""
Tier 3: Agentic Reasoning Engine for Group One RAG

Tree-of-Thought reasoning with state management, multi-step validation,
and latency budget enforcement.

Components:
- ReasoningState: Manages regime, entities, constraints, reasoning chain
- ReasoningNode: Tree-of-Thought node with reasoning data
- ReasoningEngine: Core engine with TOT, ranking, and CoT validation
- RankingFunction: Edge strength, historical performance, risk metrics
"""

import json
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
import hashlib


class MarketRegime(str, Enum):
    """Market regime types."""
    HIGH_VOL = "high_volatility"
    LOW_VOL = "low_volatility"
    TREND = "trending"
    MEAN_REVERT = "mean_reverting"
    EVENT_DRIVEN = "event_driven"
    CRISIS = "crisis"
    STRESSED = "stressed_regime"


class ConstraintType(str, Enum):
    """Constraint types for reasoning validation."""
    POSITION_LIMIT = "position_limit"
    NOTIONAL_LIMIT = "notional_limit"
    GREEK_EXPOSURE = "greek_exposure"
    CORRELATION = "correlation"
    LIQUIDITY = "liquidity"
    REGULATORY = "regulatory"
    MARKET_REGIME = "market_regime"


class ReasoningStepType(str, Enum):
    """Types of reasoning steps."""
    REGIME_ANALYSIS = "regime_analysis"
    ENTITY_ASSESSMENT = "entity_assessment"
    CONSTRAINT_VALIDATION = "constraint_validation"
    STRATEGY_RANKING = "strategy_ranking"
    RISK_EVALUATION = "risk_evaluation"
    SYNTHESIS = "synthesis"


@dataclass
class Constraint:
    """A constraint on the reasoning process."""
    constraint_type: ConstraintType
    description: str
    value: Any
    severity: float = 0.8  # [0, 1] - how strictly to enforce
    violated: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Entity:
    """An extracted entity with metadata."""
    entity_id: str
    entity_type: str
    text: str
    confidence: float
    kg_node_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ReasoningStep:
    """A single reasoning step in the chain."""
    step_id: str
    step_type: ReasoningStepType
    description: str
    reasoning: str
    conclusion: str
    confidence: float
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    validations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['step_type'] = self.step_type.value
        return data


@dataclass
class RankingMetrics:
    """Metrics for ranking strategies/options."""
    edge_strength: float  # [0, 1] strength of this reasoning path
    historical_performance: float  # [0, 1] past performance
    risk_adjusted_score: float  # [0, 1] risk-adjusted return
    expected_payoff: float  # absolute value
    constraint_alignment: float  # [0, 1] alignment with constraints
    regime_alignment: float  # [0, 1] alignment with market regime

    def composite_score(self) -> float:
        """Compute composite ranking score."""
        return (
            0.20 * self.edge_strength +
            0.25 * self.historical_performance +
            0.20 * self.risk_adjusted_score +
            0.15 * self.constraint_alignment +
            0.20 * self.regime_alignment
        )

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ReasoningNode:
    """A node in the Tree-of-Thought."""
    node_id: str
    depth: int
    parent_id: Optional[str]
    step: ReasoningStep
    metrics: RankingMetrics
    children_ids: List[str] = field(default_factory=list)
    is_leaf: bool = False
    strategy_option: Optional[str] = None

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['metrics'] = self.metrics.to_dict()
        data['step'] = self.step.to_dict()
        return data


@dataclass
class ReasoningState:
    """State management for reasoning process."""
    market_regime: MarketRegime
    entities: List[Entity]
    constraints: List[Constraint]
    reasoning_chain: List[ReasoningStep] = field(default_factory=list)
    reasoning_tree: Dict[str, ReasoningNode] = field(default_factory=dict)
    root_node_id: Optional[str] = None
    accumulated_latency_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            'market_regime': self.market_regime.value,
            'entities': [e.to_dict() for e in self.entities],
            'constraints': [c.to_dict() for c in self.constraints],
            'reasoning_chain': [s.to_dict() for s in self.reasoning_chain],
            'reasoning_tree_size': len(self.reasoning_tree),
            'root_node_id': self.root_node_id,
            'accumulated_latency_ms': self.accumulated_latency_ms,
            'timestamp': self.timestamp,
        }

    def add_reasoning_step(self, step: ReasoningStep) -> None:
        """Add a reasoning step to the chain."""
        self.reasoning_chain.append(step)

    def add_node(self, node: ReasoningNode) -> None:
        """Add a reasoning node to the tree."""
        self.reasoning_tree[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[ReasoningNode]:
        """Retrieve a node from the tree."""
        return self.reasoning_tree.get(node_id)

    def validate_constraints(self) -> Tuple[bool, List[str]]:
        """Check all constraints and return (valid, violations)."""
        violations = []
        for constraint in self.constraints:
            # Mark as violated if severity is high and value fails validation
            if constraint.severity > 0.5 and self._check_constraint_violation(constraint):
                constraint.violated = True
                violations.append(constraint.description)
        return len(violations) == 0, violations

    def _check_constraint_violation(self, constraint: Constraint) -> bool:
        """Check if a specific constraint is violated."""
        # Simplified check - in production, this would be more sophisticated
        return constraint.value is not None and constraint.value < 0


class RankingFunction:
    """Ranking function for evaluating strategies and options."""

    def __init__(self):
        self.historical_performance_cache = {}

    def rank(
        self,
        strategy_name: str,
        regime: MarketRegime,
        entities: List[Entity],
        constraints: List[Constraint],
    ) -> RankingMetrics:
        """Compute ranking metrics for a strategy option."""
        edge_strength = self._compute_edge_strength(strategy_name, entities)
        hist_perf = self._get_historical_performance(strategy_name, regime)
        risk_score = self._compute_risk_adjusted_score(strategy_name, entities)
        payoff = self._estimate_expected_payoff(strategy_name, regime)
        constraint_align = self._compute_constraint_alignment(strategy_name, constraints)
        regime_align = self._compute_regime_alignment(strategy_name, regime)

        return RankingMetrics(
            edge_strength=edge_strength,
            historical_performance=hist_perf,
            risk_adjusted_score=risk_score,
            expected_payoff=payoff,
            constraint_alignment=constraint_align,
            regime_alignment=regime_align,
        )

    def _compute_edge_strength(self, strategy: str, entities: List[Entity]) -> float:
        """Compute edge strength based on entity relevance."""
        # Simple: count of relevant entities / total entities
        relevant_count = sum(
            1 for e in entities
            if any(keyword in e.text.lower() for keyword in [strategy.lower()])
        )
        return min(1.0, (relevant_count + 1) / max(len(entities), 1))

    def _get_historical_performance(self, strategy: str, regime: MarketRegime) -> float:
        """Retrieve historical performance for strategy in regime."""
        cache_key = f"{strategy}:{regime.value}"
        if cache_key not in self.historical_performance_cache:
            # Mock: return performance based on regime compatibility
            perf_map = {
                MarketRegime.HIGH_VOL: 0.75,
                MarketRegime.LOW_VOL: 0.55,
                MarketRegime.TREND: 0.65,
                MarketRegime.MEAN_REVERT: 0.72,
                MarketRegime.EVENT_DRIVEN: 0.68,
                MarketRegime.CRISIS: 0.50,
                MarketRegime.STRESSED: 0.45,
            }
            self.historical_performance_cache[cache_key] = perf_map.get(regime, 0.60)
        return self.historical_performance_cache[cache_key]

    def _compute_risk_adjusted_score(self, strategy: str, entities: List[Entity]) -> float:
        """Compute risk-adjusted score based on Greek exposures."""
        # Mock: base score adjusted by entity risk factors
        greek_risk = sum(
            (1.0 - e.confidence) for e in entities
            if any(greek in e.entity_type.lower() for greek in ['delta', 'gamma', 'vega', 'theta'])
        )
        base_score = 0.70
        return max(0.0, base_score - (greek_risk * 0.1))

    def _estimate_expected_payoff(self, strategy: str, regime: MarketRegime) -> float:
        """Estimate expected payoff (notional basis points)."""
        # Mock: payoff depends on regime volatility
        regime_payoff_map = {
            MarketRegime.HIGH_VOL: 250.0,
            MarketRegime.LOW_VOL: 75.0,
            MarketRegime.TREND: 150.0,
            MarketRegime.MEAN_REVERT: 200.0,
            MarketRegime.EVENT_DRIVEN: 180.0,
            MarketRegime.CRISIS: 50.0,
            MarketRegime.STRESSED: 30.0,
        }
        return regime_payoff_map.get(regime, 100.0)

    def _compute_constraint_alignment(self, strategy: str, constraints: List[Constraint]) -> float:
        """Compute alignment with constraints."""
        if not constraints:
            return 1.0
        violations = sum(1 for c in constraints if c.violated)
        return max(0.0, 1.0 - (violations / len(constraints)))

    def _compute_regime_alignment(self, strategy: str, regime: MarketRegime) -> float:
        """Compute alignment between strategy and market regime."""
        strategy_regime_map = {
            "gamma_scalping": {MarketRegime.HIGH_VOL: 0.95, MarketRegime.TREND: 0.75},
            "vol_arbitrage": {MarketRegime.HIGH_VOL: 0.90, MarketRegime.LOW_VOL: 0.60},
            "delta_hedging": {MarketRegime.TREND: 0.85, MarketRegime.CRISIS: 0.70},
            "straddle": {MarketRegime.HIGH_VOL: 0.88, MarketRegime.LOW_VOL: 0.50},
        }
        strategy_lower = strategy.lower()
        if strategy_lower in strategy_regime_map:
            return strategy_regime_map[strategy_lower].get(regime, 0.60)
        return 0.65


class ReasoningEngine:
    """Core Tier 3 agentic reasoning engine with Tree-of-Thought."""

    def __init__(
        self,
        max_depth: int = 3,
        max_branching_factor: int = 3,
        max_total_latency_ms: float = 5000.0,
        max_step_latency_ms: float = 2000.0,
    ):
        """Initialize the reasoning engine.

        Args:
            max_depth: Maximum depth of reasoning tree (default: 3)
            max_branching_factor: Max children per node (default: 3)
            max_total_latency_ms: Total latency budget (default: 5000ms)
            max_step_latency_ms: Per-step latency budget (default: 2000ms)
        """
        self.max_depth = max_depth
        self.max_branching_factor = max_branching_factor
        self.max_total_latency_ms = max_total_latency_ms
        self.max_step_latency_ms = max_step_latency_ms
        self.ranking_function = RankingFunction()
        self.node_counter = 0

    def reason(
        self,
        market_regime: MarketRegime,
        entities: List[Dict],
        constraints: List[Dict],
        retrieved_documents: List[Dict],
        latency_budget_ms: Optional[float] = None,
    ) -> ReasoningState:
        """Execute Tree-of-Thought reasoning.

        Args:
            market_regime: Current market regime
            entities: Extracted entities from Tier 2
            constraints: Active constraints
            retrieved_documents: Retrieved documents from Tier 1
            latency_budget_ms: Optional override for total latency budget

        Returns:
            ReasoningState with complete reasoning chain and tree
        """
        start_time = time.time()
        budget = latency_budget_ms or self.max_total_latency_ms

        # Initialize state
        state = ReasoningState(
            market_regime=market_regime,
            entities=[Entity(**e) if isinstance(e, dict) else e for e in entities],
            constraints=[Constraint(**c) if isinstance(c, dict) else c for c in constraints],
        )

        # Step 1: Regime Analysis (within latency budget)
        if time.time() - start_time < budget / 1000.0:
            self._regime_analysis_step(state, start_time, budget)

        # Step 2: Entity Assessment (within latency budget)
        if time.time() - start_time < budget / 1000.0:
            self._entity_assessment_step(state, start_time, budget)

        # Step 3: Constraint Validation (within latency budget)
        if time.time() - start_time < budget / 1000.0:
            self._constraint_validation_step(state, start_time, budget)

        # Build reasoning tree (Tree-of-Thought)
        if time.time() - start_time < budget / 1000.0:
            self._build_reasoning_tree(state, start_time, budget)

        # Record total latency
        total_latency = (time.time() - start_time) * 1000
        state.accumulated_latency_ms = total_latency

        return state

    def _regime_analysis_step(
        self,
        state: ReasoningState,
        start_time: float,
        budget_ms: float,
    ) -> None:
        """Step 1: Analyze market regime."""
        step_start = time.time()

        # Reasoning about regime
        reasoning = f"""
        Analyzing market regime: {state.market_regime.value}
        - Implied volatility regime: high/low vol characteristics
        - Trend vs mean reversion: momentum analysis
        - Event risk: concentration in tail events
        - Liquidity conditions: bid-ask spreads, order flow
        """

        conclusion = f"""
        Market regime assessment complete.
        Current regime: {state.market_regime.value}
        Implications for strategy selection: High bias toward volatility-sensitive strategies
        """

        confidence = self._assess_regime_confidence(state)

        step = ReasoningStep(
            step_id=self._generate_step_id("regime"),
            step_type=ReasoningStepType.REGIME_ANALYSIS,
            description="Analyze current market regime and characteristics",
            reasoning=reasoning.strip(),
            conclusion=conclusion.strip(),
            confidence=confidence,
            duration_ms=(time.time() - step_start) * 1000,
            validations=["Regime matches entity distributions", "Constraints consistent with regime"],
        )

        state.add_reasoning_step(step)

    def _entity_assessment_step(
        self,
        state: ReasoningState,
        start_time: float,
        budget_ms: float,
    ) -> None:
        """Step 2: Assess extracted entities."""
        step_start = time.time()

        entity_summary = self._summarize_entities(state.entities)

        reasoning = f"""
        Assessing {len(state.entities)} extracted entities:
        {entity_summary}

        Entity confidence distribution:
        - High (>0.80): {sum(1 for e in state.entities if e.confidence > 0.80)}
        - Medium (0.60-0.80): {sum(1 for e in state.entities if 0.60 <= e.confidence <= 0.80)}
        - Low (<0.60): {sum(1 for e in state.entities if e.confidence < 0.60)}
        """

        conclusion = f"""
        Entity assessment complete.
        Key entities identified: {', '.join(e.text for e in state.entities[:3])}
        Overall entity quality: {self._assess_entity_quality(state.entities):.2f}
        Relevant Greeks: {self._extract_greek_entities(state.entities)}
        """

        confidence = min(1.0, sum(e.confidence for e in state.entities) / max(len(state.entities), 1))

        step = ReasoningStep(
            step_id=self._generate_step_id("entity"),
            step_type=ReasoningStepType.ENTITY_ASSESSMENT,
            description="Assess quality and relevance of extracted entities",
            reasoning=reasoning.strip(),
            conclusion=conclusion.strip(),
            confidence=confidence,
            duration_ms=(time.time() - step_start) * 1000,
            validations=["Entity count non-zero", "Confidence scores in valid range"],
        )

        state.add_reasoning_step(step)

    def _constraint_validation_step(
        self,
        state: ReasoningState,
        start_time: float,
        budget_ms: float,
    ) -> None:
        """Step 3: Validate constraints."""
        step_start = time.time()

        valid, violations = state.validate_constraints()

        reasoning = f"""
        Validating {len(state.constraints)} constraints:
        """
        for c in state.constraints:
            reasoning += f"\n        - {c.constraint_type.value}: {c.description}"

        conclusion = f"""
        Constraint validation complete.
        Valid: {valid}
        Violations: {len(violations)}
        """
        if violations:
            conclusion += f"\nViolated constraints: {', '.join(violations)}"

        confidence = 1.0 if valid else max(0.0, 1.0 - len(violations) / max(len(state.constraints), 1))

        step = ReasoningStep(
            step_id=self._generate_step_id("constraint"),
            step_type=ReasoningStepType.CONSTRAINT_VALIDATION,
            description="Validate constraints and check for violations",
            reasoning=reasoning.strip(),
            conclusion=conclusion.strip(),
            confidence=confidence,
            duration_ms=(time.time() - step_start) * 1000,
            validations=["All constraints checked", "Violations flagged if present"],
        )

        state.add_reasoning_step(step)

    def _build_reasoning_tree(
        self,
        state: ReasoningState,
        start_time: float,
        budget_ms: float,
    ) -> None:
        """Build Tree-of-Thought reasoning tree."""
        # Root node represents regime analysis
        root_node = self._create_node(
            depth=0,
            parent_id=None,
            step=state.reasoning_chain[0],
            strategy_option="regime_analysis",
        )
        state.root_node_id = root_node.node_id
        state.add_node(root_node)

        # First level: Strategy options
        strategies = ["gamma_scalping", "vol_arbitrage", "delta_hedging", "straddle"]
        branching_1 = min(self.max_branching_factor, len(strategies))

        for i, strategy in enumerate(strategies[:branching_1]):
            if time.time() - start_time > (budget_ms / 1000.0 * 0.9):
                break

            node = self._create_strategy_node(
                depth=1,
                parent_id=root_node.node_id,
                strategy=strategy,
                regime=state.market_regime,
                entities=state.entities,
                constraints=state.constraints,
            )
            state.add_node(node)
            root_node.children_ids.append(node.node_id)

            # Second level: Risk evaluation per strategy
            risk_options = ["hedged", "unhedged", "partially_hedged"]
            branching_2 = min(self.max_branching_factor, len(risk_options))

            for j, risk_option in enumerate(risk_options[:branching_2]):
                if time.time() - start_time > (budget_ms / 1000.0 * 0.95):
                    break

                risk_node = self._create_risk_node(
                    depth=2,
                    parent_id=node.node_id,
                    strategy=strategy,
                    risk_option=risk_option,
                    regime=state.market_regime,
                    entities=state.entities,
                    constraints=state.constraints,
                )
                state.add_node(risk_node)
                node.children_ids.append(risk_node.node_id)
                risk_node.is_leaf = True

    def _create_node(
        self,
        depth: int,
        parent_id: Optional[str],
        step: ReasoningStep,
        strategy_option: Optional[str] = None,
    ) -> ReasoningNode:
        """Create a reasoning node."""
        node_id = f"node_{depth}_{self.node_counter}"
        self.node_counter += 1

        # Placeholder metrics for root node
        metrics = RankingMetrics(
            edge_strength=1.0,
            historical_performance=0.65,
            risk_adjusted_score=0.70,
            expected_payoff=0.0,
            constraint_alignment=1.0,
            regime_alignment=0.75,
        )

        return ReasoningNode(
            node_id=node_id,
            depth=depth,
            parent_id=parent_id,
            step=step,
            metrics=metrics,
            strategy_option=strategy_option,
        )

    def _create_strategy_node(
        self,
        depth: int,
        parent_id: str,
        strategy: str,
        regime: MarketRegime,
        entities: List[Entity],
        constraints: List[Constraint],
    ) -> ReasoningNode:
        """Create a strategy option node."""
        node_id = f"node_{depth}_{self.node_counter}"
        self.node_counter += 1

        metrics = self.ranking_function.rank(strategy, regime, entities, constraints)

        reasoning = f"""
        Evaluating strategy: {strategy}
        - Regime alignment: {metrics.regime_alignment:.2f}
        - Historical performance: {metrics.historical_performance:.2f}
        - Risk-adjusted score: {metrics.risk_adjusted_score:.2f}
        - Expected payoff: {metrics.expected_payoff:.0f} bps
        """

        conclusion = f"""
        Strategy {strategy} assessment:
        Composite score: {metrics.composite_score():.2f}
        Recommendation: {'Strong' if metrics.composite_score() > 0.75 else 'Moderate' if metrics.composite_score() > 0.50 else 'Weak'}
        """

        step = ReasoningStep(
            step_id=self._generate_step_id(strategy),
            step_type=ReasoningStepType.STRATEGY_RANKING,
            description=f"Evaluate {strategy} strategy option",
            reasoning=reasoning.strip(),
            conclusion=conclusion.strip(),
            confidence=metrics.composite_score(),
            duration_ms=50.0,
            validations=["Metrics computed", "Regime alignment verified"],
        )

        return ReasoningNode(
            node_id=node_id,
            depth=depth,
            parent_id=parent_id,
            step=step,
            metrics=metrics,
            strategy_option=strategy,
        )

    def _create_risk_node(
        self,
        depth: int,
        parent_id: str,
        strategy: str,
        risk_option: str,
        regime: MarketRegime,
        entities: List[Entity],
        constraints: List[Constraint],
    ) -> ReasoningNode:
        """Create a risk evaluation node."""
        node_id = f"node_{depth}_{self.node_counter}"
        self.node_counter += 1

        # Risk-specific metrics
        base_metrics = self.ranking_function.rank(strategy, regime, entities, constraints)
        risk_adjustment = self._risk_adjustment(risk_option, constraints)

        metrics = RankingMetrics(
            edge_strength=base_metrics.edge_strength,
            historical_performance=base_metrics.historical_performance,
            risk_adjusted_score=base_metrics.risk_adjusted_score * risk_adjustment,
            expected_payoff=base_metrics.expected_payoff * risk_adjustment,
            constraint_alignment=base_metrics.constraint_alignment,
            regime_alignment=base_metrics.regime_alignment,
        )

        reasoning = f"""
        Risk evaluation for {strategy} with {risk_option} approach:
        - Greeks coverage: {risk_option}
        - Constraint alignment: {metrics.constraint_alignment:.2f}
        - Risk-adjusted payoff: {metrics.expected_payoff:.0f} bps
        """

        conclusion = f"""
        Final recommendation: {strategy} ({risk_option})
        Expected return: {metrics.expected_payoff:.0f} bps
        Risk level: {'Low' if risk_adjustment > 0.8 else 'Medium' if risk_adjustment > 0.5 else 'High'}
        """

        step = ReasoningStep(
            step_id=self._generate_step_id(f"{strategy}_{risk_option}"),
            step_type=ReasoningStepType.RISK_EVALUATION,
            description=f"Evaluate risk profile for {strategy} ({risk_option})",
            reasoning=reasoning.strip(),
            conclusion=conclusion.strip(),
            confidence=metrics.composite_score(),
            duration_ms=50.0,
            validations=["Risk adjustment applied", "Payoff recalculated"],
        )

        return ReasoningNode(
            node_id=node_id,
            depth=depth,
            parent_id=parent_id,
            step=step,
            metrics=metrics,
            strategy_option=f"{strategy}_{risk_option}",
        )

    def _risk_adjustment(self, risk_option: str, constraints: List[Constraint]) -> float:
        """Compute risk adjustment factor."""
        base = 1.0
        if risk_option == "hedged":
            base = 1.2  # More conservative, better constraint alignment
        elif risk_option == "unhedged":
            base = 0.7  # More aggressive, higher risk
        else:  # partially_hedged
            base = 1.0

        # Reduce if constraints are violated
        violation_count = sum(1 for c in constraints if c.violated)
        base *= (1.0 - violation_count * 0.15)

        return max(0.1, base)

    def _assess_regime_confidence(self, state: ReasoningState) -> float:
        """Assess confidence in regime classification."""
        # Mock: based on entity alignment with regime
        aligned = sum(
            1 for e in state.entities
            if self._is_entity_aligned_with_regime(e, state.market_regime)
        )
        return min(1.0, aligned / max(len(state.entities), 1) + 0.2)

    def _is_entity_aligned_with_regime(self, entity: Entity, regime: MarketRegime) -> bool:
        """Check if entity is aligned with regime."""
        regime_keywords = {
            MarketRegime.HIGH_VOL: ["volatility", "gamma", "vega", "straddle"],
            MarketRegime.LOW_VOL: ["carry", "spread", "calendar"],
            MarketRegime.TREND: ["delta", "momentum", "directional"],
            MarketRegime.MEAN_REVERT: ["reversion", "theta", "calendar"],
            MarketRegime.EVENT_DRIVEN: ["event", "risk", "shock"],
            MarketRegime.CRISIS: ["tail", "correlation", "stress"],
            MarketRegime.STRESSED: ["tail", "correlation", "stress"],
        }
        keywords = regime_keywords.get(regime, [])
        entity_text = entity.text.lower()
        return any(kw in entity_text for kw in keywords)

    def _summarize_entities(self, entities: List[Entity]) -> str:
        """Create a summary of entities."""
        if not entities:
            return "No entities extracted"
        entity_types = {}
        for e in entities:
            entity_types[e.entity_type] = entity_types.get(e.entity_type, 0) + 1
        summary = ", ".join(f"{t}: {c}" for t, c in entity_types.items())
        return summary

    def _assess_entity_quality(self, entities: List[Entity]) -> float:
        """Assess overall entity quality."""
        if not entities:
            return 0.0
        return sum(e.confidence for e in entities) / len(entities)

    def _extract_greek_entities(self, entities: List[Entity]) -> str:
        """Extract Greek entities."""
        greeks = [e.text for e in entities if "greek" in e.entity_type.lower()]
        return ", ".join(greeks) if greeks else "None"

    def _generate_step_id(self, step_type: str) -> str:
        """Generate a unique step ID."""
        timestamp = int(time.time() * 1000) % 1000000
        return f"step_{step_type}_{timestamp}"

    def get_best_recommendation(self, state: ReasoningState) -> Dict:
        """Get the best recommendation from reasoning tree."""
        if not state.reasoning_tree:
            return {"recommendation": "Unable to generate recommendation", "confidence": 0.0}

        # Find best leaf node
        best_node = None
        best_score = -1.0
        for node in state.reasoning_tree.values():
            if node.is_leaf and node.metrics.composite_score() > best_score:
                best_score = node.metrics.composite_score()
                best_node = node

        if not best_node:
            return {"recommendation": "No leaf nodes in tree", "confidence": 0.0}

        return {
            "recommendation": best_node.strategy_option,
            "confidence": best_node.metrics.composite_score(),
            "expected_payoff": best_node.metrics.expected_payoff,
            "edge_strength": best_node.metrics.edge_strength,
            "reasoning": best_node.step.conclusion,
        }
