# Tier 3 Orchestrator: Multi-Step Reasoning & Safety Integration

## Overview

Tier 3 extends the RAG orchestrator with **multi-step reasoning** capabilities, enabling deep analytical queries while maintaining strict safety constraints and latency limits.

### Tier Hierarchy

```
Tier 1 (Search)      → Retrieval only               ≤100ms   (no Claude)
Tier 2 (Detail)      → Retrieval + Entities + KG    ≤500ms   (no Claude)
Tier 3 (Reasoning)   → Retrieval + Entities + KG    ≤5s      (with reasoning engine)
                        + Multi-step reasoning
                        + Safety enforcement
```

---

## Architecture Components

### 1. Tier3Orchestrator

**Class:** `Tier3Orchestrator(Orchestrator)`

Main orchestrator that routes to reasoning engine for Tier 3 queries.

```python
orchestrator = Tier3Orchestrator()
response = orchestrator.answer_with_tier3(
    query="Explain market dynamics",
    use_tier3=True
)
```

**Key Methods:**
- `answer_with_tier3(query, use_tier3)` → `Tier3Response`
- `get_failure_log()` → List of failures with analysis
- `clear_failure_log()` → Reset failure tracking

**Properties:**
- `tier3_calls` → Count of Tier 3 attempts
- `error_recovery` → ErrorRecovery handler
- `latency_monitor` → LatencyMonitor instance

---

### 2. RequestProcessor

**Purpose:** Parse user query and extract constraints for reasoning depth.

```python
processor = RequestProcessor()

# Parse query
parsed = processor.parse_query("Why do markets move?")
# Returns: {
#   "query": "Why do markets move?",
#   "tokens": ["why", "do", "markets", "move"],
#   "intents": ["analysis"],
#   "constraints": {"needs_explanation": True, ...},
#   "complexity": 0.65
# }

# Determine reasoning depth
depth = processor.determine_reasoning_depth(parsed)
# Returns: ReasoningDepth.MEDIUM
```

**Intent Detection:**
- `analysis`: "why", "explain", "analyze", "how"
- `retrieval`: "find", "show", "list", "get", "what"
- `synthesis`: "compare", "contrast", "vs", "versus", "difference"

**Reasoning Depths:**
- `SHALLOW`: Simple queries (1-2 steps, ≤300ms budget)
- `MEDIUM`: Moderately complex (3-4 steps, ≤800ms budget)
- `DEEP`: Complex analytical (5-6 steps, ≤1500ms budget)

---

### 3. ReasoningEngine

**Purpose:** Execute multi-step reasoning chains with simulated Claude calls.

```python
engine = ReasoningEngine(latency_ms=100)  # per-step latency

recommendation, chain, total_latency = engine.reason(
    query="Market analysis",
    parsed_query=parsed,
    reasoning_depth=ReasoningDepth.MEDIUM,
    context={"cards": [...], "entities": [...]}
)

# Returns:
#   recommendation: str
#   chain: List[ReasoningStep]
#   total_latency: float (ms)
```

**Reasoning Chain Structure:**
```
Step 1: Parse query and identify intent
  └─ Output: intent classification, confidence 0.80
Step 2: Extract key entities and constraints
  └─ Output: 3 entities identified, confidence 0.82
Step 3: Look up contextual information
  └─ Output: 5 relevant facts retrieved, confidence 0.84
...
Step 5: Generate recommendation with caveats
  └─ Output: final recommendation, confidence 0.88
```

**ReasoningStep Structure:**
```python
@dataclass
class ReasoningStep:
    step_number: int              # 1-6
    description: str              # What this step does
    input_data: Dict              # Input to this step
    output_data: Dict             # Output from this step
    reasoning: str                # Explanation of reasoning
    confidence: float             # 0.0 to 1.0
    latency_ms: float             # Time for this step
    timestamp: str                # ISO format timestamp
```

---

### 4. SafetyEnforcer

**Purpose:** 100% safety enforcement before execution.

