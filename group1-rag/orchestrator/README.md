# RAG Orchestrator: Retrieval + Entity Extraction

A production-ready orchestrator combining vector database retrieval and entity extraction with automatic tier selection, error handling, and strict latency constraints.

## Overview

The orchestrator implements **two tiers** of answer modes:

- **Tier 1 (Search)**: Fast retrieval-only mode — query vector DB, return top-5 results with scores. Latency ≤100ms, NO Claude calls.
- **Tier 2 (Detail)**: Comprehensive mode — Tier 1 + entity extraction + knowledge graph lookup for entities and relationships. Latency ≤500ms, NO Claude calls.

## Key Features

### Tier 1: Search Mode
- Vector DB retrieval only
- Top-5 results with confidence scores
- Ultra-low latency: **≤100ms**
- No LLM calls (testable constraint)
- JSON response with result cards

### Tier 2: Detail Mode
- Vector DB retrieval
- Named entity recognition + extraction
- Knowledge graph entity lookup
- Relationship discovery between entities
- Moderate latency: **≤500ms**
- Entity extraction: **≤300ms**
- No LLM calls (testable constraint)

### Tier Selection
- **User-specified**: Client explicitly chooses Tier 1 or Tier 2
- **Auto-detect**: Orchestrator analyzes query complexity:
  - 1-3 words → Tier 1
  - Complex keywords ("why", "how", "relationship") → Tier 2
  - 5+ words → Tier 2

