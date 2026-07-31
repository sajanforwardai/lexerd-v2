# Maturity Radar — Prototype Scope (Texas & Georgia)

**Goal.** Prove the sourcing pipeline end to end on two of Lexerd's real markets: produce a
**ranked, outreach-ready list of small multifamily properties in TX and GA whose securitized
loans are maturing in 2026–2028 and are likely to struggle to refinance cleanly** — each row
carrying an owner lead and a plain-English "why now."

**Why TX + GA.** Both are core Lexerd markets. TX: The Lory of Bryan, Big Spring, College
Station, Hunter's Point. GA: The Lory of Augusta, Perimeter, Savannah. Sun Belt, heavily
securitized, active small-multifamily trade — the ideal proving ground.

**What it maps to (Lexerd's own words).** Their Investment Strategy page:
*"Lexerd moves quickly to acquire suitable assets with attractive cash flows by securing
properties at below market prices via off-market transactions"* and *"we place emphasis on our
proprietary investment acquisition process."* Maturity Radar is a tool for exactly that: find
below-market, off-market deals early and move quickly.

---

## The pipeline (four stages)

### Stage 1 — Loan universe: "who has maturing debt"
Build the list of multifamily loans in TX/GA maturing 2026–2028.

- **Primary source:** CMBS asset-level disclosure filed with the SEC under Reg AB II
  (**ABS-EE filings, EX-102 asset data, machine-readable XML**). These carry, per loan:
  property name + address + state, property type, original/current balance, **maturity date,
  interest rate, most-recent DSCR, occupancy.** This is exactly the data Sajan read at KBRA.
- **Secondary source:** Freddie Mac Multifamily securitized-loan datasets + FHFA Public Use
  Database (agency multifamily loans: property size, unpaid principal balance, seller/servicer).
- **Filter:** property state ∈ {TX, GA} · property type = multifamily · maturity ∈ 2026-01…2028-12.

> Build note: confirm the exact ABS-EE retrieval path on EDGAR during Stage 1 (filing index →
> EX-102 XML). Treat the source mechanics as the first thing to validate, not an assumption.

### Stage 2 — Refinance-pressure score: "who's in trouble"
For each loan, compute a 0–100 pressure score from fields already in the loan data:

- **Maturity proximity** — sooner = higher pressure.
- **Rate shock** — a low in-place rate (e.g. 3–4%) maturing into today's ~6% agency market is the
  squeeze; bigger gap = higher pressure.
- **DSCR** — at or below ~1.0–1.20 means the property can't comfortably cover debt and won't
  qualify to refinance at a higher rate. Strongest single signal.
- **Occupancy / debt yield** — where available, softening occupancy compounds the risk.

Output: the score plus a one-line **"why now"** ("$8.2M loan at 3.6% maturing Mar-2027; DSCR 1.08;
a refi at 6% pushes coverage below 1.0").

### Stage 3 — Owner enrichment: "who do we call"
Join each flagged property's address to county ownership records.

- **Texas:** county Appraisal Districts (CADs) — e.g. Brazos CAD (Bryan/College Station),
  Howard CAD (Big Spring) — for owner entity + mailing address; TX Comptroller / SOSDirect for
  the LLC's registered agent/principals.
- **Georgia:** county tax assessors (many on **qPublic.net** — clean structured access) — e.g.
  Richmond (Augusta), Chatham (Savannah), DeKalb/Fulton (Perimeter) — plus **GSCCCA** for deeds
  and the GA Corporations Division for entity principals.

### Stage 4 — Ranked output
A CSV + a simple Streamlit page (reuse the pattern already built for the Underwriting Assistant):
property · city/county · est. units · owner entity · maturity date · in-place rate · DSCR ·
**pressure score** · "why now" · source links. Sorted by score, filterable to Lexerd's box.

---

## Honest scope boundaries (state these in any demo)

- **Securitized loans only.** CMBS + agency K-deals are covered; **bank / local-lender loans are
  invisible.** This surfaces a real, valuable *subset* of motivated sellers — not all of them.
- **Texas is a non-disclosure state** — sale prices aren't public. Value is estimated from
  assessed value and loan balance, not verified comps.
- **LLC opacity.** Owners are usually entities; identifying the human principal needs a Secretary
  of State lookup and is imperfect.
- **Contact = mailing address / registered agent**, not a warm phone number. This *prioritizes*
  outreach; it doesn't replace the relationship, which is where Lexerd's edge already lives.
- **v1 is a batch pipeline** producing a list, not a live-updating platform.

---

## Prototype boundaries — depth over breadth

Do **not** attempt all 254 TX + 159 GA counties. Prove the pipeline on **~6 target counties**
covering Lexerd's actual footprint:

| State | Counties (market) |
|---|---|
| TX | Brazos (Bryan/College Station), Howard (Big Spring) |
| GA | Richmond (Augusta), Chatham (Savannah), DeKalb + Fulton (Perimeter) |

Stage 1–2 (loan data + scoring) run statewide for TX/GA from the CMBS/agency data; Stage 3
(owner enrichment) is done only for the **top ~20 scored properties** in those counties.

---

## Milestones (buildable increments)

1. **Loan universe.** Parse one recent CMBS ABS-EE filing (or a Freddie MF dataset), filter to
   TX/GA multifamily maturing 2026–28, emit a clean loan table. *(Proves the data is reachable.)*
2. **Pressure score.** Compute + rank; hand-sanity-check the top names. *(Proves the signal.)*
3. **Owner enrichment.** For the top ~20, pull county owner records in the 6 target counties;
   prove the address → owner join. *(Proves the lead is actionable.)*
4. **Output.** Streamlit list + CSV + "why now." *(Proves the deliverable.)*
5. **Demo narrative.** "Here are 20 TX/GA small-multifamily owners with agency/CMBS debt maturing
   into a refi they'll struggle with — ranked, with who to call, from public data."

**Minimum demoable slice:** Milestones 1–2 plus owner lookups for ~5 properties. That alone shows
the whole idea working on real data.

## Tech
Python (EDGAR/Freddie ingestion, pandas scoring) · county data via public assessor portals ·
output as CSV + Streamlit (reuse existing pattern) · **no paid APIs, all free public sources** ·
tested core scoring logic, same as the Underwriting Assistant.

## What it proves
An end-to-end **sourcing** pipeline on real public data in Lexerd's actual markets, built on the
exact loan-level data Sajan surveilled at KBRA — honest about covering securitized loans only,
and about being a prototype of the widen-later production version.
