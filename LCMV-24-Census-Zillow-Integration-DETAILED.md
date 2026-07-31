# LCMV-24: Stage 2 — Census Population & Zillow Integration

**Epic:** Stage 2 Data Integration Pipeline  
**Stage:** 2 — Data Foundation  
**Estimate:** 14 hours  
**Status:** To Do  
**Priority:** High  
**Owner:** [Assigned Developer]  
**Dependencies:** LCMV-23 (parallel development OK, shares enrichment pattern)

---

## Executive Summary

Integrate US Census API (population growth, demographics) and Zillow Multifamily API (property listings, cap-rates, rents) to enrich Market and Model scores with real market data. This is a **dual-signal integration:**

- **Population growth** → Market score signal (15% of market fundamentals)
- **Market cap-rate & rents** → Model score signal (30% of model fundamentals)

**Impact:**
- Enables evidence-based market selection (not assumed trends)
- Unlocks rent-gap and cap-rate-spread calculations
- Feeds into LCMV-26 pipeline for batch scoring
- Provides competitive intelligence (market comps)

---

## Problem Statement

### Current State (Without LCMV-24)
```
PropertyProfile {
  city: "Jacksonville",
  state: "FL",
  population_growth_yoy: None,           # ❌ Assumed 1.5% default
  market_cap_rate: None,                 # ❌ Assumed 6.0% (national avg)
  market_rent_per_unit: None,            # ❌ No comparable data
}

MarketScorer.score() → population_growth_yoy = None → 0 points
ModelScorer.score() → market_cap_rate = None → default neutral score (15/30 points)
```

**Consequences:**
- Can't differentiate between aging (0.5%) and high-growth (3%) markets
- Cap-rate spread scoring defaults to neutral 15/30 (no actionable signal)
- No ability to calculate rent gap (upside potential)
- Manual market research required for every deal

### Target State (With LCMV-24)
```
PropertyProfile {
  city: "Jacksonville",
  state: "FL",
  population_growth_yoy: 0.0218,         # ✅ Real Census data (18 bps growth)
  market_cap_rate: 0.0785,               # ✅ Real Zillow data (7.85% yield)
  market_rent_per_unit: 1850,            # ✅ Zillow comps
}

MarketScorer.score() → population_growth = 0.0218 → 12/15 points
ModelScorer.score() → cap_rate = 0.0785 → 26/30 points (250 bps spread above 6%)
PropertyProfile.rent_gap_pct() = (1850 - 1600) / 1850 = 13.5% upside
```

**Benefits:**
- Differentiated market signals (growth vs. stagnation)
- Accurate cap-rate spread scoring
- Quantified rent upside (Model score signal)
- Competitive intelligence (similar buildings, same market)

---

## Technical Architecture

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      PropertyProfile                         │
│  city="Jacksonville", state="FL",                           │
│  population_growth_yoy=None, market_cap_rate=None           │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
  ┌──────────────────────┐        ┌──────────────────────┐
  │  Census Enrichment   │        │  Zillow Enrichment   │
  │  (Population Growth) │        │  (Cap Rate & Rents)  │
  └──────────┬───────────┘        └──────────┬───────────┘
             │                               │
             ▼                               ▼
  ┌──────────────────────────┐    ┌──────────────────────────┐
  │ CensusClient             │    │ ZillowClient             │
  │ .fetch_pop_growth(msa)   │    │ .fetch_market_data(msa)  │
  │ .get_msa_by_county()     │    │ .search_properties()     │
  └──────────┬───────────────┘    └──────────┬───────────────┘
             │                               │
             ├─→ Check cache (365d)         ├─→ Check cache (30d)
             │                              │
             ├─→ POST Census API            ├─→ GET Zillow API
             │   /data/2021/acs5/          │   /multifamily/search
             │   Variables: B01003_001E    │   Filters: city, <$50M
             │                              │
             └─→ {"pop_growth_yoy": 0.0218}└─→ {"cap_rate": 0.0785,
                                                "market_rent": 1850}
                         │                               │
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                        ┌────────────────────────────────┐
                        │ PropertyProfile (enriched)    │
                        │ - population_growth_yoy        │
                        │ - market_cap_rate              │
                        │ - market_rent_per_unit         │
                        │ Ready for scoring              │
                        └────────────────────────────────┘
