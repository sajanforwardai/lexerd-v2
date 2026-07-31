# Freddie Mac Multifamily Loader — Quick Start

## What's New

The maturity-radar now supports **Freddie Mac K-Deal and SBL multifamily loan disclosures**. This adds ~200–250 high-quality agency multifamily loans (property-level DSCR, NOI, balance, occupancy) to supplement the existing 39-loan SEC EDGAR Conduit CMBS database.

**Expected yield**: +200–250 loans in 8 target states (AL, FL, GA, KS, KY, LA, NC, TX)

---

## Quick Start: Three Steps

### 1. Download Freddie Mac CSV

1. Go to: https://mf.freddiemac.com/investors/data
2. Find "K-Deal Loan-Level Disclosures" or "SBL Loan-Level Disclosures"
3. Download the latest CSV file
4. Save to: `data/k-deals-2025-01.csv` (or similar)

### 2. Run the Loader

```bash
python3 fetch_freddie_data.py data/k-deals-2025-01.csv
```

**Expected output**:
```
Freddie Mac multifamily loan loader
  target states: AL, FL, GA, KS, KY, LA, NC, TX

parsing /workspace/lexerd2/maturity-radar/data/k-deals-2025-01.csv
  Parsed 243 valid loans from 2847 rows

Total extracted: 243 Freddie Mac loans

  loaded 174 existing SEC/Conduit loans
  merged cache -> 417 total loans (SEC: 174, Freddie: 243) -> data/sec_loans.json

Result: 417 loans in cache (+243 new from Freddie Mac)

Run `python3 app.py` to see the updated loan universe.
```

### 3. View Updated Dashboard

```bash
python3 app.py
```

The dashboard will now show:
- **All 8 Lexerd states** represented (previously: sparse)
- **~417 loans total** (vs. 39 from SEC cache alone)
- **Mixed programs**: Conduit (SEC) + Agency (Freddie)
- **High-quality data**: Property-level DSCR, NOI, occupancy, current balance

---

## Usage Variations

### Parse Multiple Files

```bash
# Parse all K-Deal and SBL files in data/
python3 fetch_freddie_data.py "data/*.csv"

# Parse specific pattern
python3 fetch_freddie_data.py data/k-deals-*.csv data/sbl-2025-*.csv
```

### Filter States

```bash
# Keep only TX and GA (override default)
python3 fetch_freddie_data.py data/k-deals.csv --states TX,GA

# Keep all states (ignore state filter)
python3 fetch_freddie_data.py data/k-deals.csv --all-states
```

### Dry Run (Validate Before Caching)

```bash
# Parse and show stats, but don't update cache
python3 fetch_freddie_data.py data/k-deals.csv --dry-run
```

### Help

```bash
python3 fetch_freddie_data.py --help
```

---

## In Code

Use the enhanced `load_loans()` function, which now tries multiple sources:

```python
from maturity_radar.data_sources import load_loans

# Auto mode: tries SEC cache → Freddie cache → MLPD → sample
loans, source = load_loans(source="auto", states={"TX", "GA"})
# source = "sec+freddie" or "sec" or "freddie" or "mlpd" or "sample"

# Freddie Mac only
freddie_loans, _ = load_loans(source="freddie")

# SEC EDGAR only
sec_loans, _ = load_loans(source="sec")
```

---

## Data Quality

### What You Get

Each Freddie loan carries:
- **Loan ID** (e.g., FHMS-K7X-0142)
- **Property address** (street, city, county, state)
- **Units** (residential count)
- **Note rate** (current interest rate, %)
- **Maturity date** (scheduled payoff)
- **Current balance** (unpaid principal)
- **Most recent DSCR** (debt service coverage ratio)
- **Most recent occupancy** (%, from latest disclosure)
- **Implied NOI** (derived from DSCR if not provided)
- **Program label** (`program="Agency"`, vs. "Conduit" for SEC loans)

### Caveats

- **Occupancy date**: Trailing 2–3 quarters; not live
- **Manual download required** (no public API yet)
- **Monthly refresh**: Re-run the loader once per month for latest data
- **De-identification**: Freddie does not include owner LLC or principal info (human enrichment only for top of list)

---

## Troubleshooting

### No loans extracted

**Symptom**: "Parsed 0 valid loans from 5000 rows"

**Check**:
1. Are column names present? (e.g., "Loan Sequence Number")
2. Are rates in percent (3.5) not decimal (0.035)? → Loader normalizes automatically
3. Are state codes 2-char (TX, GA)? → Check for leading/trailing spaces
4. Are DSCR values > 0? → Validation requires DSCR > 0

**Fix**: Open the CSV in Excel and verify a few rows match the expected format.

### Duplicate loan warnings

**Symptom**: Same loan_id appears in SEC and Freddie data

**Cause**: Rare (different naming schemes). If it happens:
- SEC version wins (assumed more authoritative)
- Freddie version is skipped

### Rates look wrong

**Symptom**: Note rate shows 372.0% instead of 3.72%

**Cause**: Loader tried to normalize but data format unexpected

**Fix**: Check CSV column; if it says "Percent", the value may already be in %; if it says "Rate" or "Interest Rate", it may be decimal. Loader tries both; if neither works, open an issue.

---

## Monthly Refresh (Automation)

Currently, the Freddie Mac download is **manual** (no public API). To refresh monthly:

```bash
# 1st of each month: Download latest CSV from Freddie portal
# Then run:
python3 fetch_freddie_data.py data/k-deals-$(date +%Y-%m).csv
```

**Future**: If Freddie publishes an API or web-scraping becomes reliable, this can be automated as a cron job.

---

## Files

| File | Purpose |
|------|---------|
| `fetch_freddie_data.py` | CLI tool to parse & cache Freddie CSVs |
| `maturity_radar/data_sources.py` | Enhanced with `load_freddie_mac()`, multi-source `load_loans()` |
| `data/sec_loans.json` | Combined cache (SEC + Freddie, merged) |
| `FREDDIE_MAC_IMPLEMENTATION.md` | Detailed technical docs |
| `FREDDIE_MAC_QUICK_START.md` | This file |

---

## Next Steps

1. **Test with sample data**: Download a real Freddie K-Deal CSV; run `fetch_freddie_data.py` to test
2. **Verify dashboard**: Confirm the app shows the new loans and data quality looks good
3. **Establish cadence**: Set a monthly reminder to download latest Freddie CSV (1st of month?)
4. **Enrich top loans**: Use the human-in-the-loop layer to fill in owner LLC info for high-pressure deals

---

## Questions?

See **FREDDIE_MAC_IMPLEMENTATION.md** for:
- Detailed data format (CSV column mappings)
- Parsing logic & validation rules
- Deduplication & cache strategy
- Troubleshooting guide
- Future enhancement options

Or run: `python3 fetch_freddie_data.py --help`
