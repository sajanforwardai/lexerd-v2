# Maturity Radar

A refinance-pressure **watchlist** for small multifamily — a prototype built for Lexerd Capital's
markets (Texas & Georgia). It ranks securitized multifamily loans by how hard they will be to
refinance at today's rate, so a buyer can build the relationship — or bring the leverage — ahead
of the owner's maturity.

> **Not a motivated-seller list.** Refinance pressure times a *conversation*, not a sale. In
> today's market the dominant resolution is extend / modify / recap, not a forced sale — so this
> is a **cultivation and negotiating-leverage layer**, most useful on deals you are already
> looking at ("this owner has a 2027 maturity and a broken exit — here's the clock you're
> negotiating against").

This scope comes straight from a 5-round adversarial council (verdict: **CONDITIONAL_GO, 70%** —
see `../../council/maturity-radar/council-evaluation.md`). The council was blunt: as a shipped
*product* this is a NO (a 20-year shop isn't identification-constrained); as a **scoped, honest
demonstration of credit judgment** it's the stronger artifact.

## What it does

```
Freddie-shaped loan universe (TX/GA)
    -> score       maturity proximity + rate shock + projected-refi-DSCR  ->  0-100 pressure
    -> rank        filter to the box, sort by pressure
    -> enrich      hand-curated owner lead for the top of the list (human-in-the-loop)
    -> output      watchlist + "why now" + entry angle (purchase / recap / rescue equity)
```

The signal that makes it more than a maturity calendar: **projected refinance DSCR** =
`NOI / (current balance × today's rate)`. A loan covering fine at 3.5% can be un-refinanceable at
6%, and the equity paydown needed to clear a lender's DSCR floor is what times the outreach. That
is the KBRA loan-surveillance skill, pointed at sourcing.

## Run it

```bash
python3 radar.py               # print the TX/GA watchlist
python3 -m pytest tests/       # 20 tests, scoring hand-verified
streamlit run app.py           # interactive watchlist
```

## What it can't see — say these out loud

- **Securitized loans only.** Freddie/agency disclosure is covered; **community-bank paper is
  invisible.** A real subset of the market, not all of it.
- **Refinance pressure ≠ a willing seller.** Extend / modify / rescue-capital dominate; the signal
  front-runs any forcing event by 12–24 months. That's why it's a cultivation queue.
- **Refinance pressure ≠ value-add upside — and they can be anti-correlated.** A property squeezed
  to ~1.1x DSCR is often one whose owner *already* optimized operations. The value-add gold is the
  sloppy-but-solvent asset with a healthy loan, which is invisible to this screen.
- **The last mile is human.** County records yield an LLC and a mailing address, not a principal to
  call Tuesday. Owner enrichment here is hand-curated for the top of the list, not scraped.

## Honest status

- The scoring engine is real and tested. The **loan data is illustrative** — modeled on Freddie
  Multifamily disclosure fields for two of Lexerd's markets, so the pipeline runs end to end
  without a live scrape. `data_sources.py` documents the production path (a Freddie K-Deal / SBL
  adapter) and deliberately refuses to pretend it has live data.
- It is designed to **sit next to the Underwriting Assistant**, not replace it: Maturity Radar is
  the *source* step, the calculator is the *underwrite* step. Together they are the analyst's funnel.

## Layout

| File | Role |
|---|---|
| `maturity_radar/models.py` | Loan / ScoredLoan (Freddie-shaped fields) |
| `maturity_radar/scoring.py` | The refinance-pressure engine (tested core) |
| `maturity_radar/watchlist.py` | Score → filter → rank |
| `maturity_radar/sample_data.py` | Illustrative TX/GA loan universe + hand-curated owners |
| `maturity_radar/data_sources.py` | Production data path, documented |
| `radar.py` | CLI watchlist |
| `app.py` | Streamlit watchlist |
| `SCOPE.md` | The build scope |

*Sample properties, owners, and loans are illustrative, not real Lexerd or GSE records.*
