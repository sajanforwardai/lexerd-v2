# LCMV-23: Stage 2 — BLS Employment Data Integration

**Epic:** Stage 2 Data Integration Pipeline  
**Stage:** 2 — Data Foundation  
**Estimate:** 12 hours  
**Status:** To Do  
**Priority:** High  
**Owner:** [Assigned Developer]  

---

## Executive Summary

Integrate Bureau of Labor Statistics (BLS) employment data API to replace assumed employment growth rates with real labor market signals. This is a **critical Market score signal** (25% of market fundamentals). Currently, the scoring engine uses default/assumed values; LCMV-23 makes employment real data, improving scoring accuracy by 15-20% and enabling evidence-based market selection.

**Impact:**
- Replaces 1-2 hours of manual MSA research with automated data fetch
- Employment growth signals directly affect Market score (25 points out of 100)
- Unlocks downstream pipeline for LCMV-24 (Census/Zillow) and LCMV-26 (batch scoring)
- Enables historical backtesting of employment-based sourcing thesis

---

## Problem Statement

### Current State (Without LCMV-23)
```
PropertyProfile {
  city: "Jacksonville",
  state: "FL",
  employment_growth_yoy: None  # ❌ Assumed 2.5% default
}

MarketScorer.score() → employment_growth_yoy = None → default 0 points
```

**Consequences:**
- No differentiation between 1.5% and 4% employment growth markets
- Manual lookup of BLS data required for each property evaluation
- Impossible to backtest "employment growth" as a sourcing signal
- Decision-makers can't see which markets are firing vs. cooling

### Target State (With LCMV-23)
```
PropertyProfile {
  city: "Jacksonville",
  state: "FL",
  employment_growth_yoy: 0.0342  # ✅ Real BLS data
}

MarketScorer.score() → employment_growth_yoy = 0.0342 → 22.5/25 points
```

**Benefits:**
- Evidence-based market scoring (no guessing)
- <2 second enrichment latency per property
- Transparent data lineage (which BLS series, which date, cache age)
- Batch processing enables 1000s of properties in <30 seconds

---

## Technical Architecture

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      PropertyProfile                         │
│  city="Jacksonville", state="FL", employment_growth_yoy=None│
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────┐
          │ employment_enrichment.py │
          │ enrich_property()        │
          └────────────┬─────────────┘
                       │
                       ▼
          ┌──────────────────────────────┐
          │ BLSClient.get_msa_by_city()  │
          │ "Jacksonville", "FL" → "12220"
          └────────────┬─────────────────┘
                       │
                       ▼
       ┌────────────────────────────────────────┐
       │ BLSClient.fetch_employment_growth()    │
       │ Query BLS API                          │
       │ Series ID: LAUS1222003                 │
       │ Years: 2022-2024                       │
       └────────────┬─────────────────────────┘
                    │
                    ├─→ Check cache (24h TTL)
                    │   ├─→ Valid? Return cached
                    │   └─→ Expired? Fetch fresh
                    │
                    ├─→ Rate limit (120 req/min)
                    │
                    └─→ POST https://api.bls.gov/publicAPI/v2/timeseries/
                        {
                          "seriesid": ["LAUS1222003"],
                          "startyear": 2022,
                          "endyear": 2024,
                          "registrationkey": "${BLS_API_KEY}"
                        }
                        │
                        ├─→ Parse response → latest 2024 value
                        ├─→ Parse response → latest 2023 value
                        ├─→ Calculate YoY: (2024 - 2023) / 2023
                        ├─→ Cache result + timestamp
                        └─→ Return {"employment_growth_yoy": 0.0342}
                            │
                            ▼
       ┌────────────────────────────────────────┐
       │ PropertyProfile (enriched)            │
       │ employment_growth_yoy: 0.0342         │
       │ Ready for scoring                     │
       └────────────────────────────────────────┘
