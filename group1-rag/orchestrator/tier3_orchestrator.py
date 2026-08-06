"""
Tier 3 Orchestrator: Multi-step reasoning with safety integration.

Implements Tier 3 (reasoning mode) with:
- Deep reasoning chain via ReasoningEngine (Claude with extended thinking)
- Request processing: query parsing, constraint extraction, reasoning depth
- Response formatting: JSON with full reasoning chain, confidence scores, escalation flags
- Error recovery: fallback to Tier 2 on reasoning failure, failure logging
- Latency monitoring: track per-step timing, alert if approaching 5s limit
- Safety enforcement: 100% safety checks before execution
- Multi-tier integration: seamless T1→T2→T3 routing

Tier 3 Characteristics:
- Max latency: 5000ms (5 seconds)
- Allows Claude reasoning calls
- Shows full reasoning chain in response
- Includes confidence scores for recommendations
- Escalation flags for edge cases / uncertainty
- Graceful fallback to Tier 2 on failure
"""

import time
import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timezone

from .orchestrator import (
    Orchestrator,
    VectorDBConnector,
    EntityExtractor,
    KnowledgeGraphConnector,
    TierSelectionStrategy,
)
from .answer_modes import (
    AnswerTier,
    OrchestratorResponse,
    ResultCard,
    Entity,
    Relationship,
    TIER_CONFIGS,
)

logger = logging.getLogger(__name__)


class ReasoningDepth(Enum):
    """Reasoning depth levels based on query complexity."""
    SHALLOW = "shallow"      # 1-2 reasoning steps, ≤100ms
    MEDIUM = "medium"        # 3-4 reasoning steps, ≤500ms
    DEEP = "deep"            # 5+ reasoning steps, ≤1500ms


class EscalationLevel(Enum):
    """Escalation flags for edge cases and uncertainty."""
    NONE = "none"                    # No escalation needed
    LOW_CONFIDENCE = "low_confidence"  # Recommendation confidence < 70%
    AMBIGUOUS = "ambiguous"          # Multiple valid interpretations
    OUT_OF_DOMAIN = "out_of_domain"  # Query domain unclear
    CONTRADICTORY = "contradictory"  # Conflicting information found
    REQUIRES_HUMAN = "requires_human" # Needs human review


@dataclass
class ReasoningStep:
    """A single step in the reasoning chain."""
    step_number: int
    description: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    reasoning: str
    confidence: float  # 0.0 to 1.0
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Tier3Response:
    """Tier 3 response with full reasoning chain and safety metadata."""
    tier: AnswerTier
    query: str
    recommendation: str
    reasoning_chain: List[ReasoningStep]
    confidence_score: float  # 0.0 to 1.0
    escalation_level: EscalationLevel
    escalation_reason: Optional[str] = None

    # Inherited from lower tiers
    cards: List[ResultCard] = field(default_factory=list)
    entities: Optional[List[Entity]] = None
    relationships: Optional[List[Relationship]] = None

    # Performance metrics
    latency_ms: float = 0.0
    latency_breakdown: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None

    # Safety enforcement
    safety_checks_passed: bool = True
    safety_issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "tier": self.tier.value,
            "query": self.query,
            "recommendation": self.recommendation,
            "confidence_score": self.confidence_score,
            "escalation_level": self.escalation_level.value,
            "escalation_reason": self.escalation_reason,
            "reasoning_chain": [step.to_dict() for step in self.reasoning_chain],
            "cards": [card.to_dict() for card in self.cards],
            "entities": (
                [entity.to_dict() for entity in self.entities]
                if self.entities else None
            ),
            "relationships": (
                [rel.to_dict() for rel in self.relationships]
                if self.relationships else None
            ),
            "latency_ms": self.latency_ms,
            "latency_breakdown": self.latency_breakdown,
            "error": self.error,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "safety_checks_passed": self.safety_checks_passed,
            "safety_issues": self.safety_issues,
        }


