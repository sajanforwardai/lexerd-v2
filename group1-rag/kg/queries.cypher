/*
Neo4j Cypher Queries for Group One RAG Knowledge Graph
========================================================

Pre-built queries for common knowledge graph operations:
1. Strategy discovery and matching
2. Risk analysis and constraint checking
3. Event impact analysis
4. Opportunity identification
5. Relationship navigation
*/

// ========================================
// 1. STRATEGY DISCOVERY QUERIES
// ========================================

// Query: Find strategies applicable to a market regime
MATCH (regime:MarketRegime {name: $regime_name})-[rel:applies_to]-(strategy:Strategy)
RETURN strategy.name as strategy, strategy.description, strategy.risk_level, rel.confidence
ORDER BY rel.confidence DESC
LIMIT 20;

// Query: Find all strategies with their applicable regimes
MATCH (strategy:Strategy)-[rel:applies_to]-(regime:MarketRegime)
RETURN strategy.name, regime.name, rel.confidence, strategy.time_horizon
ORDER BY strategy.name, rel.confidence DESC;

// Query: Find strategies requiring specific Greek understanding
MATCH (strategy:Strategy)-[rel:requires]-(greek:Greeks)
WHERE greek.name IN $greek_names
RETURN DISTINCT strategy.name, strategy.description, collect(greek.name) as greeks
ORDER BY strategy.name;

// Query: Find high-confidence strategy chains
MATCH (regime:MarketRegime)-[r1:applies_to {confidence: $min_confidence}]->
       (strategy:Strategy)-[r2:creates]->(opp:TradingOpportunity)
RETURN regime.name, strategy.name, opp.name, r1.confidence, r2.confidence
ORDER BY r1.confidence * r2.confidence DESC;


// ========================================
// 2. RISK ANALYSIS & CONSTRAINT CHECKING
// ========================================

// Query: Find all risk metrics affecting a strategy
MATCH (strategy:Strategy)-[rel:constrains]-(risk:RiskMetric)
RETURN risk.name, risk.definition, risk.measurement, rel.confidence
ORDER BY rel.confidence DESC;

// Query: Identify risk metrics for a position
MATCH (position:Position {name: $position_name})-[rel:exposed_to]-(risk:RiskMetric)
RETURN position.name, risk.name, risk.definition, risk.measurement, rel.confidence
ORDER BY rel.confidence DESC;

// Query: Check position constraints against regime
MATCH (position:Position {name: $position_name})-[:exposed_to]->(risk:RiskMetric)
MATCH (regime:MarketRegime {name: $regime_name})-[:constrains]->(risk)
RETURN position.name, regime.name, risk.name, risk.measurement
ORDER BY risk.name;

// Query: Find correlated risk metrics
MATCH (r1:RiskMetric)-[rel:calculated_from]-(r2:RiskMetric)
WHERE r1.name IN $risk_metrics AND r2.name IN $risk_metrics
RETURN r1.name, r2.name, rel.confidence
ORDER BY rel.confidence DESC;

// Query: Identify gap risk in strategy
MATCH (strategy:Strategy)-[:constrains]->(risk:RiskMetric {name: 'Gap Risk'})
MATCH (strategy)-[:applies_to]->(regime:MarketRegime)
RETURN strategy.name, regime.name, risk.definition
ORDER BY strategy.name;


// ========================================
// 3. EVENT IMPACT ANALYSIS
// ========================================

// Query: Find events and their triggered opportunities
MATCH (event:Event {name: $event_name})-[rel:triggers]->(opp:TradingOpportunity)
RETURN event.name, event.type, opp.name, opp.description, rel.confidence
ORDER BY rel.confidence DESC;

// Query: Find Greeks affected by an event
MATCH (event:Event {name: $event_name})-[:triggers]->(opp:TradingOpportunity)
       -[:requires]->(greek:Greeks)
RETURN DISTINCT greek.name, greek.interpretation, collect(opp.name) as opportunities
ORDER BY greek.name;

// Query: Identify risk metric changes from events
MATCH (event:Event)-[rel:creates]->(risk:RiskMetric)
RETURN event.name, event.impact_level, risk.name, risk.measurement, rel.confidence
ORDER BY rel.confidence DESC;

// Query: Find cascading event impacts
MATCH (event:Event)-[r1:creates]->(risk1:RiskMetric)
       -[r2:constrains]->(strategy:Strategy)
       -[r3:applies_to]->(regime:MarketRegime)
WHERE r1.confidence > $min_confidence AND r2.confidence > $min_confidence
  AND r3.confidence > $min_confidence
RETURN event.name, risk1.name, strategy.name, regime.name,
       r1.confidence * r2.confidence * r3.confidence as cascade_confidence