```

### Module Structure

```
calibration/
├── data/
│   ├── __init__.py
│   ├── bls_client.py                  # ← LCMV-23.1
│   │   └── BLSClient class
│   │       ├── fetch_employment_growth(msa_code) → Dict
│   │       ├── get_msa_by_city_state(city, state) → str
│   │       ├── refresh_cache()
│   │       ├── get_cache_age(msa_code) → int
│   │       └── [Private] _load_cache(), _save_cache(), _is_cache_valid()
│   │
│   └── employment_enrichment.py        # ← LCMV-23.2
│       ├── enrich_property_with_employment(prop, client) → PropertyProfile
│       ├── enrich_batch(properties, client) → List[PropertyProfile]
│       └── estimate_msa_from_property(prop) → Optional[str]
│
├── tests/
│   ├── test_bls_integration.py         # ← LCMV-23.3
│   │   ├── TestBLSClient (11 tests, >95% coverage)
│   │   ├── TestEmploymentEnrichment (5 tests)
│   │   └── TestIntegrationWithScoring (2 tests)
│   │
│   └── conftest.py                    # (fixtures if needed)
│
└── docs/
    └── BLS_INTEGRATION.md              # ← LCMV-23.4
        ├── API Key Setup
        ├── MSA Code Reference
        ├── Troubleshooting
        └── Data Refresh Schedule
```

---

## Sub-Tickets (Breakdown)

### LCMV-23.1: BLS API Client Implementation
**Estimate:** 4 hours  
**Type:** Task  
**Acceptance Criteria:**
- [ ] `calibration/data/bls_client.py` created with BLSClient class
- [ ] Implements `fetch_employment_growth(msa_code: str) → Dict[str, float]`
- [ ] Implements `get_msa_by_city_state(city: str, state: str) → Optional[str]`
- [ ] Implements `refresh_cache()` and `get_cache_age(msa_code)`
- [ ] MSA code mapping covers 20+ secondary markets (Jacksonville, Fargo, Austin, etc.)
- [ ] 24-hour cache TTL with disk persistence (~/.bls_cache.json)
- [ ] Rate limiting: 120 requests/minute (0.5s delay between calls)
- [ ] Error handling: Network timeouts, rate limits, missing data → graceful fallback
- [ ] All functions documented with docstrings
- [ ] No hardcoded API keys (reads from BLS_API_KEY env var)

**Key Implementation Details:**

**BLS API Endpoint:**
```
POST https://api.bls.gov/publicAPI/v2/timeseries/
Content-Type: application/json

Request Payload:
{
  "seriesid": ["LAUS1222003"],      # L=Labor, A=All, U=Unemployment, S=State/Metro
  "startyear": 2022,
  "endyear": 2024,
  "registrationkey": "${BLS_API_KEY}"
}

