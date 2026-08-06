"""
Corpus Ingestion Module for Group One RAG Knowledge Graph
==========================================================

Ingests financial corpus documents (markdown) and populates the knowledge graph
with entities, relationships, and confidence scores.
"""

import os
import re
import json
import logging
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path

from kg_client import KGClient, ENTITY_TYPES, RELATIONSHIP_TYPES

logger = logging.getLogger(__name__)


class CorpusParser:
    """Parses markdown corpus files and extracts entities and relationships."""

    def __init__(self):
        self.entities: Dict[str, List[str]] = {
            entity_type: [] for entity_type in ENTITY_TYPES
        }
        self.relationships: List[Dict] = []

    def parse_file(self, filepath: str) -> Dict[str, any]:
        """Parse a markdown corpus file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return self._parse_content(content, filepath)
        except Exception as e:
            logger.error(f"Failed to parse {filepath}: {e}")
            return {}

    def _parse_content(self, content: str, source: str) -> Dict[str, any]:
        """Parse markdown content and extract entities."""
        parsed = {
            "source": source,
            "strategies": [],
            "greeks": [],
            "market_regimes": [],
            "trading_opportunities": [],
            "events": [],
            "order_flow": [],
            "risk_metrics": [],
            "vol_surfaces": []
        }

        # Extract strategies
        strategy_patterns = [
            r"(?:Delta Hedging|Gamma Scalping|Vol(?:atility)?\s+Arbitrage|Statistical Arbitrage|Event-Driven|Pairs Trading|Calendar Spread|Skew Trading)",
            r"(?:Long|Short)\s+(?:Straddle|Strangle|Butterfly|Condor|Calendar)"
        ]

        for pattern in strategy_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                strategy = match.group(0).strip()
                if strategy not in parsed["strategies"]:
                    parsed["strategies"].append(strategy)
                    self.entities["Strategy"].append(strategy)

        # Extract Greeks
        greeks = ["Delta", "Gamma", "Theta", "Vega", "Rho"]
        for greek in greeks:
            if greek in content:
                if greek not in parsed["greeks"]:
                    parsed["greeks"].append(greek)
                    self.entities["Greeks"].append(greek)

        # Extract market regimes
        regime_patterns = [
            r"(?:Bull|Bear|High-Vol|Low-Vol|Sideways|Trending|Crisis|Normal|Stressed)\s+(?:Market|Regime|Environment)"
        ]
        for pattern in regime_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                regime = match.group(0).strip()
                if regime not in parsed["market_regimes"]:
                    parsed["market_regimes"].append(regime)
                    self.entities["MarketRegime"].append(regime)

        # Extract events
        event_keywords = [
            "earnings", "IPO", "merger", "acquisition", "economic data",
            "CPI", "employment", "Fed", "central bank", "earnings announcement"
        ]
        for keyword in event_keywords:
            if keyword.lower() in content.lower():
                if keyword not in parsed["events"]:
                    parsed["events"].append(keyword)
                    if keyword not in self.entities["Event"]:
                        self.entities["Event"].append(keyword)

        # Extract risk metrics
        risk_patterns = [
            r"(?:Gap Risk|Vol-of-Vol|Correlation Risk|Liquidity Risk|Tail Risk|Model Risk|Hedging Error)"
        ]
        for pattern in risk_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                risk = match.group(0).strip()
                if risk not in parsed["risk_metrics"]:
                    parsed["risk_metrics"].append(risk)
                    if risk not in self.entities["RiskMetric"]:
                        self.entities["RiskMetric"].append(risk)

        # Extract volatility surface concepts
        vol_surface_keywords = [
            "volatility smile", "volatility skew", "volatility smile",
            "term structure", "volatility surface", "skew", "smile"
        ]
        for keyword in vol_surface_keywords:
            if keyword.lower() in content.lower():
                if keyword not in parsed["vol_surfaces"]:
                    parsed["vol_surfaces"].append(keyword)
                    if keyword not in self.entities["VolSurface"]:
                        self.entities["VolSurface"].append(keyword)

        # Extract order flow concepts
        order_flow_keywords = [
            "order flow", "microstructure", "bid-ask spread", "inventory",
            "supply-demand", "market depth", "limit order book"
        ]
        for keyword in order_flow_keywords:
            if keyword.lower() in content.lower():
                if keyword not in parsed["order_flow"]:
                    parsed["order_flow"].append(keyword)
                    if keyword not in self.entities["OrderFlow"]:
                        self.entities["OrderFlow"].append(keyword)

        # Extract trading opportunities
        opp_keywords = [
            "arbitrage", "mispricing", "opportunity", "edge", "trading setup",
            "mean reversion", "momentum", "reversal"
        ]
        for keyword in opp_keywords:
            if keyword.lower() in content.lower():
                # Extract surrounding context for better description
                matches = re.finditer(rf".{{0,50}}{keyword}.{{0,100}}", content, re.IGNORECASE)
                for match in matches:
                    context = match.group(0).strip()
                    if context not in parsed["trading_opportunities"]:
                        parsed["trading_opportunities"].append(context)

        return parsed


class EntityLinker:
    """Links entities and creates relationships with confidence scores."""

    def __init__(self):
        self.strategy_regime_map = self._build_strategy_regime_map()
        self.greek_strategy_map = self._build_greek_strategy_map()
        self.event_opportunity_map = self._build_event_opportunity_map()

    def _build_strategy_regime_map(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build mapping of strategies to their applicable regimes."""
        return {
            "Delta Hedging": [
                ("Bull Market", 0.85),
                ("Bear Market", 0.85),
                ("High-Vol Market", 0.75),
                ("Low-Vol Market", 0.65),
            ],
            "Gamma Scalping": [
                ("High-Vol Market", 0.90),
                ("Trending Market", 0.80),
                ("Bull Market", 0.70),
                ("Bear Market", 0.70),
            ],
            "Volatility Arbitrage": [
                ("High-Vol Market", 0.95),
                ("Stressed Market", 0.85),
                ("Low-Vol Market", 0.80),
            ],
            "Statistical Arbitrage": [
                ("Sideways Market", 0.90),
                ("Low-Vol Market", 0.85),
                ("Normal Market", 0.80),
            ],
            "Event-Driven": [
                ("Crisis Market", 0.95),
                ("High-Vol Market", 0.85),
                ("Stressed Market", 0.90),
            ],
            "Calendar Spread": [
                ("Low-Vol Market", 0.85),
                ("Normal Market", 0.80),
                ("Sideways Market", 0.75),
            ],
            "Skew Trading": [
                ("High-Vol Market", 0.95),
                ("Crisis Market", 0.90),
                ("Stressed Market", 0.85),
            ],
        }

    def _build_greek_strategy_map(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build mapping of Greeks to strategies that use them."""
        return {
            "Delta": [
                ("Delta Hedging", 0.95),
                ("Gamma Scalping", 0.90),
                ("Calendar Spread", 0.85),
                ("Statistical Arbitrage", 0.75),
            ],
            "Gamma": [
                ("Gamma Scalping", 0.95),
                ("Delta Hedging", 0.90),
                ("Volatility Arbitrage", 0.85),
            ],
            "Theta": [
                ("Calendar Spread", 0.95),
                ("Event-Driven", 0.85),
                ("Delta Hedging", 0.80),
                ("Volatility Arbitrage", 0.75),
            ],
            "Vega": [
                ("Volatility Arbitrage", 0.95),
                ("Skew Trading", 0.90),
                ("Event-Driven", 0.85),
                ("Calendar Spread", 0.80),
            ],
            "Rho": [
                ("Delta Hedging", 0.70),
                ("Calendar Spread", 0.65),
                ("Volatility Arbitrage", 0.60),
            ],
        }

    def _build_event_opportunity_map(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build mapping of events to trading opportunities."""
        return {
            "earnings": [
                ("IV Crush", 0.95),
                ("Mean Reversion", 0.80),
                ("Straddle Setup", 0.90),
            ],
            "merger": [
                ("Spread Arbitrage", 0.90),
                ("Deal Risk Trading", 0.85),
            ],
            "economic data": [
                ("Vol Spike Setup", 0.85),
                ("Post-Event Mean Reversion", 0.80),
            ],
            "Fed": [
                ("Rate-Vol Correlation", 0.85),
                ("Policy Anticipation", 0.75),
            ],
        }

    def link_entities(self, client: KGClient, parsed: Dict):
        """Link parsed entities and create relationships."""
        relationships = []

        # Link strategies to regimes
        for strategy in parsed.get("strategies", []):
            for regime in parsed.get("market_regimes", []):
                key = strategy.lower().split()[0] if strategy else ""
                for s, regime_list in self.strategy_regime_map.items():
                    if key in s.lower() or s.lower() in strategy.lower():
                        for r, conf in regime_list:
                            if regime.lower().startswith(r.split()[0].lower()):
                                relationships.append({
                                    "source_type": "Strategy",
                                    "source_name": strategy,
                                    "rel_type": "applies_to",
                                    "target_type": "MarketRegime",
                                    "target_name": regime,
                                    "confidence": conf,
                                    "evidence": "Pattern matching from corpus"
                                })

        # Link Greeks to strategies
        for greek in parsed.get("greeks", []):
            for strategy in parsed.get("strategies", []):
                for g, strats in self.greek_strategy_map.items():
                    if greek.lower() == g.lower():
                        for s, conf in strats:
                            if s.lower() in strategy.lower() or strategy.lower() in s.lower():
                                relationships.append({
                                    "source_type": "Strategy",
                                    "source_name": strategy,
                                    "rel_type": "requires",
                                    "target_type": "Greeks",
                                    "target_name": greek,
                                    "confidence": conf,
                                    "evidence": "Strategy analysis from corpus"
                                })

        # Link events to opportunities
        for event in parsed.get("events", []):
            for opp in parsed.get("trading_opportunities", []):
                for e, opps in self.event_opportunity_map.items():
                    if event.lower() == e.lower():
                        for o, conf in opps:
                            if o.lower() in opp.lower() or opp.lower() in o.lower():
                                relationships.append({
                                    "source_type": "Event",
                                    "source_name": event,
                                    "rel_type": "triggers",
                                    "target_type": "TradingOpportunity",
                                    "target_name": o,
                                    "confidence": conf,
                                    "evidence": "Event-opportunity correlation"
                                })

        # Link risk metrics to strategies
        for risk in parsed.get("risk_metrics", []):
            for strategy in parsed.get("strategies", []):
                # Strategies inherently constrained by various risks
                if any(keyword in strategy.lower() for keyword in
                       ["gamma", "delta", "vol", "arbitrage"]):
                    relationships.append({
                        "source_type": "RiskMetric",
                        "source_name": risk,
                        "rel_type": "constrains",
                        "target_type": "Strategy",
                        "target_name": strategy,
                        "confidence": 0.75,
                        "evidence": "Risk-strategy mapping from corpus"
                    })

        return relationships


def ingest_corpus_files(
    kg_client: KGClient,
    corpus_dir: str = "/workspace/corpus/finance"
) -> Dict[str, any]:
    """
    Ingest all corpus files and populate knowledge graph.

    Args:
        kg_client: KGClient instance
        corpus_dir: Directory containing corpus markdown files

    Returns:
        Dictionary with ingestion statistics
    """
    parser = CorpusParser()
    linker = EntityLinker()

    stats = {
        "files_processed": 0,
        "nodes_created": 0,
        "relationships_created": 0,
        "entities_by_type": {},
        "errors": []
    }

    # Parse all markdown files
    corpus_path = Path(corpus_dir)
    if not corpus_path.exists():
        logger.warning(f"Corpus directory not found: {corpus_dir}")
        return stats

    md_files = list(corpus_path.glob("*.md"))
    logger.info(f"Found {len(md_files)} corpus files")

    all_parsed = {}
    for md_file in md_files:
        logger.info(f"Parsing {md_file.name}...")
        parsed = parser.parse_file(str(md_file))
        all_parsed[md_file.name] = parsed
        stats["files_processed"] += 1

    # Create nodes for all discovered entities
    for entity_type, entity_names in parser.entities.items():
        unique_names = set(entity_names)
        for name in unique_names:
            if not name or len(name) < 2:
                continue

            try:
                node = kg_client.add_node(
                    entity_type=entity_type,
                    name=name,
                    attributes={
                        "corpus_source": "Finance Corpus",
                        "extracted_from": "Markdown parsing"
                    }
                )
                if node:
                    stats["nodes_created"] += 1
                    stats["entities_by_type"][entity_type] = (
                        stats["entities_by_type"].get(entity_type, 0) + 1
                    )
            except Exception as e:
                logger.error(f"Failed to create node {entity_type}:{name}: {e}")
                stats["errors"].append(f"Node creation: {entity_type}:{name}")

    # Link entities and create relationships
    for filename, parsed in all_parsed.items():
        try:
            relationships = linker.link_entities(kg_client, parsed)
            for rel in relationships:
                try:
                    source = kg_client.get_node_by_name(
                        rel["source_type"],
                        rel["source_name"]
                    )
                    target = kg_client.get_node_by_name(
                        rel["target_type"],
                        rel["target_name"]
                    )

                    if source and target:
                        created_rel = kg_client.add_relationship(
                            source.id,
                            rel["rel_type"],
                            target.id,
                            confidence=rel["confidence"],
                            evidence=rel["evidence"],
                            metadata={"source_file": filename}
                        )
                        if created_rel:
                            stats["relationships_created"] += 1
                except Exception as e:
                    logger.error(f"Failed to create relationship: {e}")
                    stats["errors"].append(f"Relationship: {rel['source_name']} -> {rel['target_name']}")

        except Exception as e:
            logger.error(f"Failed to link entities from {filename}: {e}")
            stats["errors"].append(f"Entity linking: {filename}")

    logger.info(f"Ingestion complete. Created {stats['nodes_created']} nodes "
                f"and {stats['relationships_created']} relationships")
    return stats


def export_ingestion_report(
    stats: Dict[str, any],
    output_file: str = "/workspace/group1-rag/kg/ingestion_report.json"
):
    """Export ingestion statistics to JSON."""
    with open(output_file, 'w') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Ingestion report saved to {output_file}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    client = KGClient(use_mock=True)
    stats = ingest_corpus_files(client)
    export_ingestion_report(stats)

    print(f"\n=== Ingestion Summary ===")
    print(f"Files processed: {stats['files_processed']}")
    print(f"Nodes created: {stats['nodes_created']}")
    print(f"Relationships created: {stats['relationships_created']}")
    print(f"Entities by type: {stats['entities_by_type']}")
