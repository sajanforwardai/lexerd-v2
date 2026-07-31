#!/usr/bin/env python3
"""Maturity Radar — print the refinance-pressure watchlist for TX & GA.

    python3 radar.py

A cultivation queue, not a seller list: it ranks small multifamily loans by how hard they will
be to refinance at today's rate, so Lexerd can build the relationship — or bring the leverage —
ahead of the owner's maturity. Coverage is securitized loans only; owner leads for the top of
the list are hand-curated (human-in-the-loop).
"""

from maturity_radar.data_sources import load_loans
from maturity_radar.watchlist import build_watchlist

RULE = "=" * 74


def main():
    loans, src = load_loans("auto")
    wl = build_watchlist(loans)
    _label = {"sec": "real SEC EDGAR CMBS (multifamily)", "mlpd": "real Freddie MLPD",
              "sample": "sample (illustrative)"}[src]
    print(f"DATA: {_label}")

    print(RULE)
    print("MATURITY RADAR  ·  Refinance-Pressure Watchlist  ·  TX & GA")
    print(RULE)
    print("A cultivation queue timed to the 2026-28 maturity wall. Higher score = harder to")
    print("refinance at ~6% = earlier, warmer conversation. NOT a motivated-seller list.")
    print()
    print(f'{"SCORE":>5}  {"PROPERTY":<26}{"MARKET":<20}{"MAT":<8}{"proj DSCR":>9}')
    print("-" * 74)
    for s in wl:
        l = s.loan
        print(f'{s.pressure_score:>5.1f}  {l.property_name[:25]:<26}{s.market:<20}'
              f'{l.maturity.strftime("%b-%y"):<8}{s.projected_refi_dscr:>9.2f}')

    print()
    print(RULE)
    print("TOP OF LIST — why now + owner lead (hand-curated)")
    print(RULE)
    for s in [x for x in wl if x.pressure_score >= 85][:6]:
        l = s.loan
        print(f"\n▸ {l.property_name} — {s.market} ({l.units} units)   [score {s.pressure_score:.0f}]")
        print(f"  {s.why_now}")
        print(f"  Entry angle: {s.entry_angle}")
        owner = l.owner_entity or "— not enriched —"
        print(f"  Owner: {owner}")
        if l.principal_hint:
            print(f"  Lead:  {l.principal_hint}")

    print()
    print(RULE)
    print("Coverage: securitized (Freddie/agency) loans only — community-bank paper is invisible.")
    print("Refi pressure ≠ a willing seller, and ≠ value-add upside. Sample data; see README.")
    print(RULE)


if __name__ == "__main__":
    main()