```

### Module Structure

```
calibration/
├── data/
│   ├── census_client.py                  # ← LCMV-24.1
│   │   ├── CensusClient class
│   │   ├── fetch_population_growth(msa_code) → Dict
│   │   ├── fetch_population_by_county(fips_code) → int
│   │   └── get_msa_for_county(county_name, state) → str
│   │
│   ├── zillow_client.py                  # ← LCMV-24.2
│   │   ├── ZillowClient class
│   │   ├── search_properties(city, state, max_price) → List[Dict]
│   │   ├── get_market_cap_rate(msa_code) → Optional[float]
│   │   └── get_comparable_rents(city, state, units) → List[Dict]
│   │
│   └── market_enrichment.py               # ← LCMV-24.3
│       ├── enrich_market_data(prop, census, zillow) → PropertyProfile
│       ├── enrich_batch(properties, census, zillow) → List[PropertyProfile]
│       └── derive_cap_rate(city, state, zillow) → Optional[float]
│
├── tests/
│   └── test_market_enrichment.py          # ← LCMV-24.4
│       ├── TestCensusClient (8 tests)
│       ├── TestZillowClient (8 tests)
│       ├── TestMarketEnrichment (6 tests)
│       └── TestIntegration (2 tests)
│
└── docs/
    └── MARKET_ENRICHMENT.md               # ← LCMV-24.5
        ├── API Key Setup (Census + Zillow)
        ├── MSA/County Code Reference
        ├── Data Freshness & Refresh
        └── Troubleshooting
```

---

## Sub-Tickets (Breakdown)

### LCMV-24.1: Census API Client Implementation
**Estimate:** 4 hours  
**Type:** Task  
**Acceptance Criteria:**
- [ ] `calibration/data/census_client.py` created with CensusClient class
- [ ] Implements `fetch_population_growth(msa_code: str) → Dict[str, float]`
- [ ] Implements `fetch_population_by_county(fips_code: str) → int`
- [ ] Implements `get_msa_for_county(county_name: str, state: str) → Optional[str]`
- [ ] Supports 350+ US MSAs with annual-updated cache (365-day TTL)
- [ ] Fetches from Census Bureau API (2021 ACS5 data)
- [ ] Error handling: missing counties, network errors → graceful fallback
- [ ] No hardcoded API keys (reads from CENSUS_API_KEY env var)
- [ ] All functions documented with docstrings

**Census API Details:**

```
Endpoint: https://api.census.gov/data/{year}/acs/acs5

Request Parameters:
- get: B01003_001E (total population)
  get: B01003_002E (total population for error checking)
- for: geographic level (e.g., "metropolitan statistical area:*")
- key: ${CENSUS_API_KEY}

Example Request:
https://api.census.gov/data/2021/acs/acs5?
  get=NAME,B01003_001E
  &for=metropolitan%20statistical%20area:*
  &key=YOUR_API_KEY

Response (JSON):
[
  ["NAME", "B01003_001E", "state", "metropolitan statistical area"],
  ["Jacksonville, FL Metro Area", "1456789", "12", "12220"],
  ["Fargo, ND-MN Metro Area", "289456", "38", "23620"],
  ...
]
```

**Population Growth Calculation:**
```python
# ACS data is annual, but we have:
# - 2021 ACS5: Population at 2021
# - 2022 ACS5: Population at 2022
# YoY growth = (Pop_2022 - Pop_2021) / Pop_2021

# For multi-year trend:
# Request multiple years and calculate rolling average
```

**Cache Structure:**
```json
{
  "12220": {
    "data": {
      "population_growth_yoy": 0.0218,
      "population_total": 1456789,
      "name": "Jacksonville, FL Metro Area"
    },
    "timestamp": 1720000000.0,
    "year": 2021
  }
}
```

---

### LCMV-24.2: Zillow Multifamily API Client
**Estimate:** 5 hours  
**Type:** Task  
**Acceptance Criteria:**
- [ ] `calibration/data/zillow_client.py` created with ZillowClient class
- [ ] Implements `search_properties(city: str, state: str, max_price: float) → List[Dict]`
- [ ] Implements `get_market_cap_rate(msa_code: str) → Optional[float]`
- [ ] Implements `get_comparable_rents(city: str, state: str, units: int) → List[Dict]`
- [ ] Implements `get_property_details(zpid: str) → Dict` (Zillow property ID)
- [ ] 30-day cache TTL (Zillow data updated monthly)
- [ ] Rate limiting: 1000 requests/day (built-in throttling)
- [ ] Derives cap-rate from sale prices and NOI estimates
- [ ] Error handling: API errors, rate limits, missing data
- [ ] No hardcoded API keys (reads from ZILLOW_API_KEY env var)

**Zillow API Details:**

```
Endpoint: https://www.zillow.com/api/
(Zillow has limited official APIs; may use scraping or licensed data feed)