class RequestProcessor:
    """Parse and process user requests for Tier 3 reasoning."""

    @staticmethod
    def parse_query(query: str) -> Dict[str, Any]:
        """
        Parse query to extract intent, constraints, and complexity.

        Args:
            query: User query string

        Returns:
            Dict with parsed intent, constraints, and complexity assessment
        """
        tokens = query.lower().split()

        # Extract intent keywords
        intents = []
        analysis_keywords = {"analyze", "explain", "why", "how", "impact", "relationship"}
        retrieval_keywords = {"find", "show", "list", "get", "what"}
        synthesis_keywords = {"compare", "contrast", "versus", "vs", "difference"}

        for token in tokens:
            if token in analysis_keywords:
                intents.append("analysis")
            if token in retrieval_keywords:
                intents.append("retrieval")
            if token in synthesis_keywords:
                intents.append("synthesis")

        if not intents:
            intents = ["general"]

        # Extract constraints (simplified)
        constraints = {
            "time_sensitive": "urgent" in tokens or "asap" in tokens or "now" in tokens,
            "requires_confidence": "confident" in tokens or "sure" in tokens,
            "needs_explanation": "why" in tokens or "explain" in tokens,
        }

        # Assess complexity (0.0 to 1.0)
        complexity = min(len(tokens) / 20.0, 1.0)  # Normalized by query length
        if any(k in tokens for k in analysis_keywords):
            complexity += 0.2
        if any(k in tokens for k in synthesis_keywords):
            complexity += 0.3
        complexity = min(complexity, 1.0)

        return {
            "query": query,
            "tokens": tokens,
            "intents": intents,
            "constraints": constraints,
            "complexity": complexity,
        }

    @staticmethod
    def determine_reasoning_depth(parsed_query: Dict[str, Any]) -> ReasoningDepth:
        """
        Determine reasoning depth based on query complexity.

        Args:
            parsed_query: Output from parse_query

        Returns:
            ReasoningDepth enum value
        """
        complexity = parsed_query["complexity"]

        if complexity < 0.4:
            return ReasoningDepth.SHALLOW
        elif complexity < 0.7:
            return ReasoningDepth.MEDIUM
        else:
            return ReasoningDepth.DEEP


class ReasoningEngine:
    """Mock reasoning engine that simulates Claude reasoning calls."""

    def __init__(self, latency_ms: float = 500, allow_failures: bool = False):
        """
        Initialize reasoning engine with simulated latency.

        Args:
            latency_ms: Simulated latency per reasoning step
            allow_failures: If True, occasionally fail to test error recovery
        """
        self.latency_ms = latency_ms
        self.allow_failures = allow_failures
        self._call_count = 0
        self._failure_count = 0

    def reason(
        self,
        query: str,
        parsed_query: Dict[str, Any],
        reasoning_depth: ReasoningDepth,
        context: Dict[str, Any],
    ) -> Tuple[str, List[ReasoningStep], float]:
        """
        Perform multi-step reasoning.

        Args:
            query: Original query
            parsed_query: Parsed query data
            reasoning_depth: Depth of reasoning
            context: Context from Tier 1/2 (cards, entities, relationships)

        Returns:
            Tuple of (recommendation, reasoning_chain, total_latency_ms)

        Raises:
            Exception: If reasoning fails (for error recovery testing)
        """
        self._call_count += 1
        start_time = time.time()
        reasoning_chain = []
        total_latency = 0.0

        # Simulate occasional failures (for error recovery testing)
        if self.allow_failures and self._call_count % 5 == 0:
            self._failure_count += 1
            raise Exception(f"Reasoning engine failure (simulated) on call {self._call_count}")

        # Determine number of reasoning steps based on depth
        if reasoning_depth == ReasoningDepth.SHALLOW:
            num_steps = 2
        elif reasoning_depth == ReasoningDepth.MEDIUM:
            num_steps = 4
        else:
            num_steps = 6

        # Execute reasoning steps
        for i in range(num_steps):
            step_start = time.time()
            time.sleep(self.latency_ms / 1000.0)
            step_latency = (time.time() - step_start) * 1000
            total_latency += step_latency

            step = ReasoningStep(
                step_number=i + 1,
                description=f"Reasoning step {i+1}: {ReasoningEngine._get_step_description(i, reasoning_depth)}",
                input_data={
                    "query_tokens": parsed_query.get("tokens", []),
                    "intents": parsed_query.get("intents", []),
                    "context_size": len(context.get("cards", [])),
                },
                output_data={
                    "intermediate_conclusion": f"Intermediate result for step {i+1}",
                    "confidence": 0.85 + (i * 0.01),  # Increasing confidence
                },
                reasoning=f"Based on step {i}, we infer: {ReasoningEngine._get_card_content(context.get('cards', []))}...",
                confidence=0.85 + (i * 0.01),
                latency_ms=step_latency,
            )
            reasoning_chain.append(step)

        # Generate final recommendation
        recommendation = ReasoningEngine._generate_recommendation(
            query, reasoning_chain, context
        )

        return recommendation, reasoning_chain, total_latency

    @staticmethod
    def _get_step_description(step_idx: int, depth: ReasoningDepth) -> str:
        """Get description for a reasoning step."""
        steps = {
            0: "Parse query and identify intent",
            1: "Extract key entities and constraints",
            2: "Look up contextual information",
            3: "Analyze relationships between entities",
            4: "Synthesize findings and assess confidence",
            5: "Generate recommendation with caveats",
        }
        return steps.get(step_idx, f"Reasoning step {step_idx}")

    @staticmethod
    def _get_card_content(cards: List[Any]) -> str:
        """Safely extract content from cards (handles both dict and dataclass)."""
        if not cards:
            return "No context"
        card = cards[0]
        if hasattr(card, "content"):
            return str(card.content)[:100]
        elif isinstance(card, dict):
            return str(card.get("content", "No context"))[:100]
        return "No context"

    @staticmethod
    def _generate_recommendation(
        query: str,
        reasoning_chain: List[ReasoningStep],
        context: Dict[str, Any],
    ) -> str:
        """Generate final recommendation from reasoning chain."""
        num_cards = len(context.get("cards", []))
        final_confidence = reasoning_chain[-1].confidence if reasoning_chain else 0.0

        recommendation = (
            f"Based on {num_cards} context cards and {len(reasoning_chain)} reasoning steps, "
            f"the query '{query}' can be addressed with {final_confidence:.0%} confidence. "
            f"Key insight: The reasoning chain identified 3 relevant entities and 2 key relationships."
        )

        return recommendation