Response:
{
  "status": "REQUEST_SUCCEEDED",
  "Results": {
    "series": [
      {
        "seriesID": "LAUS1222003",
        "data": [
          {"year": "2024", "period": "M03", "value": "1256789", "latest": true},
          {"year": "2024", "period": "M02", "value": "1245678"},
          {"year": "2023", "period": "M03", "value": "1215000"}
        ]
      }
    ]
  }
}
```

**MSA Code Mapping (Minimum 20 markets):**
```python
MSA_CODES = {
    ("Jacksonville", "FL"): "12220",
    ("Fargo", "ND"): "23620",
    ("Austin", "TX"): "12420",
    ("Atlanta", "GA"): "12060",
    ("Miami", "FL"): "33124",
    ("Tampa", "FL"): "45300",
    ("Orlando", "FL"): "36100",
    ("Charlotte", "NC"): "16740",
    ("Raleigh", "NC"): "39580",
    ("Nashville", "TN"): "34980",
    ("Memphis", "TN"): "32820",
    ("Phoenix", "AZ"): "38060",
    ("Denver", "CO"): "19740",
    ("Dallas", "TX"): "19100",
    ("Houston", "TX"): "26420",
    ("San Antonio", "TX"): "41700",
    ("Kansas City", "MO"): "28140",
    ("New Orleans", "LA"): "35380",
    ("Birmingham", "AL"): "12260",
    ("Mobile", "AL"): "33660",
}
```

**Cache Structure:**
```json
{
  "12220": {
    "data": {
      "employment_growth_yoy": 0.0342
    },
    "timestamp": 1722472800.0,
    "series_id": "LAUS1222003"
  },
  "23620": {
    "data": {
      "employment_growth_yoy": 0.0156
    },
    "timestamp": 1722472800.0,
    "series_id": "LAUS2362003"
  }
}
```

**Error Handling Matrix:**

| Error | BLS Response | Handling |
|-------|---|---|
| Invalid MSA | 400 / NOT_PROCESSED | Return None, log warning |
| Rate limited | 429 | Return None after backoff attempt |
| Network timeout | Exception | Return None, log error |
| Missing data in response | Empty array | Return None, log warning |
| Invalid value field | Non-numeric | Skip record, try next |
| Both years missing | No 2023 or 2024 data | Return None |

---

### LCMV-23.2: Employment Enrichment Module
**Estimate:** 3 hours  
**Type:** Task  
**Acceptance Criteria:**
- [ ] `calibration/data/employment_enrichment.py` created
- [ ] Implements `enrich_property_with_employment(prop, client) → PropertyProfile`
- [ ] Implements `enrich_batch(properties, client) → List[PropertyProfile]`
- [ ] Implements `estimate_msa_from_property(prop) → Optional[str]`
- [ ] Enriches 100 properties in <2 seconds (benchmark)
- [ ] Does not modify original PropertyProfile (returns new copy)
- [ ] Logs enrichment results (property_id, growth rate, data freshness)
- [ ] Handles missing city/state gracefully
- [ ] Handles already-enriched properties (skip if employment_growth_yoy is not None)
- [ ] Error recovery: failed enrichments return original property unmodified

**Function Signatures:**

```python
def enrich_property_with_employment(
    prop: PropertyProfile,
    bls_client: BLSClient,
    confidence_threshold: float = 0.0,
) -> PropertyProfile:
    """
    Enrich single property with employment data.
    
    Args:
        prop: PropertyProfile to enrich
        bls_client: BLSClient instance
        confidence_threshold: Not currently used; reserved for future confidence scoring
    
    Returns:
        New PropertyProfile with employment_growth_yoy populated
    
    Flow:
    1. Skip if already enriched (employment_growth_yoy is not None)
    2. Skip if missing city or state
    3. Get MSA code via bls_client.get_msa_by_city_state()
    4. Fetch employment growth via bls_client.fetch_employment_growth()
    5. Return enriched copy or original if no data found
    
    Logging:
    - INFO: Successful enrichment (property_id, growth_rate, cache_age)
    - DEBUG: Skipped (missing MSA, already enriched)
    - WARNING: Failed fetch (no BLS data available)
    - ERROR: Unexpected exceptions
    """

def enrich_batch(
    properties: List[PropertyProfile],
    bls_client: BLSClient,
    confidence_threshold: float = 0.0,
) -> List[PropertyProfile]:
    """
    Enrich multiple properties in parallel-safe manner.
    
    Args:
        properties: List of PropertyProfile objects
        bls_client: BLSClient instance
        confidence_threshold: Minimum confidence threshold
    
    Returns:
        List of enriched PropertyProfile objects (same length as input)
    
    Performance:
    - 100 properties in <2 seconds (including API calls + caching)
    - Respects BLS rate limits (120 req/minute)
    - Uses cache to minimize API calls
    
    Error Handling:
    - Individual property failures don't halt batch
    - Failed properties returned unmodified
    - All errors logged, batch continues
    
    Logging:
    - INFO: Batch completion (total count)
    - Per-property logs: see enrich_property_with_employment()
    """

def estimate_msa_from_property(prop: PropertyProfile) -> Optional[str]:
    """
    Estimate MSA code from property location.
    
    Args:
        prop: PropertyProfile with city/state
    
    Returns:
        MSA code or None if not found in MSA_CODES
    
    Note:
        This is a simple lookup; production could use fuzzy matching
        for properties with misspelled cities or alternate names.
    """
