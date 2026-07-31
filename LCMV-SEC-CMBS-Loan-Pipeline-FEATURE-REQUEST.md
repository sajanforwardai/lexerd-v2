# Stage 2 - Securitized SEC Loan Maturity Pipeline

**Feature Request Title:** LCMV-48: Securitized SEC Loan Maturity Pipeline (Private-Label CMBS)  
**Status:** CONDITIONAL_GO (pending LCMV-37 stability validation)  
**Priority:** Medium (complementary to LCMV-37)  
**Stakeholder:** Lexerd Capital Management  
**Created:** 2026-07-31  

---

## Executive Summary

Extend the loan maturity pipeline (LCMV-37: GSE channel) to include private-label securitized multifamily loans via SEC filings (424B5 prospectuses, 10-D servicer reports, 8-K events). This closes the coverage gap from 41% (GSE-only) to 80-90% of multifamily loan market, unlocking ~$57.7B in 2026 CMBS maturity opportunities that competitors miss.

**Strategic Value:**
- **Market gap:** Freddie Mac/Fannie Mae cover GSE channel (41% of originations); SEC captures private-label CMBS (40-50%)
- **Addressable deals:** 2026 CMBS maturity wall = $76.6B-$146.2B; ~$57.7B with default risk
- **First-mover advantage:** 8-K filings flag distress 30-60 days before formal default designation
- **Competitive moat:** Data is public, but integration quality + early detection window = defensible

---

## Problem Statement

### Current State (LCMV-37 GSE-Only)
```
Loan maturity pipeline identifies maturing GSE loans (Freddie Mac/Fannie Mae):
- Coverage: ~41% of multifamily market ($118.4B of $289B originations)
- Data source: B3 monthly tapes (free, public, Freddie Mac + Fannie Mae)
- Timeliness: Weekly updates, 1-2 week lag
- Signal: Strong (real, official data)

Gap: Missing 40-50% of multifamily loans in private-label CMBS channel
```

### Target State (LCMV-37 + LCMV-48)
```
Unified loan maturity pipeline spans both channels:
- GSE channel (LCMV-37): Freddie Mac/Fannie Mae B3 tapes (41% coverage)
- CMBS channel (LCMV-48): SEC filings prospectuses + servicer reports (40-50% coverage)
- Combined: 80-90% market coverage
- Early warning: 8-K events flag stress before servicer designation

Result: 80-90% addressable multifamily market, unified sourcing signal
```

---

## Requirements & Scope

### Data Sources (Priority Order)

#### Priority 1: CMBS Prospectuses (Form 424B5)
**What:** Initial loan-level tape at securitization closing  
**When:** One-time per deal (origination snapshot)  
**Coverage:** All SEC-filed CMBS deals (JPMorgan, Bank of America, UBS, Wells Fargo, etc.)  
**Key Data:**
- Property address, units, class, year built
- Loan ID, original balance, current balance
- Interest rate, maturity date, amortization
- DSCR, LTV, occupancy (if disclosed)
- Owner/sponsor names
- Loan schedule (property-by-property detail)

**Extraction:**
- Format: PDF with tables + loan schedules (OCR + table parsing)
- Effort: 60-95 hours per 100 deals
- Accuracy: 85%+ (tables more reliable than prose)
- Access: SEC EDGAR (free via data.sec.gov API)

**Example Search:**
```
SEC EDGAR Form 424B5 + keywords: "multifamily", "apartment", "residential"
CIK: 0001576455 (JPMorgan Securitizations)
```

#### Priority 2: Servicer Reports (Form 10-D)
**What:** Monthly/quarterly performance updates  
**When:** Monthly (typically 1-2 month lag vs. B3 tapes)  
**Coverage:** Every CMBS deal has servicer reports  
**Key Data:**
- Current balance, payment status (performing/60+ delinquent/default)
- Occupancy trends, rent data (sometimes)
- Maturity dates, extensions, modifications
- Reserve account balances
- Loan modifications, workout agreements

**Extraction:**
- Format: Structured tables (easier to parse than prospectuses)
- Effort: 24-35 hours per 100 deals
- Accuracy: 90%+ (table-based)
- Frequency: Monthly updates (vs. weekly for B3)

