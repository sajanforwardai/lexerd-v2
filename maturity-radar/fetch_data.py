#!/usr/bin/env python3
"""Fetch real multifamily loans from SEC EDGAR and cache them for the dashboard.

    python3 fetch_data.py [max_deals] [STATES|ALL]
    python3 fetch_data.py 60 ALL
    python3 fetch_data.py 60 TX,GA

Pulls recent conduit CMBS ABS-EE filings, keeps only multifamily (propertyTypeCode == MF)
loans (all 50 states by default), and writes data/sec_loans.json. Also refreshes the live
refinance-rate benchmark. The app reads both. Re-run any time to refresh.
"""

import sys

from maturity_radar.data_sources import save_sec_cache
from maturity_radar.rates import fetch_current_rate, save_rate
from maturity_radar.sec_edgar import fetch_universe


def main():
    max_deals = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    arg = sys.argv[2] if len(sys.argv) > 2 else "ALL"
    states = None if arg.upper() == "ALL" else set(arg.split(","))

    print("Refreshing live refinance rate...")
    r = fetch_current_rate()
    if r:
        save_rate(r)
        print(f"  rate: {r['rate']*100:.2f}%  (10-yr UST {r['ten_year']*100:.2f}% + "
              f"{r['spread']*10000:.0f} bps, as of {r['as_of']})")

    loans = fetch_universe(states=states, max_deals=max_deals)
    if not loans:
        print("No loans fetched — cache left unchanged.")
        return
    path = save_sec_cache(loans)
    n_states = len({l.state for l in loans})
    print(f"cached {len(loans)} multifamily loans across {n_states} states -> {path}")


if __name__ == "__main__":
    main()
