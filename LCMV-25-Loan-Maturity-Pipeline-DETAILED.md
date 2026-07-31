# LCMV-25: Stage 2 — Securitized Loan Maturity Pipeline

**Epic:** Stage 2 Deal Sourcing Engine  
**Stage:** 2 — Sourcing Intelligence  
**Status:** To Do  
**Priority:** High  
**Owner:** [Assigned Developer]  
**Dependencies:** LCMV-23, LCMV-24 (can be parallel)

---

## Executive Summary

Build an **automated, quantified deal sourcing pipeline** using Freddie Mac and Fannie Mae monthly loan tapes to identify maturing loans (1–3 year horizon) in secondary markets as off-market refinance opportunities. This is Lexerd's **proprietary deal pipeline** — the cornerstone of sourcing strategy.

**Strategic Impact:**
- Identifies $2–3B in maturing multifamily loans annually in target markets
- Flags deals with refinance stress (DSCR <1.25x, LTV >70%) **before** they hit the market
- Quantifies "maturity wall" as a sourcing signal (not qualitative)
- Creates repeatable monthly sourcing discipline (refresh tapes → score → alert)
- Potential pipeline: 50–100 deal opportunities annually in target markets (5–10 close rate = 3–5 deals/year)

---

## Problem Statement & Opportunity

### The Maturity Wall (2024–2027)

