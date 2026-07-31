# LCMV-25: Securitized Loan Maturity Pipeline

**Stage:** 2 — Data Integration  
**Estimate:** 16 hours  
**Status:** To Do  
**Priority:** High  

---

## Summary

Parse Freddie Mac and Fannie Mae monthly loan tape data (free, public) to identify maturing loans (1–3 year horizon) as a sourcing signal. Maturing loans = refinance opportunity = off-market deal potential. Creates proprietary deal pipeline.

---

## Problem Statement

**Current State:**
- No systematic sourcing of distressed/off-market deals
- Relying on broker networks and inbound leads
- Missing $162B maturity wall opportunity (2024–2027)

**Target State:**
- Automated identification of maturing loans in target markets
- Flag deals with refinance risk (DSCR <1.25x, high LTV)
- 500+ deal opportunities annually from maturity pipeline

---

## Deliverables

### 1. `calibration/data/loan_tape_parser.py` (5 hours)

Parse Freddie Mac/Fannie Mae monthly loan tapes.

**Data Sources:**
- Freddie Mac: https://www.freddiemac.com/research/datasets/
- Fannie Mae: https://www.fanniemae.com/research-and-insights/
- Monthly tapes with security-level detail

**Functions:**
```python
def parse_tape(filepath: str) -> pd.DataFrame
def extract_loan_details(tape: pd.DataFrame) -> pd.DataFrame
def filter_multifamily(tape: pd.DataFrame) -> pd.DataFrame
```

**Field Extraction:**
- Loan ID
- Property address, MSA, state
- Original loan amount, current balance
- Interest rate, maturity date
- Current occupancy, NOI
- DSCR, LTV

**Data Quality:**
- Validate MSA codes against mapping
- Flag incomplete records
- Handle data format variations (annual updates)

### 2. `calibration/data/maturity_scorer.py` (4 hours)

Score loans by refinance risk.

**Functions:**
```python
def calculate_dscr(loan: Dict) -> float
def calculate_ltv(loan: Dict) -> float
def score_refinance_risk(loan: Dict) -> float
def flag_target_opportunities(loans: List[Dict]) -> List[Dict]
```

**Scoring Logic:**
- DSCR <1.25x = refinance stress (weight: 40%)
- LTV >70% = refinance difficulty (weight: 30%)
- Maturity <18 months = urgent (weight: 30%)
- Combined score: 0–100 (higher = more distressed)

**Thresholds:**
- Tier 1 (Critical): Score >75 (immediate refinance pressure)
- Tier 2 (High): Score 60–75 (near-term risk)
- Tier 3 (Monitor): Score 40–60 (normal monitoring)

### 3. `calibration/data/secondary_market_filter.py` (3 hours)

Filter loans to target markets.

**Logic:**
- Keep loans in LCMV target states (GA, FL, AL, SC, NC, TX, KS)
- Filter for 70–300 unit properties
- Filter for Class B/B-
- Filter for <$50M acquisition value

**Output:**
- Target opportunity list with refinance risk scores
- Enrichment-ready for pipeline

### 4. `calibration/data/stress_analysis.py` (2 hours)

Model rate stress scenarios.

**Functions:**
```python
def stress_scenario_100bps(loan: Dict) -> Dict  # +100 bps rate
def stress_scenario_200bps(loan: Dict) -> Dict  # +200 bps rate
def calculate_refinance_cost(loan: Dict, rate_shock: float) -> float
```

**Use Case:**
- How many loans break DSCR >1.25x if rates rise 200 bps?
- Identify deals most vulnerable to rate increases

### 5. `calibration/data/alert_system.py` (2 hours)

Flag deals matching Lexerd criteria.

**Functions:**
```python
def match_lexerd_criteria(loan: Dict) -> bool
def rank_by_opportunity(loans: List[Dict]) -> List[Dict]
def generate_alert_report() -> str
```

**Logic:**
- DSCR <1.30x ✓
- LTV >65% ✓
- Maturity <24 months ✓
- In target market ✓
- Property fits Lory playbook ✓

### 6. Unit Tests (4 hours)

**File:** `calibration/tests/test_loan_pipeline.py`

**Test Coverage:**
- Tape parsing accuracy (sample 100 records)
- DSCR/LTV calculation correctness
- MSA filtering
- Stress scenario modeling
- Alert accuracy (false positive rate <10%)
- Performance: Parse 10k loans <5 seconds

---

## Acceptance Criteria

- [ ] Parse Freddie Mac tapes (2+ years of history)
- [ ] Identify 500+ target opportunities in 2026 maturity window
- [ ] Stress test: model +200 bps rate scenario
- [ ] Performance: <5 seconds to parse/score 10k loans
- [ ] Alert system flags deals matching Lexerd criteria
- [ ] Historical backtest: signal predicts actual deals?
- [ ] All tests pass (>95% coverage)
- [ ] Documentation: How to refresh tapes monthly

---

## Technical Notes

### Tape Format

Freddie Mac/Fannie Mae provide:
- Fixed-format text files (FNMA B3 format)
- ~200 fields per loan
- Monthly refresh (updated 6 days after month end)
- Public access (no authentication required)

### Data Freshness

- Pipeline runs monthly (day 10)
- Identifies maturity windows updated every 30 days
- Historical backfill: 24 months of tapes

---

## Success Metrics

- **Coverage:** 80%+ of commercial multifamily loans in target markets
- **Accuracy:** Refinance risk score within 10 points of lender assessment
- **Speed:** Process entire month's tape <5 seconds
- **Signal Quality:** Backtest shows 60%+ of flagged deals actually trade in next 12 months

---

## Sourcing Impact

**Annual Opportunity:**
- US multifamily loan volume: $100B+ maturing annually
- Target markets: ~$2–3B annually
- Addressable deals: 50–100 per year
- Lexerd capacity: 3–5 deals per year
- Pipeline yield: 5–10% close rate

---

## Integration Points

**Input:**
- Freddie Mac/Fannie Mae monthly tapes (free download)

**Output:**
- Deal opportunity list (CSV/JSON)
- Alert report (weekly/monthly)

**Downstream:**
- LCMV-26 pipeline orchestrator ingests alerts
- Feeds into deal sourcing workflow

---

*Ticket owner: [Your name]  
Created: 2026-07-31  
Updated: 2026-07-31*
