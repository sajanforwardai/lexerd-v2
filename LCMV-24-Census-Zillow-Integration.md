# LCMV-24: Census Population & Zillow Integration

**Stage:** 2 — Data Integration  
**Estimate:** 14 hours  
**Status:** To Do  
**Priority:** High  

---

## Summary

Integrate US Census API for population growth data and Zillow Multifamily API for property listings, cap-rates, and market comparables. Provides 15% improvement in Model score accuracy by using real market data.

---

## Problem Statement

**Current State:**
- Cap-rate spread estimated/assumed
- No real property market data
- Population growth signals missing

**Target State:**
- Actual cap-rates from Zillow for target markets
- Real population growth by MSA from Census Bureau
- Market comparable data for benchmarking

---

## Deliverables

### 1. `calibration/data/census_client.py` (4 hours)

Census API wrapper for population data.

**Methods:**
```python
def fetch_population_growth(msa_code: str) -> Dict[str, float]
def fetch_population_by_county(fips_code: str) -> int
def get_msa_for_county(county_name: str, state: str) -> Optional[str]
```

**Features:**
- Query Census API for MSA population data
- Calculate YoY growth rates
- Cache results (365-day TTL, data updated annually)
- Support 350+ MSAs in US
- Error handling for missing data

### 2. `calibration/data/zillow_client.py` (5 hours)

Zillow Multifamily API wrapper.

**Methods:**
```python
def search_properties(city: str, state: str, max_price: float) -> List[Dict]
def get_market_cap_rate(msa_code: str) -> Optional[float]
def get_comparable_rents(city: str, units: int) -> List[Dict]
def get_property_details(zpid: str) -> Dict
```

**Data Extraction:**
- Property listings in target MSAs
- Sale prices → derive cap rates
- Comparable rents by unit count
- Market trends

**Rate Limiting:**
- Zillow API has lower limits than BLS
- Implement caching (30-day TTL)
- Batch requests where possible

### 3. `calibration/data/market_enrichment.py` (3 hours)

Merge Census + Zillow data into PropertyProfile.

**Functions:**
```python
def enrich_market_data(prop: PropertyProfile) -> PropertyProfile
def enrich_batch(properties: List[PropertyProfile]) -> List[PropertyProfile]
def derive_cap_rate(city: str, state: str) -> Optional[float]
```

**Logic:**
- Add population_growth_yoy from Census
- Add market_cap_rate from Zillow comparables
- Log data freshness and confidence levels

### 4. Integration Testing (2 hours)

**File:** `calibration/tests/test_market_enrichment.py`

**Test Cases:**
- Census data accuracy (Jacksonville, Fargo, Austin)
- Zillow cap-rate derivation
- Batch enrichment speed (<5s for 100 properties)
- Error handling (missing data, API failures)
- Cache behavior (expiration, refresh)

---

## Acceptance Criteria

- [ ] Fetch population data for 50+ MSAs
- [ ] Derive cap-rates from Zillow listings
- [ ] Enrich 100 properties in <5 seconds
- [ ] All tests pass (>90% coverage)
- [ ] Cache strategy implemented
- [ ] Error handling for missing data
- [ ] Documentation complete

---

## Technical Notes

### Census Bureau API

- **Endpoint:** https://api.census.gov/data/
- **Key Data:** Decennial Census, American Community Survey (ACS)
- **MSA Population:** B01003_001E (total population)
- **Rate Limit:** 500 requests/second (free tier)

### Zillow API

- **Endpoint:** https://www.zillow.com/api/
- **Authentication:** API key (free tier available)
- **Data:** Multifamily listings, rental comparables
- **Rate Limit:** 1000 requests/day (varies by tier)

---

## Success Metrics

- 95%+ MSA population data coverage
- Cap-rate accuracy within 50 bps of market
- <5s batch enrichment time
- Upstream feeds LCMV-26 pipeline with real data

---

## Dependencies

- `requests` library
- Census API key (free signup)
- Zillow API key (free signup)
- LCMV-23 (BLS integration) — parallel development OK

---

*Ticket owner: [Your name]  
Created: 2026-07-31  
Updated: 2026-07-31*
