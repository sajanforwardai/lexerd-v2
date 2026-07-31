#!/usr/bin/env python3
"""Fetch and parse Freddie Mac K-Deal and SBL multifamily loan disclosures.

Freddie Mac publishes loan-level disclosures through their Investor Portal at:
    https://mf.freddiemac.com/investors/data

This script processes downloaded K-Deal and SBL CSV files and caches them for the dashboard.

USAGE:

    # Parse a single K-Deal or SBL CSV file
    python3 fetch_freddie_data.py data/k-deals-2025-01.csv

    # Parse multiple files (glob pattern)
    python3 fetch_freddie_data.py "data/k-deals-*.csv"

    # Parse with state filter
    python3 fetch_freddie_data.py data/k-deals.csv --states TX,GA,FL

OBTAINING FREDDIE MAC FILES:

    1. Go to: https://mf.freddiemac.com/investors/data
    2. Navigate to "K-Deal Performance" or "SBL Portfolio" section
    3. Download the latest "Loan-Level Disclosures" CSV file(s)
    4. Save to data/ directory (e.g., data/k-deals-2025-01.csv)
    5. Run this script to index and cache the data

FILES:

    K-Deals: Securitized multifamily loans (K-Deal pools, e.g., FHMS-K7XX)
    SBL: Subordinated borrowing loans (e.g., FHMS-SBL-XXXX)

EXPECTED CSV COLUMNS:

    - Loan Sequence Number (or Loan ID)
    - Property State
    - Units / Number of Units
    - Note Rate / Interest Rate (percent, e.g. 3.50)
    - Maturity Date
    - Current Balance / Current UPB
    - Original Balance / Original UPB
    - Most Recent DSCR / Debt Service Coverage Ratio
    - Most Recent Occupancy / Occupancy Rate
    - Most Recent NOI / Net Operating Income (optional; derived from DSCR if missing)
    - Property Name (optional)
    - City (optional)
    - County (optional)
    - Deal Name (optional)

The exact column names vary by file; this script normalizes common variants.

OUTPUT:

    Writes cache to data/freddie_mac_loans.json — merged with any existing SEC EDGAR data
    (by loan_id, with SEC taking priority if a loan appears in both sources).
"""

import sys
import os
import glob
from pathlib import Path

from maturity_radar.data_sources import load_freddie_mac, save_freddie_mac_cache, _load_sec_cache, save_sec_cache, SEC_CACHE, FREDDIE_MAC_CACHE


def merge_and_cache(freddie_loans, dry_run=False):
    """Merge Freddie Mac loans with existing SEC cache (no duplicates), then save both.

    Freddie loans only fill gaps — if a loan_id already exists in SEC cache, the SEC version wins
    (to preserve conduit CMBS data and human enrichment). Returns tuple of (total_loans, new_loans).
    """
    existing_sec = []
    sec_ids = set()
    if os.path.isfile(SEC_CACHE):
        try:
            existing_sec = _load_sec_cache(SEC_CACHE)
            sec_ids = {l.loan_id for l in existing_sec}
            print(f"  loaded {len(existing_sec)} existing SEC/Conduit loans")
        except Exception as e:
            print(f"  warning: could not load SEC cache: {e}")

    # Merge: Freddie loans fill gaps
    all_loans = {l.loan_id: l for l in existing_sec}  # SEC takes priority
    new_count = 0
    for l in freddie_loans:
        if l.loan_id not in all_loans:
            all_loans[l.loan_id] = l
            new_count += 1

    if not dry_run:
        # Save both SEC + Freddie combined (updating the SEC cache since it's the primary read source)
        path = save_sec_cache(list(all_loans.values()), SEC_CACHE)
        print(f"  merged cache -> {len(all_loans)} total loans (SEC: {len(existing_sec)}, Freddie: {new_count}) -> {path}")
    else:
        print(f"  [dry run] would merge to {len(all_loans)} total loans (SEC: {len(existing_sec)}, Freddie: {new_count})")

    return len(all_loans), new_count


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse Freddie Mac K-Deal and SBL disclosures and update the loan cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "csvfile",
        nargs="*",
        help="Path to K-Deal or SBL CSV file(s). Supports glob patterns (e.g., 'data/*.csv'). "
             "If not provided, looks for data/k-deals*.csv and data/sbl*.csv"
    )
    parser.add_argument(
        "--states",
        default="AL,FL,GA,KS,KY,LA,NC,TX",
        help="Comma-separated state abbreviations to keep (default: Lexerd target states)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files but don't update cache"
    )
    parser.add_argument(
        "--all-states",
        action="store_true",
        help="Keep loans from all states (overrides --states)"
    )

    args = parser.parse_args()

    # Determine files to process
    files = []
    if args.csvfile:
        for pattern in args.csvfile:
            matches = glob.glob(pattern)
            if not matches:
                print(f"error: no files match {pattern}")
                sys.exit(1)
            files.extend(matches)
    else:
        # Default: look for standard Freddie files in data/
        for pattern in ["data/k-deals*.csv", "data/sbl*.csv", "data/*freddie*.csv"]:
            files.extend(glob.glob(pattern))
        if not files:
            print("No CSV files found. Usage:")
            print("  python3 fetch_freddie_data.py data/k-deals-2025-01.csv")
            print("\nSet FREDDIE_MF_DISCLOSURE env var to override the data source URL.")
            sys.exit(1)

    states = None if args.all_states else set(args.states.upper().split(","))

    print(f"Freddie Mac multifamily loan loader")
    print(f"  target states: {', '.join(sorted(states)) if states else 'ALL'}")
    print()

    all_freddie_loans = []
    for filepath in sorted(set(files)):  # unique, sorted
        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            print(f"skip {filepath} (not found)")
            continue

        print(f"parsing {filepath}")
        loans = load_freddie_mac(filepath, states=states, log=lambda x: print(f"  {x}"))
        all_freddie_loans.extend(loans)
        print()

    if not all_freddie_loans:
        print("No valid loans extracted. Check file format and state filter.")
        sys.exit(1)

    print(f"Total extracted: {len(all_freddie_loans)} Freddie Mac loans")
    print()

    total, new = merge_and_cache(all_freddie_loans, dry_run=args.dry_run)
    print()
    print(f"Result: {total} loans in cache (+{new} new from Freddie Mac)")

    if not args.dry_run:
        print("\nRun `python3 app.py` to see the updated loan universe.")


if __name__ == "__main__":
    main()