ORDER BY cascade_confidence DESC;

// Query: Earnings impact on volatility and Greeks
MATCH (event:Event {type: 'Earnings'})-[:triggers]->(opp:TradingOpportunity)
MATCH (opp)-[:requires]->(greek:Greeks)
WHERE greek.name IN ['Vega', 'Theta', 'Gamma']
RETURN event.name, opp.name, collect(greek.name) as affected_greeks
ORDER BY event.name;


// ========================================
// 4. OPPORTUNITY IDENTIFICATION
// ========================================

// Query: Find trading opportunities from order flow patterns
MATCH (of:OrderFlow)-[rel:indicates]->(opp:TradingOpportunity)
WHERE rel.confidence > $min_confidence
RETURN opp.name, opp.description, of.name, rel.confidence, rel.evidence
ORDER BY rel.confidence DESC;

// Query: Find arbitrage opportunities
MATCH (vs1:VolSurface)-[rel:creates]->(opp:TradingOpportunity {type: 'Arbitrage'})
       -[:composed_of]->(greek:Greeks)
RETURN vs1.name, opp.name, opp.expected_return, greek.name
ORDER BY opp.expected_return DESC;

// Query: Identify mean-reversion opportunities
MATCH (regime:MarketRegime)-[r1:applies_to]->(strategy:Strategy {name: 'Statistical Arbitrage'})
MATCH (strategy)-[r2:creates]->(opp:TradingOpportunity {type: 'Mean Reversion'})
RETURN regime.name, strategy.name, opp.name, opp.entry_criteria, opp.exit_criteria
ORDER BY regime.name;

// Query: Find opportunities with supporting Greeks
MATCH (opp:TradingOpportunity)-[:requires]->(g1:Greeks)
       -[:calculated_from]-(g2:Greeks)
RETURN opp.name, opp.description, collect(DISTINCT g1.name) as primary_greeks,
       collect(DISTINCT g2.name) as supporting_greeks
ORDER BY opp.name;


// ========================================
// 5. VOLATILITY SURFACE ANALYSIS
// ========================================

// Query: Analyze volatility surface characteristics
MATCH (vs:VolSurface)-[:composed_of]->(greek:Greeks)
RETURN vs.name, vs.characteristic, collect(greek.name) as components, vs.trading_implication
ORDER BY vs.name;

// Query: Find skew trading opportunities
MATCH (vs:VolSurface {characteristic: 'Skew'})-[rel:creates]->(opp:TradingOpportunity)
RETURN vs.name, opp.name, opp.description, rel.confidence, opp.expected_return
ORDER BY rel.confidence DESC;

// Query: Find calendar spread opportunities
MATCH (vs:VolSurface {characteristic: 'Term Structure'})-[rel:creates]->(opp:TradingOpportunity)
RETURN vs.name, opp.name, opp.time_horizon, rel.confidence
ORDER BY rel.confidence DESC;


// ========================================
// 6. RELATIONSHIP NAVIGATION
// ========================================

// Query: Find all nodes connected to a strategy
MATCH (s:Strategy {name: $strategy_name})-[rel]->(connected)
RETURN type(rel) as relationship_type, connected.name, rel.confidence
UNION ALL
MATCH (s:Strategy {name: $strategy_name})<-[rel]-(connected)
RETURN type(rel) as relationship_type, connected.name, rel.confidence
ORDER BY relationship_type, rel.confidence DESC;

// Query: Find shortest path between nodes
MATCH path = shortestPath(
  (start {name: $start_name})-[*..5]-(end {name: $end_name})
)
RETURN length(path) as path_length,
       [node IN nodes(path) | node.name] as node_path,
       [rel IN relationships(path) | type(rel)] as rel_types;

// Query: Find communities (highly connected node clusters)
MATCH (n1)-[rel1 {confidence: $min_confidence}]-(n2)
WHERE n1.name < n2.name  // Avoid duplicates
RETURN n1.name, n1.entity_type, n2.name, n2.entity_type, rel1.confidence
ORDER BY rel1.confidence DESC
LIMIT 50;


// ========================================
// 7. GREEK-CENTRIC ANALYSIS
// ========================================

// Query: Find all Greeks and their relationships
MATCH (greek:Greeks)
RETURN greek.name, greek.definition, greek.risk_factor, greek.interpretation
ORDER BY greek.name;

// Query: Strategies grouped by primary Greek exposure
MATCH (strategy:Strategy)-[rel:requires]->(greek:Greeks)
WHERE rel.confidence > $min_confidence
RETURN greek.name, collect(strategy.name) as strategies,
       avg(rel.confidence) as avg_confidence
ORDER BY avg_confidence DESC;

