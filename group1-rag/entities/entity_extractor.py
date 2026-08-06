"""
Entity Extraction Service for Tier 2 RAG
Extracts entities and relationships from retrieved trading text
Target: F1 ≥0.85, Latency ≤500ms (extraction ≤300ms)
"""

import json
import re
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """Supported entity types from KG schema"""
    MARKET_REGIME = "MarketRegime"
    STRATEGY = "Strategy"
    GREEK_DELTA = "Greek.delta"
    GREEK_GAMMA = "Greek.gamma"
    GREEK_THETA = "Greek.theta"
    GREEK_VEGA = "Greek.vega"
    GREEK_RHO = "Greek.rho"
    VOL_SURFACE = "VolSurface"
    TRADING_OPPORTUNITY = "TradingOpportunity"
    EVENT = "Event"
    ORDER_FLOW = "OrderFlow"
    RISK_METRIC = "RiskMetric"
    POSITION = "Position"


class RelationshipType(str, Enum):
    """Supported relationship types from KG schema"""
    APPLIES_TO = "applies_to"
    TRIGGERS = "triggers"
    CONSTRAINS = "constrains"
    INDICATES = "indicates"
    ARBITRAGE_TARGET = "arbitrage_target"
    CALCULATED_FROM = "calculated_from"
    MITIGATED_BY = "mitigated_by"
    CORRELATES_WITH = "correlates_with"
    DEPENDS_ON = "depends_on"
    PRECEDES = "precedes"


@dataclass
class Entity:
    """Represents an extracted entity"""
    text: str
    entity_type: EntityType
    confidence: float
    span_start: int
    span_end: int
    kg_node_id: Optional[str] = None
    attributes: Dict[str, str] = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


@dataclass
class Relationship:
    """Represents an inferred relationship between entities"""
    source_entity: str
    target_entity: str
    relationship_type: RelationshipType
    confidence: float
    reasoning: str


@dataclass
class ExtractionResult:
    """Container for extraction results"""
    entities: List[Entity]
    relationships: List[Relationship]
    text: str
    latency_ms: float
    used_fallback: bool
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "entities": [
                {
                    "text": e.text,
                    "type": e.entity_type.value,
                    "confidence": round(e.confidence, 3),
                    "span": {"start": e.span_start, "end": e.span_end},
                    "kg_node_id": e.kg_node_id,
                    "attributes": e.attributes
                }
                for e in self.entities
            ],
            "relationships": [
                {
                    "source": r.source_entity,
                    "target": r.target_entity,
                    "type": r.relationship_type.value,
                    "confidence": round(r.confidence, 3),
                    "reasoning": r.reasoning
                }
                for r in self.relationships
            ],
            "text": self.text,
            "latency_ms": round(self.latency_ms, 2),
            "used_fallback": self.used_fallback,
            "metadata": self.metadata,
            "summary": {
                "entity_count": len(self.entities),
                "relationship_count": len(self.relationships),
                "avg_entity_confidence": round(
                    sum(e.confidence for e in self.entities) / len(self.entities)
                    if self.entities else 0, 3
                ),
                "avg_relationship_confidence": round(
                    sum(r.confidence for r in self.relationships) / len(self.relationships)
                    if self.relationships else 0, 3
                )
            }
        }


class KnowledgeGraphMatcher:
    """Matches extracted entities to KG nodes"""

    # KG node patterns and aliases
    KG_NODES = {
        # Strategies
        "straddle": {"type": EntityType.STRATEGY, "aliases": ["straddle", "straddling"]},
        "strangle": {"type": EntityType.STRATEGY, "aliases": ["strangle", "strangling"]},
        "iron_butterfly": {"type": EntityType.STRATEGY, "aliases": ["iron butterfly", "iron-butterfly"]},
        "call_spread": {"type": EntityType.STRATEGY, "aliases": ["call spread", "bull call spread"]},
        "put_spread": {"type": EntityType.STRATEGY, "aliases": ["put spread", "bear put spread"]},
        "gamma_scalping": {"type": EntityType.STRATEGY, "aliases": ["gamma scalp", "gamma scalping"]},
        "vol_arbitrage": {"type": EntityType.STRATEGY, "aliases": ["vol arb", "volatility arbitrage"]},
        "skew_trading": {"type": EntityType.STRATEGY, "aliases": ["skew trade", "skew trading"]},

        # Market Regimes
        "high_vol": {"type": EntityType.MARKET_REGIME, "aliases": ["high volatility", "elevated vol", "high vol"]},
        "low_vol": {"type": EntityType.MARKET_REGIME, "aliases": ["low volatility", "low vol", "calm"]},
        "event_driven": {"type": EntityType.MARKET_REGIME, "aliases": ["event driven", "event-driven"]},
        "mean_reversion": {"type": EntityType.MARKET_REGIME, "aliases": ["mean revert", "mean reverting"]},
        "trend_following": {"type": EntityType.MARKET_REGIME, "aliases": ["trend following", "trending"]},
        "stressed_regime": {"type": EntityType.MARKET_REGIME, "aliases": ["stress", "market stress", "crisis"]},

        # Vol Surface features
        "smile": {"type": EntityType.VOL_SURFACE, "aliases": ["smile", "vol smile"]},
        "skew": {"type": EntityType.VOL_SURFACE, "aliases": ["skew", "vol skew"]},
        "term_structure": {"type": EntityType.VOL_SURFACE, "aliases": ["term structure", "term-structure"]},
        "surface_curvature": {"type": EntityType.VOL_SURFACE, "aliases": ["curvature"]},
    }

    @classmethod
    def match_entity(cls, entity_text: str, entity_type: EntityType) -> Optional[str]:
        """Match entity text to KG node ID"""
        text_lower = entity_text.lower().strip()

        for node_id, node_info in cls.KG_NODES.items():
            if node_info["type"] == entity_type:
                for alias in node_info["aliases"]:
                    if alias.lower() == text_lower:
                        return node_id
        return None


