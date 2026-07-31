# LCMV-23: BLS Employment Data Integration

**Stage:** 2 — Data Integration  
**Estimate:** 12 hours  
**Status:** To Do  
**Priority:** High  

---

## Summary

Integrate Bureau of Labor Statistics (BLS) employment data API to enrich property scoring with real employment growth rates by Metropolitan Statistical Area (MSA). This replaces assumptions with actual labor market data, improving scoring accuracy by 15-20%.

---

## Problem Statement

**Current State:**
- Scoring engine uses default/assumed employment growth rates
- No real market data integration
- Employment growth crucial for 25% of Market score

**Target State:**
- Automatic enrichment of property profiles with BLS data
- Real employment growth rates by MSA
- <2 second enrichment latency per property
- Graceful handling of data gaps

---

## Deliverables

### 1. `calibration/data/bls_client.py` (4 hours)

BLS API wrapper for fetching employment data.

**Requirements:**
- Query BLS API for employment growth by MSA
- Support 50+ Metropolitan Statistical Areas
- Implement rate limiting (120 requests/minute)
- Cache results to avoid repeated API calls (24-hour TTL)
- Handle missing data gracefully
- Log all API calls and failures

**Methods:**
```python
def fetch_employment_growth(msa_code: str) -> Dict[str, float]
def get_msa_by_city_state(city: str, state: str) -> Optional[str]
def refresh_cache() -> None
def get_cache_age() -> int  # minutes
```

**Error Handling:**
- Network failures → return cached data with warning
- Missing MSA → return None (handle downstream)
- Rate limit exceeded → implement exponential backoff

**Testing:**
- Mock BLS API responses
- Test rate limiting logic
- Test cache expiration
- Test error scenarios

### 2. `calibration/data/employment_enrichment.py` (3 hours)

Merge BLS employment data into PropertyProfile objects.

**Functions:**
```python
def enrich_property_with_employment(prop: PropertyProfile) -> PropertyProfile
def enrich_batch(properties: List[PropertyProfile]) -> List[PropertyProfile]
def estimate_msa_from_property(prop: PropertyProfile) -> Optional[str]
```

**Logic:**
- Parse property city/state to MSA
- Fetch employment growth from BLS API
- Merge into PropertyProfile.employment_growth_yoy
- Log enrichment confidence (high if exact match, low if estimated)

### 3. `calibration/tests/test_bls_integration.py` (3 hours)

Comprehensive unit tests.

**Test Cases:**
- `test_fetch_employment_growth_success` — Valid MSA returns data
- `test_fetch_employment_growth_missing_msa` — Unknown MSA returns None
- `test_cache_expiration` — Cached data refreshes after TTL
- `test_rate_limiting` — Respects API rate limits
- `test_batch_enrichment` — Process 100+ properties without errors
- `test_network_failure` — Uses cached fallback on network error
- `test_enrichment_accuracy` — Enriched values match known data

**Fixtures:**
- Mock BLS API responses (Jacksonville, Fargo, Austin)
- Sample PropertyProfile objects
- Cached data snapshots

### 4. Documentation

**File:** `calibration/docs/BLS_INTEGRATION.md`

**Contents:**
- API key setup
- MSA code reference
- Data refresh schedule
- Troubleshooting

---

## Acceptance Criteria

- [ ] Fetch employment growth for 50+ MSAs without errors
- [ ] Cache results with 24-hour TTL
- [ ] Enrich 100 properties in <2 seconds total
- [ ] All unit tests pass (>95% coverage on bls_client.py)
- [ ] Handle API failures gracefully (fallback to cached/default)
- [ ] Document all functions with docstrings
- [ ] No hardcoded API keys (use environment variables)

---

## Integration Points

**Input:**
- PropertyProfile (with city, state)

**Output:**
- PropertyProfile (enriched with employment_growth_yoy)

**Dependencies:**
- `requests` library (HTTP client)
- BLS API (free, public)
- `calibration/models/thesis.py` (PropertyProfile)

**Downstream:**
- `calibration/models/scorers.py` (MarketScorer uses employment_growth_yoy)

---

## Technical Notes

### BLS API

- **Endpoint:** https://api.bls.gov/publicAPI/v2/timeseries/
- **Series ID:** LAUS[MSA_CODE]03 (employment level by MSA)
- **Rate Limit:** 120 requests/minute (free tier)
- **Data Lag:** Monthly (updated 6 days after month end)

### MSA Code Mapping

```python
MSA_CODES = {
    "Jacksonville, FL": "12220",
    "Fargo, ND": "23620",
    "Austin, TX": "12420",
    # ... 50+ mappings
}
```

---

## Success Metrics

- 95%+ MSA code matches from city/state
- <100ms average API response time (cached)
- 99.9% availability (with fallback logic)
- Scoring improvement: employment signal now real, not assumed

---

## Risks & Mitigations

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| BLS API downtime | Low | Cache strategy, fallback to default |
| MSA code mismatches | Medium | Maintain accurate mapping, manual override support |
| Rate limiting | Low | Caching + batch refresh during off-hours |
| Data staleness | Low | Document refresh schedule, log age |

---

## Next Steps

1. **LCMV-24** depends on this: Census integration uses same enrichment pattern
2. **LCMV-26** orchestrates this: Pipeline coordinator calls BLS client
3. Performance monitoring: Track API latency in production

---

*Ticket owner: [Your name]  
Created: 2026-07-31  
Updated: 2026-07-31*
