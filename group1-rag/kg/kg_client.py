"""
Knowledge Graph Client for Group One RAG
========================================
Neo4j-based knowledge graph for trading strategies, market regimes, Greeks,
volatility surfaces, and risk metrics.

Schema: 9 entity types with relationships tagged by confidence and type.
"""

import os
import json
import hashlib
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from functools import lru_cache
import re

try:
    from neo4j import GraphDatabase, basic_auth
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logging.warning("neo4j package not installed; using mock mode")

logger = logging.getLogger(__name__)

# Entity types in the schema
ENTITY_TYPES = {
    "MarketRegime": {
        "description": "Market conditions (bull, bear, high-vol, low-vol, etc.)",
        "attributes": ["name", "characteristics", "volatility_level", "risk_profile"]
    },
    "Strategy": {
        "description": "Trading strategies (delta hedging, gamma scalping, vol arbitrage, etc.)",
        "attributes": ["name", "description", "risk_level", "capital_requirement", "time_horizon"]
    },
    "Greeks": {
        "description": "Option Greeks (delta, gamma, theta, vega, rho)",
        "attributes": ["name", "definition", "formula", "interpretation", "risk_factor"]
    },
    "VolSurface": {
        "description": "Volatility surface characteristics and patterns",
        "attributes": ["name", "characteristic", "pattern", "trading_implication"]
    },
    "TradingOpportunity": {
        "description": "Specific market misalignments and trading setups",
        "attributes": ["name", "description", "entry_criteria", "exit_criteria", "expected_return"]
    },
    "Event": {
        "description": "Market events (earnings, economic data, mergers, etc.)",
        "attributes": ["name", "type", "impact_level", "volatility_impact"]
    },
    "OrderFlow": {
        "description": "Market microstructure and order flow dynamics",
        "attributes": ["name", "type", "impact", "detectability"]
    },
    "RiskMetric": {
        "description": "Risk measures and metrics (gap risk, vol-of-vol, correlation risk, etc.)",
        "attributes": ["name", "definition", "measurement", "mitigation"]
    },
    "Position": {
        "description": "Trading positions and holdings",
        "attributes": ["name", "type", "size", "entry_price", "current_value"]
    }
}

# Relationship types with meanings
RELATIONSHIP_TYPES = {
    "applies_to": "Strategy applies to/effective in Market Regime",
    "triggers": "Event triggers Trading Opportunity or Order Flow pattern",
    "calculated_from": "Greek or Risk Metric calculated from underlying factors",
    "constrains": "Risk Metric constrains or limits Position or Strategy",
    "affects": "Greek affects Position or Strategy P&L",
    "composed_of": "VolSurface composed of or characterized by Greeks",
    "creates": "Event creates or impacts Risk Metric",
    "indicates": "OrderFlow pattern indicates Trading Opportunity",
    "requires": "Strategy requires understanding of specific Greek",
    "exposed_to": "Position exposed to specific Market Regime or Risk Factor",
}


class KGNode:
    """Represents a node in the knowledge graph."""

    def __init__(self, entity_type: str, name: str, attributes: Dict[str, Any]):
        self.entity_type = entity_type
        self.name = name
        self.attributes = attributes
        self.id = hashlib.md5(f"{entity_type}:{name}".encode()).hexdigest()[:12]
        self.created_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "name": self.name,
            "attributes": self.attributes,
            "created_at": self.created_at
        }


class KGRelationship:
    """Represents a relationship between nodes."""

    def __init__(
        self,
        source: KGNode,
        rel_type: str,
        target: KGNode,
        confidence: float = 0.8,
        evidence: str = "",
        metadata: Dict[str, Any] = None
    ):
        self.source = source
        self.rel_type = rel_type
        self.target = target
        self.confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        self.evidence = evidence
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow().isoformat()

        if self.rel_type not in RELATIONSHIP_TYPES:
            logger.warning(f"Unknown relationship type: {rel_type}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source.id,
            "source_name": self.source.name,
            "rel_type": self.rel_type,
            "target_id": self.target.id,
            "target_name": self.target.name,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "metadata": self.metadata,
            "created_at": self.created_at
        }