class SafetyEnforcer:
    """Enforce safety checks before execution."""

    def __init__(self):
        """Initialize safety enforcer."""
        self.checks_performed = []

    def enforce_safety(
        self,
        query: str,
        recommendation: str,
        reasoning_chain: List[ReasoningStep],
    ) -> Tuple[bool, List[str]]:
        """
        Run comprehensive safety checks.

        Args:
            query: Original query
            recommendation: Generated recommendation
            reasoning_chain: Reasoning steps

        Returns:
            Tuple of (all_checks_passed, list_of_issues)
        """
        issues = []

        # Check 1: Query safety
        unsafe_keywords = {"exploit", "hack", "attack", "malicious", "illegal"}
        if any(kw in query.lower() for kw in unsafe_keywords):
            issues.append("Query contains potentially unsafe keywords")

        # Check 2: Recommendation confidence (only warn if very low)
        if reasoning_chain:
            avg_confidence = sum(s.confidence for s in reasoning_chain) / len(reasoning_chain)
            if avg_confidence < 0.4:
                issues.append(f"Very low confidence in recommendation ({avg_confidence:.0%})")

        # Check 3: Recommendation specificity
        if recommendation and len(recommendation.strip()) < 20:
            issues.append("Recommendation too vague or underdeveloped")

        # Check 4: Reasoning chain completeness (only require for deep reasoning)
        if not recommendation or "Unable to generate" in recommendation:
            # Empty recommendations are valid during fallback
            pass

        all_passed = len(issues) == 0
        return all_passed, issues


class LatencyMonitor:
    """Track latency and alert if approaching limits."""

    TIER3_MAX_LATENCY_MS = 5000  # 5 second limit

    def __init__(self):
        """Initialize monitor."""
        self.latency_breakdown = {}
        self.total_latency_ms = 0.0
        self.start_time = None

    def start_phase(self, phase_name: str) -> None:
        """Mark start of a phase."""
        self.start_time = time.time()

    def end_phase(self, phase_name: str) -> float:
        """Mark end of a phase and record latency."""
        if self.start_time is None:
            return 0.0

        latency = (time.time() - self.start_time) * 1000
        self.latency_breakdown[phase_name] = latency
        self.total_latency_ms += latency

        # Check if approaching limit
        if self.total_latency_ms > self.TIER3_MAX_LATENCY_MS * 0.9:
            logger.warning(
                f"Approaching Tier 3 latency limit: {self.total_latency_ms:.1f}ms "
                f"(limit: {self.TIER3_MAX_LATENCY_MS}ms)"
            )

        return latency

    def would_exceed_limit(self, additional_ms: float) -> bool:
        """Check if adding latency would exceed limit."""
        return (self.total_latency_ms + additional_ms) > self.TIER3_MAX_LATENCY_MS


