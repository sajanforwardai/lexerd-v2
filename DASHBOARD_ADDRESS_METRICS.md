# Dashboard Address Metrics — Corrected Analysis

**Date:** August 7, 2026  
**Status:** Final Analysis (273 Dashboard Loans)

---

## Executive Summary

**CORRECTED METRICS FOR 273 DASHBOARD LOANS:**

| Metric | Count | % |
|--------|-------|---|
| **Total Loans** | 273 | 100% |
| **With Addresses** | 249 | 91.2% |
| **Without Addresses** | 24 | 8.8% |

---

## Address Coverage Breakdown

### Raw Freddie Mac Data
- **With addresses:** 26 (9.5%)
- **Without addresses:** 247 (90.5%)

### Phase 1 Discovery (Google Maps + County Assessor)
- **Found:** 223 (90.3% of missing properties)
- **Not found:** 24 (9.7% of missing properties)

### Combined Coverage (Raw + Phase 1)
- **Total with addresses:** 249 (91.2%)
- **Total without addresses:** 24 (8.8%)

---

## Phase 1 Coverage Percentages

### Coverage of Missing Properties
- **Phase 1 found 90.3% of the 247 missing properties**
- 223 discovered / 247 missing = 90.3%

### Coverage of Total Dashboard Loans
- **Phase 1 contributed 81.7% of all addresses**
- 223 found / 273 total = 81.7%

### Note on "Phase 1 Coverage %"
When we say "Phase 1 coverage is 91.2%", we mean:
- **Combined (raw + Phase 1) = 91.2% of dashboard loans now have addresses**
- Raw data alone: 9.5%
- Phase 1 added: 81.7%
- Total: 91.2%

---

## 24 Missing Properties (Without Addresses)

| # | Property Name | City | State | County | Units |
|---|---|---|---|---|---|
| 1 | Fountains Matthews | (unknown) | TX | — | 0 |
| 2 | Arzano | (unknown) | TX | — | 0 |
| 3 | 2000 Penn | (unknown) | TX | — | 0 |
| 4 | Danker Village Apartments | (unknown) | TX | — | 0 |
| 5 | Ashton Parc | (unknown) | FL | — | 0 |
| 6 | Cobblestone at Eagle Harbor | (unknown) | FL | — | 0 |
| 7 | Butternut Ridge Apartments | (unknown) | TX | — | 0 |
| 8 | Country Glenn Apartments | (unknown) | TX | — | 0 |
| 9 | Flats at Dunlap | (unknown) | KS | — | 0 |
| 10 | The Flamingo | (unknown) | TX | — | 0 |
| 11 | Defeased | (multiple) | GA | — | 402 |
| 12 | Wimberley Hill Country | Wimberley | TX | Hays | 130 |
| 13 | Clear Lake Park | Clear Lake | TX | Harris | 170 |
| 14 | Palm Beach Gardens | West Palm Beach | FL | — | 160 |
| 15 | Defeased | (multiple) | TX | — | 634 |
| 16 | Magnolia Springs | Magnolia | TX | Montgomery | 160 |
| 17 | Southern Garden | Valparaiso | FL | Okaloosa | 84 |
| 18 | Topeka Heights Residential | Topeka | KS | Shawnee | 150 |
| 19 | Sugar Land Technology | Sugar Land | TX | Fort Bend | 200 |
| 20 | Fort Worth Midtown | Fort Worth | TX | Tarrant | 210 |
| 21 | The Club at Crystal Lake | Deerfield Beach | FL | Broward | 125 |
| 22 | MEADOWS PLACE SENIORS VILLAGE | Stafford | TX | Fort Bend | 182 |
| 23 | Magnolia Flats Apartments | Balcones Heights | TX | Bexar | 54 |
| 24 | THE BLUFFS | Junction City | KS | Geary | 544 |

---

## Phase 2 Target

**24 properties** need county assessor lookups to reach 95%+ coverage.

**Expected Phase 2 Results:**
- If Phase 2 finds 15 addresses: 264/273 = 96.7%
- If Phase 2 finds 20 addresses: 269/273 = 98.5%

---

## Dashboard Updates

### Fixed Today
1. ✅ Removed property name placeholders from address column
2. ✅ Address column now shows actual address or "—" (empty placeholder)
3. ✅ Dashboard metrics update dynamically with cleaned dataset (273 loans)
4. ✅ KPIs recalculate when loans added/removed

### Metrics Tracked
- **Loans on watch:** Total loans in filtered watchlist (dynamic)
- **Severe:** Loans with projected DSCR < 1.0 (dynamic)
- **Maturing within 24 months:** Loans with maturity ≤ 24 months (dynamic)
- **Total loan balance:** Sum of current balances (dynamic)

---

## Conclusion

**Current Dashboard State:**
- ✅ 249/273 loans (91.2%) have verified addresses
- ✅ 24/273 loans (8.8%) need Phase 2 work
- ✅ Dashboard displays clean data with no misleading placeholders
- ✅ All metrics update dynamically based on filtered watchlist
- ✅ Ready for Phase 2 County Assessor implementation

---
