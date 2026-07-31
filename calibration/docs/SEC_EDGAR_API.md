# SEC EDGAR API Query & Download Module (LCMV-79)

## Overview

The SEC EDGAR API module provides systematic access to SEC filings for CMBS (Commercial Mortgage-Backed Securities) deal discovery and analysis. This is a critical competitive advantage for Lexerd Capital Management — we can identify multifamily CMBS deals and refinancing opportunities faster than competitors by parsing SEC data before it hits the market.

**Why this matters:**
- Form 424B5 prospectuses are filed when deals close (origination snapshot with loan-level tape)
- Form 10-D servicer reports filed monthly (performance updates, delinquencies, extensions)
- SEC data covers 40-50% of multifamily securitization market missed by GSE pipelines (Freddie Mac B3)
- No authentication required; data is 100% public and free

**Data latency:**
- 424B5: Filed within days of deal closing
- 10-D: Monthly servicer reports (updated regularly)
- 8-K: Material events (distress signals, extensions, payoffs)

## Quick Start

### Basic Query for Multifamily CMBS Deals

```python
from calibration.data.sec_edgar_client import SecEdgarClient

# Initialize client
client = SecEdgarClient(cache_enabled=True)

# Query recent multifamily CMBS deals (2024-2025)
deals = client.query_cmbs_deals(
    years=[2024, 2025],
    keywords=["multifamily", "apartment"],
    form_types=["424B5"]
)

# Examine results
for deal in deals[:5]:
    print(f"{deal['deal_name']} ({deal['filing_date']})")
    print(f"  CIK: {deal['cik']}")
    print(f"  Filing URL: {deal['filing_url']}")
```

### Download Prospectus

```python
# Download a specific prospectus
filing_url = deals[0]['filing_url']
content, cache_path = client.download_prospectus(
    filing_url,
    deal_name=deals[0]['deal_name']
)

if content:
    # Save to file
    with open(f"{deals[0]['deal_name']}.pdf", "wb") as f:
        f.write(content)
    print(f"Saved to {cache_path}")
```

### Download All Prospectuses in Batch

```python
# Batch download all deals from recent query
for deal in deals:
    content, cache_path = client.download_prospectus(
        deal['filing_url'],
        deal_name=deal['deal_name'],
        cache=True  # Reuses cached files on next run
    )
    if content:
        print(f"Downloaded: {deal['deal_name']}")
```

## API Reference

### SecEdgarClient Class

#### Initialization

```python
client = SecEdgarClient(
    cache_enabled: bool = True,
    rate_limit_seconds: float = None,  # Default: 1.0 (1 req/sec)
    cache_dir: Path = None              # Default: calibration/opportunities/cache/sec_prospectuses/
)
```

**Parameters:**
- `cache_enabled`: Enable local file caching (365-day TTL). Recommended for repeated queries.
- `rate_limit_seconds`: Seconds between API calls. Default respects SEC rate limits (~10 req/sec max).
- `cache_dir`: Custom cache directory. If None, uses project default.

#### query_cmbs_deals()

Query SEC EDGAR for CMBS deals with multifamily loans.

```python
deals = client.query_cmbs_deals(
    keywords: Optional[List[str]] = None,      # Default: config.MULTIFAMILY_KEYWORDS
    years: Optional[List[int]] = None,         # Default: [2022, 2023, 2024, 2025]
    form_types: Optional[List[str]] = None,    # Default: ["424B5", "10-D"]
    ciks: Optional[List[str]] = None           # Default: major CMBS issuer CIKs
) -> List[Dict]
```

**Returns:** List of dictionaries with keys:
- `cik`: Issuer CIK number
- `accession`: Filing accession number
- `deal_name`: Official deal name from SEC filing
- `form_type`: Form type (424B5, 10-D, 8-K)
- `filing_date`: Filing date (YYYY-MM-DD)
- `filing_url`: Full URL to SEC filing

**Example:**

```python
# Query JPMorgan and BofA multifamily deals from 2024
deals = client.query_cmbs_deals(
    years=[2024],
    keywords=["multifamily", "apartment"],
    ciks=["0000048104", "0000070858"]  # JPMorgan, BofA
)

# Filter to prospectuses only
prospectuses = [d for d in deals if d['form_type'] == '424B5']
print(f"Found {len(prospectuses)} prospectuses")
```