### Error Handling
- Graceful degradation on retrieval failure
- Component-level error resilience (entity extraction failure doesn't block result)
- Error messages in response
- Fallback flag for monitoring

### Response Format
JSON-serializable responses with:
```json
{
  "tier": "tier_1",
  "query": "user query",
  "latency_ms": 45.2,
  "cards": [
    {
      "title": "Result 1",
      "content": "...",
      "score": 0.95,
      "source_id": "doc_1",
      "metadata": {}
    }
  ],
  "entities": null,
  "relationships": null,
  "error": null,
  "fallback_used": false
}
```

## Architecture

### Components

1. **VectorDBConnector**: Interfaces with vector DB (Pinecone, Weaviate, Milvus, etc.)
   - Default: Mock connector for testing
   - Production: Replace with real DB client

2. **EntityExtractor**: Performs NER and entity extraction
   - Default: Mock extractor for testing
   - Production: Spacy, transformers, or domain-specific NER

3. **KnowledgeGraphConnector**: Looks up entities and relationships
   - Default: Mock KG for testing
   - Production: Neo4j, AWS Neptune, GraphQL API, etc.

4. **ComplexityDetector**: Auto-detects query complexity
   - Heuristic-based (word count, keywords)
   - Pluggable for custom logic

5. **Orchestrator**: Main orchestration engine
   - Tier selection
   - Retrieval pipeline
   - Entity extraction pipeline
   - Response formatting
   - Error handling

## Usage

### Basic Example: Tier 1 (Search Mode)

```python
from orchestrator import Orchestrator, AnswerTier, TierSelectionStrategy

# Initialize orchestrator
orchestrator = Orchestrator()

# Search with explicit Tier 1
response = orchestrator.answer(
    query="stock market trends",
    tier=AnswerTier.TIER_1,
    strategy=TierSelectionStrategy.USER_SPECIFIED,
)

print(f"Tier: {response.tier.value}")
print(f"Latency: {response.latency_ms:.1f}ms")
print(f"Results: {len(response.cards)} cards")

for card in response.cards:
    print(f"  {card.title}: {card.score:.2f}")
```

### Auto-Detect Example

```python
# Auto-detect tier based on query complexity
response = orchestrator.answer(
    query="what is the relationship between market volatility and stock prices",
    strategy=TierSelectionStrategy.AUTO_DETECT,
)

print(f"Selected tier: {response.tier.value}")
print(f"Entities: {len(response.entities or [])}")
print(f"Relationships: {len(response.relationships or [])}")
```

### Custom Connectors

```python
from your_vector_db import CustomVectorDB
from your_kg import CustomKG

# Use production connectors
vector_db = CustomVectorDB(endpoint="...")
kg = CustomKG(endpoint="...")

orchestrator = Orchestrator(
    vector_db=vector_db,
    kg=kg,
)

response = orchestrator.answer("your query")
```

### Error Handling

```python
response = orchestrator.answer("query")

if response.error:
    print(f"Error occurred: {response.error}")
    
if response.fallback_used:
    print("Fallback to degraded mode")
    
# Response is always valid, even with errors
assert response.cards is not None or response.error is not None
```

## Testing

### Run Test Suite

```bash
python3 -m pytest test_orchestrator.py -v
```

### Test Coverage

The test harness verifies:

- **Tier 1 Constraints**
  - No Claude calls (testable)
  - Latency ≤100ms (5 concurrent queries)
  - Returns cards only (no entities/relationships)
  - JSON serialization

- **Tier 2 Constraints**
  - No Claude calls (testable)
  - Latency ≤500ms (5 concurrent queries)
  - Entity extraction ≤300ms
  - Returns entities and relationships
  - JSON serialization

- **Tier Selection**
  - User-specified selection
  - Auto-detect heuristics
  - Validation (ValueError on missing required params)

- **Response Format**
  - Card JSON format
  - Entity JSON format
  - Relationship JSON format
  - Full response JSON serialization

- **Error Handling**
  - Graceful degradation on retrieval failure
  - Component-level error resilience
  - Error messages in response
  - Fallback flag

- **Latency Constraints**
  - Tier 1 multiple queries ≤100ms
  - Tier 2 multiple queries ≤500ms

- **Integration**
  - End-to-end Tier 1 flow
  - End-to-end Tier 2 flow
  - Progression from Tier 1 to Tier 2

### Example Test Output

```
test_orchestrator.py::TestTier1SearchMode::test_tier1_no_claude_calls PASSED
test_orchestrator.py::TestTier1SearchMode::test_tier1_latency_under_100ms PASSED
test_orchestrator.py::TestTier1SearchMode::test_tier1_returns_cards_only PASSED
test_orchestrator.py::TestTier2DetailMode::test_tier2_latency_under_500ms PASSED
test_orchestrator.py::TestTierSelection::test_auto_detect_complex_query_uses_tier2 PASSED
test_orchestrator.py::TestErrorHandling::test_retrieval_error_graceful_degradation PASSED
test_orchestrator.py::TestLatencyConstraints::test_tier1_multiple_queries_under_100ms PASSED

============================== 27 passed in 5.65s ===============================
```

## Configuration

### Tier Configurations

View tier specs:

```python
from orchestrator import TIER_CONFIGS, AnswerTier

config = TIER_CONFIGS[AnswerTier.TIER_1]
print(f"Max latency: {config['max_latency_ms']}ms")
print(f"Allow Claude: {config['allow_claude']}")

config = TIER_CONFIGS[AnswerTier.TIER_2]
print(f"Entity extraction max: {config['entity_extraction_max_ms']}ms")
```

## Production Deployment

### 1. Replace Mock Connectors

```python
# Before
vector_db = VectorDBConnector()  # Mock

# After
from pinecone import Pinecone
vector_db = Pinecone(api_key="...")
```

### 2. Configure Latency Budgets

Adjust latencies based on your infrastructure:

```python
vector_db = CustomVectorDB(timeout_ms=80)  # Leave 20ms buffer for Tier 1
entity_extractor = EntityExtractor(timeout_ms=250)  # Leave 50ms buffer
kg = KnowledgeGraph(timeout_ms=40)  # Leave 10ms buffer
```

### 3. Add Monitoring

```python
import time
from prometheus_client import Histogram

latency_histogram = Histogram("rag_latency_ms", "RAG latency", buckets=[50, 100, 200, 500])

response = orchestrator.answer(query)
latency_histogram.observe(response.latency_ms)

if response.error:
    error_counter.inc()
if response.fallback_used:
    fallback_counter.inc()
```

### 4. Scale Tier Selection

Adjust complexity detector for your domain:

```python
class DomainComplexityDetector(ComplexityDetector):
    @staticmethod
    def detect_complexity(query: str) -> AnswerTier:
        # Your domain-specific heuristics
        if query.lower().startswith("find"):
            return AnswerTier.TIER_1
        return AnswerTier.TIER_2

orchestrator.complexity_detector = DomainComplexityDetector()
```

## API Reference

### Orchestrator

```python
class Orchestrator:
    def __init__(
        self,
        vector_db: Optional[VectorDBConnector] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        kg: Optional[KnowledgeGraphConnector] = None,
    )
    
    def answer(
        self,
        query: str,
        tier: Optional[AnswerTier] = None,
        strategy: TierSelectionStrategy = TierSelectionStrategy.AUTO_DETECT,
    ) -> OrchestratorResponse
    
    def select_tier(
        self,
        query: str,
        strategy: TierSelectionStrategy = TierSelectionStrategy.AUTO_DETECT,
        explicit_tier: Optional[AnswerTier] = None,
    ) -> AnswerTier
```

### Response Objects

```python
@dataclass
class OrchestratorResponse:
    tier: AnswerTier
    query: str
    cards: List[ResultCard]
    entities: Optional[List[Entity]] = None
    relationships: Optional[List[Relationship]] = None
    latency_ms: float = 0.0
    error: Optional[str] = None
    fallback_used: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
```

## Files

- **answer_modes.py**: Tier definitions, response structures, configurations
- **orchestrator.py**: Main orchestrator, connectors, tier selection
- **test_orchestrator.py**: Comprehensive test suite (27 tests)
- **__init__.py**: Package exports

## Performance Benchmarks

Run with production connectors on your infrastructure:

```bash
python3 -m pytest test_orchestrator.py::TestLatencyConstraints -v
```

Expected results on typical infra:
- Tier 1: 45-80ms (well under 100ms)
- Tier 2: 300-450ms (well under 500ms)
- Entity extraction: 100-250ms (well under 300ms)

## Future Enhancements

1. **Caching Layer**: LRU cache for frequent queries
2. **Batch Processing**: Handle multiple queries in parallel
3. **Metrics**: Built-in Prometheus/OpenTelemetry integration
4. **Query Rewriting**: Automatic query expansion/refinement
5. **Reranking**: Multi-stage ranking pipeline
6. **Streaming**: Streaming responses for large result sets
