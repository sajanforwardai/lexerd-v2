# Automated Address Discovery System — Proposal

## Problem
- 252 properties (90.6%) have no addresses in Freddie Mac supplemental data
- Manual lookup is inefficient
- Need reliable, scalable, automated solution

---

## Proposed Multi-Tier System

### **TIER 1: High-Confidence Automated Sources** (60-70% coverage expected)

#### 1A. County Property Tax Assessor APIs
**Approach:** Query public property tax databases by county, property name, and city
- **Coverage:** All US counties (varying quality)
- **Automation:** Python requests to county assessor websites
- **Confidence:** 95%+ (official government records)
- **Cost:** Free (public records)
- **Implementation:**
  ```
  For each property:
    1. Extract county from loan data (already available)
    2. Query county assessor API/website by property name
    3. Extract address from tax record
    4. Validate: address city matches loan city
  ```

**County APIs Available:**
- Texas: Many counties have public property search APIs
- Georgia: Fulton, Cobb, DeKalb Counties have online databases
- Florida: Most counties have PALM (Property Appraiser Mapping & Listing)
- North Carolina: County Register of Deeds databases
- Kansas, Alabama, Louisiana: County assessor websites (HTML scrape)

**Example - Texas Harris County:**
- URL: `https://hcad.org/property-search/`
- Query by property name and city
- Extract address from results

---

#### 1B. Real Estate Aggregator APIs
**Approach:** Query Zillow, Apartments.com, ApartmentsList for property listings
- **Coverage:** 70-80% of multifamily properties
- **Automation:** Official APIs where available
- **Confidence:** 85-90% (some outdated listings, rebranding)
- **Cost:** Free tier available; paid tier $100-500/month for commercial use

**Implementation:**
```python
for property in properties_without_addresses:
    # Zillow API
    result = zillow_api.search(
        property_name=property.name,
        city=property.city,
        state=property.state,
        property_type="multifamily"
    )
    if result and unit_count_matches(result.units, property.units):
        address = result.address
        confidence = 0.90
        
    # Fallback: ApartmentsList API
    if not result:
        result = apartments_list_api.search(...)
```

**Available APIs:**
- Zillow Zestimate API (free tier + paid)
- ApartmentsList API (commercial license)
- CoStar LoopNet API (requires membership)
- RealPage API (property management focused)

---

#### 1C. Property Management Company Database Lookup
**Approach:** Match sponsor/owner name to property management companies, extract address
- **Coverage:** 40-60% (larger management companies)
- **Automation:** API calls + web scraping
- **Confidence:** 80% (may be different addresses for management vs. property)
- **Cost:** Free (public websites)

**Implementation:**
```python
for property in properties:
    if sponsor_name := property.sponsor:
        # Search property management company database
        company = property_mgmt_companies.search(sponsor_name)
        if company:
            # Get all properties managed by this company
            properties_by_company = company.list_managed_properties()
            # Match by name, units, city
            if matched_property := properties_by_company.find(
                name=property.name,
                units=property.units,
                city=property.city
            ):
                address = matched_property.address
                confidence = 0.85
```

**Data Sources:**
- ApartmentsList (largest US property manager listings)
- Zillow multifamily search
- AppFolio (property management software)
- Yardi (property management software)
- CoStar data (commercial properties)

---

### **TIER 2: Medium-Confidence Automated Sources** (30-40% additional coverage)

#### 2A. CMBS Prospectus PDF Parsing
**Approach:** Extract property details from SEC CMBS prospectuses via OCR/text extraction
- **Coverage:** 289 properties in CMBS deals
- **Automation:** Python PDF parsing (PyPDF2, pdfplumber)
- **Confidence:** 75-85% (OCR errors, formatting variability)
- **Cost:** Free (public SEC documents)

**Implementation:**
```python
for loan in loans_in_cmbs_deals:
    sec_url = loan.source_url
    
    # Download prospectus PDF
    pdf_file = download_sec_prospectus(sec_url)
    
    # Extract text
    text = extract_text_from_pdf(pdf_file)
    
    # Search for property section
    property_section = find_property_section(text, loan.property_name)
    
    # Parse structured property information
    property_info = parse_property_details(property_section)
    
    if address := property_info.get('address'):
        # Validate: city/state match
        if property_info.city == loan.city and property_info.state == loan.state:
            confidence = 0.80
```

