# Florida County Assessor Integration Guide

## Overview

The Florida County Assessor scraper discovers addresses for multifamily properties by querying public property appraiser records across Florida's 67 counties. 

**Current Status:** 33 Florida properties without addresses across 13 counties.

## Counties with Properties

| County | Properties | Status |
|--------|-----------|--------|
| Sarasota | 2 | 🔄 In scope |
| Duval | 5 | 🔄 In scope |
| Hillsborough | 3 | 🔄 In scope |
| Pinellas | 1 | 🔄 In scope |
| Lee | 2 | 🔄 In scope |
| Broward | 5 | 🔄 In scope |
| Okaloosa | 1 | 🔄 In scope |
| Miami-Dade | 2 | 🔄 In scope |
| Columbia | 1 | 🔄 In scope |
| Osceola | 2 | 🔄 In scope |
| Bay | 1 | 🔄 In scope |
| Orange | 2 | 🔄 In scope |
| Alachua | 2 | 🔄 In scope |
| Escambia | 1 | 🔄 In scope |
| Unknown | 3 | ❓ Needs manual review |

**Total: 33 properties**

## Scraping Strategies by County

### Tier 1: Direct API / Simple HTML (Recommended First)

These counties have public search endpoints that can be queried programmatically:

1. **Hillsborough County (Tampa)**
   - URL: `https://apps.hcpafl.org/Asp/OwnerSearch.asp`
   - Method: HTML form search by owner/property name
   - Parser: BeautifulSoup
   - Expected coverage: 100%

2. **Orange County (Orlando)**
   - URL: `https://epass.ocpafl.org/ePass/Search/QuickSearch.aspx`
   - Method: DataGrid results with property links
   - Parser: BeautifulSoup
   - Expected coverage: 100%

### Tier 2: JavaScript-Heavy (Requires Selenium)

These counties use JavaScript frameworks that require browser automation:

3. **Duval County (Jacksonville)**
   - URL: `https://webpub.duvalassessor.com/Map/`
   - Technology: React/JavaScript map interface
   - Parser: Selenium WebDriver
   - Expected coverage: 85-90%

4. **Miami-Dade County**
   - URL: `https://www.miamidade.gov/pa/propertysearch/index.html`
   - Technology: JavaScript search with dynamic results
   - Parser: Selenium WebDriver
   - Expected coverage: 90-95%

5. **Broward County**
   - URL: `https://www.broward.org/PD/AssessorsOffice/`
   - Technology: Dynamic search interface
   - Parser: Selenium WebDriver
   - Expected coverage: 85-90%

### Tier 3: Specialized Interfaces (Manual or API)

6. **Lee County (Fort Myers)**
   - URL: `https://www.leecountyfl.gov/pa/`
   - Note: May require account registration for detailed searches
   - Alternative: Contact via phone: (239) 533-6200

7. **Sarasota County**
   - URL: `https://www.sarasotacountyassessor.org/`
   - Note: Consider contacting directly for batch queries
   - Phone: (941) 861-7700

## Implementation Approaches

### Approach A: BeautifulSoup (Current)

✅ **Pros:**
- Lightweight, no external dependencies
- Fast for simple HTML parsing
- Works for static sites

❌ **Cons:**
- Fails on JavaScript-heavy sites
- Limited to sites with static HTML

**File:** `address_discovery_system/florida_assessor_enhanced.py`

### Approach B: Selenium WebDriver (Recommended for Production)

✅ **Pros:**
- Handles JavaScript-heavy sites
- Can interact with forms/buttons
- Takes screenshots for verification
- Supports all major browsers (Chrome, Firefox)

❌ **Cons:**
- Slower (2-5 seconds per property)
- Requires browser installation
- Higher resource usage

**Setup Required:**
```bash
pip install selenium
# Download ChromeDriver: https://chromedriver.chromium.org/
```

**File:** `address_discovery_system/florida_assessor_selenium.py` (to be created)