For Production:
- Option A: Zillow Web Services API (requires license)
- Option B: Commercial data aggregator (LoopNet, CoStar)
- Option C: Zillow's public data + parsing (see below)

Workaround: Zillow public data
- Listings available at: https://www.zillow.com/homes/for_sale/
- Parse market-level data (median rents, cap rates by market)
- Cache for 30 days

Search Response Example:
{
  "listings": [
    {
      "zpid": "12345678",
      "address": "123 Oak Lane",
      "city": "Jacksonville",
      "state": "FL",
      "salePrice": 45000000,
      "rentZestimate": 1850,
      "propertyType": "apartment",
      "units": 180,
      "taxYear": 2023
    }
  ]
}

Cap Rate Derivation:
cap_rate = annual_rent / purchase_price
         = (rentZestimate * 12 * units) / salePrice
         = (1850 * 12 * 180) / 45000000
         = 3996000 / 45000000
         = 0.0888 (8.88%)
```

**Market Comparable Data:**
```python
def get_comparable_rents(city: str, state: str, units: int) -> List[Dict]:
    """
    Returns list of 5-10 comparable properties in the market.
    
    Example Response:
    [
        {
            "address": "100 Main St",
            "units": 175,
            "rent_per_unit": 1750,
            "cap_rate": 0.0850,
            "year_built": 2010,
            "occupancy": 0.94
        },
        ...
    ]
    """
```

**Cache Structure:**
```json
{
  "Jacksonville,FL": {
    "data": {
      "market_cap_rate": 0.0785,
      "median_rent": 1850,
      "comparable_properties": [
        {"address": "...", "rent": 1750},
        ...
      ]
    },
    "timestamp": 1722000000.0,
    "count": 42
  }
}
```

---

### LCMV-24.3: Market Data Enrichment Module
**Estimate:** 3 hours  
**Type:** Task  
**Acceptance Criteria:**
- [ ] `calibration/data/market_enrichment.py` created
- [ ] Implements `enrich_market_data(prop, census_client, zillow_client) → PropertyProfile`
- [ ] Implements `enrich_batch(properties, census_client, zillow_client) → List[PropertyProfile]`
- [ ] Implements `derive_cap_rate(city, state, zillow_client) → Optional[float]`
- [ ] Enriches 100 properties in <5 seconds
- [ ] Prioritizes Zillow data > Census; graceful fallback
- [ ] Handles partial enrichment (population yes, cap-rate no)
- [ ] Logs data freshness and sources
- [ ] Integrates with BLS enrichment (parallel safe)

**Enrichment Priority:**
```
PropertyProfile.market_cap_rate:
  1. Check Zillow API (real market data) ← preferred
  2. Fall back to PropertyProfile.market_cap_rate if already set
  3. Final fallback: None (MarketScorer uses default 15/30)

PropertyProfile.market_rent_per_unit:
  1. Check Zillow API (comparable rents) ← preferred
  2. Return None if not available

PropertyProfile.population_growth_yoy:
  1. Check Census API (official government data) ← preferred
  2. Return None if not available
```

---

### LCMV-24.4: Comprehensive Unit Tests
**Estimate:** 2 hours  
**Type:** Task  
**Acceptance Criteria:**
- [ ] `calibration/tests/test_market_enrichment.py` created
- [ ] 24+ test cases:
  - CensusClient: 8 tests
  - ZillowClient: 8 tests
  - MarketEnrichment: 6 tests
  - Integration: 2 tests
- [ ] Test coverage: >90% on both client modules
- [ ] All mocked (no real API calls)
- [ ] Performance benchmark: 100 properties in <5 seconds
- [ ] Fixtures for sample properties, market data

**Test Case Examples:**

```python
class TestCensusClient:
    def test_fetch_population_growth_success(self): pass
    def test_fetch_population_growth_missing_msa(self): pass
    def test_cache_age_tracking(self): pass
    def test_msa_for_county_accuracy(self): pass
    def test_multi_year_trend(self): pass
    def test_network_timeout_fallback(self): pass
    def test_no_hardcoded_keys(self): pass
    def test_batch_accuracy_vs_api(self): pass

class TestZillowClient:
    def test_search_properties_by_market(self): pass
    def test_get_market_cap_rate(self): pass
    def test_get_comparable_rents_filtering(self): pass
    def test_derive_cap_rate_from_sales(self): pass
    def test_rate_limiting_enforcement(self): pass
    def test_cache_expiration_30days(self): pass
    def test_handle_missing_rental_data(self): pass
    def test_api_error_handling(self): pass

