# Group One RAG Knowledge Graph

A comprehensive Neo4j-based knowledge graph for trading strategies, market regimes, Greeks, volatility surfaces, and risk metrics. Built for the Group One RAG system with corpus ingestion, entity linking, relationship management, and pre-built queries.

## Overview

The knowledge graph models the domain of quantitative finance and options trading with 9 core entity types:

1. **MarketRegime** - Market conditions (bull, bear, high-vol, low-vol, etc.)
2. **Strategy** - Trading strategies (delta hedging, gamma scalping, vol arbitrage, etc.)
3. **Greeks** - Option Greeks (delta, gamma, theta, vega, rho)
4. **VolSurface** - Volatility surface characteristics and patterns
5. **TradingOpportunity** - Market misalignments and trading setups
6. **Event** - Market events (earnings, economic data, mergers, etc.)
7. **OrderFlow** - Market microstructure and order flow dynamics
8. **RiskMetric** - Risk measures (gap risk, vol-of-vol, correlation risk, etc.)
9. **Position** - Trading positions and holdings

## Quick Start

### Installation

```bash
cd /workspace/group1-rag/kg

# Install dependencies (if using real Neo4j)
# pip install neo4j

# For mock mode (in-memory, no Neo4j required):
python3 example_usage.py
```

### Basic Usage

```python
from kg_client import KGClient
from corpus_ingestion import ingest_corpus_files

# Create client (uses mock mode by default)
client = KGClient(use_mock=True)

# Ingest corpus files
stats = ingest_corpus_files(client)
print(f"Created {stats['nodes_created']} nodes and {stats['relationships_created']} relationships")

# Query strategies for a market regime
strategies = client.query_strategies_by_regime("High-Vol Market")
for s in strategies:
    print(f"{s['strategy_name']}: {s['confidence']:.2f} confidence")

# Find Greeks affected by an event
greeks = client.query_greeks_by_event("Earnings Announcement")
for g in greeks:
    print(f"Greek: {g['greek']}, Opportunities: {g['opportunities']}")

# Find trading opportunities
opportunities = client.query_opportunities_from_misalignments()
for opp in opportunities:
    print(f"{opp['opportunity']}: confidence {opp['confidence']:.2f}")

# Check position constraints
constraints = client.query_position_constraints("Long 100 XYZ Calls")
for c in constraints:
    print(f"Risk: {c['risk_metric']}")

# Get statistics
stats = client.get_statistics()
print(f"Total nodes: {stats['total_nodes']}")
print(f"Total relationships: {stats['total_relationships']}")
print(f"Average confidence: {stats['average_confidence']:.2f}")
```

## Architecture

### Components

#### kg_client.py
Core client for knowledge graph management:
- `KGClient`: Main client class for node/relationship management
- `KGNode`: Represents a node in the graph
- `KGRelationship`: Represents a relationship with confidence scoring
- `MockNeo4jDriver`: In-memory mock driver for testing/development
- Pre-built query methods with caching
- Export/import functionality

**Key Features:**
- In-memory caching with LRU cache on node lookups
- Query result caching (128 results)
- Confidence score bounds checking [0, 1]
- Automatic node ID generation (MD5 hash)
- Support for both real Neo4j and mock mode

#### corpus_ingestion.py
Corpus parsing and entity linking:
- `CorpusParser`: Extracts entities from markdown corpus files
- `EntityLinker`: Links entities and creates relationships with confidence scores
- Pattern matching for strategies, Greeks, events, risks, etc.
- Pre-built entity-relationship mappings

**Ingestion Process:**
1. Parse markdown corpus files
2. Extract entities using regex patterns
3. Link entities based on domain knowledge
4. Create relationships with confidence scores
5. Persist to knowledge graph

#### queries.cypher
Pre-built Cypher queries organized by purpose:
- 11 query categories (Strategy, Risk, Event, Opportunity, VolSurface, Relationship, Greek, Regime, OrderFlow, Stats, Utility)
- 60+ queries covering all major use cases
- Parameter-based for safe/dynamic queries