class EntityRecognizer:
    """Recognizes entities from text using pattern matching as fallback"""

    PATTERNS = {
        EntityType.GREEK_DELTA: [
            r"\bdelta\b",
            r"\bdelta exposure\b",
            r"\bdelta neutral",
            r"Δ",
        ],
        EntityType.GREEK_GAMMA: [
            r"\bgamma\b",
            r"\bgamma exposure\b",
            r"\bgamma scalp",
            r"Γ",
        ],
        EntityType.GREEK_THETA: [
            r"\btheta\b",
            r"\btheta decay\b",
            r"\btime decay\b",
            r"Θ",
        ],
        EntityType.GREEK_VEGA: [
            r"\bvega\b",
            r"\bvega exposure\b",
            r"\bvega risk\b",
            r"ν",
        ],
        EntityType.GREEK_RHO: [
            r"\brho\b",
            r"ρ",
        ],
        EntityType.STRATEGY: [
            r"\b(straddle|strangle|butterfly|scalping?|hedge)\b",
            r"\b(call spread|put spread|iron butterfly|gamma scalping|vol arb|skew trade)\b",
        ],
        EntityType.MARKET_REGIME: [
            r"\b(high volatility|low volatility|high vol|low vol)\b",
            r"\b(event.?driven|mean.?revert(?:ing)?|trending|crisis|stress|elevated vol)\b",
        ],
        EntityType.EVENT: [
            r"\b(earnings|FOMC|Fed|earnings surprise|earnings shock|earnings report)\b",
            r"\b(earnings call|guidance|earnings beat|earnings miss)\b",
        ],
        EntityType.VOL_SURFACE: [
            r"\b(volatility smile|smile|skew|term structure)\b",
            r"\b(vol surface|volatility surface|iv surface)\b",
        ],
        EntityType.TRADING_OPPORTUNITY: [
            r"\b(arbitrage|mispricing)\b",
        ],
        EntityType.ORDER_FLOW: [
            r"\b(order flow|order imbalance|buyer initiated|seller initiated)\b",
            r"\b(VWAP|market order|limit order)\b",
        ],
        EntityType.RISK_METRIC: [
            r"\b(var|value at risk|max loss|drawdown)\b",
        ],
    }

    @classmethod
    def extract_entities(cls, text: str) -> List[Tuple[str, EntityType, int, int]]:
        """Extract entities using pattern matching"""
        entities = []
        found_spans = set()  # Track found spans to avoid duplicates

        for entity_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    span = (match.start(), match.end())
                    if span not in found_spans:
                        entities.append((match.group(), entity_type, match.start(), match.end()))
                        found_spans.add(span)

        return entities


