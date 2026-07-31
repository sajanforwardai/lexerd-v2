# Multifamily Loan Data Sources Integration Guide

## Overview

The maturity-radar application integrates loan data from three free, public sources:

1. **SEC EDGAR CMBS** (Conduit) — Historical CMBS filings, 10+ years
2. **Fannie Mae Multifamily** (Agency) — 72,000+ loans, loan-level performance data
3. **Freddie Mac K-Deal/SBL** (Agency) — K-Deal and SBL disclosures

All sources are fully public and require no paid subscriptions.

## Current Data Status

**As of 2026-07-31:**
- **Total loans loaded:** 414
- **Loans in 8 target states (AL, FL, GA, KS, KY, LA, NC, TX):** 282
- **Breakdown by program:**
  - Conduit (SEC CMBS): 144 loans
  - Agency (Fannie Mae): 125 loans
  - Agency (Sample/other): 13 loans

**Target State Distribution:**
| State | Count |
|-------|-------|
| TX    | 150   |
| FL    | 39    |
| GA    | 35    |
| NC    | 20    |
| AL    | 9     |
| LA    | 12    |
| KS    | 11    |
| KY    | 6     |

## Data Source 1: SEC EDGAR CMBS (Expanded)

### What is it?
Public CMBS (Conduit Commercial Mortgage-Backed Securities) loan-level disclosures filed with the SEC under Regulation AB II, Form ABS-EE, Exhibit 102. Every loan in these filings includes current balance, note rate, maturity, DSCR, NOI, occupancy, and property detail.

### Coverage
- 10+ years of history (back to ~2014)
- Multifamily-only loans (propertyTypeCode == "MF")
- All 50 states (filter to 8 target states in code)

### How to fetch
```bash
# Expanded search (150 deals, ~10 year history)
python3 fetch_expanded_data.py 150 AL,FL,GA,KS,KY,LA,NC,TX

# Standard search (25 deals, recent only)
python3 fetch_data.py 60 AL,FL,GA,KS,KY,LA,NC,TX
```

### Data Quality
- **Pros:** Loan-level detail, SEC-filed, traceable to exact filings, includes rates/DSCR/NOI
- **Cons:** Conduit CMBS only (not full agency universe), only deals that filed ABS-EE

### Cache Location
`data/sec_loans.json` — auto-refreshed by fetch scripts

---

## Data Source 2: Fannie Mae Multifamily (Agency)

### What is it?
Fannie Mae's loan-level multifamily performance data, available through their free Data Dynamics platform. This is agency multifamily, not conduit CMBS — real portfolio loans with standard underwriting and disclosure.

### Coverage
- 72,000+ loans available
- Portfolio multifamily (apartments, garden/mid-rise)
- Includes current balance, rate, maturity, DSCR, occupancy

### How to fetch
1. **Register (free):**
   - Visit https://capitalmarkets.fanniemae.com/
   - Click "Data Dynamics" or "Loan-Level Data"
   - Create free account (requires email, name, institution)

2. **Download:**
   - Select "Multifamily Performance Data"
   - Choose latest dataset or historical version
   - Download CSV file

3. **Load:**
   ```bash
   python3 fetch_fannie_mae.py ~/Downloads/fannie_mae_data.csv
   python3 fetch_fannie_mae.py ~/Downloads/fannie_mae_data.csv TX,GA,FL
   ```

### Data Quality
- **Pros:** Massive universe (72K+ loans), portfolio multifamily, standardized fields
- **Cons:** Requires registration (free but manual), CSV download varies by release

### CSV Column Flexibility
The loader is flexible and handles these common column name variations:
- Loan ID variants: "Loan Identifier", "Loan ID", "loanid", "LoanID"
- State: "Property State", "State", "code_st"
- Rate: "Interest Rate", "Note Rate", "interest_rate", "rate_int"
- And many others (see `load_fannie_mae()` docstring for full list)

### Cache Location
`data/fannie_mae_loans.json` — manually refreshed when you download new data

---

## Data Source 3: Freddie Mac K-Deal / SBL (Agency)

### What is it?
Freddie Mac's loan-level disclosures from K-Deal and SBL securitizations. Agency multifamily with property-level detail, current balance, rate, maturity, DSCR, occupancy.

### Coverage
- Agency multifamily only
- Freddie Mac securitized loans

### How to fetch
1. **Access:**
   - Register at https://mf.freddiemac.com/investors/data
   - Download K-Deal or SBL disclosure files (CSV format)

2. **Load:**
   ```bash
   python3 fetch_freddie_data.py
   # Looks for data/MLPD.csv or via MLPD_PATH env var
   ```

### Cache Location
`data/freddie_mac_loans.json` — managed by `fetch_freddie_data.py`

---

## Using the Data in Code

### Load all sources (default)
```python
from maturity_radar.data_sources import load_loans

loans, sources = load_loans()
# -> (list of Loan objects, "sec+fannie+sample")
```