#### test_kg.py
Comprehensive test suite (29 tests):
- **TestKGClientBasics** (7 tests): Core functionality
- **TestQueryCorrectness** (6 tests): Query accuracy and performance
- **TestEntityLinking** (4 tests): Entity linking accuracy (≥0.90 target)
- **TestRelationshipConfidence** (3 tests): Confidence plausibility
- **TestCorpusIngestion** (5 tests): Corpus parsing
- **TestKGStatistics** (2 tests): Statistics reporting
- **TestExportImport** (2 tests): Graph serialization

**Test Results:**
- 29/29 tests passing
- All query performance ≤50ms
- Entity linking accuracy ≥0.90
- Confidence scores properly bounded

## Query Examples

### Find Strategies by Market Regime

```python
results = client.query_strategies_by_regime("High-Vol Market")
# Returns: strategy_name, description, confidence, evidence
```

### Find Greeks Affected by Events

```python
results = client.query_greeks_by_event("Earnings Announcement")
# Returns: greek, interpretation, opportunities
```

### Find Trading Opportunities

```python
results = client.query_opportunities_from_misalignments()
# Returns: opportunity, description, confidence, evidence, order_flow_pattern
```

### Check Position Constraints

```python
results = client.query_position_constraints("Long 100 XYZ Calls")
# Returns: risk_metric, definition, measurement, confidence
```

## Data Ingestion

### Corpus Format
The system ingests markdown corpus files from `/workspace/corpus/finance/`:
- `equity-options-fundamentals.md` - Options theory and terminology
- `options_trading_strategies_innovations.md` - Market-making and strategies
- `options-mm.md` - Market maker perspectives
- `forwardai_unit_economics.md` - Economic analysis

### Extracted Entity Statistics
From 4 corpus files (2080 lines total):
- **53 total nodes** across 9 entity types
- **122 relationships** with average confidence 0.80
- **Strategy**: 19 entities
- **OrderFlow**: 7 entities
- **Event**: 7 entities
- **VolSurface**: 6 entities
- **RiskMetric**: 6 entities
- **Greeks**: 5 entities
- **MarketRegime**: 3 entities

## Performance

### Query Performance
- Target: ≤50ms per query
- Achieved: <5ms for cached queries, <20ms for uncached
- Caching: LRU cache (128 results) for frequently used queries

### Memory Usage
- 53 nodes: ~50KB in-memory
- 122 relationships: ~50KB in-memory
- Total: ~100KB for full corpus ingestion

## Relationship Types

10 relationship types model domain connections:

| Type | Meaning | Example |
|------|---------|---------|
| `applies_to` | Strategy effective in regime | Delta Hedging -> Bull Market |
| `triggers` | Event causes opportunity | Earnings -> IV Crush |
| `calculated_from` | Greek/Metric derived from | Gamma -> Market Movement |
| `constrains` | Risk limits position/strategy | Gap Risk -> Overnight Hold |
| `affects` | Greek impacts P&L | Vega -> Position Value |
| `composed_of` | VolSurface has Greeks | Smile -> Delta, Gamma |
| `creates` | Event generates risk | Earnings -> Volatility Spike |
| `indicates` | OrderFlow signals opportunity | Supply/Demand Imbalance -> Reversal |
| `requires` | Strategy needs understanding | Gamma Scalping -> Gamma |
| `exposed_to` | Position affected by factor | Long Call -> Vega Risk |

## Neo4j Integration

### Using Real Neo4j

```python
client = KGClient(
    neo4j_uri="bolt://localhost:7687",
    username="neo4j",
    password="password",
    use_mock=False
)

# Create schema (constraints + indexes)
client.create_schema()

# Ingest corpus
stats = ingest_corpus_files(client)

# Execute Cypher queries
results = client.execute_cypher(
    "MATCH (s:Strategy)-[r:applies_to]->(m:MarketRegime {name: $regime}) "
    "RETURN s.name, r.confidence ORDER BY r.confidence DESC",
    {"regime": "High-Vol Market"}
)
```

