# Freddie Mac Multifamily Data Loader — Implementation Notes

## Summary

This document describes the Freddie Mac K-Deal and SBL multifamily loan loader implementation for Lexerd Capital Management's maturity-radar. The system adds ~200–250 high-quality agency multifamily loans (property-level DSCR, NOI, balance, occupancy) to the existing 39-loan SEC EDGAR Conduit CMBS database.

## Architecture

### Data Flow

```
Freddie Mac Investor Portal (https://mf.freddiemac.com/investors/data)
    ↓ [Manual download or API future]
K-Deal & SBL CSV files (loan-level disclosures)
    ↓ [fetch_freddie_data.py]
load_freddie_mac() parser (CSV → Loan objects)
    ↓ [merge by loan_id, SEC wins conflicts]
Combined cache: data/sec_loans.json (both SEC + Freddie)
    ↓ [load_loans() orchestrator]
Dashboard, scoring, watchlist
```

### Key Files

1. **`maturity_radar/data_sources.py`**
   - `load_freddie_mac(path, states, log)` — Parse a K-Deal/SBL CSV file
   - `save_freddie_mac_cache()` — Write loans to JSON (legacy; now merged into SEC cache)
   - `_load_freddie_mac_cache()` — Read cached Freddie loans from JSON
   - `load_loans(source="auto", states)` — Enhanced orchestrator: tries SEC → Freddie → MLPD → sample
   - Helper functions: `_num()`, `_rate()`, `_parse_date()` (re-used from sec_edgar.py & mlpd.py)

2. **`fetch_freddie_data.py`** (executable)
   - CLI tool to download, parse, and cache Freddie Mac CSV files
   - Supports glob patterns and state filtering
   - Merges with existing SEC EDGAR cache (no duplicates)
   - Usage: `python3 fetch_freddie_data.py data/k-deals-2025-01.csv --states TX,GA`

3. **Models & Integration**
   - `models.py` unchanged — Loan dataclass already matches Freddie disclosure schema
   - Loans carry `program="Agency"` (vs. Conduit for SEC loans)
   - Source tracking: `source_url` points to Freddie investor portal for each loan

---

## Data Format: K-Deal & SBL CSV

### Field Mapping

Freddie Mac publishes K-Deal (securitized) and SBL (whole loans) disclosures as CSV files. Column names vary by report; the loader normalizes common variants:

| Logical Field | CSV Column Variants | Type | Example | Notes |
|---|---|---|---|---|
| **Loan ID** | Loan Sequence Number, LoanSequenceNumber, Loan ID, lnno | string | FHMS-K7X-0142 | Unique identifier per loan |
| **State** | Property State, State, code_st | string (2-char) | TX, GA | Required; used for filtering |
| **Units** | Units, Number of Units, cnt_rsdntl_unit | int | 184 | Required; >0 for inclusion |
| **Note Rate** | Note Rate, Interest Rate, rate_int | float | 3.50 or 0.035 | Percent (3.50) or decimal (0.035); normalized to decimal |
| **Maturity Date** | Maturity Date, dt_mty | date | 02/01/2027 | Multiple formats supported |
| **Current Balance** | Current Balance, Current UPB, Unpaid Balance, amt_upb_endg | float | 13,950,000 | Dollar amount; required |
| **Original Balance** | Original Balance, Original UPB, original amount | float | 14,800,000 | Falls back to current if missing |
| **DSCR** | Most Recent DSCR, Debt Service Coverage Ratio, rate_dcr | float | 1.29 | Required; >0 for inclusion |
| **Occupancy** | Most Recent Occupancy, Occupancy Rate | float | 93 or 0.93 | Percent (93) or decimal (0.93); normalized to decimal |
| **NOI** | Most Recent NOI, Net Operating Income, noi | float | 910,000 | **Optional**; derived from DSCR if missing |
| **Property Name** | Property Name, property_name | string | Aggieland Flats | Fallback: `Loan {loan_id}` |
| **City** | City, city | string | College Station | Fallback: state abbreviation |
| **County** | County, county | string | Brazos | Optional |
| **Deal Name** | Deal Name, deal_name, Dealname | string | FHMS-K7X | Optional; used for tracking |