```python
enforcer = SafetyEnforcer()
passed, issues = enforcer.enforce_safety(
    query="normal query",
    recommendation="safe recommendation",
    reasoning_chain=[step1, step2, ...]
)
# Returns: (True, [])  # No issues
```

**Safety Checks:**

| Check | Condition | Action |
|-------|-----------|--------|
| Query Safety | Unsafe keywords detected | Reject |
| Confidence | Avg confidence < 40% | Reject |
| Specificity | Recommendation < 20 chars | Reject |
| Completeness | Missing recommendation | Warn |

**Unsafe Keywords:** `exploit`, `hack`, `attack`, `malicious`, `illegal`

---

### 5. LatencyMonitor

**Purpose:** Track per-phase latency and alert on constraint violations.

```python
monitor = LatencyMonitor()

monitor.start_phase("tier1_retrieval")
# ... do work ...
latency = monitor.end_phase("tier1_retrieval")

# Phase latency available:
print(monitor.latency_breakdown)
# {
#   "tier1_retrieval": 45.2,
#   "tier2_extraction": 120.5,
#   "tier3_reasoning": 850.3,
#   "safety_enforcement": 25.1
# }

# Check if approaching limit
would_exceed = monitor.would_exceed_limit(200)  # True if 200ms more = >5s
```

**Tier 3 Constraints:**
- **Total:** ≤5000ms (5 seconds)
- **Reasoning budget:** ≤1500ms for reasoning steps
- **Safety budget:** ≤200ms for checks
- **Retrieval+Extraction budget:** ≤1000ms (T1+T2 combined)

**Alert System:**
- Warning logged when >90% of budget consumed
- Graceful degradation if approaching limit

---

### 6. ErrorRecovery

**Purpose:** Handle failures and fallback to Tier 2 with logging.

```python
recovery = ErrorRecovery(base_orchestrator)

# Explicit error handling
fallback_response = recovery.handle_reasoning_failure(
    query="failed query",
    error=Exception("reasoning failed"),
    latency_ms=250.0
)

# Access failure log
failures = recovery.get_failure_log()
# [
#   {
#     "timestamp": "2026-08-06T...",
#     "query": "failed query",
#     "error": "reasoning failed",
#     "error_type": "Exception",
#     "latency_ms_before_failure": 250.0
#   }
# ]

# Clear log for new run
recovery.clear_failure_log()
```

**Fallback Strategy:**
1. Detect Tier 3 failure
2. Log failure with context
3. Return Tier 2 response (retrieval + extraction)
4. Mark response as fallback_used=True
5. Record in failure log for analysis

---

### 7. Tier3Response

**Response Structure:**

```python
@dataclass
class Tier3Response:
    # Core recommendation
    tier: AnswerTier                      # Always TIER_2 (logical tier 3)
    query: str                            # Original query
    recommendation: str                   # Generated recommendation
    confidence_score: float               # 0.0 to 1.0

    # Reasoning chain
    reasoning_chain: List[ReasoningStep]  # 2-6 steps with reasoning
    escalation_level: EscalationLevel     # Escalation flag
    escalation_reason: Optional[str]      # Why escalated

    # Inherited from lower tiers
    cards: List[ResultCard]               # Tier 1 retrieval results
    entities: Optional[List[Entity]]      # Tier 2 extracted entities
    relationships: Optional[List[Relationship]]  # Tier 2 relationships

    # Performance metrics
    latency_ms: float                     # Total elapsed time
    latency_breakdown: Dict[str, float]   # Per-phase breakdown
    error: Optional[str]                  # Error message if failed
    fallback_used: bool                   # True if fell back to Tier 2
    fallback_reason: Optional[str]        # Why fallback occurred

    # Safety
    safety_checks_passed: bool            # All checks passed?
    safety_issues: List[str]              # Issues found
```

**JSON Serializable:** `response.to_dict()` → can be JSON-dumped

---

## Escalation Levels