**PDF Sources:**
- SEC EDGAR: 82 CMBS prospectuses (424B5 forms)
- Each prospectus contains detailed property-level information:
  - Street address
  - Lease information
  - Tenant mix
  - Property history

**Tools:**
- `pdfplumber` (Python) — Text extraction with layout preservation
- `PyPDF2` — PDF parsing
- `pytesseract` — OCR for image-based PDFs
- `pdfrw` — PDF manipulation

---

#### 2B. Loan ID to Property Record Matching
**Approach:** Use Freddie Mac loan ID to cross-reference property records
- **Coverage:** 20-30% (where loan IDs are tracked in county records)
- **Automation:** County database queries by loan ID
- **Confidence:** 90%+ (official loan documents)
- **Cost:** Free (public records)

**Implementation:**
```python
for loan in loans_without_addresses:
    # Query county recorder by loan ID
    property_record = county_recorder.search_by_loan_id(loan.loan_id)
    if property_record:
        address = property_record.address
        confidence = 0.95
```

---

### **TIER 3: Deterministic but Semi-Automated**

#### 3A. County Assessor Web Scraping
**Approach:** Automated web scraping of county tax assessor websites
- **Coverage:** 95%+ (all counties have online records)
- **Automation:** Selenium/Playwright for JavaScript-heavy sites
- **Confidence:** 95%+ (official government data)
- **Cost:** Free
- **Rate Limit:** 1-2 requests/second to avoid blocking

**Implementation:**
```python
import playwright

county_scraper_config = {
    "Harris County, TX": {
        "url": "https://hcad.org/property-search/",
        "search_field": "property_name",
        "result_selector": ".property-address",
        "headers": ["Address", "City", "State", "Zip"]
    },
    # ... config for each county
}

for loan in loans_without_addresses:
    county = loan.county
    config = county_scraper_config.get(f"{county}, {loan.state}")
    
    if config:
        scraper = CountyAssessorScraper(config)
        result = scraper.search(loan.property_name, loan.city)
        if result and matches_loan_data(result, loan):
            address = result.address
            confidence = 0.92
```

---

#### 3B. Direct Property Contact via Phone/Email
**Approach:** Automated outreach to property management companies
- **Coverage:** 85%+ (properties have public phone numbers)
- **Automation:** API calls to communication services (Twilio, SendGrid)
- **Confidence:** 98%+ (official from property)
- **Cost:** $0.01-0.05 per contact (Twilio/SendGrid)

**Implementation:**
```python
for property in properties_without_addresses:
    if phone := find_property_phone(property.name, property.city):
        # Send automated SMS/email request
        message = f"""
        Hi {property.name}! Quick question for data verification:
        Can you confirm your street address? Replying with address 
        helps us keep records accurate.
        """
        
        result = send_sms(phone, message)
        # Parse response for address
        if response_text := await receive_sms(result.from_number):
            address = parse_address_from_response(response_text)
            confidence = 0.98
```

**Phone Number Sources:**
- Google Maps (already searched)
- Zillow/Apartments.com listings
- ApartmentsList property pages
- 411.com reverse phone lookup

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Input: 252 Properties                     │
│           (Name, City, State, Units, Sponsor)               │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
    ┌───▼────────┐            ┌──────▼──────┐
    │   TIER 1   │            │   TIER 2    │
    │ (High-conf)│            │  (Med-conf) │
    │ 60-70%     │            │ 30-40%      │
    └───┬────────┘            └──────┬──────┘
        │                            │
    ┌───▼────────────────────────────▼──────┐
    │  ✓ County Assessor APIs (95%)          │
    │  ✓ Zillow/ApartmentsList (85-90%)     │
    │  ✓ Property Mgmt Company (80%)         │
    │  ✓ CMBS PDF Parsing (75-85%)          │
    │  ✓ Loan ID Matching (90%+)            │
    └───┬──────────────────────────────────┘
        │
    ┌───▼─────────────────────────┐
    │ Deduplication & Validation  │
    │ - Unit count match          │
    │ - City/state match          │
    │ - Address format validation │
    └───┬─────────────────────────┘
        │
    ┌───▼────────────────────────────────────┐
    │   Confidence Scoring & Ranking         │
    │  High conf (90%+) → Use immediately    │
    │  Med conf (70-89%) → Manual review     │
    │  Low conf (<70%) → Skip or contact     │
    └───┬────────────────────────────────────┘
        │
    ┌───▼─────────────┐
    │  TIER 3         │
    │ (Fallback)      │
    │ 15-25%          │
    └───┬─────────────┘
        │
    ┌───▼────────────────────────────┐
    │ ✓ County Web Scraping (95%+)   │
    │ ✓ Direct Property Contact (98%)│
    └───┬────────────────────────────┘
        │
    ┌───▼──────────────────────────────────┐
    │  Output: Address Cache (JSON)        │
    │  Format: property|city|state → addr  │
    │  Include: confidence, source, timestamp
    └──────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Quick Wins (Week 1)
