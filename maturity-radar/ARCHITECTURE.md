# Freddie Mac Loader Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LEXERD CAPITAL MANAGEMENT                          │
│                     Multifamily Loan Maturity Radar                         │
└─────────────────────────────────────────────────────────────────────────────┘

                              DATA SOURCES (Inputs)
                              ════════════════════════

SEC EDGAR                 Freddie Mac MLPD      MLPD File           Sample Data
(Conduit CMBS)          (Agency K/SBL)       (Panel Data)       (Illustrative)
     │                        │                   │                    │
     ▼                        ▼                   ▼                    ▼
  sec_edgar.py          load_freddie_mac()    load_mlpd()      sample_data.py
     │                        │                   │                    │
     └────────────────────────┴───────────────────┴────────────────────┘
                               │
                               ▼
                    ORCHESTRATION LAYER
                    ═══════════════════════
              
              load_loans(source="auto", states=None)
              ─────────────────────────────────────────
                  1. Try SEC cache (174 loans)
                  2. Try Freddie Mac cache (if available)
                  3. Try MLPD file (if available)
                  4. Fall back to sample data (13 loans)
                  5. Merge results, dedupe by loan_id
                  6. Return (loans, source_label)

                               │
                               ▼
                        DATA CACHE (sec_loans.json)
                        ════════════════════════════
                      Combined: SEC + Freddie + MLPD
                      (240–290 loans in 8 Lexerd states)
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
            Watchlist        Scoring         Dashboard
            ────────         ──────          ─────────
            (filters)    (pressure calc)    (visualization)
                │              │              │
                └──────────────┴──────────────┘
                               │
                               ▼
                    EXPORT / VISUALIZATIONS
                    ═══════════════════════
                   (HTML, JSON, CSV, etc.)

```

## Data Flow: Freddie Mac K-Deal → Cache → Dashboard

```
1. USER DOWNLOADS
   ────────────────────────────────────────────────────────────────
   Navigate to: https://mf.freddiemac.com/investors/data
   Download: "K-Deal Loan-Level Disclosures" CSV
   Save to: data/k-deals-2025-01.csv

2. PARSE & VALIDATE
   ────────────────────────────────────────────────────────────────
   python3 fetch_freddie_data.py data/k-deals-2025-01.csv
                      │
                      ├─ Open CSV file
                      ├─ Read rows
                      ├─ Normalize column headers (case-insensitive)
                      ├─ For each row:
                      │   ├─ Extract: loan_id, state, units, rate, maturity, balance, DSCR
                      │   ├─ Validate: all required fields present and > 0
                      │   ├─ Normalize: rates (3.5→0.035), dates (multiple formats)
                      │   ├─ Filter: only target states (AL, FL, GA, KS, KY, LA, NC, TX)
                      │   └─ Create Loan object (program="Agency")
                      │
                      └─ Return list of Loan objects

3. MERGE & DEDUPE
   ────────────────────────────────────────────────────────────────
   merge_and_cache(freddie_loans)
           │
           ├─ Load existing SEC cache (data/sec_loans.json)
           │   174 Conduit CMBS loans (program="Conduit")
           │
           ├─ Merge by loan_id (SEC wins if duplicates)
           │   + All 174 SEC loans
           │   + 200–250 new Freddie loans (no overlap)
           │   ────────────────────
           │   = 374–424 total loans
           │
           └─ Write to data/sec_loans.json
               (both SEC and Freddie in one cache)

4. READ FROM CACHE
   ────────────────────────────────────────────────────────────────
   load_loans(source="auto")
           │
           ├─ Try: _load_sec_cache(data/sec_loans.json)
           │   ✓ Loads 374–424 merged loans
           │   └─ Return source="sec+freddie"
           │
           └─ If cache missing or corrupt:
               Try MLPD → Try sample data (fallback)

5. SCORE & VISUALIZE
   ────────────────────────────────────────────────────────────────
   app.py
       │
       ├─ Load loans (merged cache)
       ├─ Load market rate (10-yr UST + Freddie spread)
       ├─ Score each loan (maturity-pressure calc)
       ├─ Sort by pressure_score (desc)
       ├─ Display in dashboard / radar chart / table
       └─ Show: property name, city, state, pressure score, entry angle, why_now

```

## Component Interactions

### Key Classes & Functions

```python
# models.py
class Loan:
    loan_id: str           # Unique identifier
    property_name: str
    state: str            # State abbreviation
    units: int
    current_balance: float
    note_rate: float      # Decimal (0.035 = 3.5%)
    maturity: date
    most_recent_dscr: float
    occupancy: float      # Decimal (0.93 = 93%)
    program: str          # "Conduit" or "Agency"
    source_url: str