### Approach C: Hybrid (Recommended)

Use BeautifulSoup for Tier 1 counties, Selenium for Tier 2 counties:

```python
from address_discovery_system.florida_assessor_enhanced import FloridaCountyAssessorEnhanced
from address_discovery_system.florida_assessor_selenium import FloridaCountyAssessorSelenium

# Try BeautifulSoup first (fast)
bs_result = assessor_bs.search_by_county(property_name, county, city)

# Fall back to Selenium if BeautifulSoup fails
if not bs_result or bs_result['confidence'] < 0.5:
    selenium_result = assessor_selenium.search_by_county(property_name, county, city)
```

## Expected Results

### Conservative Estimate (BeautifulSoup Only)
- **Coverage:** 40-50% (Hillsborough + Orange counties)
- **Time:** ~1-2 minutes for all 33 properties
- **Confidence:** 0.75-0.85 per address

### Aggressive Estimate (With Selenium)
- **Coverage:** 85-95% for Tier 1 + Tier 2 counties
- **Time:** ~3-5 minutes for all 33 properties
- **Confidence:** 0.80-0.95 per address

### Full Coverage
- **Coverage:** 95%+ including Tier 3 manual methods
- **Time:** ~10-30 minutes including manual lookups
- **Confidence:** 0.90-1.0 per address

## Integration with Discovery System

### Step 1: Run discovery
```bash
python scripts/run_florida_discovery.py
```

### Step 2: Update database
Discovered addresses are automatically written to `loans.property_address` with:
- `address_source`: 'florida_assessor_<county>'
- `address_confidence`: 0.75-0.95
- `address_last_updated`: Current timestamp

### Step 3: Audit results
```bash
python scripts/audit_florida_discovery.py
```

## Manual Verification Process

For properties not found by automated scraping:

1. **Online Search** (~2 min per property)
   - Go to county assessor website
   - Search by property name or owner
   - Copy address to database

2. **Batch Email Request** (~1 day)
   - Prepare list of missing properties
   - Email county assessor office
   - Request bulk address lookup

3. **Phone Contact** (~5 min per property)
   - Call county assessor office
   - Provide property name + city
   - Record address provided

## Files Created

- `address_discovery_system/florida_assessor.py` — Base class with county configs
- `address_discovery_system/florida_assessor_enhanced.py` — BeautifulSoup-based scraper
- `address_discovery_system/florida_assessor_selenium.py` — Selenium WebDriver scraper (to be created)
- `scripts/run_florida_discovery.py` — Main discovery orchestrator
- `scripts/test_florida_scraper.py` — Test suite for scrapers
- `scripts/audit_florida_discovery.py` — Results auditor (to be created)

## Next Steps

1. ✅ Create base Florida assessor module
2. ✅ Build BeautifulSoup scraper for Tier 1 counties
3. ⏳ **NEXT: Build Selenium scraper for Tier 2 counties**
4. ⏳ Run full discovery against all 33 Florida properties
5. ⏳ Create audit report with coverage metrics
6. ⏳ Integrate with dashboard for live address display

## Usage Example

```python
from address_discovery_system.florida_assessor_enhanced import FloridaCountyAssessorEnhanced
from address_discovery_system.database import get_session, update_loan_address

# Initialize assessor
assessor = FloridaCountyAssessorEnhanced()

# Search for a property
result = assessor.search_by_county(
    property_name='Clubside Apartments',
    county='Sarasota',
    city='Venice'
)

# Update database if found
if result['address']:
    session = get_session()
    update_loan_address(
        session=session,
        loan_id=5,
        address=result['address'],
        source=result['source'],
        confidence=result['confidence']
    )
    session.close()
```

## References

- [Florida Property Appraiser Association](https://www.fpaa.org/)
- [Public Records Access Guide](https://www.myfloridalegal.com/pages.php?page=305)
- [County Appraiser Contact List](https://www.fpaa.org/members/)