- [ ] Implement County Assessor APIs for TX, GA, FL (top 3 states)
- [ ] Add Zillow API integration
- [ ] Expected coverage: ~150 addresses (60%)
- [ ] Effort: 2-3 days
- [ ] Cost: $0 (free APIs)

### Phase 2: Advanced Automation (Week 2)
- [ ] CMBS PDF parsing for 82 deals
- [ ] Property management company lookup
- [ ] Property phone number extraction
- [ ] Expected additional coverage: ~60 addresses (24%)
- [ ] Effort: 3-4 days
- [ ] Cost: ~$50 (Zillow commercial API)

### Phase 3: Fallback Automation (Week 3)
- [ ] County assessor web scraping (all counties)
- [ ] Automated SMS/email outreach
- [ ] Expected additional coverage: ~40 addresses (16%)
- [ ] Effort: 2-3 days
- [ ] Cost: ~$20-50 (Twilio/SendGrid)

### **Total Expected Coverage: 250/252 addresses (99%+)**
### **Total Effort: 1-2 weeks**
### **Total Cost: $100-150 (optional services)**

---

## Code Structure

```
/workspace/lexerd2/
├── address_discovery_system/
│   ├── __init__.py
│   ├── config.py                    # API keys, county configs
│   ├── orchestrator.py              # Main coordination logic
│   ├── sources/
│   │   ├── county_assessor.py       # Tier 1A
│   │   ├── real_estate_apis.py      # Tier 1B (Zillow, etc.)
│   │   ├── property_mgmt.py         # Tier 1C
│   │   ├── cmbs_parser.py           # Tier 2A (PDF extraction)
│   │   ├── loan_id_matcher.py       # Tier 2B
│   │   └── web_scraper.py           # Tier 3A
│   ├── validators/
│   │   ├── address_validator.py     # Format, city/state match
│   │   ├── unit_count_validator.py  # Confirm property identity
│   │   └── confidence_scorer.py     # Rank results
│   ├── outputs/
│   │   ├── cache_writer.py          # Write to JSON cache
│   │   └── report_generator.py      # Summary statistics
│   └── tests/
│       ├── test_county_apis.py
│       ├── test_real_estate_apis.py
│       └── test_parsers.py
```

---

## Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Total addresses found | 250+ (99%+) | To build |
| High confidence (90%+) | 240+ (95%+) | To build |
| Automation rate | 95%+ | To build |
| False positive rate | <2% | To validate |
| Average time per address | <5 seconds | To measure |
| Cost per address | <$0.50 | To achieve |

---

## Risk Mitigation

1. **API Rate Limits**
   - Implement request queuing and backoff
   - Respect rate limits (1-2 req/sec per county)

2. **Data Quality**
   - Validate addresses (format, city/state match, unit count)
   - Flag low-confidence results for review

3. **Change of Address**
   - Properties may have been renamed or relocated
   - Validate against loan date (use property data from origination date)

4. **API Availability**
   - Fallback to next tier if API fails
   - Cache results to avoid re-fetching

---

## Recommendation

**Build Tier 1 first (1 week, $0 cost)** to get 60-70% coverage, then evaluate if Tier 2 & 3 are needed based on coverage results.

Most valuable to implement immediately:
1. County Assessor APIs (TX, GA, FL)
2. Zillow API integration
3. CMBS document parsing

This would likely yield **200+ addresses (80%+)** with minimal cost.