#### download_prospectus()

Download 424B5 prospectus PDF from SEC.

```python
content, cache_path = client.download_prospectus(
    filing_url: str,
    deal_name: Optional[str] = None,
    cache: bool = True
) -> Tuple[Optional[bytes], Optional[Path]]
```

**Parameters:**
- `filing_url`: SEC filing URL (from query results)
- `deal_name`: Deal name for cache file naming (optional)
- `cache`: Cache file locally for future use

**Returns:**
- `content`: PDF bytes (or None on error)
- `cache_path`: Local cache path (or None if not cached)

**Example:**

```python
# Download with caching
content, cache_path = client.download_prospectus(
    deals[0]['filing_url'],
    deal_name=deals[0]['deal_name']
)

if content:
    # Use cached file on next run (365-day TTL)
    print(f"Cached at: {cache_path}")
```

#### download_servicer_report()

Download 10-D servicer report from SEC.

```python
content, cache_path = client.download_servicer_report(
    filing_url: str,
    deal_name: Optional[str] = None,
    cache: bool = True
) -> Tuple[Optional[bytes], Optional[Path]]
```

Same API as `download_prospectus()` but for servicer reports.

#### search_by_cik()

Search all SEC filings by CIK number (issuer identifier).

```python
filings = client.search_by_cik(cik: str) -> List[Dict]
```

**Parameters:**
- `cik`: SEC CIK number (e.g., "0000048104")

**Returns:** List of all filings by that issuer

**Example:**

```python
# Get all filings by JPMorgan
filings = client.search_by_cik("0000048104")
for filing in filings[:10]:
    print(f"{filing['form_type']} filed {filing['filing_date']}")
```

#### Cache Management

**get_cache_status()** - Get cache statistics

```python
status = client.get_cache_status() -> Dict
```

Returns:
- `total_files`: Number of cached files
- `total_size_mb`: Total cache size
- `oldest_file`: Age of oldest file (ISO format)
- `newest_file`: Age of newest file (ISO format)
- `cache_dir`: Cache directory path

**Example:**

```python
status = client.get_cache_status()
print(f"Cache: {status['total_files']} files, {status['total_size_mb']}MB")
```

**clear_cache()** - Delete cached files

```python
deleted_count = client.clear_cache(
    older_than_days: Optional[int] = None
) -> int
```

**Parameters:**
- `older_than_days`: Only delete files older than N days. If None, delete all.

**Returns:** Number of files deleted

**Example:**

```python
# Clear files older than 180 days
deleted = client.clear_cache(older_than_days=180)
print(f"Deleted {deleted} old cache files")

# Clear entire cache
deleted = client.clear_cache()
print(f"Cleared cache: {deleted} files deleted")
```

## Configuration

Edit `/calibration/data/sec_edgar_config.py` to customize:

### CMBS_ISSUER_CIKS

Dictionary mapping issuer names to CIK numbers. Update quarterly with new issuers.

```python
CMBS_ISSUER_CIKS = {
    "JPMorgan Chase": "0000048104",
    "Bank of America": "0000070858",
    "Wells Fargo": "0000072971",
    # Add more issuers here
}
```

### MULTIFAMILY_KEYWORDS

Keywords for filtering multifamily deals:

```python
MULTIFAMILY_KEYWORDS = [
    "multifamily",
    "apartment",
    "residential",
    "housing",
    # Add more keywords
]
```

### Rate Limiting

```python
RATE_LIMIT_REQUESTS_PER_SECOND = 1      # ~1 request/second (conservative)
RATE_LIMIT_BURST_SIZE = 5               # Allow brief bursts
```

### Cache Configuration

```python
CACHE_TTL_DAYS = 365                    # SEC filings never change
DEFAULT_QUERY_START_YEAR = 2022
DEFAULT_QUERY_END_YEAR = 2025
RESULTS_PER_PAGE = 100                  # SEC API limit
```

## Usage Patterns

### Pattern 1: Backfill Historical Deals