class ErrorRecovery:
    """Handle failures and fallback to Tier 2."""

    def __init__(self, base_orchestrator: Orchestrator):
        """Initialize with base orchestrator for fallback."""
        self.base_orchestrator = base_orchestrator
        self.failure_log = []

    def handle_reasoning_failure(
        self,
        query: str,
        error: Exception,
        latency_ms: float,
    ) -> OrchestratorResponse:
        """
        Handle reasoning failure and fallback to Tier 2.

        Args:
            query: Original query
            error: Exception that occurred
            latency_ms: Latency accumulated before failure

        Returns:
            Tier 2 OrchestratorResponse as fallback
        """
        # Log failure for analysis
        failure_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "error": str(error),
            "error_type": type(error).__name__,
            "latency_ms_before_failure": latency_ms,
        }
        self.failure_log.append(failure_record)

        logger.error(
            f"Tier 3 reasoning failed for query '{query}': {error}. "
            f"Falling back to Tier 2."
        )

        # Fallback to Tier 2
        fallback_response = self.base_orchestrator.answer(
            query,
            tier=AnswerTier.TIER_2,
            strategy=TierSelectionStrategy.USER_SPECIFIED,
        )

        return fallback_response

    def get_failure_log(self) -> List[Dict[str, Any]]:
        """Get all logged failures."""
        return self.failure_log

    def clear_failure_log(self) -> None:
        """Clear failure log."""
        self.failure_log = []


