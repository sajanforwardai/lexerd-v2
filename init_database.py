#!/usr/bin/env python3
"""Initialize the loans database from data source"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "maturity-radar"))

from maturity_radar.data_sources import load_loans
from address_discovery_system.database import init_db, load_loans_into_db, get_address_coverage, get_session
from address_discovery_system.dashboard_filter import DASHBOARD_STATES


def main():
    """Initialize database with loans"""

    print("════════════════════════════════════════════════════════════════════")
    print("DATABASE INITIALIZATION: Loading Loans")
    print("════════════════════════════════════════════════════════════════════\n")

    # Step 1: Create database schema
    print("Step 1: Creating database schema...")
    init_db()
    print()

    # Step 2: Load loans from data source
    print("Step 2: Loading loans from data source...")
    all_loans, _ = load_loans("auto")
    print(f"  Loaded {len(all_loans)} total loans from CSV\n")

    # Step 3: Load dashboard loans into database
    print("Step 3: Loading dashboard loans (8-state watchlist) into database...")
    loaded = load_loans_into_db(all_loans, state_filter=DASHBOARD_STATES)
    print()

    # Step 4: Show coverage statistics
    print("Step 4: Database coverage statistics...")
    session = get_session()
    stats = get_address_coverage(session, state_filter=DASHBOARD_STATES)

    print(f"\n  Total dashboard loans: {stats['total']}")
    print(f"  ✓ With addresses: {stats['with_address']} ({stats['coverage_pct']:.1f}%)")
    print(f"  ✗ Without addresses: {stats['without_address']} ({100-stats['coverage_pct']:.1f}%)")
    print()

    session.close()

    print("════════════════════════════════════════════════════════════════════")
    print("✅ DATABASE INITIALIZATION COMPLETE")
    print("════════════════════════════════════════════════════════════════════\n")
    print("Database location: data/loans.db")
    print("Total loans in database:", stats['total'])
    print("\nNext steps:")
    print("  1. Update app.py to use database queries instead of JSON files")
    print("  2. Link discovered addresses back to loan records")
    print("  3. Query live data for dynamic metrics\n")


if __name__ == "__main__":
    main()
