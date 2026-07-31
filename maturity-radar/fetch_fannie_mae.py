#!/usr/bin/env python3
"""Load Fannie Mae multifamily loan data and cache it.

Fannie Mae provides free, public loan-level performance data via their Data Dynamics platform.

SETUP:
  1. Register free at: https://capitalmarkets.fanniemae.com/
  2. Navigate to "Data Dynamics" or "Loan-Level Data"
  3. Download "Multifamily Performance Data" (latest or historical)
  4. Save as: fannie_mae_data.csv

USAGE:
    python3 fetch_fannie_mae.py fannie_mae_data.csv
    python3 fetch_fannie_mae.py fannie_mae_data.csv AL,FL,GA,KS,KY,LA,NC,TX
    python3 fetch_fannie_mae.py fannie_mae_data.csv ALL

The script parses the CSV, filters to target states, and caches as data/fannie_mae_loans.json.
"""

import sys
import os

from maturity_radar.data_sources import load_fannie_mae, save_fannie_mae_cache, TARGET_STATES


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fetch_fannie_mae.py <path_to_csv> [STATES|ALL]")
        print(f"\nDefault states: {','.join(sorted(TARGET_STATES))}")
        print("\nExample:")
        print("  python3 fetch_fannie_mae.py ~/Downloads/fannie_mae_data.csv")
        print("  python3 fetch_fannie_mae.py ~/Downloads/fannie_mae_data.csv TX,GA")
        return

    csv_path = sys.argv[1]
    if not os.path.isfile(csv_path):
        print(f"Error: File not found: {csv_path}")
        return

    arg = sys.argv[2] if len(sys.argv) > 2 else None
    states = None if arg and arg.upper() == "ALL" else (set(arg.split(",")) if arg else TARGET_STATES)

    print(f"Loading Fannie Mae data from: {csv_path}")
    print(f"Filtering to states: {','.join(sorted(states)) if states else 'ALL'}")

    loans = load_fannie_mae(csv_path, states=states)

    if not loans:
        print("No loans parsed from file.")
        return

    path = save_fannie_mae_cache(loans)
    n_states = len({l.state for l in loans})
    print(f"\nSuccessfully cached {len(loans)} multifamily loans across {n_states} states -> {path}")

    # Show breakdown by state
    by_state = {}
    for l in loans:
        by_state[l.state] = by_state.get(l.state, 0) + 1
    print("\nLoans by target state:")
    for st in sorted(TARGET_STATES):
        count = by_state.get(st, 0)
        print(f"  {st}: {count}")


if __name__ == "__main__":
    main()