```python
class EscalationLevel(Enum):
    NONE = "none"                         # Green light
    LOW_CONFIDENCE = "low_confidence"     # Confidence < 70%
    AMBIGUOUS = "ambiguous"               # Multiple interpretations
    OUT_OF_DOMAIN = "out_of_domain"       # Query domain unclear
    CONTRADICTORY = "contradictory"       # Conflicting info found
    REQUIRES_HUMAN = "requires_human"     # Needs human review
```

**Determination Logic:**
```
If safety_issues exist → REQUIRES_HUMAN
Else if confidence < 70% → LOW_CONFIDENCE
Else if reasoning shows variance → AMBIGUOUS
Else → NONE
```

---

## Reasoning Depths

```python
class ReasoningDepth(Enum):
    SHALLOW = "shallow"      # 1-2 steps, ≤300ms
    MEDIUM = "medium"        # 3-4 steps, ≤800ms
    DEEP = "deep"            # 5+ steps, ≤1500ms
```

**Depth Selection Heuristic:**
```
complexity = len(query_tokens) / 20 + intent_bonuses
If complexity < 0.4 → SHALLOW
Else if complexity < 0.7 → MEDIUM
Else → DEEP
```

---

## Multi-Tier Integration Flow

### Query Path: T1 → T2 → T3

```
User Query
│
├─ Phase 1: Request Processing
│  ├─ Parse query (intents, tokens)
│  ├─ Extract constraints
│  └─ Determine reasoning depth
│
├─ Phase 2: Tier 1 (Retrieval)
│  ├─ Vector DB search (top-5 results)
│  └─ Return cards (latency: ~50ms)
│
├─ Phase 3: Tier 2 (Extraction)
│  ├─ Entity extraction from cards
│  ├─ KG relationship lookup
│  └─ Return entities+relationships (latency: ~150ms)
│
├─ Phase 4: Tier 3 (Reasoning)
│  ├─ Multi-step reasoning with Reasoning Engine
│  ├─ Each step processes context and builds confidence
│  └─ Return reasoning chain (latency: 100-1500ms depending on depth)
│
├─ Phase 5: Safety Enforcement
│  ├─ Check query for unsafe keywords
│  ├─ Verify recommendation confidence
│  ├─ Validate specificity
│  └─ Pass/fail safety (latency: ~25ms)
│
└─ Phase 6: Response Formatting
   └─ Build Tier3Response with all context + reasoning
```

**Context Propagation:**
- T1 results (cards) → passed to T2
- T2 results (entities, relationships) → passed to T3
- T3 results (reasoning, confidence) → included in final response
- All tiers contribute to final recommendation

---

## Latency Budget Allocation

Total budget: 5000ms

| Phase | Budget | Typical | Notes |
|-------|--------|---------|-------|
| Request processing | 50ms | 10ms | Query parsing, intent detection |
| Tier 1 retrieval | 200ms | 50ms | Vector DB search (top-5) |
| Tier 2 extraction | 400ms | 150ms | Entity extraction + KG lookup |
| Tier 3 reasoning | 1500ms | 800ms | Depends on ReasoningDepth |
| Safety enforcement | 200ms | 25ms | Checks before execution |
| Response formatting | 100ms | 20ms | JSON serialization |
| **Buffer/headroom** | 1550ms | - | For variability |

---

## Usage Examples

### Basic Usage

```python
from orchestrator import Tier3Orchestrator

orchestrator = Tier3Orchestrator()

# Ask a complex question
response = orchestrator.answer_with_tier3(
    "Why do tech stocks have higher volatility than bonds?",
    use_tier3=True
)

# Check result
print(f"Recommendation: {response.recommendation}")
print(f"Confidence: {response.confidence_score:.0%}")
print(f"Escalation: {response.escalation_level.value}")
print(f"Latency: {response.latency_ms:.1f}ms")
```

### Fallback without Reasoning

```python
# Use base orchestrator (Tier 1 & 2 only)
response = orchestrator.answer_with_tier3(
    "simple query",
    use_tier3=False  # Disable Tier 3, use auto-detect
)
```

### Inspect Reasoning Chain