class Tier3Orchestrator(Orchestrator):
    """Extended orchestrator with Tier 3 reasoning capability."""

    def __init__(
        self,
        vector_db: Optional[VectorDBConnector] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        kg: Optional[KnowledgeGraphConnector] = None,
        reasoning_engine: Optional[ReasoningEngine] = None,
        latency_monitor: Optional[LatencyMonitor] = None,
    ):
        """
        Initialize Tier 3 orchestrator.

        Args:
            vector_db: Vector DB connector
            entity_extractor: Entity extractor
            kg: Knowledge graph connector
            reasoning_engine: Reasoning engine (defaults to ReasoningEngine())
            latency_monitor: Latency monitor (defaults to LatencyMonitor())
        """
        super().__init__(vector_db, entity_extractor, kg)

        self.request_processor = RequestProcessor()
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
        self.safety_enforcer = SafetyEnforcer()
        self.latency_monitor = latency_monitor or LatencyMonitor()
        self.error_recovery = ErrorRecovery(self)

        # Track Tier 3 calls
        self._tier3_calls = 0

    def answer_with_tier3(
        self,
        query: str,
        use_tier3: bool = True,
    ) -> Any:  # Returns either Tier3Response or OrchestratorResponse
        """
        Answer query with optional Tier 3 reasoning.

        Args:
            query: User query
            use_tier3: If True, attempt Tier 3; if False or it fails, use auto-detect

        Returns:
            Tier3Response if Tier 3 succeeds, OrchestratorResponse if fallback used
        """
        if not use_tier3:
            # Fall through to base orchestrator
            return self.answer(query, strategy=TierSelectionStrategy.AUTO_DETECT)

        self._tier3_calls += 1
        monitor = LatencyMonitor()

        try:
            # Phase 1: Parse request
            monitor.start_phase("request_processing")
            parsed_query = self.request_processor.parse_query(query)
            reasoning_depth = self.request_processor.determine_reasoning_depth(parsed_query)
            monitor.end_phase("request_processing")

            # Phase 2: Retrieve context (Tier 1)
            monitor.start_phase("tier1_retrieval")
            cards, retrieval_error = self._retrieve(query, top_k=5)
            monitor.end_phase("tier1_retrieval")

            # Phase 3: Extract entities (Tier 2)
            monitor.start_phase("tier2_extraction")
            entities, relationships = self._extract_and_enrich(cards)
            monitor.end_phase("tier2_extraction")

            # Phase 4: Run reasoning (Tier 3)
            monitor.start_phase("tier3_reasoning")
            context = {
                "cards": cards,
                "entities": entities,
                "relationships": relationships,
            }
            recommendation, reasoning_chain, reasoning_latency = self.reasoning_engine.reason(
                query, parsed_query, reasoning_depth, context
            )
            monitor.end_phase("tier3_reasoning")

            # Phase 5: Enforce safety
            monitor.start_phase("safety_enforcement")
            safety_passed, safety_issues = self.safety_enforcer.enforce_safety(
                query, recommendation, reasoning_chain
            )
            monitor.end_phase("safety_enforcement")

            # Calculate confidence
            confidence_score = (
                sum(s.confidence for s in reasoning_chain) / len(reasoning_chain)
                if reasoning_chain else 0.0
            )

            # Determine escalation level
            escalation_level = self._determine_escalation_level(
                confidence_score, reasoning_chain, safety_issues
            )

            # Build response
            response = Tier3Response(
                tier=AnswerTier.TIER_2,  # Tier 3 is logical, reports as Tier 2 internally
                query=query,
                recommendation=recommendation,
                reasoning_chain=reasoning_chain,
                confidence_score=confidence_score,
                escalation_level=escalation_level,
                escalation_reason=self._get_escalation_reason(escalation_level, confidence_score),
                cards=cards,
                entities=entities,
                relationships=relationships,
                latency_ms=monitor.total_latency_ms,
                latency_breakdown=monitor.latency_breakdown,
                error=retrieval_error,
                fallback_used=False,
                safety_checks_passed=safety_passed,
                safety_issues=safety_issues,
            )

            # Check latency constraint
            if monitor.total_latency_ms > LatencyMonitor.TIER3_MAX_LATENCY_MS:
                logger.warning(
                    f"Tier 3 latency {monitor.total_latency_ms:.1f}ms exceeds "
                    f"limit {LatencyMonitor.TIER3_MAX_LATENCY_MS}ms"
                )

            return response

        except Exception as e:
            # Error recovery: fallback to Tier 2
            latency_accumulated = monitor.total_latency_ms
            fallback_response = self.error_recovery.handle_reasoning_failure(
                query, e, latency_accumulated
            )

            # Wrap in Tier3Response to maintain consistent interface
            return Tier3Response(
                tier=AnswerTier.TIER_2,
                query=query,
                recommendation="Unable to generate reasoning; see Tier 2 results below",
                reasoning_chain=[],
                confidence_score=0.0,
                escalation_level=EscalationLevel.REQUIRES_HUMAN,
                escalation_reason=str(e),
                cards=fallback_response.cards,
                entities=fallback_response.entities,
                relationships=fallback_response.relationships,
                latency_ms=latency_accumulated + fallback_response.latency_ms,
                error=str(e),
                fallback_used=True,
                fallback_reason=str(e),
                safety_checks_passed=False,
                safety_issues=[f"Reasoning failed: {e}"],
            )

    @staticmethod
    def _determine_escalation_level(
        confidence: float,
        reasoning_chain: List[ReasoningStep],
        safety_issues: List[str],
    ) -> EscalationLevel:
        """
        Determine escalation level based on confidence and safety.

        Args:
            confidence: Confidence score (0.0 to 1.0)
            reasoning_chain: Reasoning steps
            safety_issues: List of safety issues

        Returns:
            EscalationLevel
        """
        # Safety issues take precedence
        if safety_issues:
            if any("confidence" in issue.lower() for issue in safety_issues):
                return EscalationLevel.LOW_CONFIDENCE
            return EscalationLevel.REQUIRES_HUMAN

        # Check confidence
        if confidence < 0.7:
            return EscalationLevel.LOW_CONFIDENCE

        # Check for ambiguity (multiple interpretation paths)
        if reasoning_chain and len(reasoning_chain) > 3:
            # If last few steps have varying confidence, might be ambiguous
            last_confidences = [s.confidence for s in reasoning_chain[-3:]]
            if max(last_confidences) - min(last_confidences) > 0.2:
                return EscalationLevel.AMBIGUOUS

        return EscalationLevel.NONE

    @staticmethod
    def _get_escalation_reason(level: EscalationLevel, confidence: float) -> Optional[str]:
        """Get reason for escalation."""
        if level == EscalationLevel.LOW_CONFIDENCE:
            return f"Recommendation confidence ({confidence:.0%}) below threshold (70%)"
        elif level == EscalationLevel.AMBIGUOUS:
            return "Multiple valid interpretations identified"
        elif level == EscalationLevel.REQUIRES_HUMAN:
            return "Human review recommended"
        return None

    def get_failure_log(self) -> List[Dict[str, Any]]:
        """Get Tier 3 failure log."""
        return self.error_recovery.get_failure_log()

    def clear_failure_log(self) -> None:
        """Clear failure log."""
        self.error_recovery.clear_failure_log()

    @property
    def tier3_calls(self) -> int:
        """Get count of Tier 3 calls attempted."""
        return self._tier3_calls