### Example Rows (Illustrative)

The sample_data.py file shows real-world examples:

```python
Loan("FHMS-K7X-0142", "Aggieland Flats", "College Station", "Brazos", "TX", 184,
     2017, 14_800_000, 13_950_000, 0.0372, date(2027, 2, 1), True,
     910_000, 1.29, 0.93,
     program="Agency", deal="FHMS-K7X", 
     source_url="https://mf.freddiemac.com/investors/performance-lookup")
```

---

## Parsing Logic & Validation

### Normalization Steps

1. **Column header matching** (case-insensitive, strip whitespace)
   - Handles variations: "Loan Sequence Number", "LoanSequenceNumber", "Loan ID"

2. **Numeric parsing** (`_num()`)
   - Strips whitespace, removes commas, handles NaN/None/"."
   - Returns float; default 0.0 on error

3. **Rate normalization** (`_rate()`)
   - Input: 3.50% (as decimal 3.50) or 0.035 (already decimal)
   - Output: decimal (0.035 in both cases)
   - Rule: if value > 1, divide by 100; else use as-is

4. **Date parsing** (`_parse_date()`)
   - Tries formats in order: MM/DD/YYYY, MM-DD-YYYY, YYYY-MM-DD, DDMMMYYYY
   - Returns Python date object or None on failure

5. **Occupancy normalization**
   - If > 1, assume percent; divide by 100 to get decimal
   - Otherwise use as decimal (0.0–1.0)

### Inclusion Criteria

A loan is included if:
- Loan ID and state are present (non-empty after stripping)
- State matches filter (if provided) — default: AL, FL, GA, KS, KY, LA, NC, TX
- Units > 0
- Note rate > 0
- Maturity date is valid
- Current balance > 0
- DSCR > 0

Rows with missing/invalid core fields are silently skipped (logged with row count).

### NOI Derivation

If "Most Recent NOI" is missing or ≤ 0, NOI is derived:

```
NOI = DSCR × Current Balance × Note Rate
```

This is mathematically sound (DSCR = Debt Service / NOI) and matches the approach in mlpd.py.

---

## Integration with Existing Systems

### Loan Deduplication

When `load_loans(source="auto")` combines multiple sources, priority is:
1. **SEC EDGAR** (Conduit CMBS, program="Conduit")
2. **Freddie Mac** (Agency multifamily, program="Agency")
3. **MLPD** (Agency, de-identified)
4. **Sample data**

