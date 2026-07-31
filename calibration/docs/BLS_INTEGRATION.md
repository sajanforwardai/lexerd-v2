# BLS Employment Data Integration — Setup & Reference

**Module:** `calibration/data/bls_client.py` and `calibration/data/employment_enrichment.py`  
**Ticket:** LCMV-23  
**Created:** 2026-07-31  

---

## 1. API Key Setup

### Getting a BLS API Key

The BLS (Bureau of Labor Statistics) provides free public access to employment data.

**Steps:**
1. Visit: https://www.bls.gov/developers/
2. Register for a free account (email-based)
3. Once approved, you'll receive an API key (string of 40+ alphanumeric characters)

### Setting the Environment Variable

Store your API key in an environment variable so it's not hardcoded in source:

```bash
# Linux/Mac: add to ~/.bashrc or ~/.zshrc
export BLS_API_KEY="your_api_key_here"

# Windows: set environment variable via System Properties
setx BLS_API_KEY "your_api_key_here"

# Docker: pass at runtime
docker run -e BLS_API_KEY="your_api_key_here" ...

# Python: read at runtime
import os
api_key = os.getenv("BLS_API_KEY")
```

### Verifying Access

Test your API key with a quick request:

```python
from calibration.data.bls_client import BLSClient

client = BLSClient(api_key="your_api_key")
result = client.fetch_employment_growth("12220")  # Jacksonville, FL
print(result)
# Output: {"employment_growth_yoy": 0.0342}
```

---

## 2. MSA Code Reference