```

---

### LCMV-23.3: Comprehensive Unit Tests
**Estimate:** 3 hours  
**Type:** Task  
**Acceptance Criteria:**
- [ ] `calibration/tests/test_bls_integration.py` created
- [ ] Minimum 18 test cases covering:
  - BLSClient: 11 tests (see below)
  - EmploymentEnrichment: 5 tests
  - Integration with MarketScorer: 2 tests
- [ ] Test coverage: >95% on bls_client.py, >90% on employment_enrichment.py
- [ ] All tests use mocking (no real API calls)
- [ ] Fixtures for sample properties, MSA codes, mock responses
- [ ] Parametrized tests for multiple MSA codes
- [ ] Performance benchmarks (batch of 100 in <2 seconds)
- [ ] All tests pass (pytest -v calibration/tests/test_bls_integration.py)

**Test Cases:**

**BLSClient Tests (11):**
1. `test_fetch_employment_growth_success` — Valid MSA returns Dict with employment_growth_yoy
2. `test_fetch_employment_growth_missing_msa` — Invalid MSA returns None (no crash)
3. `test_cache_expiration` — Expired cache (>24h) is refreshed on next fetch
4. `test_cache_valid` — Valid cache (<24h) is used without API call
5. `test_rate_limiting` — API 429 response handled gracefully
6. `test_network_timeout` — Connection timeout returns None, logs error
7. `test_batch_enrichment_performance` — 100 properties enriched in <2 seconds
8. `test_msa_mapping_accuracy` — City/state maps to correct BLS code
   - Jacksonville, FL → 12220
   - Fargo, ND → 23620
   - Austin, TX → 12420
9. `test_cache_age_tracking` — get_cache_age() returns correct minutes or None
10. `test_no_hardcoded_keys` — API key from env var (BLS_API_KEY), not hardcoded
11. `test_error_handling_missing_data` — Malformed BLS response handled gracefully

**EmploymentEnrichment Tests (5):**
1. `test_enrich_property_single` — Single property enriched correctly
2. `test_enrich_batch_multiple` — Batch of 10+ properties enriched without errors
3. `test_enrich_property_already_enriched` — Skip if employment_growth_yoy already set
4. `test_enrich_handles_missing_city_state` — Missing location doesn't crash
5. `test_enrich_preserves_original` — Original PropertyProfile not modified

**Integration Tests (2):**
1. `test_enriched_employment_data_feeds_scorer` — MarketScorer accepts enriched data
2. `test_end_to_end_property_pipeline` — Property → BLS client → enriched → scored

---

### LCMV-23.4: Documentation & Setup Guide
**Estimate:** 2 hours  
**Type:** Task  
**Deliverable:** `calibration/docs/BLS_INTEGRATION.md`
**Acceptance Criteria:**
- [ ] Setup instructions for BLS API key
- [ ] MSA code reference (all 20+ markets)
- [ ] Data refresh schedule and monitoring
- [ ] Troubleshooting guide (common errors)
- [ ] Performance benchmarks (latency, cache hits, API calls)
- [ ] Security notes (API key handling, cache file permissions)
- [ ] Integration points with downstream modules

**Document Outline:**

```markdown
# BLS Integration Setup & Reference

## 1. API Key Setup
- How to register at bls.gov
- Generating API key
- Setting BLS_API_KEY environment variable
- Verifying access with test call

## 2. MSA Code Reference
- Table of all 20+ supported markets
- How to add new MSA code
- BLS series ID format (LAUS{code}03)

## 3. Data Refresh Schedule
- When cache refreshes (24h TTL)
- Manual refresh via refresh_cache()
- Monitoring cache age for stale data

## 4. Troubleshooting
- "ValueError: MSA not found" → Add to MSA_CODES
- "Connection timeout" → Check network, retry
- "Rate limited (429)" → Wait, client handles backoff
- "Insufficient data for YoY" → Wait for next month's data release

## 5. Performance Baseline
- Single property enrichment: ~200ms (with network)
- Batch 100 properties: <2 seconds (cached, 1-2 API calls)
- Cache hit rate: 95%+ (24h TTL)

## 6. Security
- API key never logged (stripped from debug output)
- Cache file: ~/.bls_cache.json (user-readable only)
- No credentials in source code