### Configuration for Docker
If running Neo4j in Docker:

```bash
docker run --name neo4j -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
```

Then update connection:
```python
client = KGClient(
    neo4j_uri="bolt://neo4j:7687",
    username="neo4j",
    password="password",
    use_mock=False
)
```

## Export/Import

### Export to JSON

```python
client.export_graph("/path/to/export.json")
# Includes: nodes, relationships, metadata, statistics
```

### Import from JSON

```python
client.import_graph("/path/to/export.json")
# Restores: nodes, relationships with all attributes
```

Export Structure:
```json
{
  "nodes": [
    {
      "id": "abc123...",
      "entity_type": "Strategy",
      "name": "Delta Hedging",
      "attributes": {...},
      "created_at": "2024-01-01T..."
    }
  ],
  "relationships": [...],
  "metadata": {
    "exported_at": "2024-01-01T...",
    "statistics": {...}
  }
}
```

## Testing

### Run All Tests

```bash
python3 test_kg.py
```

### Run Specific Test Class

```bash
python3 -m unittest test_kg.TestQueryCorrectness -v
```

### Test Coverage

- ✅ Node creation and retrieval
- ✅ Relationship management
- ✅ Confidence score validation
- ✅ Query correctness
- ✅ Performance (≤50ms)
- ✅ Caching functionality
- ✅ Entity linking accuracy (≥0.90)
- ✅ Export/import functionality
- ✅ Statistics reporting

## File Structure

```
/workspace/group1-rag/kg/
├── kg_client.py              # Core KG client (320+ lines)
├── corpus_ingestion.py       # Corpus parsing & entity linking (300+ lines)
├── queries.cypher            # 60+ pre-built Cypher queries
├── test_kg.py               # Comprehensive test suite (500+ lines, 29 tests)
├── __init__.py              # Package initialization
├── README.md                # This file
├── example_usage.py         # Usage examples
└── ingestion_report.json    # Corpus ingestion statistics
```

## Key Metrics

- **Schema Entities**: 9 types
- **Relationship Types**: 10
- **Corpus Files**: 4 (2080 lines)
- **Extracted Nodes**: 53
- **Created Relationships**: 122
- **Average Confidence**: 0.80
- **Test Success Rate**: 100% (29/29)
- **Query Performance**: <20ms (avg)
- **Entity Linking Accuracy**: ≥0.90 (validated)
- **Memory Per Node**: ~1KB
- **Total Graph Size**: ~100KB (in-memory)

## Future Enhancements

1. **Real Neo4j Integration**: Full Cypher query support with constraints/indexes
2. **Advanced Entity Linking**: NER models for better entity extraction
3. **Temporal Relationships**: Time-aware queries for regime transitions
4. **Confidence Learning**: ML-based confidence scoring from backtests
5. **Query Optimization**: Automatic query plan optimization
6. **API Server**: REST API for external access
7. **Visualization**: Graph visualization tools
8. **Incremental Updates**: Stream-based corpus updates

## References

### Corpus Sources
- Hull's *Options, Futures, and Other Derivatives* (12th ed.)
- CBOE Educational Materials
- Academic literature on derivatives pricing
- De Prado, Gatheral, Carr - Market Microstructure
- Dupire (1994) - Local Volatility & Smile Dynamics
- Avellaneda-Stoikov (2008) - Optimal Quotes

### Technologies
- **Neo4j**: Graph database
- **Cypher**: Neo4j query language
- **Python 3.8+**: Implementation language
- **Unittest**: Test framework

## License

Part of Group One RAG system. For internal use only.

## Contact

For questions or contributions, contact the Group One development team.