class LLMEntityExtractor:
    """Extracts entities using LLM-based extraction"""

    def __init__(self, client=None, timeout_ms: int = 300):
        """
        Initialize LLM extractor
        Args:
            client: Anthropic client (optional, for testing)
            timeout_ms: Timeout for LLM calls in milliseconds
        """
        self.client = client
        self.timeout_ms = timeout_ms

    def extract(self, text: str) -> Optional[Dict]:
        """
        Extract entities and relationships using LLM
        Returns None if LLM unavailable
        """
        if self.client is None:
            return None

        try:
            prompt = self._build_extraction_prompt(text)

            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = message.content[0].text
            return self._parse_llm_response(response_text)

        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return None

    def _build_extraction_prompt(self, text: str) -> str:
        """Build the extraction prompt for the LLM"""

        entity_types_str = ", ".join([
            "MarketRegime", "Strategy", "Greeks (delta/gamma/theta/vega/rho)",
            "VolSurface", "TradingOpportunity", "Event", "OrderFlow", "RiskMetric"
        ])

        relationship_types_str = ", ".join([
            "applies_to", "triggers", "constrains", "indicates",
            "arbitrage_target", "calculated_from", "mitigated_by",
            "correlates_with", "depends_on", "precedes"
        ])

        return f"""Extract entities and relationships from the following trading text.

TEXT:
{text}

TASK:
1. Identify all entities of these types: {entity_types_str}
2. For each entity, provide:
   - The exact text span
   - Entity type
   - Confidence score (0.0-1.0)
3. Identify relationships between entities:
   - Source entity
   - Target entity
   - Relationship type from: {relationship_types_str}
   - Confidence score (0.0-1.0)
   - Brief reasoning

OUTPUT FORMAT (valid JSON):
{{
  "entities": [
    {{"text": "...", "type": "...", "confidence": 0.85, "span": {{"start": 0, "end": 5}}}},
    ...
  ],
  "relationships": [
    {{"source": "...", "target": "...", "type": "applies_to", "confidence": 0.90, "reasoning": "..."}},
    ...
  ]
}}

REQUIREMENTS:
- Only extract if confidence >= 0.60
- Be conservative: prefer fewer high-confidence extractions
- Focus on trading/finance entities
- Relationship confidence should reflect context strength
"""

    def _parse_llm_response(self, response_text: str) -> Optional[Dict]:
        """Parse LLM response to structured format"""
        try:
            # Find JSON block in response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                return None

            json_text = json_match.group(0)
            data = json.loads(json_text)

            return data
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")
            return None