### Load specific source only
```python
loans, sources = load_loans(source="sec")      # SEC EDGAR only
loans, sources = load_loans(source="fannie")   # Fannie Mae only
loans, sources = load_loans(source="freddie")  # Freddie Mac only
```

### Filter by states
```python
loans, sources = load_loans(states={"TX", "GA", "FL"})
```

### Combine filters
```python
loans, sources = load_loans(source="fannie", states={"TX", "FL"})
```

---

## Priority & Deduplication

When `load_loans(source="auto")` merges multiple sources, deduplication is by `loan_id` with this priority:

1. **SEC EDGAR** (highest priority — newest CMBS versions)
2. **Fannie Mae** (agency loans not in SEC)
3. **Freddie Mac** (K-Deal loans not in above)
4. **MLPD** (registered Freddie file)
5. **Sample** (illustrative fallback)

This ensures you get the broadest universe without duplicates, preferring SEC's CMBS detail and newer filings.

---

## Updating Data Regularly

### SEC EDGAR (quarterly or as needed)
```bash
# Expanded search for 10-year history
python3 fetch_expanded_data.py 150 ALL

# Or target states only
python3 fetch_expanded_data.py 150 AL,FL,GA,KS,KY,LA,NC,TX
```

### Fannie Mae (monthly recommended)
1. Visit https://capitalmarkets.fanniemae.com/ and download latest CSV
2. Run:
   ```bash
   python3 fetch_fannie_mae.py ~/Downloads/fannie_mae_data.csv
   ```

### Freddie Mac (monthly recommended)
1. Download latest K-Deal or SBL file from https://mf.freddiemac.com/investors/data
2. Place at `data/MLPD.csv` (or set `MLPD_PATH` env var)
3. Run:
   ```bash
   python3 fetch_freddie_data.py
   ```

---

## Loan Data Schema

All loans are parsed into the `Loan` dataclass with these fields:

```python
@dataclass
class Loan:
    loan_id: str              # Unique identifier
    property_name: str        # Property name
    city: str                 # City
    county: str               # County (optional)
    state: str                # State abbreviation
    units: int                # Number of units
    
    origination_year: int     # Year loan was originated
    original_balance: float   # Original UPB
    current_balance: float    # Current UPB
    note_rate: float          # Interest rate (decimal, e.g., 0.045 = 4.5%)
    maturity: date            # Maturity date
    interest_only: bool       # Is loan interest-only?
    
    most_recent_noi: float    # Annual NOI
    most_recent_dscr: float   # DSCR (in-place)
    occupancy: float          # Occupancy (decimal, 0.94 = 94%)
    
    # Provenance
    program: str              # "Conduit" | "Agency"
    deal: str                 # Deal/securitization name
    source_url: str           # URL to SEC filing or source
    
    # Human enrichment (for top of list)
    owner_entity: str         # LLC on title
    owner_mailing: str        # Mailing address
    principal_hint: str       # Principal contact hint
```

---

## Testing the Loaders

```bash
# Test SEC EDGAR expanded search
python3 -c "
from maturity_radar.sec_edgar import find_all_cmbs_deals
deals = find_all_cmbs_deals(max_deals=50)
print(f'Found {len(deals)} deals')
"

# Test Fannie Mae loader on sample data
python3 -c "
from maturity_radar.data_sources import load_fannie_mae
loans = load_fannie_mae('data/fannie_mae_sample.csv', states={'TX', 'GA'})
print(f'Parsed {len(loans)} loans')
"

# Test merged load
python3 -c "
from maturity_radar.data_sources import load_loans
loans, sources = load_loans()
print(f'Loaded {len(loans)} loans from {sources}')
"
```

---

## Integration with Dashboard

The app automatically loads loans on startup:

```python
# In app.py or fetch_data flow
loans, source_label = load_loans(source="auto", states=TARGET_STATES)
```

No additional setup is needed beyond running the fetch scripts once.

---

## Troubleshooting

### "No usable SEC cache"
→ Run: `python3 fetch_expanded_data.py 150 ALL`

### "File not found: fannie_mae_loans.json"
→ Download from https://capitalmarkets.fanniemae.com/ and run: `python3 fetch_fannie_mae.py ~/Downloads/fannie_mae_data.csv`

### "No MLPD file found"
→ Register at https://mf.freddiemac.com/investors/data and place file at `data/MLPD.csv`

### Loans not appearing
1. Check `load_loans()` is filtering to correct states
2. Verify cache files exist in `data/` directory
3. Ensure state abbreviations are uppercase (e.g., "TX" not "tx")

---

## References

- **SEC EDGAR:** https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=ABS-EE&dateb=&owner=exclude&count=100
- **Fannie Mae Data Dynamics:** https://capitalmarkets.fanniemae.com/
- **Freddie Mac Investor Data:** https://mf.freddiemac.com/investors/data
- **Regulation AB II ABS-EE Form:** https://www.sec.gov/Archives/edgar/data/

---

**Last Updated:** 2026-07-31  
**Dataset Version:** sec_loans.json (276 total), fannie_mae_loans.json (125 total)