US commercial real estate faces a massive refinance cliff:
- **$2.0T in loans maturing 2024–2027** (CBRE, Q1 2024)
- **Multifamily segment: $450B+** (highest concentration)
- **Secondary markets underserved**: fewer lenders, higher refinance stress
- **Refinance risk drivers:**
  - Rates ↑200bps since 2021 originations (8% vs. 3%)
  - DSCR compression (was 1.40x, now stressed 1.15x)
  - LTV trapped (can't refi without capital injection)

### Lexerd's Thesis

Lexerd targets **off-market, distressed deals** in secondary markets where:
1. Owner/lender facing refinance maturity (12–24 months out)
2. DSCR <1.30x (can't refinance "clean")
3. LTV >65% (need equity partner)
4. Property class B/B- with operational upside
5. 70–300 units, <$50M value
6. Tier-1 secondary markets (Jacksonville, Fargo, Austin, Charlotte, etc.)

**Market Gap:** Most deal flow sources (CoStar, LoopNet, brokers) identify loans **after** they maturity. Lexerd's advantage: **identify maturity risk 12–24 months early**.

### Current State (Without LCMV-25)

```
Deal sourcing = manual + reactive:
- Broker relationships (slow, deal-dependent)
- Inbound leads (late-stage, already marketed)
- CoStar/LoopNet alerts (expensive, slow data)
- No systematic refinance signal

Result: Reactive pipeline, high competition, lower margins
```

### Target State (With LCMV-25)

```
Monthly automated pipeline:
1. Download Freddie Mac/Fannie Mae loan tapes (1st of month)
2. Parse 50K+ loans → extract multifamily subset
3. Filter: secondary markets, 70–300 units, <$50M
4. Score: DSCR, LTV, maturity risk, occupancy trends
5. Alert: Top 50–100 deals with refinance risk
6. Output: CSV of opportunity pipeline (property, owner, lender, maturity date)

Result: Proactive sourcing, first-mover advantage, direct outreach to lenders
```

---

## Technical Architecture

### Data Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Freddie Mac / Fannie Mae                           │
│  Monthly Loan Tape Data (B3 Fixed-Format, ~50K–70K loans per month)    │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │ Tape Download (Manual or Automated)│
        │ /data/tapes/fannie_mae_2024_08.txt │
        │ /data/tapes/freddie_mac_2024_08.txt│
        └────────────────┬───────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │ LCMV-25.1: loan_tape_parser.py             │
        │ Parse B3 fixed-format → structured records │
        │ - Extract 200+ fields per loan             │
        │ - Validate MSA codes                       │
        │ - Handle format variations                 │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
     DataFrame: 50K+ loans with structured data
     Columns: [loanid, property_addr, msa, origamt, curbal, rate, 
               maturity_date, occupancy, noi, property_type, units, ...]
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │ LCMV-25.2: loan_tape_parser.py             │
        │ filter_multifamily() + extract_loan_details│
        │ - Keep only multifamily (property_type=MF) │
        │ - Extract key fields: DSCR, LTV, maturity  │
        │ - Map property_state to target states      │
        │ - Keep if units 70–300 range               │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
     Filtered DataFrame: ~5K–8K multifamily loans
     (50K loans → 10–15% multifamily → units filter → 5–8K)
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │ LCMV-25.3: maturity_scorer.py              │
        │ Score loans by refinance risk              │
        │ - calculate_dscr() → 0–100 scale           │
        │ - calculate_ltv() → 0–100 scale            │
        │ - score_refinance_risk() → 0–100 composite │
        │ - Tier 1/2/3 classification                │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
     Scored DataFrame: ~5K loans with risk scores
     Columns: [loanid, dscr_score, ltv_score, maturity_score, risk_tier, ...]
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │ LCMV-25.4: secondary_market_filter.py      │
        │ Filter to Lexerd target markets            │
        │ - Keep only: GA, FL, AL, SC, NC, TX, KS    │
        │ - Keep if: 70–300 units                    │
        │ - Keep if: Class B/B-                      │
        │ - Keep if: <$50M acquisition value         │
        │ - Flag if: Maturity 12–24 months (urgent)  │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
     Opportunity DataFrame: ~200–500 deals
     (Tier 1 opportunity, risk >60, in-market, <$50M)
                         │
                         ├──────────────────────────┐
                         │                          │
                         ▼                          ▼
        ┌───────────────────────┐    ┌──────────────────────────┐
        │ LCMV-25.5:            │    │ LCMV-25.6:               │
        │ stress_analysis.py    │    │ alert_system.py          │
        │ +100bps rate scenario │    │ Rank by opportunity      │
        │ DSCR break threshold  │    │ Generate alert report    │
        └───────────────────────┘    └──────────────────────────┘
                         │                          │
                         ▼                          ▼
        ┌────────────────────────────────────────────┐
        │ Output: CSV + Alert Report                 │
        │ - opportunity_pipeline.csv (200–500 deals) │
        │ - alert_report.html (top 50 by priority)   │
        │ - Deal summary (owner, lender, maturity)   │
        └────────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │ LCMV-26: Pipeline Orchestrator             │
        │ Ingests opportunity pipeline                │
        │ Enriches with market/model data             │
        │ Re-scores with full 3M model                │
        │ Feeds into CRM/sourcing workflow            │
        └────────────────────────────────────────────┘
```

### Module Structure

```
calibration/
├── data/
│   ├── loan_tape_parser.py                    # ← LCMV-25.1
│   │   ├── parse_tape(filepath) → pd.DataFrame
│   │   ├── extract_loan_details(tape) → pd.DataFrame
│   │   ├── filter_multifamily(tape) → pd.DataFrame
│   │   └── validate_msa_codes(tape) → bool
│   │
│   ├── maturity_scorer.py                     # ← LCMV-25.2
│   │   ├── calculate_dscr(loan) → float
│   │   ├── calculate_ltv(loan) → float
│   │   ├── score_refinance_risk(loan) → float (0–100)
│   │   └── flag_target_opportunities(loans) → List[Dict]
│   │
│   ├── secondary_market_filter.py             # ← LCMV-25.3
│   │   ├── filter_target_states(loans) → List
│   │   ├── filter_property_criteria(loans) → List
│   │   └── apply_lexerd_filters(loans) → List
│   │
│   ├── stress_analysis.py                     # ← LCMV-25.4
│   │   ├── stress_scenario_100bps(loan) → Dict
│   │   ├── stress_scenario_200bps(loan) → Dict
│   │   └── calculate_refinance_cost(loan, rate_shock) → float
│   │
│   └── alert_system.py                        # ← LCMV-25.5
│       ├── match_lexerd_criteria(loan) → bool
│       ├── rank_by_opportunity(loans) → List
│       ├── generate_alert_report() → str
│       └── export_opportunity_pipeline() → CSV
│
├── tests/
│   └── test_loan_pipeline.py                  # ← LCMV-25.6
│       ├── TestTapeParser (8 tests)
│       ├── TestMaturityScorer (8 tests)
│       ├── TestSecondaryMarketFilter (6 tests)
│       ├── TestStressAnalysis (4 tests)
│       ├── TestAlertSystem (4 tests)
│       └── TestIntegration (2 tests)
│
└── docs/
    └── LOAN_PIPELINE.md                       # ← LCMV-25.7
        ├── Tape Format Reference
        ├── DSCR/LTV Calculation Formulas
        ├── Stress Scenario Methodology
        ├── Monthly Refresh Process
        └── Troubleshooting
```

---

## Sub-Tickets (Comprehensive Breakdown)

### LCMV-25.1: Loan Tape Parser
**Type:** Task  
**Acceptance Criteria:**
- [ ] `loan_tape_parser.py` parses Freddie Mac B3 fixed-format tapes
- [ ] Extracts 30+ key fields per loan (see Field Extraction below)
- [ ] Handles 2+ years of historical tapes (24-month backfill)
- [ ] Validates MSA codes against official mapping
- [ ] Filters to multifamily (property_type = "MF" or "MH")
- [ ] Skips invalid/incomplete records, logs warnings
- [ ] Performance: parse 50K loans <30 seconds
- [ ] All functions documented

**Field Extraction (Minimum 30 fields):**
```
Loan Identifiers:
- loan_id (unique identifier)
- msa_code (market)
- state (property state)

Property Details:
- property_address
- property_city
- property_type (MF, SFR, retail, industrial, etc.)
- units (number of residential units)
- property_class (A, A-, B, B+, B-, C)
- year_built
- occupancy (0.0–1.0)

Financial Terms:
- original_loan_amount
- current_loan_balance
- interest_rate
- maturity_date
- origination_date
- remaining_term_months

Loan Performance:
- current_principal_balance
- current_interest_rate
- loan_age_months
- months_to_maturity

Underwriting:
- noi (net operating income, estimated or actual)
- dscr (debt service coverage ratio)
- ltv (loan-to-value)
- occupancy_rate

Lender:
- lender_name
- servicer_name

Securitization:
- deal_id (security identifier)
- security_number (pool)
```

**Data Validation:**
```python
# Tape format validation:
- MSA code is 5 digits (e.g., "12220")
- Maturity date format: YYYYMM (e.g., "202512")
- Interest rate 0.01–0.15 (1%–15%, realistic range)
- Units 1–1000 (valid multifamily range)
- DSCR 0.50–2.50 (realistic range)
- LTV 0.40–0.95 (realistic range)
- Occupancy 0.00–1.00 (0%–100%)

# Error handling:
- Missing fields → flag as incomplete, skip or default
- Invalid data type → log error, use None
- Outlier values (DSCR >2.5) → log warning, keep record
```

---

### LCMV-25.2: Maturity Scorer
**Type:** Task  
**Description:** Score each loan by refinance risk (DSCR, LTV, maturity timeline).

**Acceptance Criteria:**
- [ ] Implements DSCR calculation (from tape data or estimate if missing)
- [ ] Implements LTV calculation
- [ ] Implements composite refinance risk score (0–100 scale)
- [ ] Tier classification: Tier 1 (Critical), Tier 2 (High), Tier 3 (Monitor)
- [ ] Handles missing data (defaults to neutral score)
- [ ] All calculations documented with formulas

**Refinance Risk Scoring:**

```
Scoring Dimensions:

1. DSCR Score (Weight: 40%)
   - DSCR < 1.10 → Score 100 (critical stress)
   - DSCR 1.10–1.20 → Score 80–100 (high stress)
   - DSCR 1.20–1.30 → Score 60–80 (moderate stress)
   - DSCR 1.30–1.40 → Score 40–60 (manageable)
   - DSCR > 1.40 → Score 0–40 (healthy, low stress)

2. LTV Score (Weight: 30%)
   - LTV > 80% → Score 100 (trapped in security)
   - LTV 70–80% → Score 80–100 (high leverage)
   - LTV 60–70% → Score 40–80 (moderate leverage)
   - LTV 50–60% → Score 20–40 (healthy leverage)
   - LTV < 50% → Score 0–20 (low leverage)

3. Maturity Urgency (Weight: 30%)
   - Months to maturity < 6 → Score 100 (imminent)
   - Months to maturity 6–12 → Score 80 (urgent)
   - Months to maturity 12–18 → Score 60 (upcoming)
   - Months to maturity 18–24 → Score 40 (near-term)
   - Months to maturity > 24 → Score 0 (future)

Composite Score:
risk_score = (dscr_score * 0.40) + (ltv_score * 0.30) + (maturity_score * 0.30)

Tier Classification:
- Tier 1 (Critical): risk_score > 75 → immediate refinance pressure
- Tier 2 (High): 60 ≤ risk_score ≤ 75 → near-term risk
- Tier 3 (Monitor): 40 ≤ risk_score < 60 → normal monitoring
- Below 40: low priority
```

**Tier Definitions:**

| Tier | Risk Score | DSCR | LTV | Maturity | Sourcing Signal |
|------|---|---|---|---|---|
| 1 (Critical) | >75 | <1.25 | >70% | <12m | **Immediate** — lender seeking solution |
| 2 (High) | 60–75 | 1.25–1.35 | 65–70% | 12–24m | **Near-term** — owner stressed |
| 3 (Monitor) | 40–60 | 1.35–1.45 | 60–65% | >24m | **Future** — watch trend |

---

### LCMV-25.3: Secondary Market Filter
**Type:** Task  
**Description:** Filter loans to Lexerd's target markets and property criteria.

**Acceptance Criteria:**
- [ ] Filters by target states: GA, FL, AL, SC, NC, TX, KS
- [ ] Filters by property criteria: 70–300 units, Class B/B-, <$50M value
- [ ] Estimates acquisition value: (loan_balance / LTV) = property value
- [ ] Ranks by Lexerd scoring (Tier 1 > Tier 2 > Tier 3)
- [ ] Outputs filtered, ranked opportunity list

**Filtering Logic:**

```python
def apply_lexerd_filters(loans: List[Dict]) -> List[Dict]:
    """
    Apply all Lexerd investment criteria filters.
    
    Returns: filtered list ranked by opportunity
    """
    
    # 1. Geographic: Target states only
    loans = [l for l in loans if l['state'] in ['GA', 'FL', 'AL', 'SC', 'NC', 'TX', 'KS']]
    
    # 2. Property type: Multifamily only
    loans = [l for l in loans if l['property_type'] == 'MF']
    
    # 3. Unit count: 70–300 units
    loans = [l for l in loans if 70 <= l['units'] <= 300]
    
    # 4. Property class: B/B-/B+
    loans = [l for l in loans if l['property_class'] in ['B', 'B-', 'B+']]
    
    # 5. Acquisition value: <$50M
    # property_value = loan_balance / LTV
    loans = [l for l in loans if (l['current_balance'] / l['ltv']) < 50_000_000]
    
    # 6. Maturity window: 12–36 months (near-term refinance risk)
    loans = [l for l in loans if 12 <= l['months_to_maturity'] <= 36]
    
    # 7. DSCR stress: <1.35x (can't refinance clean)
    loans = [l for l in loans if l['dscr'] < 1.35]
    
    # 8. LTV stress: >65% (trapped capital)
    loans = [l for l in loans if l['ltv'] > 0.65]
    
    # Rank by risk tier (Tier 1 first)
    loans = sorted(loans, key=lambda l: l['risk_tier'], reverse=False)
    
    return loans
```

---

### LCMV-25.4: Stress Analysis
**Type:** Task  
**Description:** Model rate stress scenarios to identify deals most vulnerable to rate increases.

**Acceptance Criteria:**
- [ ] Implements `stress_scenario_100bps(loan)` — +100 basis point rate shock
- [ ] Implements `stress_scenario_200bps(loan)` — +200 basis point rate shock
- [ ] Calculates DSCR under stress (new debt service with higher rates)
- [ ] Identifies loans that break DSCR >1.25x under stress
- [ ] Estimates refinance cost (premium to refinance distressed)

**Stress Analysis Formula:**

```
Current Debt Service = (Principal * rate) / (1 - (1 + rate)^-years)

Stress Scenarios:
- 100bps scenario: new_rate = current_rate + 0.01
- 200bps scenario: new_rate = current_rate + 0.02

Stressed Debt Service = (Principal * new_rate) / (1 - (1 + new_rate)^-years)

Stressed DSCR = NOI / Stressed Debt Service

Refinance Cost Calculation:
- Base refinance cost: 2–3% of new loan balance
- Distressed refinance premium: +1–2% (higher rates, lender caution)
- Total cost: $Refinance = Loan_Balance * (0.03 to 0.05)

Owner's Equity Impact:
- Original equity: Property_Value - Loan_Balance
- After stress refinance: Original_Equity - Refinance_Costs - Rate_Adjustment
- Equity compressed? → Need capital partner
```

**Stress Output:**

```python
{
    "loan_id": "FM12345",
    "original_dscr": 1.32,
    "current_rate": 0.055,
    "stressed_dscr_100bps": 1.15,  # Breaks 1.25x threshold
    "stressed_dscr_200bps": 1.02,  # Critically stressed
    "breaks_refinance_floor": True,  # 100bps pushes below 1.25x
    "refinance_cost_estimate": 1200000,  # $1.2M @ 3% of $40M balance
    "equity_compression_pct": 8.5,  # % of equity lost to refinance
    "sourcing_signal": "CRITICAL"  # Owner needs capital partner
}
```

---

### LCMV-25.5: Alert System & Ranking
**Type:** Task  
**Description:** Rank deals by opportunity and generate structured alert report.

**Acceptance Criteria:**
- [ ] Ranks loans by Lexerd opportunity score
- [ ] Flags deals matching all Lexerd criteria (DSCR, LTV, maturity, market, units)
- [ ] Generates opportunity pipeline CSV
- [ ] Generates alert report HTML/PDF
- [ ] Outputs owner/lender contact info (when available)

**Opportunity Ranking Formula:**

```
opportunity_score = (risk_tier_weight * 40) + 
                    (rent_growth_signal * 20) +
                    (dscr_spread * 20) +
                    (maturity_urgency * 20)

Where:
- risk_tier_weight: Tier 1 = 100, Tier 2 = 75, Tier 3 = 50
- rent_growth_signal: Market employment/pop growth (from LCMV-23/24)
- dscr_spread: Distance from 1.25x threshold (higher spread = worse)
- maturity_urgency: Months to maturity (12m = 100, 36m = 50)

Top 100 deals = highest opportunity_score
```

**Alert Report Structure:**

```
LEXERD DEAL OPPORTUNITY PIPELINE
Generated: 2024-08-01
Data Source: Freddie Mac Monthly Tape (July 2024)

═══════════════════════════════════════════════════════════
TIER 1 CRITICAL OPPORTUNITIES (12 deals)
═══════════════════════════════════════════════════════════

Rank 1: Bridgeview Apartments, Jacksonville FL
- Property: 245 units, Class B, built 2008
- MSA: Jacksonville FL (12220)
- Loan: $32.5M (Freddie Mac LOAN_ID: FM98765)
- Maturity: Nov 2025 (15 months)
- DSCR: 1.18 (below 1.25 refi floor)
- LTV: 72% (capital needed)
- Stress Test: 100bps → DSCR 1.01 (CRITICAL)
- NOI: $2.8M
- Estimated Refi Cost: $975K
- Market Signal: Jacksonville employment +3.4% YoY (strong market)
- Owner: [Extracted from tape if available]
- Lender: Freddie Mac

═══════════════════════════════════════════════════════════
TIER 2 HIGH OPPORTUNITIES (48 deals)
═══════════════════════════════════════════════════════════
[Similar detail for each]

═══════════════════════════════════════════════════════════
TIER 3 MONITORING (150+ deals)
═══════════════════════════════════════════════════════════
[Summary list only]

METHODOLOGY:
- Scoring based on DSCR stress, LTV, maturity timeline, market fundamentals
- Rank 1–100 represent highest sourcing opportunity
- All deals: secondary markets (target states), 70–300 units, <$50M value
```

---

### LCMV-25.6: Comprehensive Unit Tests
**Type:** Task  
**Acceptance Criteria:**
- [ ] 32+ test cases covering all modules
- [ ] Test coverage >90% on all loan pipeline modules
- [ ] Tape parser tests: format validation, field extraction, filtering
- [ ] Scorer tests: DSCR/LTV calculations, tier classification
- [ ] Filter tests: geographic, unit count, property class
- [ ] Stress analysis tests: rate shock scenarios
- [ ] Alert ranking tests: opportunity scoring
- [ ] Integration test: end-to-end tape → pipeline

**Test Suite Structure:**

```python
class TestTapeParser:
    # 8 tests
    def test_parse_tape_freddie_mac_format(self): pass
    def test_parse_tape_fannie_mae_format(self): pass
    def test_extract_loan_details_all_fields(self): pass
    def test_filter_multifamily_only(self): pass
    def test_validate_msa_codes_accuracy(self): pass
    def test_handle_missing_fields(self): pass
    def test_performance_50k_loans_under_30s(self): pass
    def test_historical_tape_format_variations(self): pass

class TestMaturityScorer:
    # 8 tests
    def test_calculate_dscr_from_tape(self): pass
    def test_calculate_ltv_accuracy(self): pass
    def test_score_refinance_risk_tier1_vs_tier2(self): pass
    def test_score_refinance_risk_tier3_vs_monitor(self): pass
    def test_dscr_weighting_40_percent(self): pass
    def test_ltv_weighting_30_percent(self): pass
    def test_maturity_weighting_30_percent(self): pass
    def test_missing_data_defaults(self): pass

class TestSecondaryMarketFilter:
    # 6 tests
    def test_filter_target_states_only(self): pass
    def test_filter_units_70_to_300_range(self): pass
    def test_filter_property_class_b_only(self): pass
    def test_filter_acquisition_value_under_50m(self): pass
    def test_filter_maturity_12_to_36_months(self): pass
    def test_combined_filters_expected_output_count(self): pass

class TestStressAnalysis:
    # 4 tests
    def test_stress_100bps_dscr_recalculation(self): pass
    def test_stress_200bps_dscr_recalculation(self): pass
    def test_breaks_refi_floor_detection(self): pass
    def test_refinance_cost_estimation(self): pass

class TestAlertSystem:
    # 4 tests
    def test_opportunity_ranking_tier1_first(self): pass
    def test_alert_report_generation_html(self): pass
    def test_export_opportunity_pipeline_csv(self): pass
    def test_top_100_deals_selection(self): pass

class TestIntegration:
    # 2 tests
    def test_end_to_end_tape_to_pipeline(self): pass
    def test_historical_backtest_known_deals(self): pass
```

---

### LCMV-25.7: Documentation & Monthly Refresh Process
**Type:** Task  
**Deliverable:** `LOAN_PIPELINE.md`
**Sections:**
- Freddie Mac/Fannie Mae tape format reference (B3 fixed format)
- DSCR/LTV calculation formulas (with examples)
- Stress scenario methodology
- Monthly refresh checklist
- Data freshness SLA
- Troubleshooting (parsing errors, missing fields, format changes)
- Historical backtest results (accuracy validation)

---

## Acceptance Criteria (LCMV-25 Overall)

### Functionality
- [ ] Parse Freddie Mac/Fannie Mae tapes (2+ years historical)
- [ ] Identify 500+ target opportunities in annual maturity window
- [ ] Score all loans by refinance risk (0–100 scale, Tier 1/2/3)
- [ ] Stress test: model +100bps and +200bps rate scenarios
- [ ] Filter to secondary markets, 70–300 units, <$50M value
- [ ] Rank by opportunity and generate alert system
- [ ] Performance: parse 50K loans and score in <30 seconds

### Code Quality
- [ ] All functions documented with docstrings
- [ ] Type hints on all signatures
- [ ] Follows Lexerd code style
- [ ] Logging at appropriate levels (INFO, WARNING, ERROR)

### Testing
- [ ] 32+ unit tests with >90% coverage
- [ ] All mocked (no real API calls)
- [ ] Performance benchmarks included
- [ ] pytest passes with all green

### Documentation
- [ ] LOAN_PIPELINE.md complete
- [ ] Tape format reference documented
- [ ] Calculation formulas with examples
- [ ] Monthly refresh process documented
- [ ] Troubleshooting guide

---

## Integration Points

### Upstream Dependencies
- Freddie Mac monthly tape (public, free download)
- Fannie Mae monthly tape (public, free download)
- PropertyProfile structure (calibration/models/thesis.py)

### Downstream Consumers
- **LCMV-26 Pipeline Orchestrator** — Ingests opportunity pipeline
- **Enrichment modules (LCMV-23, LCMV-24)** — Add market/employment signals
- **Sourcing CRM workflow** — Alert distribution to deal team
- **Historical backtesting** — Validate sourcing signal accuracy

---

## Data Sources

| Source | Coverage | Cost | Freshness | Format |
|--------|----------|------|-----------|--------|
| Freddie Mac | ~40% of market | Free | Monthly (day 6 post month-end) | B3 fixed format |
| Fannie Mae | ~40% of market | Free | Monthly (day 6 post month-end) | B3 fixed format |
| Data Aggregators | 100% coverage | $$$ | Real-time | Normalized APIs |

**Recommendation:** Use Freddie Mac + Fannie Mae public data (covers ~80% of market) for MVP; integrate CoStar/LoopNet for remaining coverage in production.

---

## Success Metrics

| Metric | Target | Verification |
|--------|--------|---|
| Deal identification accuracy | 90%+ vs. manual | Backtest against known deals |
| Tier classification accuracy | Tier 1 captures 95%+ of actual problem loans | Validation vs. post-maturity data |
| Pipeline size | 200–500 annual opportunities | Output deal count |
| Time to pipeline | <30 minutes (monthly) | Performance benchmark |
| False positive rate | <10% | Track deals that didn't refinance |
| Code coverage | >90% | pytest --cov report |

---

## Timeline & Sequencing

1. **LCMV-25.1** (Tape Parser) — Foundation for all downstream modules
2. **LCMV-25.2** (Scorer) → **LCMV-25.3** (Filter) → **LCMV-25.4** (Stress Analysis) [parallel possible]
3. **LCMV-25.5** (Alert System) — Depends on all above
4. **LCMV-25.6** (Tests) — Throughout, test-first
5. **LCMV-25.7** (Documentation) — Final polish

---

## Definition of Done

- ✅ All 7 sub-tickets completed
- ✅ pytest calibration/tests/test_loan_pipeline.py → all green
- ✅ Coverage >90% on all loan pipeline modules
- ✅ LOAN_PIPELINE.md complete
- ✅ Sample monthly pipeline generated and verified
- ✅ Code review approved
- ✅ Integrated into LCMV-26 orchestrator

---

## References

- Freddie Mac Datasets: https://www.freddiemac.com/research/datasets/
- Fannie Mae Research: https://www.fanniemae.com/research-and-insights/
- Loan Tape Documentation: B3 Loan Level Dataset specifications
- Lexerd Thesis: LEXERD_THESIS.md
- PropertyProfile: calibration/models/thesis.py

---

*Created: 2026-07-31 | Owner: [TBD]*
