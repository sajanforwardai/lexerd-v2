#!/usr/bin/env python3
"""Fetch expanded multifamily loans from SEC EDGAR (10+ year history) and cache them.

This script performs a deep search of EDGAR's CMBS ABS-EE filings to capture a more complete
universe of multifamily loans, including historical deals, amendments, and restructurings.

    python3 fetch_expanded_data.py [max_deals] [STATES|ALL]
    python3 fetch_expanded_data.py 150 ALL
    python3 fetch_expanded_data.py 150 TX,GA,FL

By default, searches for 150+ deals spanning 10+ years of CMBS history. Merges with existing
cache, deduplicating by loan_id.
"""

import sys

from maturity_radar.data_sources import save_sec_cache, _load_sec_cache, SEC_CACHE
from maturity_radar.rates import fetch_current_rate, save_rate
from maturity_radar.sec_edgar import fetch_expanded_universe
import os


def main():
    max_deals = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    arg = sys.argv[2] if len(sys.argv) > 2 else "ALL"
    states = None if arg.upper() == "ALL" else set(arg.split(","))

    print("Refreshing live refinance rate...")
    r = fetch_current_rate()
    if r:
        save_rate(r)
        print(f"  rate: {r['rate']*100:.2f}%  (10-yr UST {r['ten_year']*100:.2f}% + "
              f"{r['spread']*10000:.0f} bps, as of {r['as_of']})")

    print("\nFetching expanded SEC EDGAR universe (10+ year history)...")
    new_loans = fetch_expanded_universe(states=states, max_deals=max_deals)

    if not new_loans:
        print("No new loans fetched — cache left unchanged.")
        return

    # Load existing cache and merge (dedup by loan_id)
    existing = {}
    if os.path.isfile(SEC_CACHE):
        try:
            existing_loans = _load_sec_cache(SEC_CACHE)
            for l in existing_loans:
                existing[l.loan_id] = l
        except Exception as e:
            print(f"Warning: could not load existing cache: {e}")

    # Merge: new loans override existing (to get latest versions)
    for l in new_loans:
        existing[l.loan_id] = l

    all_loans = list(existing.values())
    path = save_sec_cache(all_loans)
    n_states = len({l.state for l in all_loans})
    print(f"\ncached {len(all_loans)} multifamily loans across {n_states} states -> {path}")
    print(f"  (was {len(existing_loans) if existing_loans else 0}, +{len(new_loans)} new/updated)")


if __name__ == "__main__":
    main()
