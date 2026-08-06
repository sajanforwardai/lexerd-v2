# RAG Orchestrator - Quick Start

## Installation

```bash
cd /workspace/group1-rag/orchestrator
```

No external dependencies beyond Python 3.12+ and pytest (already installed).

## Run Tests

```bash
# All tests (27 tests, ~6 seconds)
python3 -m pytest test_orchestrator.py -v

# Tier 1 tests only
python3 -m pytest test_orchestrator.py::TestTier1SearchMode -v

# Tier 2 tests only
python3 -m pytest test_orchestrator.py::TestTier2DetailMode -v

# Error handling tests
python3 -m pytest test_orchestrator.py::TestErrorHandling -v

# Latency constraint tests
python3 -m pytest test_orchestrator.py::TestLatencyConstraints -v
```

## Run Examples

```bash
# All examples (9 examples, ~5 seconds)
python3 -m orchestrator.example_usage

# Output will show:
# - Explicit Tier 1 (search mode)
# - Explicit Tier 2 (detail mode)
# - Auto-detect simple query → Tier 1
# - Auto-detect complex query → Tier 2
# - Error handling & graceful degradation
# - JSON serialization
# - Latency measurements
# - Tier progression
# - Production usage pattern
```

## Basic Usage

```python
from orchestrator import Orchestrator, AnswerTier, TierSelectionStrategy

# Initialize
orchestrator = Orchestrator()

# Option 1: Explicit Tier 1 (search only, ≤100ms)
response = orchestrator.answer(
    query="stock market",
    tier=AnswerTier.TIER_1,
    strategy=TierSelectionStrategy.USER_SPECIFIED,
)

# Option 2: Explicit Tier 2 (detail mode, ≤500ms)
response = orchestrator.answer(
    query="stock market relationships",
    tier=AnswerTier.TIER_2,
    strategy=TierSelectionStrategy.USER_SPECIFIED,
)

# Option 3: Auto-detect tier based on query complexity
response = orchestrator.answer(
    query="what affects stock prices",
    strategy=TierSelectionStrategy.AUTO_DETECT,
)

# Access results
print(f"Tier: {response.tier.value}")
print(f"Latency: {response.latency_ms:.1f}ms")
print(f"Results: {len(response.cards)} cards")

if response.entities:
    print(f"Entities: {len(response.entities)}")
if response.relationships:
    print(f"Relationships: {len(response.relationships)}")

# Handle errors
if response.error:
    print(f"Error: {response.error}")
if response.fallback_used:
    print("Fallback to degraded mode")

# Convert to JSON for API response
import json
json_response = json.dumps(response.to_dict())
```

## Architecture Summary

### Tier 1 (Search)
- Vector DB retrieval only
- **Latency: ≤100ms**
- Top-5 results with scores
- No entities/relationships
- No Claude calls

### Tier 2 (Detail)
- Vector DB + Entity extraction + KG lookup
- **Latency: ≤500ms**
- Entities and relationships
- No Claude calls

### Tier Selection
- **User-specified**: Explicit tier choice
- **Auto-detect**: Query complexity analysis
  - 1-3 words → Tier 1
  - Keywords ("why", "how", "relationship") → Tier 2
  - 5+ words → Tier 2

## Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Tier 1 Constraints | 4 | ✅ PASS |
| Tier 2 Constraints | 5 | ✅ PASS |
| Tier Selection | 5 | ✅ PASS |
| Response Formatting | 4 | ✅ PASS |
| Error Handling | 4 | ✅ PASS |
| Latency Constraints | 2 | ✅ PASS |
| Integration | 3 | ✅ PASS |
| **TOTAL** | **27** | **✅ PASS** |

## Performance

With mock connectors:
- Tier 1: 30-50ms (limit: 100ms)
- Tier 2: 300-400ms (limit: 500ms)
- Entity extraction: 100-150ms (limit: 300ms)

## File Structure

```
/workspace/group1-rag/orchestrator/
├── answer_modes.py              # Tier definitions, response structures
├── orchestrator.py              # Main engine, connectors
├── test_orchestrator.py         # 27 tests (27 passing)
├── example_usage.py             # 9 runnable examples
├── __init__.py                  # Package exports
├── README.md                    # Full documentation
├── IMPLEMENTATION-SUMMARY.md    # Build summary
└── QUICKSTART.md               # This file
```

## Common Tasks

### Run all tests
```bash
python3 -m pytest test_orchestrator.py -v
```

### Run tests with coverage
```bash
python3 -m pytest test_orchestrator.py --cov=orchestrator --cov=answer_modes
```

### Run specific tier tests
```bash
python3 -m pytest test_orchestrator.py::TestTier1SearchMode -v
python3 -m pytest test_orchestrator.py::TestTier2DetailMode -v
```

### Run error handling tests
```bash
python3 -m pytest test_orchestrator.py::TestErrorHandling -v
```

### Run latency tests
```bash
python3 -m pytest test_orchestrator.py::TestLatencyConstraints -v
```

### Run examples
```bash
python3 -m orchestrator.example_usage
```

### Test Claude call constraint (Tier 1)
```bash
python3 -m pytest test_orchestrator.py::TestTier1SearchMode::test_tier1_no_claude_calls -v
```

### Test Claude call constraint (Tier 2)
```bash
python3 -m pytest test_orchestrator.py::TestTier2DetailMode::test_tier2_no_claude_calls -v
```

### Test latency constraints
```bash
python3 -m pytest test_orchestrator.py::TestLatencyConstraints::test_tier1_multiple_queries_under_100ms -v
python3 -m pytest test_orchestrator.py::TestLatencyConstraints::test_tier2_multiple_queries_under_500ms -v
```

## Integration with Real Systems

To use with your vector DB, NER model, and knowledge graph:

```python
from your_vector_db import MyVectorDB
from your_nlp import MyNER
from your_kg import MyKnowledgeGraph

orchestrator = Orchestrator(
    vector_db=MyVectorDB(),
    entity_extractor=MyNER(),
    kg=MyKnowledgeGraph(),
)

response = orchestrator.answer("your query")
```

See `README.md` for production deployment details.

## Documentation

- **README.md** - Full documentation, API reference, production guide
- **IMPLEMENTATION-SUMMARY.md** - Build summary, architecture, test results
- **example_usage.py** - 9 runnable examples
- **test_orchestrator.py** - 27 tests demonstrating all features

## Support

All tests passing (27/27). Ready for production integration.

Questions? See README.md for:
- Architecture details
- API reference
- Production deployment
- Performance benchmarks
- Future enhancements