**Value:** Tracks loan evolution; identifies deterioration between origination and maturity

#### Priority 3: Material Events (Form 8-K)
**What:** Loan defaults, extensions, workouts, refinances  
**When:** Event-driven (real-time)  
**Coverage:** Critical events only  
**Key Data:**
- Event type (default, extension, modification, payoff)
- Event date, effective date
- New terms (if modification)
- Servicer actions (special servicing, liquidation)

**Extraction:**
- Format: Prose narrative (NLP required)
- Effort: 80-120 hours (complex NLP)
- Accuracy: 70-80% (prone to parsing errors)
- **Early warning value:** Flags distress 30-60 days before standard reporting

**Value:** Early warning signal (~3-4 week advantage over 10-D updates)

#### Priority 4: Operator 10-K Filings (Stretch Goal)
**What:** Large MF operator annual reports (Blackstone, Starwood, etc.)  
**When:** Annual  
**Coverage:** Only large public operators (~20-30% of market)  
**Effort:** 120-180 hours (highly unstructured)  
**Note:** Low priority for interview; skip unless late in project

---

### Feature Architecture (Proposed)

```
SEC Loan Pipeline (LCMV-48)
├── Data Sources
│   ├── 424B5 Prospectuses (loan origination tapes)
│   ├── 10-D Servicer Reports (monthly updates)
│   └── 8-K Material Events (early warnings)
│
├── Data Extraction Layer
│   ├── SEC EDGAR API client (query + download filings)
│   ├── PDF parser (424B5: loan schedules, tables)
│   ├── 10-D extractor (structured tables)
│   └── 8-K NLP classifier (event detection)
│
├── Data Enrichment Layer
│   ├── Match SEC loans to LCMV-37 (dedupe GSE vs. CMBS)
│   ├── Extract loan metrics (same as B3: DSCR, LTV, maturity)
│   ├── Classify loan status (performing/workout/default)
│   └── Calculate maturity urgency (months to maturity)
│
├── Scoring Layer
│   ├── Reuse LCMV-37 maturity_scorer.py (same Tier 1/2/3 logic)
│   ├── Apply secondary_market_filter.py (Lexerd criteria)
│   └── Apply stress_analysis.py (rate shock scenarios)
│
└── Alert System
    ├── Unified pipeline combining B3 + SEC loans
    ├── Rank by opportunity (Tier 1 critical first)
    ├── Flag "SEC-only" deals (not in B3, private-label advantage)
    └── Export: opportunity_pipeline.csv (unified sourcing list)
```

---

## Sub-Tickets (Proposed Decomposition)

### LCMV-48.1: SEC EDGAR API Client
**Estimate:** 12 hours  
**Scope:**
- Query SEC EDGAR API for CMBS deals
- Download 424B5 prospectuses (PDF)
- Download 10-D servicer reports
- Implement caching (365d TTL, public data)
- Error handling (missing filings, network errors)

### LCMV-48.2: Prospectus Loan Schedule Parser
**Estimate:** 20 hours  
**Scope:**
- Parse loan schedules from 424B5 PDFs
- Extract property details + loan terms
- Table parsing (PDF → structured data)
- OCR for older deals (pre-2010 format variations)
- Validation (DSCR, LTV ranges; flag outliers)

### LCMV-48.3: Servicer Report Extractor
**Estimate:** 12 hours  
**Scope:**
- Extract performance data from 10-D forms
- Parse monthly/quarterly tables
- Track current balance, payment status
- Identify delinquencies, workouts
- Calculate months to maturity

### LCMV-48.4: 8-K Event Classifier (Optional)
**Estimate:** 16 hours  
**Scope:**
- Parse 8-K event descriptions
- Classify event type (default, extension, payoff, etc.)
- Extract key dates and terms
- Flag early warning signals
- **Note:** Lower priority; NLP is complex

### LCMV-48.5: Loan Deduplication & Matching
**Estimate:** 8 hours  
**Scope:**
- Match SEC loans to LCMV-37 B3 loans (if in both systems)
- Dedupe on property address + loan amount
- Identify "SEC-only" deals (private-label advantage)
- Merge loan records (combine B3 + SEC data)