Query 3+ years of deals for initial market baseline:

```python
client = SecEdgarClient(cache_enabled=True)

# Get all deals 2022-2025
deals = client.query_cmbs_deals(
    years=[2022, 2023, 2024, 2025],
    form_types=["424B5"]
)

print(f"Backfill: Found {len(deals)} multifamily CMBS deals")

# Download all prospectuses (will cache)
for deal in deals:
    content, path = client.download_prospectus(deal['filing_url'])
    if content:
        print(f"Downloaded: {deal['deal_name']}")
```

### Pattern 2: Weekly/Monthly Monitoring

Check for new deals since last run:

```python
import json
from pathlib import Path

def check_for_new_deals():
    client = SecEdgarClient(cache_enabled=True)
    
    # Query only this year (faster)
    deals = client.query_cmbs_deals(
        years=[2025],
        form_types=["424B5", "10-D"]
    )
    
    # Compare to previous results (stored in file)
    previous_deals_file = Path("previous_deals.json")
    if previous_deals_file.exists():
        with open(previous_deals_file) as f:
            previous_deals = json.load(f)
            previous_ids = {d['accession'] for d in previous_deals}
    else:
        previous_ids = set()
    
    current_ids = {d['accession'] for d in deals}
    new_ids = current_ids - previous_ids
    
    # Download new deals
    for deal in deals:
        if deal['accession'] in new_ids:
            content, _ = client.download_prospectus(deal['filing_url'])
            print(f"NEW: {deal['deal_name']}")
    
    # Save for next run
    with open(previous_deals_file, 'w') as f:
        json.dump(deals, f)

if __name__ == "__main__":
    check_for_new_deals()
```

### Pattern 3: Specific Issuer Deep Dive

Get all filings by a single CMBS issuer:

```python
# All JPMorgan CMBS filings
filings = client.search_by_cik("0000048104")

# Filter to specific form types
prospectuses = [f for f in filings if f['form_type'] == '424B5']
servicer_reports = [f for f in filings if f['form_type'] == '10-D']

print(f"JPMorgan: {len(prospectuses)} prospectuses, {len(servicer_reports)} servicer reports")
```

## Error Handling

### Common Errors

**Network Error (No Internet)**
```python
content, path = client.download_prospectus(url)
if content is None:
    logger.error("Download failed - check network connection")
```

**SEC API Timeout**
The client automatically retries with exponential backoff (1s, 2s, 4s).

**Cache Corruption**
Cache files older than TTL are automatically re-downloaded.

**Rate Limit**
The client self-throttles to 1 request/second (configurable).

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

client = SecEdgarClient()
# Now all operations print debug info
```

## Cache Strategy

### Why Cache?

- SEC filings never change (immutable archives)
- 365-day TTL is safe (filings won't be updated)
- Dramatically speeds up repeated queries
- Avoids redundant SEC API calls

### Cache Location

Default: `calibration/opportunities/cache/sec_prospectuses/`

Structure:
```
sec_prospectuses/
  ├── sec_filings_index.json          # Metadata for all cached files
  ├── 48104/                          # CIK directory
  │   ├── 0001234567-24-001234_JPMorgan_CMBS_2024.pdf
  │   └── 0001234567-24-001235_JPMorgan_CMBS_2024.pdf
  └── 70858/                          # Another CIK
      └── 0001234567-24-001236_BofA_CMBS_2024.pdf
```

### Cache Index

`sec_filings_index.json` tracks all cached files:

```json
{
  "https://www.sec.gov/Archives/...": {
    "cache_path": "/path/to/cache/file.pdf",
    "deal_name": "JPMorgan CMBS 2024",
    "downloaded_at": "2024-03-15T10:30:00"
  }
}
```

### Manual Cache Cleanup

```python
# Delete files older than 180 days
client.clear_cache(older_than_days=180)

# Delete entire cache
client.clear_cache()