class MockNeo4jDriver:
    """Mock Neo4j driver for testing/development without a running Neo4j instance."""

    def __init__(self):
        self.nodes: Dict[str, KGNode] = {}
        self.relationships: List[KGRelationship] = []

    def add_node(self, node: KGNode):
        self.nodes[node.id] = node

    def add_relationship(self, rel: KGRelationship):
        self.relationships.append(rel)

    def query(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        # Simple mock query implementation
        return []

    def close(self):
        pass


class KGClient:
    """
    Neo4j-based Knowledge Graph Client.

    Manages nodes, relationships, and queries with caching.
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_mock: bool = False
    ):
        """
        Initialize KG Client.

        Args:
            neo4j_uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            username: Neo4j username
            password: Neo4j password
            use_mock: If True, use in-memory mock driver instead of Neo4j
        """
        self.use_mock = use_mock or not NEO4J_AVAILABLE
        self.driver = None
        self.session = None

        if self.use_mock:
            self.driver = MockNeo4jDriver()
            logger.info("Using mock Neo4j driver (in-memory storage)")
        else:
            self._connect_neo4j(neo4j_uri, username, password)

        # In-memory caches
        self.node_cache: Dict[str, KGNode] = {}
        self.rel_cache: List[KGRelationship] = []
        self._query_cache: Dict[str, List[Dict]] = {}

    def _connect_neo4j(self, uri: str, username: str, password: str):
        """Connect to Neo4j instance."""
        if not NEO4J_AVAILABLE:
            logger.error("neo4j package not available; switching to mock mode")
            self.use_mock = True
            self.driver = MockNeo4jDriver()
            return

        try:
            self.driver = GraphDatabase.driver(
                uri or "bolt://localhost:7687",
                auth=basic_auth(username or "neo4j", password or "password"),
                encrypted=False
            )
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}. Falling back to mock mode.")
            self.use_mock = True
            self.driver = MockNeo4jDriver()

    def create_schema(self) -> bool:
        """Create Neo4j schema with constraints and indexes."""
        if self.use_mock:
            logger.info("Mock mode: schema creation skipped")
            return True

        try:
            with self.driver.session() as session:
                # Create constraints for each entity type
                for entity_type in ENTITY_TYPES:
                    session.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{entity_type}) "
                        f"REQUIRE (n.id, n.name) IS UNIQUE"
                    )

                # Create indexes
                session.run(
                    "CREATE INDEX IF NOT EXISTS FOR (n:KGNode) ON (n.entity_type, n.name)"
                )
                session.run(
                    "CREATE INDEX IF NOT EXISTS FOR (r:KGRelationship) ON (r.confidence)"
                )

                logger.info("Schema created successfully")
                return True
        except Exception as e:
            logger.error(f"Schema creation failed: {e}")
            return False

    def add_node(
        self,
        entity_type: str,
        name: str,
        attributes: Dict[str, Any] = None
    ) -> Optional[KGNode]:
        """
        Add a node to the knowledge graph.

        Args:
            entity_type: One of ENTITY_TYPES
            name: Node name/label
            attributes: Dictionary of attributes

        Returns:
            Created KGNode or None on error
        """
        if entity_type not in ENTITY_TYPES:
            logger.error(f"Invalid entity type: {entity_type}")
            return None

        attributes = attributes or {}
        node = KGNode(entity_type, name, attributes)

        # Cache locally
        self.node_cache[node.id] = node

        # Persist to Neo4j if available
        if not self.use_mock:
            try:
                with self.driver.session() as session:
                    session.run(
                        f"MERGE (n:{entity_type} {{id: $id, name: $name}}) "
                        f"SET n += $attributes, n.created_at = $created_at",
                        {
                            "id": node.id,
                            "name": node.name,
                            "attributes": node.attributes,
                            "created_at": node.created_at
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to persist node to Neo4j: {e}")
        else:
            self.driver.add_node(node)

        logger.debug(f"Added node: {entity_type}:{name} (id={node.id})")
        return node

    def add_relationship(
        self,
        source_id: str,
        rel_type: str,
        target_id: str,
        confidence: float = 0.8,
        evidence: str = "",
        metadata: Dict[str, Any] = None
    ) -> Optional[KGRelationship]:
        """
        Add a relationship between two nodes.

        Args:
            source_id: Source node ID
            rel_type: Relationship type (from RELATIONSHIP_TYPES)
            target_id: Target node ID
            confidence: Confidence score [0, 1]
            evidence: Evidence or citation for this relationship
            metadata: Additional metadata

        Returns:
            Created KGRelationship or None on error
        """
        if source_id not in self.node_cache or target_id not in self.node_cache:
            logger.error(f"Node not found: {source_id} or {target_id}")
            return None

        source = self.node_cache[source_id]
        target = self.node_cache[target_id]

        rel = KGRelationship(
            source, rel_type, target,
            confidence=confidence,
            evidence=evidence,
            metadata=metadata
        )

        # Cache locally
        self.rel_cache.append(rel)

        # Persist to Neo4j if available
        if not self.use_mock:
            try:
                with self.driver.session() as session:
                    session.run(
                        f"MATCH (s {{id: $source_id}}) MATCH (t {{id: $target_id}}) "
                        f"MERGE (s)-[r:{rel_type} {{confidence: $confidence}}]->(t) "
                        f"SET r.evidence = $evidence, r.metadata = $metadata, "
                        f"r.created_at = $created_at",
                        {
                            "source_id": source_id,
                            "target_id": target_id,
                            "confidence": confidence,
                            "evidence": evidence,
                            "metadata": metadata or {},
                            "created_at": rel.created_at
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to persist relationship to Neo4j: {e}")
        else:
            self.driver.add_relationship(rel)

        logger.debug(
            f"Added relationship: {source.name} -{rel_type} "
            f"[{confidence:.2f}]-> {target.name}"
        )
        return rel

    @lru_cache(maxsize=128)
    def get_node_by_name(self, entity_type: str, name: str) -> Optional[KGNode]:
        """Get a node by entity type and name."""
        for node in self.node_cache.values():
            if node.entity_type == entity_type and node.name == name:
                return node
        return None

    def query_strategies_by_regime(self, regime_name: str) -> List[Dict[str, Any]]:
        """
        Find strategies that apply to a specific market regime.

        Cypher:
        MATCH (r:MarketRegime {name: $regime})-[rel:applies_to]-(s:Strategy)
        RETURN s.name, s.description, rel.confidence
        ORDER BY rel.confidence DESC
        """
        cache_key = f"strategies_by_regime:{regime_name}"
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        results = []
        regime = self.get_node_by_name("MarketRegime", regime_name)
        if not regime:
            logger.warning(f"Regime not found: {regime_name}")
            return results

        for rel in self.rel_cache:
            if (rel.source.id == regime.id and
                rel.rel_type == "applies_to" and
                rel.target.entity_type == "Strategy"):
                results.append({
                    "strategy_name": rel.target.name,
                    "description": rel.target.attributes.get("description"),
                    "confidence": rel.confidence,
                    "evidence": rel.evidence
                })

        results.sort(key=lambda x: x["confidence"], reverse=True)
        self._query_cache[cache_key] = results
        return results

    def query_greeks_by_event(self, event_name: str) -> List[Dict[str, Any]]:
        """
        Find Greeks affected by a specific event.

        Cypher:
        MATCH (e:Event {name: $event})-[:triggers]->(opp:TradingOpportunity)
        -[:requires]->(g:Greeks)
        RETURN g.name, g.interpretation, collect(opp.name) as opportunities
        """
        cache_key = f"greeks_by_event:{event_name}"
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        results = {}
        event = self.get_node_by_name("Event", event_name)
        if not event:
            logger.warning(f"Event not found: {event_name}")
            return []

        # Find opportunities triggered by event
        for rel in self.rel_cache:
            if rel.source.id == event.id and rel.rel_type == "triggers":
                opp = rel.target
                # Find Greeks required by opportunity
                for rel2 in self.rel_cache:
                    if (rel2.source.id == opp.id and
                        rel2.rel_type == "requires" and
                        rel2.target.entity_type == "Greeks"):
                        greek = rel2.target
                        if greek.name not in results:
                            results[greek.name] = {
                                "greek": greek.name,
                                "interpretation": greek.attributes.get("interpretation"),
                                "opportunities": []
                            }
                        if opp.name not in results[greek.name]["opportunities"]:
                            results[greek.name]["opportunities"].append(opp.name)

        result_list = list(results.values())
        self._query_cache[cache_key] = result_list
        return result_list

    def query_opportunities_from_misalignments(self) -> List[Dict[str, Any]]:
        """
        Find trading opportunities arising from market misalignments.

        Cypher:
        MATCH (of:OrderFlow)-[rel:indicates]->(opp:TradingOpportunity)
        WHERE rel.confidence > 0.75
        RETURN opp.name, opp.description, rel.confidence, rel.evidence
        ORDER BY rel.confidence DESC
        """
        cache_key = "opportunities_from_misalignments"
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        results = []
        for rel in self.rel_cache:
            if (rel.rel_type == "indicates" and
                rel.target.entity_type == "TradingOpportunity" and
                rel.confidence > 0.75):
                results.append({
                    "opportunity": rel.target.name,
                    "description": rel.target.attributes.get("description"),
                    "confidence": rel.confidence,
                    "evidence": rel.evidence,
                    "order_flow_pattern": rel.source.name
                })

        results.sort(key=lambda x: x["confidence"], reverse=True)
        self._query_cache[cache_key] = results
        return results

    def query_position_constraints(self, position_name: str) -> List[Dict[str, Any]]:
        """
        Verify risk constraints on a position.

        Cypher:
        MATCH (p:Position {name: $position})-[:exposed_to]->(rm:RiskMetric)
        RETURN rm.name, rm.definition, rm.measurement
        """
        cache_key = f"position_constraints:{position_name}"
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        results = []
        position = self.get_node_by_name("Position", position_name)
        if not position:
            logger.warning(f"Position not found: {position_name}")
            return results

        for rel in self.rel_cache:
            if (rel.source.id == position.id and
                rel.rel_type == "exposed_to" and
                rel.target.entity_type == "RiskMetric"):
                results.append({
                    "risk_metric": rel.target.name,
                    "definition": rel.target.attributes.get("definition"),
                    "measurement": rel.target.attributes.get("measurement"),
                    "confidence": rel.confidence
                })

        self._query_cache[cache_key] = results
        return results

    def execute_cypher(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        """
        Execute arbitrary Cypher query.

        Args:
            cypher: Cypher query string
            parameters: Query parameters

        Returns:
            Query results
        """
        if self.use_mock:
            logger.warning("Cypher queries not supported in mock mode")
            return []

        try:
            with self.driver.session() as session:
                result = session.run(cypher, parameters or {})
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        entity_counts = {}
        for entity_type in ENTITY_TYPES:
            entity_counts[entity_type] = sum(
                1 for n in self.node_cache.values()
                if n.entity_type == entity_type
            )

        rel_counts = {}
        for rel_type in RELATIONSHIP_TYPES:
            rel_counts[rel_type] = sum(
                1 for r in self.rel_cache
                if r.rel_type == rel_type
            )

        avg_confidence = (
            sum(r.confidence for r in self.rel_cache) / len(self.rel_cache)
            if self.rel_cache else 0.0
        )

        return {
            "total_nodes": len(self.node_cache),
            "total_relationships": len(self.rel_cache),
            "entities_by_type": entity_counts,
            "relationships_by_type": rel_counts,
            "average_confidence": avg_confidence,
            "cache_size": len(self._query_cache)
        }

    def export_graph(self, filepath: str):
        """Export knowledge graph as JSON."""
        export = {
            "nodes": [n.to_dict() for n in self.node_cache.values()],
            "relationships": [r.to_dict() for r in self.rel_cache],
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "statistics": self.get_statistics()
            }
        }

        with open(filepath, 'w') as f:
            json.dump(export, f, indent=2)

        logger.info(f"Graph exported to {filepath}")

    def import_graph(self, filepath: str):
        """Import knowledge graph from JSON."""
        try:
            with open(filepath, 'r') as f:
                import_data = json.load(f)

            # Import nodes
            for node_dict in import_data.get("nodes", []):
                node = KGNode(
                    node_dict["entity_type"],
                    node_dict["name"],
                    node_dict["attributes"]
                )
                node.id = node_dict["id"]
                node.created_at = node_dict["created_at"]
                self.node_cache[node.id] = node

            # Import relationships
            for rel_dict in import_data.get("relationships", []):
                source = self.node_cache[rel_dict["source_id"]]
                target = self.node_cache[rel_dict["target_id"]]
                rel = KGRelationship(
                    source,
                    rel_dict["rel_type"],
                    target,
                    confidence=rel_dict["confidence"],
                    evidence=rel_dict["evidence"],
                    metadata=rel_dict["metadata"]
                )
                rel.created_at = rel_dict["created_at"]
                self.rel_cache.append(rel)

            logger.info(f"Graph imported from {filepath}")
        except Exception as e:
            logger.error(f"Failed to import graph: {e}")

    def clear_cache(self):
        """Clear query cache."""
        self._query_cache.clear()
        logger.info("Query cache cleared")

    def close(self):
        """Close Neo4j connection."""
        if self.driver and not self.use_mock:
            self.driver.close()
            logger.info("Neo4j connection closed")


def create_client(
    neo4j_uri: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    use_mock: bool = True
) -> KGClient:
    """Factory function to create a KG client."""
    return KGClient(neo4j_uri, username, password, use_mock)