### LCMV-48.6: Unified Scoring & Alerts
**Estimate:** 8 hours  
**Scope:**
- Reuse LCMV-37 scoring (maturity_scorer.py, secondary_market_filter.py, stress_analysis.py)
- Apply to SEC loans
- Combine B3 + SEC opportunities
- Rank unified opportunity list
- Export: opportunity_pipeline.csv (all sources)

### LCMV-48.7: Comprehensive Testing
**Estimate:** 12 hours  
**Scope:**
- 24+ test cases (prospectus parsing, 10-D extraction, matching, scoring)
- Mock SEC filing data (sample prospectuses, servicer reports)
- Performance: parse 100 deals in <5 minutes
- Coverage: >90% on extraction modules
- Integration: validate B3 + SEC unified pipeline

### LCMV-48.8: Documentation & Deployment
**Estimate:** 8 hours  
**Scope:**
- SEC_LOAN_PIPELINE.md (setup guide, data source reference)
- Deployment guide (scheduled monthly updates)
- Known limitations (OCR accuracy, 10-D lag, data gaps)
- Troubleshooting (malformed filings, missing fields)

**Total Estimate: 96 hours (~2.4 work weeks, assuming sequential)**

---

## Acceptance Criteria

### Functionality
- [ ] Query SEC EDGAR API for CMBS deals (JPMorgan, BofA, UBS, Wells Fargo, etc.)
- [ ] Parse 424B5 prospectuses (loan schedules, property details, loan terms)
- [ ] Extract 10-D servicer reports (monthly performance data)
- [ ] Identify 100+ multifamily loans from SEC filings in test dataset
- [ ] Extract loan metrics: property address, units, class, DSCR, LTV, maturity date, owner
- [ ] Match SEC loans to B3 loans (dedupe via address + balance matching)
- [ ] Identify "SEC-only" deals (not in Freddie Mac/Fannie Mae, private-label)
- [ ] Score SEC loans using LCMV-37 logic (Tier 1/2/3, stress testing)
- [ ] Rank unified opportunity list (B3 + SEC combined, Tier 1 first)
- [ ] Flag early warning signals from 8-K events (optional, if time permits)

### Code Quality
- [ ] All extraction functions documented (docstrings, examples)
- [ ] Type hints on all signatures
- [ ] Error handling for malformed PDFs, missing data
- [ ] Logging at appropriate levels (INFO, WARNING, ERROR)
- [ ] Follows Lexerd code style (PEP 8, 88-char lines)

### Testing
- [ ] 24+ unit tests covering extraction modules
- [ ] Test coverage >90% on core parsers
- [ ] Mock SEC filing data (sample 424B5, 10-D)
- [ ] Performance: parse 100 deals in <5 minutes
- [ ] Integration test: B3 + SEC pipeline end-to-end

### Documentation
- [ ] SEC_LOAN_PIPELINE.md (setup, troubleshooting, data source reference)
- [ ] Deployment guide (monthly refresh schedule)
- [ ] Known limitations (OCR accuracy, data freshness, coverage gaps)
- [ ] Example usage (query API, parse prospectus, score loans)

---

## Council Recommendation & Conditions

**Verdict: CONDITIONAL_GO (62% Confidence)**

**Recommendation:**
Build SEC pipeline IF LCMV-37 (GSE pipeline) is >95% reliable. If B3 has bugs or uncertainty, SEC adds opportunity cost and weakens demo quality. Data breadth matters less than execution quality for interview.

**Conditions for GO:**
1. **B3 pipeline stable:** LCMV-37 passes >95% of tests, <2% parsing errors on 1000+ deals
2. **Scope ruthlessly defined:** Start with 424B5 + 10-D only (skip 8-K initially)
3. **Parsing accuracy 85%+:** Transparent error reporting (show what fails)
4. **SEC covers 25-50 deals in demo:** Enough to show "80-90% coverage" narrative, not full production

**If conditions met:** Build LCMV-48 as secondary feature (bonus for interview narrative)

**If conditions NOT met:** Focus 100% on LCMV-31 (Census/Zillow) + LCMV-45 (Pipeline Orchestrator)

---

## Interview Strategy