class TestMarketEnrichment:
    def test_enrich_property_full(self): pass
    def test_enrich_batch_performance(self): pass
    def test_partial_enrichment_handling(self): pass
    def test_integration_with_bls_enrichment(self): pass
    def test_market_rent_gap_calculation(self): pass
    def test_data_source_logging(self): pass
```

---

### LCMV-24.5: Documentation & Setup Guide
**Estimate:** (included in test/doc time)  
**Type:** Task  
**Deliverable:** `calibration/docs/MARKET_ENRICHMENT.md`
**Sections:**
- Census API key setup (registration, rate limits)
- Zillow data source options (licensed vs. public)
- MSA/County code reference (350+ markets)
- Cap-rate derivation formula
- Data freshness policy
- Troubleshooting (API errors, missing markets)
- Performance benchmarks

---

## Acceptance Criteria (LCMV-24 Overall)

### Functionality
- [ ] Fetch population data for 50+ MSAs
- [ ] Derive cap-rates from Zillow listings (median market data)
- [ ] Enrich 100 properties in <5 seconds
- [ ] Cache Census data (365d TTL), Zillow (30d TTL)
- [ ] Handle partial enrichment (one API fails, continue)

### Code Quality
- [ ] All functions documented (docstrings + type hints)
- [ ] No hardcoded API keys (env vars: CENSUS_API_KEY, ZILLOW_API_KEY)
- [ ] Follows Lexerd code style (PEP 8)
- [ ] Logging at appropriate levels

### Testing
- [ ] 24+ unit tests covering all paths
- [ ] Coverage >90% on both client modules
- [ ] Performance: 100 properties in <5 seconds
- [ ] All mocked (no real API calls)

### Documentation
- [ ] MARKET_ENRICHMENT.md complete
- [ ] Inline docstrings on all functions
- [ ] README integration point documented

---

## Integration Points

### Upstream Dependencies
- PropertyProfile from `calibration/models/thesis.py`
- BLS client from LCMV-23 (optional, parallel development OK)

### Downstream Consumers
- **LCMV-26 Data Pipeline** — Orchestrates Census + Zillow enrichment
- **MarketScorer** — Consumes population_growth_yoy
- **ModelScorer** — Consumes market_cap_rate, market_rent_per_unit
- **PropertyProfile.rent_gap_pct()** — Uses market_rent_per_unit

---

## Data Sources & API Options

### Census Bureau (Population Growth)
| Source | Coverage | Cost | Freshness | Notes |
|--------|----------|------|-----------|-------|
| Census ACS5 | 350+ MSAs | Free | Annual | Official, reliable |
| ACS1 | Major MSAs only | Free | Annual | Faster release |

### Zillow (Cap Rates & Rents)
| Source | Coverage | Cost | Freshness | Notes |
|--------|----------|------|-----------|-------|
| Zillow API | Limited (licensed) | $$ | Real-time | Official, requires license |
| Zillow public data | All markets | Free | Monthly | Scraping required |
| LoopNet/CoStar | Institutional | $$$ | Real-time | Commercial aggregator |

**Recommended:** Census (free, official) + Zillow public data (free, monthly update) with fallback to LoopNet for production.

---

## Success Metrics

| Metric | Target | Verification |
|--------|--------|---|
| MSA coverage | 350+ | Census API coverage |
| Population accuracy | ±2% vs. official | Sample 10 MSAs |
| Cap-rate accuracy | ±50 bps vs. market | Compare to Zillow/LoopNet |
| Enrichment speed | <5s per 100 props | Load test |
| Cache hit rate | 95%+ | Monitor cache age logs |
| Code coverage | >90% | pytest --cov report |

---

## Timeline

- **Day 1 (4h):** LCMV-24.1 Census client
- **Day 1 (5h):** LCMV-24.2 Zillow client
- **Day 2 (3h):** LCMV-24.3 Market enrichment module
- **Day 2 (2h):** LCMV-24.4 Unit tests
- **Async:** LCMV-24.5 Documentation

**Total: 14 hours (1.75 work days)**

---

## Definition of Done

- ✅ All 5 sub-tickets completed
- ✅ pytest calibration/tests/test_market_enrichment.py → all green
- ✅ Coverage >90% on both client modules
- ✅ MARKET_ENRICHMENT.md complete
- ✅ Integrated into Streamlit app
- ✅ Code review approved

---

## References

- Census API: https://www.census.gov/data/developers/guidance/
- Zillow Real Estate Data: https://www.zillow.com/research/
- ACS Data: https://www.census.gov/programs-surveys/acs/
- Lexerd Thesis: `LEXERD_THESIS.md`

---

*Created: 2026-07-31 | Owner: [TBD]*