# data_sources.py
def load_freddie_mac(path, states, log) -> List[Loan]
    # Parse K-Deal/SBL CSV → Loan objects

def load_loans(source="auto", states=None) -> (List[Loan], str)
    # Orchestrate multi-source loading + merge

def save_sec_cache(loans, path) -> str
    # Serialize loans to JSON

# fetch_freddie_data.py (CLI)
main(csv_file, states, dry_run)
    # Entry point for user to load Freddie data
```

## Cache Strategy

### Why Single Unified Cache?

The system writes all loans (SEC + Freddie) to a single `data/sec_loans.json` cache because:

1. **Simpler app read**: The dashboard reads one file
2. **Faster load**: No need to merge at app startup
3. **Deduplication at source**: Freddie loader handles conflicts before cache
4. **Backward compatible**: Existing app code works unchanged

### Alternative (Not Implemented)

Could split into separate caches (`sec_loans.json` + `freddie_mac_loans.json`) and merge in `load_loans()`. This would:
- Separate concerns (each source in its own file)
- But add complexity to the reader
- Slower at app startup (multiple file loads)

Current approach is simpler and faster. Can be refactored later if needed.

## Testing & Validation

### Unit Tests (Implemented)
- ✅ CSV parsing with sample data
- ✅ State filtering
- ✅ Rate normalization
- ✅ Date parsing
- ✅ NOI derivation

### Integration Tests (Implemented)
- ✅ Load SEC cache
- ✅ Load auto mode (multi-source)
- ✅ Merge without duplicates
- ✅ Full scoring pipeline
- ✅ Mixed Conduit + Agency scoring

### Manual Tests (For User)
```bash
# 1. Download real Freddie CSV from investor portal
# 2. Dry-run validation
python3 fetch_freddie_data.py data/k-deals-2025-01.csv --dry-run

# 3. Load (for real)
python3 fetch_freddie_data.py data/k-deals-2025-01.csv

# 4. Verify dashboard
python3 app.py  # Should show updated loan count
```

## Performance Notes

### Load Time (Estimated)

- **SEC cache read**: 174 loans in ~50ms
- **Freddie parsing**: 250 loans from CSV in ~200ms
- **Merge + write**: All 424 loans in ~100ms
- **Total first load**: ~350ms
- **Subsequent loads**: ~50ms (cached)

### Memory Usage (Estimated)

- **174 SEC loans**: ~500 KB
- **250 Freddie loans**: ~750 KB
- **Total cache**: ~1.25 MB (small enough to load on every app request)

---

## Deployment Checklist

- [x] Code written and tested
- [x] Syntax verified
- [x] Integration verified (works with scoring, watchlist, etc.)
- [x] Documentation complete
- [x] Helper functions tested
- [x] CLI tool tested
- [ ] Real Freddie CSV downloaded (user action)
- [ ] First load run (user action)
- [ ] Dashboard verified with new loans (user action)
- [ ] Monthly cadence established (user action)

---

## Future Enhancements

### Tier 1 (Easy)
- [ ] Add "source" column to dashboard (show Conduit vs. Agency)
- [ ] Add confidence flags for partially-filled records
- [ ] Cache versioning (track which Freddie K-Deal file was used)

### Tier 2 (Medium)
- [ ] Unit tests for edge cases (empty CSV, corrupt data, etc.)
- [ ] Support for Fannie Mae DLY files (similar structure)
- [ ] Web UI for manual file upload (vs. CLI)

### Tier 3 (Hard / Blocked)
- [ ] Freddie API integration (when/if published)
- [ ] Web scraper for auto-detecting latest files
- [ ] MLPD subscription integration (if budget allows)
- [ ] Real-time data feed (replace quarterly refresh)

---

## Rollback Procedure

If Freddie data causes issues:

```bash
# 1. Remove Freddie loans from cache
rm data/freddie_mac_loans.json

# 2. Restore SEC-only cache (from version control or backup)
git checkout data/sec_loans.json
# or
cp data/sec_loans.json.backup data/sec_loans.json

# 3. Restart app
python3 app.py
```

The `load_loans()` function will fall back to SEC only, and app works as before.

---

## References

- **Freddie Mac Investor Portal**: https://mf.freddiemac.com/investors/data
- **K-Deal Performance Data**: https://mf.freddiemac.com/investors/performance-lookup
- **Implementation Details**: See FREDDIE_MAC_IMPLEMENTATION.md
- **Quick Start**: See FREDDIE_MAC_QUICK_START.md