class EntityExtractor:
    """Main entity extraction service"""

    def __init__(self, llm_client=None, use_llm: bool = True, timeout_ms: int = 500):
        """
        Initialize entity extractor
        Args:
            llm_client: Anthropic client for LLM-based extraction
            use_llm: Whether to use LLM (fallback to patterns if False/unavailable)
            timeout_ms: Maximum time allowed for extraction
        """
        self.llm_client = llm_client
        self.use_llm = use_llm
        self.timeout_ms = timeout_ms
        self.llm_extractor = LLMEntityExtractor(llm_client, timeout_ms=300)
        self.recognizer = EntityRecognizer()
        self.kg_matcher = KnowledgeGraphMatcher()

    def extract(self, text: str) -> ExtractionResult:
        """
        Extract entities and relationships from text
        Args:
            text: Input text from retrieval layer
        Returns:
            ExtractionResult with entities, relationships, and metadata
        """
        start_time = time.time()
        used_fallback = False
        entities_list = []
        relationships_list = []

        # Try LLM extraction first
        llm_data = None
        if self.use_llm:
            llm_data = self.llm_extractor.extract(text)

        # If LLM succeeds, use its results
        if llm_data:
            entities_list = self._process_llm_entities(llm_data.get("entities", []), text)
            relationships_list = self._process_llm_relationships(
                llm_data.get("relationships", []),
                entities_list
            )
        else:
            # Fallback to pattern-based extraction
            used_fallback = True
            pattern_entities = self.recognizer.extract_entities(text)
            entities_list = self._process_pattern_entities(pattern_entities)

            # Simple relationship inference based on co-occurrence
            if entities_list:
                relationships_list = self._infer_relationships(entities_list, text)

        # Link entities to KG nodes
        for entity in entities_list:
            entity.kg_node_id = self.kg_matcher.match_entity(entity.text, entity.entity_type)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        return ExtractionResult(
            entities=entities_list,
            relationships=relationships_list,
            text=text,
            latency_ms=latency_ms,
            used_fallback=used_fallback,
            metadata={
                "model": "gpt-3.5-turbo" if (self.use_llm and llm_data) else "pattern-match",
                "extraction_method": "llm" if llm_data else "fallback"
            }
        )

    def _process_llm_entities(self, llm_entities: List[Dict], text: str) -> List[Entity]:
        """Process entities from LLM output"""
        entities = []

        for entity_data in llm_entities:
            try:
                entity_type = EntityType(entity_data["type"])
                confidence = float(entity_data.get("confidence", 0.5))
                span = entity_data.get("span", {})

                entity = Entity(
                    text=entity_data["text"],
                    entity_type=entity_type,
                    confidence=confidence,
                    span_start=int(span.get("start", 0)),
                    span_end=int(span.get("end", 0)),
                )
                entities.append(entity)
            except (ValueError, KeyError) as e:
                logger.debug(f"Failed to process LLM entity: {e}")
                continue

        return entities

    def _process_pattern_entities(self, pattern_matches: List[Tuple]) -> List[Entity]:
        """Convert pattern matches to Entity objects"""
        entities = []

        for text_match, entity_type, start, end in pattern_matches:
            # Confidence based on entity type specificity
            confidence_scores = {
                EntityType.GREEK_DELTA: 0.95,
                EntityType.GREEK_GAMMA: 0.95,
                EntityType.GREEK_THETA: 0.95,
                EntityType.GREEK_VEGA: 0.95,
                EntityType.GREEK_RHO: 0.95,
                EntityType.EVENT: 0.85,
                EntityType.STRATEGY: 0.80,
                EntityType.MARKET_REGIME: 0.75,
                EntityType.VOL_SURFACE: 0.80,
                EntityType.TRADING_OPPORTUNITY: 0.65,
                EntityType.ORDER_FLOW: 0.70,
                EntityType.RISK_METRIC: 0.70,
            }

            confidence = confidence_scores.get(entity_type, 0.70)

            entity = Entity(
                text=text_match,
                entity_type=entity_type,
                confidence=confidence,
                span_start=start,
                span_end=end,
            )
            entities.append(entity)

        return entities

    def _process_llm_relationships(self, llm_relationships: List[Dict],
                                  entities: List[Entity]) -> List[Relationship]:
        """Process relationships from LLM output"""
        relationships = []
        entity_texts = {e.text for e in entities}

        for rel_data in llm_relationships:
            try:
                # Verify both entities exist
                if rel_data["source"] in entity_texts and rel_data["target"] in entity_texts:
                    rel_type = RelationshipType(rel_data["type"])
                    confidence = float(rel_data.get("confidence", 0.5))

                    relationship = Relationship(
                        source_entity=rel_data["source"],
                        target_entity=rel_data["target"],
                        relationship_type=rel_type,
                        confidence=confidence,
                        reasoning=rel_data.get("reasoning", "")
                    )
                    relationships.append(relationship)
            except (ValueError, KeyError) as e:
                logger.debug(f"Failed to process LLM relationship: {e}")
                continue

        return relationships

    def _infer_relationships(self, entities: List[Entity], text: str) -> List[Relationship]:
        """Infer relationships between entities based on context"""
        relationships = []

        # Simple heuristics for common trading relationships
        entity_texts = [e.text for e in entities]
        entity_types = {e.text: e.entity_type for e in entities}

        # Relationship inference rules
        strategy_entities = {e.text for e in entities if e.entity_type == EntityType.STRATEGY}
        greek_entities = {e.text for e in entities if e.entity_type.value.startswith("Greek")}
        regime_entities = {e.text for e in entities if e.entity_type == EntityType.MARKET_REGIME}
        opportunity_entities = {e.text for e in entities if e.entity_type == EntityType.TRADING_OPPORTUNITY}

        # Rule 1: Strategies apply_to Regimes
        for strategy in strategy_entities:
            for regime in regime_entities:
                if self._are_nearby(text, strategy, regime):
                    relationships.append(Relationship(
                        source_entity=strategy,
                        target_entity=regime,
                        relationship_type=RelationshipType.APPLIES_TO,
                        confidence=0.70,
                        reasoning="Strategy and regime mentioned in same context"
                    ))

        # Rule 2: Greeks constrains Strategies
        for greek in greek_entities:
            for strategy in strategy_entities:
                if self._are_nearby(text, greek, strategy):
                    relationships.append(Relationship(
                        source_entity=greek,
                        target_entity=strategy,
                        relationship_type=RelationshipType.CONSTRAINS,
                        confidence=0.65,
                        reasoning="Greek risk metric affects strategy"
                    ))

        # Rule 3: Events trigger Opportunities
        event_entities = {e.text for e in entities if e.entity_type == EntityType.EVENT}
        for event in event_entities:
            for opp in opportunity_entities:
                if self._are_nearby(text, event, opp):
                    relationships.append(Relationship(
                        source_entity=event,
                        target_entity=opp,
                        relationship_type=RelationshipType.TRIGGERS,
                        confidence=0.75,
                        reasoning="Event creates trading opportunity"
                    ))

        return relationships

    def _are_nearby(self, text: str, entity1: str, entity2: str, window: int = 200) -> bool:
        """Check if two entities are mentioned nearby in text"""
        idx1 = text.lower().find(entity1.lower())
        idx2 = text.lower().find(entity2.lower())

        if idx1 == -1 or idx2 == -1:
            return False

        return abs(idx1 - idx2) < window


def extract_entities(text: str, llm_client=None) -> Dict:
    """
    Convenience function for entity extraction
    Args:
        text: Input text from retrieval
        llm_client: Optional Anthropic client
    Returns:
        JSON-serializable dictionary with results
    """
    extractor = EntityExtractor(llm_client=llm_client)
    result = extractor.extract(text)
    return result.to_dict()