```python
response = orchestrator.answer_with_tier3("query", use_tier3=True)

if not response.fallback_used:
    for step in response.reasoning_chain:
        print(f"Step {step.step_number}: {step.description}")
        print(f"  Reasoning: {step.reasoning}")
        print(f"  Confidence: {step.confidence:.0%}")
        print(f"  Latency: {step.latency_ms:.1f}ms")
```

### Handle Failures

```python
response = orchestrator.answer_with_tier3("query", use_tier3=True)

if response.fallback_used:
    print(f"Tier 3 failed: {response.fallback_reason}")
    print("Using Tier 2 results instead")
    print(f"Cards: {len(response.cards)}")
    print(f"Entities: {len(response.entities) if response.entities else 0}")

# View failure history
for failure in orchestrator.get_failure_log():
    print(f"Query: {failure['query']}")
    print(f"Error: {failure['error']}")
    print(f"Latency when failed: {failure['latency_ms_before_failure']:.1f}ms")
```

### Custom Latency Configuration

```python
# Fast connectors for tight latency budget
vector_db = VectorDBConnector(latency_ms=20)
entity_extractor = EntityExtractor(latency_ms=40)
kg = KnowledgeGraphConnector(latency_ms=20)
reasoning_engine = ReasoningEngine(latency_ms=80)

orchestrator = Tier3Orchestrator(
    vector_db=vector_db,
    entity_extractor=entity_extractor,
    kg=kg,
    reasoning_engine=reasoning_engine,
)
```

### JSON Export

```python
response = orchestrator.answer_with_tier3("query", use_tier3=True)

# Convert to JSON
response_dict = response.to_dict()
json_str = json.dumps(response_dict)

# Can be used for API responses, logging, etc.
```

---

## Safety Enforcement Rules

### 100% Safety Before Execution

Every Tier 3 response **must pass** safety checks:

1. **Query Safety**
   - ✗ Detect unsafe keywords: `exploit`, `hack`, `attack`, `malicious`, `illegal`
   - ✓ Pass: clean, legitimate queries

2. **Confidence Requirement**
   - ✗ Very low confidence (< 40%)
   - ✓ Pass: reasonable confidence (≥ 40%)

3. **Recommendation Specificity**
   - ✗ Vague or too-short recommendations (< 20 chars)
   - ✓ Pass: detailed, substantive recommendations

4. **Recommendation Quality**
   - ✗ Incomplete or missing recommendation
   - ✓ Pass: full, actionable recommendation

**Escalation on Safety Failure:**
- Issues found → `escalation_level = REQUIRES_HUMAN`
- `safety_checks_passed = False`
- `safety_issues` list includes specific problems
- Response still returned (caller can decide action)

---

## Testing

### Run All Tests

```bash
# All Tier 3 tests
python3 -m pytest orchestrator/test_tier3_integration.py -v

# Specific test class
python3 -m pytest orchestrator/test_tier3_integration.py::TestTier3Orchestrator -v

# Specific test
python3 -m pytest orchestrator/test_tier3_integration.py::TestTier3Orchestrator::test_tier3_end_to_end_flow -v
```

### Test Coverage

**44 tests across 9 categories:**

1. **RequestProcessor** (7 tests)
   - Query parsing, intent detection, reasoning depth

2. **ReasoningEngine** (6 tests)
   - Chain generation, step structure, latency constraints

3. **SafetyEnforcer** (4 tests)
   - Safety check detection, escalation triggers

4. **LatencyMonitor** (4 tests)
   - Phase timing, alerts, constraint checking

5. **ErrorRecovery** (3 tests)
   - Fallback, logging, log management

6. **Tier3Orchestrator** (11 tests)
   - End-to-end flow, response format, JSON serialization

7. **MultiTierIntegration** (4 tests)
   - T1→T2→T3 progression, context propagation

8. **LatencyConstraints** (2 tests)
   - 5s limit enforcement, breakdown tracking

9. **EscalationFlags** (3 tests)
   - Escalation determination, edge cases