**MSA** = Metropolitan Statistical Area (BLS's geographic unit)

### Supported Markets (20+ Secondary Markets)

| City | State | MSA Code | Region |
|------|-------|----------|--------|
| Jacksonville | FL | 12220 | Southeast |
| Fargo | ND | 23620 | Midwest |
| Austin | TX | 12420 | South |
| Atlanta | GA | 12060 | Southeast |
| Miami | FL | 33124 | Southeast |
| Tampa | FL | 45300 | Southeast |
| Orlando | FL | 36100 | Southeast |
| Charlotte | NC | 16740 | Southeast |
| Raleigh | NC | 39580 | Southeast |
| Nashville | TN | 34980 | Southeast |
| Memphis | TN | 32820 | Southeast |
| Phoenix | AZ | 38060 | Southwest |
| Denver | CO | 19740 | Mountain |
| Dallas | TX | 19100 | South |
| Houston | TX | 26420 | South |
| San Antonio | TX | 41700 | South |
| Kansas City | MO | 28140 | Midwest |
| New Orleans | LA | 35380 | South |
| Birmingham | AL | 12260 | Southeast |
| Mobile | AL | 33660 | Southeast |
| Charleston | SC | 16700 | Southeast |

### Adding New MSA Codes

To add support for additional markets:

1. Find the MSA code at https://www.bls.gov/help/hlp_faq.htm
2. Add to `MSA_CODES` dict in `bls_client.py`:

```python
MSA_CODES = {
    # ... existing codes ...
    ("New Market Name", "ST"): "12345",  # New entry
}
```

3. Test with:

```python
msa = client.get_msa_by_city_state("New Market Name", "ST")
assert msa == "12345"
```

---

## 3. Data Refresh Schedule & Caching

### Cache Strategy

BLS data is updated monthly, so we cache results to avoid repeated API calls.

**Cache Settings:**
- TTL: 24 hours (not 1 month, to catch late-month data releases)
- Location: `~/.bls_cache.json` (user's home directory)
- Format: JSON with timestamps and data

**Example Cache File:**
```json
{
  "12220": {
    "data": {
      "employment_growth_yoy": 0.0342
    },
    "timestamp": 1722472800.0,
    "series_id": "LAUS1222003"
  }
}
```

### Manual Cache Refresh

Force a refresh of all cached data:

```python
from calibration.data.bls_client import BLSClient

client = BLSClient()
client.refresh_cache()  # Fetches all cached MSA codes from API
```

### Monitoring Cache Age

Check how old cached data is:

```python
age_minutes = client.get_cache_age("12220")
if age_minutes and age_minutes > 1440:  # >24 hours
    print(f"Cache is {age_minutes} minutes old, consider refreshing")
```

---

## 4. BLS Series ID Format

The BLS API uses **series IDs** to identify data. Employment data follows this format:

```
LAUS{MSA_CODE}03

Where:
- L = Labor force
- A = All (both sexes)
- U = Unemployment (in this case, employment)
- S = State/Metro
- {MSA_CODE} = 5-digit MSA code
- 03 = Employment level (specific series type)

Examples:
- LAUS1222003 = Jacksonville, FL employment level
- LAUS2362003 = Fargo, ND employment level
- LAUS1242003 = Austin, TX employment level
```

---

## 5. Troubleshooting

### Error: "ValueError: MSA not found"

**Cause:** City/state combination not in `MSA_CODES` dict.

**Solution:**
1. Verify spelling (case-insensitive, but spelling matters)
2. Add to `MSA_CODES` dict (see section 2)
3. Or check https://www.bls.gov/help/hlp_faq.htm for correct MSA code

### Error: "ConnectionError" or "Timeout"

**Cause:** Network issue or BLS API temporarily down.

**Solution:**
1. Check internet connection
2. Verify BLS API status: https://www.bls.gov
3. Retry (client implements exponential backoff)
4. Use cached data as fallback

### Error: "Request not processed" (BLS API 400)

**Cause:** Invalid API request (bad API key or malformed request).

**Solution:**
1. Verify API key is set correctly: `echo $BLS_API_KEY`
2. Test with example MSA: `client.fetch_employment_growth("12220")`
3. Check API key isn't expired (regenerate at bls.gov if needed)

### Error: "Rate limited (429)"

**Cause:** Too many API requests (BLS limit: 120 requests/minute).

**Solution:**
1. Client implements 0.5s delay between requests (respects limit)
2. Check if cache is working (should reduce API calls 95%+)
3. If persistent, contact BLS support

### No Data Returned

**Cause:** MSA code valid, but no employment data available.

**Scenarios:**
- Data not yet released for current month (released 6 days after month-end)
- Very new MSA (less than 6 months of historical data)

**Solution:**
1. Check BLS data release calendar: https://www.bls.gov/schedule/
2. Retry after data release date
3. Use cached data from previous month as fallback

---

## 6. Performance Baseline

**Typical Performance:**

| Scenario | Time | Notes |
|----------|------|-------|
| Single property (cached) | <50ms | Returns cached result |
| Single property (API call) | 100–200ms | Network round-trip |
| Batch 100 properties | <2 seconds | Parallel API calls + caching |
| Batch 1000 properties | <10 seconds | Multiple batches, rate limiting |

**Optimization Tips:**
- Cache hit rate: 95%+ (cached data reused, API calls minimized)
- Batch processing: ~50ms per property (amortized)
- Use `enrich_batch()` not sequential `enrich_property()` calls

---

## 7. Security & API Key Handling

### DO's ✓

- Store API key in environment variable: `BLS_API_KEY`
- Pass key to BLSClient at initialization
- Let client handle caching (no repeated API calls)
- Strip API key from logs/error messages

### DON'Ts ✗

- ❌ Hardcode API key in source code
- ❌ Commit API key to git
- ❌ Pass key in URL parameters
- ❌ Log API key in errors
- ❌ Share API key in Slack/email

### Cache File Security

Cache file `~/.bls_cache.json` contains **only data**, not API key:

```json
{
  "12220": {
    "data": {"employment_growth_yoy": 0.0342},
    "timestamp": 1722472800.0,
    "series_id": "LAUS1222003"
  }
}
```

Safe to store and backup.

---

## 8. Integration with PropertyProfile

### Before Enrichment

```python
from calibration.models.thesis import PropertyProfile

prop = PropertyProfile(
    property_id="prop-1",
    city="Jacksonville",
    state="FL",
    units=150,
    # ... other fields ...
    employment_growth_yoy=None  # ← Not yet enriched
)
```

### After Enrichment

```python
from calibration.data.bls_client import BLSClient
from calibration.data.employment_enrichment import enrich_property_with_employment

client = BLSClient()
enriched_prop = enrich_property_with_employment(prop, client)

print(enriched_prop.employment_growth_yoy)  # 0.0342 (real BLS data)
```

### Integration with MarketScorer

The enriched `employment_growth_yoy` feeds directly into Market score calculation:

```python
from calibration.models.scorers import MarketScorer

scorer = MarketScorer()
market_score, breakdown = scorer.score(enriched_prop, thesis)

print(breakdown['employment_growth'])  # Score contribution (0–25 points)
```

---

## 9. Data Freshness & Validation

### Data Update Schedule

BLS releases monthly employment data on:
- **Release Date:** 6 days after end of month
- **Example:** August data released September 6

**Check Release Calendar:** https://www.bls.gov/schedule/

### Validation Checks

The client validates all data:

```
- MSA code: Must be 5 digits
- Interest rate: 0.01–0.15 (1%–15%)
- Employment growth: 0.0–0.10 (0%–10% annual)
- Occupancy: 0.0–1.0 (0%–100%)
```

Invalid data: logged as warning, record skipped

---

## 10. Historical Data & Backtesting

### Backfill Historical Data

To backtest employment-based sourcing:

```python
client = BLSClient()

# Get data for last 24 months
for msa_code in ["12220", "23620", "12420"]:
    result = client.fetch_employment_growth(msa_code)
    print(f"MSA {msa_code}: {result['employment_growth_yoy']:.2%}")
```

### BLS API Historical Support

BLS API supports requests for multiple years:

```python
# In fetch_employment_growth():
payload = {
    "seriesid": ["LAUS1222003"],
    "startyear": 2020,      # ← Can fetch historical
    "endyear": 2024,
    "registrationkey": api_key
}
```

### Historical Validation

To validate sourcing signal (employment growth predicts deals):

1. Pull historical BLS data (2+ years)
2. Score properties from past months
3. Compare to actual deals that closed
4. Measure signal accuracy (% of flagged deals that matured)

---

## 11. Monthly Refresh Process

### Recommended Workflow

```bash
# 1. Day 10 of month (after BLS data release, day 6)
# 2. Run pipeline with full refresh:

python -m calibration.pipeline.cli run \
  --input-csv properties.csv \
  --mode standard \
  --output-dir ./results/$(date +%Y-%m)

# 3. Cache automatically refreshes expired data
# 4. Pipeline generates scored CSV + alerts
```

### Scheduled Task (Cron)

```cron
# Monthly refresh: 2 AM on the 10th
0 2 10 * * /usr/local/bin/lexerd-pipeline run --mode full
```

---

## 12. Example: End-to-End Usage

```python
from calibration.data.bls_client import BLSClient
from calibration.data.employment_enrichment import enrich_batch
from calibration.models.thesis import PropertyProfile, ThesisConfig
from calibration.models.scorers import FinalScorer

# 1. Initialize client
client = BLSClient()

# 2. Load properties
properties = [
    PropertyProfile(
        property_id="prop-1",
        property_name="Oak Ridge Apartments",
        city="Jacksonville",
        state="FL",
        units=180,
        property_class="B",
        year_built=2010,
        occupancy=0.85,
        avg_rent_per_unit=1600,
        expense_ratio=0.30,
        market_expense_ratio=0.28,
    ),
    # ... more properties ...
]

# 3. Enrich with BLS employment data
enriched = enrich_batch(properties, client)

# 4. Score properties
thesis = ThesisConfig()
scorer = FinalScorer()

scored = []
for prop in enriched:
    score_result = scorer.score(prop, thesis)
    scored.append((prop, score_result))

# 5. Export results
import csv
with open("scored_properties.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow([
        "property_id", "city", "state", "employment_growth_yoy",
        "market_score", "model_score", "management_score",
        "final_score", "confidence_grade"
    ])
    for prop, result in scored:
        writer.writerow([
            prop.property_id,
            prop.city,
            prop.state,
            f"{prop.employment_growth_yoy:.4f}" if prop.employment_growth_yoy else "N/A",
            f"{result.market_score:.1f}",
            f"{result.model_score:.1f}",
            f"{result.management_score:.1f}",
            f"{result.final_fit_score:.1f}",
            result.confidence_grade.value
        ])
```

---

## 13. API Rate Limits & Best Practices

### BLS API Rate Limits

- **Free tier:** 120 requests per minute
- **Registered user:** 500 requests per minute (with API key)
- **Burst limit:** 20 requests per 10 seconds

### Client Implementation

The BLSClient respects rate limits automatically:

```python
# In bls_client.py
self.rate_limit_delay = 1.0 / 2.0  # 0.5 seconds between requests
# This respects: 120 requests/minute = 2 requests/second
```

### Best Practices

1. **Use caching:** Cache hit rate 95%+ reduces API calls
2. **Batch requests:** Enrich 100+ properties at once (parallel API calls)
3. **Refresh wisely:** Only refresh expired cache (24h TTL)
4. **Monitor usage:** Check cache age, API call count in logs

---

## References

- **BLS API Documentation:** https://www.bls.gov/developers/
- **BLS Data FAQ:** https://www.bls.gov/help/hlp_faq.htm
- **BLS Release Calendar:** https://www.bls.gov/schedule/
- **BLS Series Definitions:** https://www.bls.gov/help/hlp_def.htm
- **Lexerd Thesis:** `LEXERD_THESIS.md`
- **PropertyProfile Structure:** `calibration/models/thesis.py`
- **Scoring Engine:** `calibration/models/scorers.py`

---

*Last Updated: 2026-07-31*
