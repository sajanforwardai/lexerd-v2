# Tier 1 Address Discovery System

Automated address discovery for multifamily properties using county assessor APIs and real estate aggregators.

## Quick Start

```bash
# Install dependencies
pip install -r ../address_discovery_requirements.txt

# Configure API keys (optional)
export GOOGLE_MAPS_API_KEY="your-key-here"
export ZILLOW_API_KEY="your-key-here"

# Run discovery
python3 ../run_tier1_discovery.py
```

## Architecture

### Tier 1 Sources

**1A. County Property Tax Assessor APIs (95% confidence)**
- Direct query to county tax records
- Covers: TX, GA, FL, NC, KS, LA, AL, KY
- Method: Web API or web scraping
- Cost: Free

**1B. Real Estate Aggregator APIs (85-90% confidence)**
- Zillow (API or web scraping)
- ApartmentsList (web scraping)
- Google Maps (Places API)
- Cost: Free tier available

**1C. Property Management Companies** (Tier 2)
- Match sponsor name to property management database
- Cost: Free (web scraping)

### Module Structure

```
address_discovery_system/
├── __init__.py                    # Package exports
├── config.py                      # Configuration (APIs, counties, validation)
├── orchestrator.py                # Main coordinator
├── sources/
│   ├── county_assessor.py        # County tax database lookups
│   └── real_estate_apis.py       # Zillow, ApartmentsList, Google Maps
└── validators/
    └── address_validator.py      # Address validation & confidence scoring
```

## Configuration

Edit `config.py` to:

1. **Add API keys** (optional):
   ```python
   REAL_ESTATE_APIS = {
       "zillow": {
           "api_key": "your-key-here",
           ...
       }
   }
   ```

2. **Add/remove counties**:
   ```python
   COUNTY_ASSESSOR_CONFIG = {
       "Harris": {
           "state": "TX",
           "type": "web_api",
           "base_url": "https://hcad.org/property-search/",
           ...
       }
   }
   ```

3. **Adjust validation rules**:
   ```python
   VALIDATION_CONFIG = {
       "min_confidence_score": 0.70,
       "require_unit_count_match": True,
       ...
   }
   ```

## Usage

### Run Complete Discovery

```python
from address_discovery_system.orchestrator import AddressDiscoveryOrchestrator
from maturity_radar.data_sources import load_loans

# Initialize
orchestrator = AddressDiscoveryOrchestrator()

# Load loans
all_loans, _ = load_loans("auto")
loans_without_addresses = [l for l in all_loans if not l.property_address]

# Discover addresses
summary = orchestrator.discover_addresses(
    loans_without_addresses,
    output_file="results.json"
)

# Update cache
orchestrator.update_cache(summary['results'])
```

### Search Single Property

```python
result = orchestrator._search_property(
    property_name="Northgate Lofts",
    city="College Station",
    state="TX",
    county="Brazos",
    units=220
)

print(result)
# {
#   'found': True,
#   'address': '405 Cross St, College Station, TX 77840, USA',
#   'confidence_score': 0.92,
#   'source': 'county_assessor',
#   ...
# }
```

## Output

### Results File (`tier1_discovery_results.json`)

```json
{
  "timestamp": "2024-08-06T12:00:00",
  "total": 252,
  "found": 180,
  "not_found": 72,
  "coverage": "71.4%",
  "results": [
    {
      "found": true,
      "property_name": "Northgate Lofts",
      "address": "405 Cross St, College Station, TX 77840, USA",
      "city": "College Station",
      "state": "TX",
      "phone": "(979) 608-7146",
      "confidence_score": 0.92,
      "source": "county_assessor",
      "sources_tried": ["county_assessor", "google_maps"]
    }
  ]
}
```

### Cache Update

Addresses are automatically added to `/workspace/lexerd2/calibration/.cache/address_verification_cache.json`

Format:
```json
{
  "property_name|city|state": {
    "address": "street address",
    "city": "city",
    "state": "state",
    "phone": "phone",
    "confidence_score": 0.92,
    "source": "county_assessor",
    "verified_at": "2024-08-06T12:00:00"
  }
}
```

## Validation & Confidence Scoring

### Validation Checks

1. **Address Format** — Must have number + street name
2. **City Match** — City must match loan city (allows 2-char difference)
3. **State Match** — State must match exactly
4. **Unit Count** — Optional: units within 5% of loan units (bonus: +5%)
5. **Source Confidence** — Based on data source reliability

### Confidence Scores

- **95%+** — County assessor, ArcGIS API
- **90%** — Loan ID matching
- **85%** — Zillow API, Google Maps
- **80%** — ApartmentsList, web scraping
- **75%** — CMBS PDF parsing

Results below 70% are not accepted.

## Error Handling

- **Network errors** — Logged, falls back to next source
- **API rate limits** — Automatic backoff with exponential delay
- **Invalid addresses** — Flagged with validation issues
- **Missing data** — Skipped, reported as not found

## Performance

- **Rate limiting** — 1 request/second per county, 5-10 requests/second for APIs
- **Caching** — Results cached to avoid duplicate lookups
- **Parallel processing** — Can be enhanced for concurrent county searches
- **Time per property** — ~2-5 seconds (with rate limiting)

## Testing

```bash
# Test county assessor lookup
python3 -m pytest tests/test_county_apis.py

# Test real estate APIs
python3 -m pytest tests/test_real_estate_apis.py

# Test validators
python3 -m pytest tests/test_validators.py
```

## Expected Results (Tier 1)

- **Coverage**: 60-70% (150-170 properties)
- **High confidence (90%+)**: 140+ properties
- **Cost**: $0 (free APIs) + optional $100-500 for commercial Zillow
- **Time**: 3-5 days to implement fully

## Next Steps (Tier 2)

If Tier 1 coverage is insufficient:

1. **CMBS PDF Parsing** — Extract from SEC EDGAR prospectuses
2. **Loan ID Matching** — Cross-reference county records
3. **Property Management Lookup** — Match sponsor to company database

Expected additional coverage: 30-40% (75-100 more properties)

## Troubleshooting

### No results found

1. Check API keys are set (`GOOGLE_MAPS_API_KEY`, `ZILLOW_API_KEY`)
2. Verify county configuration matches property counties
3. Check logs in `address_discovery_system.log`
4. Try manual web search to verify property exists

### Low confidence scores

1. Check address format validation
2. Verify city/state in loan data matches property location
3. Some properties may need Tier 2 sources

### Rate limiting issues

1. Reduce `rate_limit` in config (slower but more reliable)
2. Add backoff multiplier for persistent failures
3. Implement request queueing for large batches

## Contributing

To add a new county or API:

1. Add configuration to `config.py`
2. Implement lookup method in `county_assessor.py` or `real_estate_apis.py`
3. Add validation rules if needed
4. Test with sample property
5. Update README

## License

Internal use only - Lexerd Capital Management