A loan_id appearing in both sources uses the SEC version (assumed more authoritative / human-enriched for Lexerd's top-of-list). Freddie Mac fills gaps (new loan_ids not in SEC cache).

### Cache Strategy

- **Single unified cache**: `data/sec_loans.json` contains both SEC and Freddie loans (merged)
  - Reason: The app reads one cache file; combining sources keeps the loader simple
  - Trade-off: SEC loans remain intact; Freddie loans only add new records
  
- **Freddie-only cache** (legacy): `data/freddie_mac_loans.json` is written but not read by default
  - Future: could be used if Freddie loans are queried separately (e.g., by program)

### Source URL Tracking

Each loan carries `source_url` for user attribution:
- SEC loans: Link to the SEC EDGAR filing (human-browsable)
- Freddie loans: `https://mf.freddiemac.com/investors/data` (generic; future: deep link if available)

---

## Monthly Refresh Process

### Current Blocker: Manual Download Requirement

**Key Issue**: Freddie Mac does not publish a public API for K-Deal/SBL loan-level disclosures. Files must be downloaded manually from the Investor Portal.

**Process**:
1. User navigates to https://mf.freddiemac.com/investors/data
2. Finds the latest "K-Deal Loan-Level Disclosures" or "SBL Loan-Level Disclosures" CSV
3. Downloads and saves to `data/k-deals-2025-02.csv` (or similar)
4. Runs: `python3 fetch_freddie_data.py data/k-deals-2025-02.csv`
5. Cache updates; app refreshes

### Future Enhancements (Post-MVP)

1. **API Automation** (if Freddie publishes API access)
   - Rewrite `fetch_freddie_data.py` to fetch directly
   - Schedule as cron job or Lambda

2. **Scraper** (web scraping K-Deal index)
   - If Freddie UI stabilizes, could auto-discover latest file URLs
   - Risk: brittle; Freddie updates UI without warning

3. **Combine with MLPD**
   - MLPD is panel data (Q1, Q2, Q3, Q4 per loan per year)
   - Could pull origination dates, full rate history
   - Requires Freddie subscription; better data than public disclosure

4. **Rate Updates**
   - Current implementation fetches only once per load
   - Could schedule `fetch_current_rate()` separately to refresh refinance benchmark

### Automation: Cron Job Example

Once Freddie publishes an API (or if scraping is added):

```bash
# Monthly (first of each month, 6 AM UTC)
0 6 1 * * cd /workspace/lexerd2/maturity-radar && python3 fetch_freddie_data.py --auto-fetch 2>&1 | mail -s "Freddie Mac update" sajan@...
```

---

## Data Quality Notes

### Strengths of Freddie K-Deal / SBL Disclosure

- **Property-level detail**: Not aggregate/metro-only like FHFA PUDB
- **Multifamily-specific**: No mixed CRE (CMBS conduit has office, retail, etc.)
- **Real metrics**: Current balance, note rate, maturity, NOI, DSCR, occupancy
- **Live updates**: Freddie updates disclosures quarterly
- **No de-identification**: Property names, cities, counties (unlike MLPD)

### Limitations vs. SEC EDGAR CMBS

| Metric | Freddie K-Deal/SBL | SEC Conduit CMBS |
|---|---|---|
| Program | Agency (Freddie-owned) | Conduit (pooled/securitized) |
| Typical size | $50M–$500M each | $1B–$3B pools |
| Loan-level fill | Always complete | Often sparse (only P&L summary) |
| Property address | Yes | Yes |
| Owner LLC info | Minimal | Minimal (public filer name only) |
| Human enrichment | None (automated) | Possible (if Lexerd has done research) |

### Occupancy Caveat

Freddie disclosures include "Most Recent Occupancy" (typically trailing 2–3 quarters). If missing in a file, the loader defaults to 0.0 (not a sign of vacancy — just missing data). App scoring should handle this gracefully.

---

## Testing & Validation

### Unit Tests (to add)

```python
# test_freddie_loader.py
def test_load_freddie_mac_with_sample_csv():
    """Verify parser extracts loans and normalizes rates/dates."""
    # Create temp CSV with known data
    # Assert: correct number of loans, rate is decimal, maturity is date, etc.

def test_merge_no_duplicates():
    """Verify load_loans(source="auto") dedupes and preserves SEC priority."""

def test_state_filter():
    """Verify --states filtering works; non-matching states dropped."""

def test_noi_derivation():
    """Verify NOI is derived correctly when missing: DSCR * Balance * Rate."""
```

### Manual Testing

1. **With sample data**: Create a small K-Deal CSV; verify parsing
   ```bash
   python3 fetch_freddie_data.py test_data/mini-kdeal.csv --dry-run
   ```

2. **With real Freddie file**: Download latest K-Deal CSV; parse a state
   ```bash
   python3 fetch_freddie_data.py data/k-deals-2025-01.csv --states TX
   ```

3. **Verify dashboard sees merged data**:
   ```bash
   python3 app.py  # Should show loans, "source" label in data source
   ```

---

## Troubleshooting

### No loans extracted from CSV

**Symptom**: "Parsed 0 valid loans from 5000 rows"

**Causes**:
1. Column names don't match any expected variant
   - **Fix**: Add new variants to `get_col()` call in `load_freddie_mac()`
2. State filter too strict
   - **Fix**: `--all-states` or adjust `--states`
3. Data validation failing (e.g., missing maturity, DSCR = 0)
   - **Fix**: Inspect a few rows manually; may need schema adjustment

### Duplicate loan_ids after merge

**Symptom**: Dashboard shows same loan twice (different source)

**Causes**:
1. SEC and Freddie have same loan_id (unlikely; different naming schemes)
   - **Fix**: Check loan_id normalization (Freddie: FHMS-K7X-0142, SEC: CONDUIT-2017-5-42)
2. Freddie file has duplicates within itself
   - **Fix**: Check source file; may need pre-processing

### Rates look wrong (e.g., 372.0% instead of 3.72%)

**Symptom**: Note rate is 300+ (should be <10%)

**Cause**: `_rate()` normalization not triggered (value was already in wrong form)

**Fix**: Check CSV column; if it has "Percent", pre-divide by 100 before calling `_rate()`.

---

## Current Implementation Status

### ✅ Implemented

- `load_freddie_mac()` function in `data_sources.py`
  - Flexible CSV parsing (case-insensitive column headers)
  - State filtering (default: 8 Lexerd states)
  - Validation & error handling
  - NOI derivation from DSCR

- `load_loans()` enhancement
  - Multi-source orchestration (SEC → Freddie → MLPD → sample)
  - Deduplication by loan_id (SEC priority)
  - Source tracking in return label

- `fetch_freddie_data.py` CLI tool
  - Parse single or multiple CSV files (glob patterns)
  - Merge with existing SEC cache
  - Dry-run mode for validation
  - Clear logging & error messages

- Integration with existing Loan model & scoring
  - No schema changes needed
  - `program="Agency"` label for Freddie loans
  - Source attribution via URL

### ⏳ Blocked / Future

**Current Blocker: Manual Download Step**

Freddie Mac data is not available via public API. The loader expects CSV files to be downloaded manually and placed in `data/`. This is acceptable for MVP (quarterly refresh, Sajan downloads once per month) but not ideal for production automation.

**Options**:
1. **Accept manual step**: Documented, ~5 min per month
2. **Build scraper**: Auto-detect latest files on Freddie portal (fragile)
3. **Wait for Freddie API**: Unlikely in near term; Freddie prioritizes institutional investors
4. **Use MLPD subscription**: Better data, but costs & requires separate login

**Recommendation**: Ship MVP with manual download; add automation layer if/when Freddie publishes API or Sajan allocates time for scraper.

---

## Files Created/Modified

### New Files
- `fetch_freddie_data.py` — CLI automation script
- `FREDDIE_MAC_IMPLEMENTATION.md` — This document

### Modified Files
- `maturity_radar/data_sources.py`
  - Added: `load_freddie_mac()`, `save_freddie_mac_cache()`, `_load_freddie_mac_cache()`
  - Added: `_num()`, `_rate()`, `_parse_date()` helpers (duplicated from sec_edgar.py & mlpd.py)
  - Enhanced: `load_loans()` for multi-source orchestration & deduplication

### Unchanged
- `models.py` — Loan dataclass already matches Freddie schema
- `app.py`, `radar.py`, `scoring.py` — No changes needed; work with merged cache
- `rates.py`, `watchlist.py` — No changes

---

## References

- **Freddie Mac Investor Portal**: https://mf.freddiemac.com/investors/data
- **Sample Data**: `maturity_radar/sample_data.py` (illustrative, Freddie-shaped)
- **SEC EDGAR Loader**: `maturity_radar/sec_edgar.py` (for comparison)
- **MLPD Loader**: `maturity_radar/mlpd.py` (panel data, de-identified)
- **Existing Cache Format**: `data/sec_loans.json` (JSON, Loan objects serialized)