**If SEC built:** "I identified the 40-50% market gap Freddie Mac misses. SEC CMBS filings are where private-label deals hide. We parse prospectuses to find maturing loans before they hit the market. Combined with B3, we have 80-90% market coverage — the industry-wide view competitors can't match."

**If SEC skipped:** "We start with Freddie Mac/Fannie Mae — 41% of market, public data, weekly updates, zero friction. GSE deals are where the most distress is. Once this works perfectly, adding SEC CMBS is trivial (same scoring logic, different data source)."

---

## Risk Assessment

| Risk | Probability | Mitigation |
|------|---|---|
| PDF parsing brittle (OCR fails) | Medium | Start with clean modern prospectuses (2015+); older deals have worse OCR |
| 10-D lag (1-2 months) reduces early warning | Medium | Use 8-K for real early warning (optional, later) |
| SEC data already commoditized (competitors have it) | High | Moat is integration quality, not data access; focus on speed + accuracy |
| Scope creep (tries to parse 8-K, 10-K, too much) | High | Ruthlessly limit to 424B5 + 10-D; 8-K is optional stretch |
| Time overrun (takes 120+ hours, misses interview) | Medium | Cap at 96 hours; stop and ship if time runs out |
| Interviewers don't care about SEC coverage | Medium | They care about execution quality first, data breadth second; prioritize B3 polish |

---

## Success Metrics

| Metric | Target | Verification |
|--------|--------|---|
| Prospectus parsing accuracy | 85%+ | Test on 50 sample prospectuses, compare extracted data to manual validation |
| Loan coverage | 100+ loans extracted from test dataset | Count unique loans in output |
| "SEC-only" deal identification | Accurate matching to B3 | Manual spot-check: 10 SEC deals, verify not in B3 |
| Unified ranking | Tier 1 deals ranked correctly | Verify risk scores match LCMV-37 logic |
| Performance | <5 min for 100 deals | Benchmark parse + scoring time |
| Code coverage | >90% on extraction modules | pytest --cov report |

---

## Timeline & Sequencing

**Proposed:** Build LCMV-48 AFTER LCMV-31 (Census/Zillow) and LCMV-45 (Pipeline Orchestrator) are complete.

**Reason:** LCMV-31 + LCMV-45 are on critical path for interview demo. SEC is bonus. If time remains (week 5-6), build LCMV-48.

**Preferred sequence:**
1. ✅ LCMV-30 (BLS Integration) — Done
2. ✅ LCMV-37 (Freddie Mac/Fannie Mae Loan Pipeline) — Done
3. 🔄 LCMV-31 (Census & Zillow) — Next priority
4. 🔄 LCMV-45 (Pipeline Orchestrator) — Then this
5. ⏳ LCMV-48 (SEC CMBS Pipeline) — If time remains (optional)

---

## Definition of Done

- ✅ SEC EDGAR API client functional (query + download filings)
- ✅ Prospectus parser extracts 85%+ of loan data accurately
- ✅ Servicer report extractor functional (10-D performance data)
- ✅ Loan deduplication/matching working (B3 ↔ SEC cross-reference)
- ✅ Unified scoring pipeline combines B3 + SEC deals
- ✅ 24+ unit tests, >90% coverage
- ✅ SEC_LOAN_PIPELINE.md complete
- ✅ End-to-end test: SEC + B3 unified opportunity pipeline working
- ✅ Demo data: 25-50 SEC deals included in sample pipeline
- ✅ Code review approved

---

## References

- **Council Evaluation:** `/workspace/council/lexerd-cmbs-decision/council-evaluation.md`
- **Corpus Research:** `/workspace/corpus/financial-services/sec-multifamily-data.md`
- **LCMV-37 (GSE Pipeline):** LCMV-37-Loan-Maturity-Pipeline-DETAILED.md
- **SEC EDGAR API:** https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- **CMBS Prospectus Format:** https://www.sifma.org/ (CMBS documentation)
- **Freddie Mac/Fannie Mae Coverage:** "2024 Freddie Mac Multifamily Volume" press release

---

*Created: 2026-07-31 | Status: CONDITIONAL_GO | Recommendation: Build after LCMV-31 + LCMV-45 if time permits*