// Query: How Greeks affect position P&L
MATCH (greek:Greeks)-[rel:affects]->(position:Position)
RETURN greek.name, position.name, greek.interpretation, rel.confidence
ORDER BY greek.name, rel.confidence DESC;

// Query: Greeks in a volatility regime
MATCH (regime:MarketRegime)-[:constrains]->(greek:Greeks)
RETURN regime.name, collect(greek.name) as key_greeks
ORDER BY regime.name;


// ========================================
// 8. MARKET REGIME ANALYSIS
// ========================================

// Query: Find strategies by regime volatility level
MATCH (regime:MarketRegime)-[rel:applies_to]->(strategy:Strategy)
WHERE regime.volatility_level = $vol_level
RETURN regime.name, strategy.name, strategy.risk_level, rel.confidence
ORDER BY rel.confidence DESC;

// Query: Regime transitions and strategy shifts
MATCH (r1:MarketRegime)-[rel:transforms_to]-(r2:MarketRegime)
MATCH (r1)-[:applies_to]-(s1:Strategy)
MATCH (r2)-[:applies_to]-(s2:Strategy)
WHERE s1.name <> s2.name
RETURN r1.name, r2.name, s1.name, s2.name, rel.confidence
ORDER BY rel.confidence DESC;

// Query: Optimal strategies for current regime
MATCH (regime:MarketRegime {name: $current_regime})-[rel:applies_to {confidence: $min_confidence}]
       ->(strategy:Strategy)
RETURN regime.name, strategy.name, strategy.description,
       strategy.capital_requirement, rel.confidence
ORDER BY rel.confidence DESC
LIMIT 10;


// ========================================
// 9. ORDER FLOW ANALYSIS
// ========================================

// Query: Order flow patterns and their implications
MATCH (of:OrderFlow)-[rel:indicates]->(opp:TradingOpportunity)
RETURN of.name, of.type, opp.name, rel.confidence, rel.evidence
ORDER BY of.type, rel.confidence DESC;

// Query: Microstructure opportunities
MATCH (of:OrderFlow {type: 'Microstructure'})-[rel:indicates]->(opp:TradingOpportunity)
WHERE opp.type = 'Arbitrage'
RETURN of.name, opp.name, of.detectability, rel.confidence
ORDER BY rel.confidence DESC;


// ========================================
// 10. PERFORMANCE & STATS QUERIES
// ========================================

// Query: Relationship confidence distribution
MATCH ()-[rel]-()
RETURN
  ROUND(rel.confidence * 10) / 10 as confidence_bucket,
  COUNT(*) as count,
  AVG(rel.confidence) as avg_confidence
ORDER BY confidence_bucket DESC;

// Query: Entity type distribution
MATCH (n)
RETURN labels(n)[0] as entity_type, COUNT(*) as count
ORDER BY count DESC;

// Query: Most connected nodes (hubs)
MATCH (n)-[r]-(m)
RETURN n.name, labels(n)[0] as type, COUNT(*) as degree
ORDER BY degree DESC
LIMIT 20;

// Query: Relationships by type
MATCH ()-[r]-()
RETURN type(r) as relationship_type, COUNT(*) as count,
       AVG(r.confidence) as avg_confidence
ORDER BY count DESC;


// ========================================
// 11. UTILITY QUERIES
// ========================================

// Query: Find orphaned nodes (no relationships)
MATCH (n)
WHERE NOT (n)-[]-()
RETURN n.name, labels(n)[0] as entity_type
ORDER BY entity_type, n.name;

// Query: Low confidence relationships (quality check)
MATCH ()-[r]-()
WHERE r.confidence < $confidence_threshold
RETURN r.source.name, type(r), r.target.name, r.confidence, r.evidence
ORDER BY r.confidence ASC
LIMIT 50;

// Query: Validate entity consistency
MATCH (n)
WHERE NOT n.name
RETURN n.id, labels(n)[0] as entity_type, "Missing name" as issue
UNION ALL
MATCH ()-[r]-()
WHERE r.confidence < 0 OR r.confidence > 1
RETURN r, labels(r)[0], "Invalid confidence score" as issue;

// Query: Find recommendations for strategy based on regime and risk profile
MATCH (regime:MarketRegime {name: $regime_name})-[rel1:applies_to]->(strategy:Strategy)
MATCH (strategy)-[rel2:constrains]-(risk:RiskMetric)
WHERE rel1.confidence > $min_confidence AND rel2.confidence > $min_confidence
RETURN strategy.name, strategy.description, strategy.risk_level,
       collect(risk.name) as risks, rel1.confidence as regime_match
ORDER BY rel1.confidence DESC
LIMIT $top_n;