# Check cache size
status = client.get_cache_status()
print(f"{status['total_size_mb']}MB used")
```

## Known Limitations

### 1. OCR-Required PDFs

Some prospectuses are scanned (image-based PDFs), not machine-readable. Text extraction requires OCR.

**Workaround:** Use cloud OCR service (Google Cloud Vision, AWS Textract) for scanned documents.

### 2. Form 10-D Formatting Inconsistency

Servicer reports vary significantly in format (HTML, PDF, Excel tables). No standardized structure.

**Workaround:** Use prospectus (424B5) for loan-level data; use 10-D for performance updates only.

### 3. Missing or Delayed Filings

Occasionally SEC filings are delayed or missing from EDGAR.

**Workaround:** Cross-reference with mortgage market data (MBA, CMBS.com).

### 4. Rate Limits (Self-Imposed)

We limit to 1 request/second. SEC doesn't enforce strict limits, but aggressive scraping can trigger IP blocks.

**Workaround:** Increase `rate_limit_seconds` if needed, but stay respectful.

### 5. CIK Lookup Not Automated

CIK numbers must be manually added to config. SEC doesn't provide reliable company-name-to-CIK lookup.

**Workaround:** Use SEC EDGAR company search manually to find new CIKs.

## Performance Tips

### Tip 1: Enable Caching

Always enable caching for production use:

```python
client = SecEdgarClient(cache_enabled=True)
```

### Tip 2: Query Strategically

Query by year to speed up searches:

```python
# Good: Query one year at a time
deals_2024 = client.query_cmbs_deals(years=[2024])

# Slower: Query 10 years at once
deals_all = client.query_cmbs_deals(years=list(range(2015, 2025)))
```

### Tip 3: Filter by Keywords Locally

Keyword filtering happens after API call. For best performance:

```python
# Query only multifamily keywords (narrower search)
deals = client.query_cmbs_deals(
    keywords=["multifamily", "apartment"],
    years=[2024]
)
```

### Tip 4: Batch Download

Download multiple files in a loop; rate limiting is automatic:

```python
for deal in deals:
    content, path = client.download_prospectus(deal['filing_url'])
    # Rate limit enforced automatically between downloads
```

## Integration with Pipeline

This module is part of the Securitized SEC Loan Maturity Pipeline (LCMV-58):

```
SEC EDGAR (LCMV-79)  →  PDF Parser (LCMV-80)  →  Loan Scorer (LCMV-81)  →  Opportunity Ranking (LCMV-82)
  ↓                      ↓                         ↓                         ↓
Query & Download     Extract Loan Tape        Score Maturity            Find Refinancing
CMBS Deals          (Address, DSCR, LTV)     Risk Signals              Opportunities
```

## Testing

Run tests to verify functionality:

```bash
# Run all SEC EDGAR tests
pytest calibration/tests/test_sec_edgar_client.py -v

# Run specific test class
pytest calibration/tests/test_sec_edgar_client.py::TestSecEdgarQueryCmbsDeals -v

# Run with coverage
pytest calibration/tests/test_sec_edgar_client.py --cov=calibration.data.sec_edgar_client
```

## Troubleshooting

### Issue: "No deals found"

**Cause:** Query parameters too restrictive

**Solution:** Loosen filters
```python
# Try broader keywords
deals = client.query_cmbs_deals(keywords=["loan", "deal"])
```

### Issue: "Network error / Connection refused"

**Cause:** SEC API unreachable

**Solution:** Check network, retry with backoff
```python
import time
try:
    deals = client.query_cmbs_deals()
except Exception as e:
    print(f"Error: {e}")
    time.sleep(5)
    deals = client.query_cmbs_deals()  # Retry
```

### Issue: "Cache file corrupted"

**Cause:** Incomplete download or disk error

**Solution:** Clear and re-download
```python
client.clear_cache()
content, path = client.download_prospectus(url)
```

### Issue: "Rate limit exceeded"

**Cause:** Too many rapid requests

**Solution:** Increase rate limit delay
```python
client = SecEdgarClient(rate_limit_seconds=2.0)
```

## Contact & Support

For issues or questions:
- Check CLAUDE.md for system context
- Review test cases in `test_sec_edgar_client.py`
- Consult `/workspace/corpus/finance/` for CMBS intelligence

---

**Last Updated:** 2026-07-31  
**Module Version:** 1.0  
**Author:** Sajan Goswami (Lexerd Capital Management)  
**Status:** Production Ready