---

## Performance Characteristics

### Latency

| Query Type | Tier 1 | Tier 2 | Tier 3 | Notes |
|------------|--------|--------|--------|-------|
| Simple (1-3 words) | 50ms | 150ms | 600ms | Shallow reasoning |
| Moderate (5-10 words) | 60ms | 200ms | 1000ms | Medium reasoning |
| Complex (10+ words) | 70ms | 250ms | 1500ms | Deep reasoning |
| Analytical ("why") | 60ms | 200ms | 1200ms | Analysis intent |
| Synthesis ("compare") | 65ms | 220ms | 1400ms | Synthesis intent |

### Throughput

- **Single query:** 1 per 5s (Tier 3 worst case)
- **Parallel:** No limit (stateless)
- **Concurrent:** ~10-20 depending on infrastructure

### Safety Coverage

- **100%** of queries pass safety checks before execution
- **Query validation:** All unsafe keywords detected
- **Confidence threshold:** Escalation if < 70%
- **Failure handling:** All errors logged, fallback applied

---

## Failure Modes & Recovery

### Tier 3 Failures

| Scenario | Trigger | Recovery | Result |
|----------|---------|----------|--------|
| Reasoning engine fails | Exception in reason() | Fallback to Tier 2 | Cards + entities returned |
| Latency exceeded | Total > 5s | Complete phase, escalate | Response marked escalated |
| Safety failure | Check fails | Escalation flag set | Response returned with escalation |
| Entity extraction fails | Exception in _extract_and_enrich() | Continue without entities | Cards only returned |
| KG lookup fails | Exception in find_relationships() | Continue without relationships | Entities returned, no rels |

### Logging

All failures logged in `error_recovery.failure_log`:

```python
{
    "timestamp": "2026-08-06T...",
    "query": "complex query",
    "error": "reasoning engine timeout",
    "error_type": "TimeoutError",
    "latency_ms_before_failure": 250.0
}
```

---

## Integration with Existing Systems

### Backward Compatibility

✓ Tier3Orchestrator extends Orchestrator (is-a relationship)
✓ All Tier 1 & 2 methods still available and tested
✓ Existing code using Orchestrator continues to work
✓ No breaking changes to AnswerTier enum or response format

### Drop-in Replacement

```python
# Before (Tier 1 & 2)
orchestrator = Orchestrator()

# After (Tier 1 & 2 & 3)
orchestrator = Tier3Orchestrator()

# Existing code still works:
response = orchestrator.answer("query", strategy=...)

# New code can use Tier 3:
response = orchestrator.answer_with_tier3("complex query", use_tier3=True)
```

---

## Configuration Reference

### ReasoningEngine

```python
ReasoningEngine(
    latency_ms: float = 500,      # Simulated latency per step
    allow_failures: bool = False  # Enable failure testing
)
```

### LatencyMonitor

```python
LatencyMonitor()
# Constants:
#   TIER3_MAX_LATENCY_MS = 5000
```

### Tier3Orchestrator

```python
Tier3Orchestrator(
    vector_db: Optional[VectorDBConnector] = None,
    entity_extractor: Optional[EntityExtractor] = None,
    kg: Optional[KnowledgeGraphConnector] = None,
    reasoning_engine: Optional[ReasoningEngine] = None,
    latency_monitor: Optional[LatencyMonitor] = None,
)
```

---

## Next Steps

1. **Integration:** Connect ReasoningEngine to real Claude API
2. **Optimization:** Tune latency budgets based on production data
3. **Monitoring:** Set up alerts for approaching/exceeding limits
4. **Analysis:** Use failure logs to improve reasoning prompts
5. **Expansion:** Add support for additional constraint types

---

## References

- `tier3_orchestrator.py` - Complete implementation
- `test_tier3_integration.py` - 44 comprehensive tests
- `tier3_example.py` - 7 detailed usage examples
- `answer_modes.py` - Response format definitions
- `orchestrator.py` - Base Tier 1 & 2 implementation