## 7. Integration
- Consumed by: employment_enrichment.enrich_batch()
- Feeds: MarketScorer (employment_growth signal)
- Upstream: LCMV-24 (Census/Zillow use same enrichment pattern)
```

---

## Acceptance Criteria (LCMV-23 Overall)

### Functionality ✅
- [ ] Fetch employment growth for 50+ MSAs without errors
- [ ] Cache results with 24-hour TTL (disk-persisted)
- [ ] Enrich 100 properties in <2 seconds total
- [ ] Handle API failures gracefully (timeout, rate limit, network error)
- [ ] Support manual cache refresh via refresh_cache()

### Code Quality ✅
- [ ] All functions documented with docstrings (type hints + examples)
- [ ] No hardcoded API keys (reads from BLS_API_KEY env var)
- [ ] Type hints on all function signatures
- [ ] Logging at appropriate levels (INFO, DEBUG, WARNING, ERROR)
- [ ] Follows Lexerd code style (PEP 8, 88-char lines)

### Testing ✅
- [ ] 18+ unit tests covering happy path, errors, performance
- [ ] Test coverage >95% on bls_client.py, >90% on enrichment
- [ ] All mocked API calls (no real BLS API hits in test suite)
- [ ] Performance benchmark: 100 properties in <2 seconds
- [ ] pytest -v passes with all green

### Documentation ✅
- [ ] BLS_INTEGRATION.md: setup, MSA reference, troubleshooting
- [ ] Inline docstrings on all public functions
- [ ] README integration point documented
- [ ] Error messages are user-friendly and actionable

---

## Integration Points

### Upstream Dependencies
- `PropertyProfile` from `calibration/models/thesis.py`
- `ThesisConfig` for default values
- Environment variable: `BLS_API_KEY`

### Downstream Consumers
- **LCMV-24 Census/Zillow Integration** — Uses same enrichment pattern
- **LCMV-26 Data Pipeline** — Orchestrates BLS enrichment for batch scoring
- **MarketScorer** — Consumes employment_growth_yoy for Market score calculation

### Data Flow
```
CSV Input (properties.csv)
    ↓
calibration/ui/app.py (Streamlit)
    ↓
enrich_batch([properties], bls_client)
    ↓
BLSClient.fetch_employment_growth()
    ↓
MarketScorer.score()
    ↓
CSV Output (scored_properties.csv)
```

---

## Success Metrics

| Metric | Target | Verification |
|--------|--------|---|
| MSA coverage | 20+ markets | MSA_CODES dict has 20+ entries |
| API latency | <100ms avg (cached) | Load test 100 properties |
| Cache hit rate | 95%+ | Monitor cache_age() logs |
| Accuracy | Within 10bps of BLS published | Sample 5 MSAs vs. BLS website |
| Uptime | 99.9% (with fallback) | Error logs show graceful handling |
| Code coverage | >95% bls_client.py | pytest --cov report |
| Test count | 18+ tests | pytest collection count |

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|---|---|---|
| BLS API downtime | Low | Medium | Cache strategy, fallback to default |
| MSA code mismatches | Medium | Low | Maintain accurate mapping, support additions |
| Rate limiting | Low | Low | Client implements 0.5s delay, respects limits |
| Stale data | Low | Low | Document refresh schedule, log cache age |
| Network timeouts | Medium | Low | Timeout handling, retry logic, logged failures |

---

## Timeline

- **Day 1 (4h):** LCMV-23.1 BLS client implementation + testing
- **Day 2 (3h):** LCMV-23.2 Enrichment module
- **Day 2 (3h):** LCMV-23.3 Unit tests (parallel to 23.2 if possible)
- **Day 3 (2h):** LCMV-23.4 Documentation + final review

**Total: 12 hours (1.5 work days)**

---

## Definition of Done

- ✅ All 4 sub-tickets completed
- ✅ pytest calibration/tests/test_bls_integration.py → all green
- ✅ Coverage report shows >95% on bls_client.py
- ✅ BLS_INTEGRATION.md complete and reviewed
- ✅ Code review: one peer reviewer approves (LCMV code style, no security issues)
- ✅ Integrated into Streamlit app (sample usage in ui/app.py)
- ✅ Jira ticket transitioned to Done

---

## References

- BLS Public API: https://www.bls.gov/developers/
- Series ID Format: https://www.bls.gov/help/hlp_faq.htm
- Lexerd Thesis: `/workspace/Lexerd Capital Management/calibration/docs/LEXERD_THESIS.md`
- PropertyProfile Structure: `calibration/models/thesis.py`
- MarketScorer: `calibration/models/scorers.py`

---

*Created: 2026-07-31 | Last Updated: 2026-07-31 | Owner: [TBD]*
