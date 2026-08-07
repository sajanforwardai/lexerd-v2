#!/usr/bin/env python3
"""Run Tier 1 Address Discovery on all dashboard properties"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "maturity-radar"))

from address_discovery_system.orchestrator import AddressDiscoveryOrchestrator
from maturity_radar.data_sources import load_loans
from maturity_radar.watchlist import build_watchlist
from maturity_radar import DEFAULT_MARKET_RATE, DEFAULT_REFI_DSCR_FLOOR


def main():
    """Run Tier 1 address discovery"""

    print("\n" + "=" * 80)
    print("🔍 TIER 1 ADDRESS DISCOVERY - LEXERD MATURITY RADAR")
    print("=" * 80 + "\n")

    # Load dashboard properties
    print("📊 Loading dashboard properties...")
    all_loans, _ = load_loans("auto")

    _state_map = {
        "Alabama": "AL", "Florida": "FL", "Georgia": "GA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "North Carolina": "NC", "Texas": "TX",
    }
    states = list(_state_map.values())

    wl = build_watchlist(
        all_loans,
        states=set(states),
        market_rate=DEFAULT_MARKET_RATE,
        floor=DEFAULT_REFI_DSCR_FLOOR,
        min_score=0
    )

    # Get unique properties
    seen = set()
    unique_props = []
    for s in wl:
        loan = s.loan
        key = (loan.property_name, loan.city, loan.state)
        if key not in seen:
            seen.add(key)
            unique_props.append(loan)

    print(f"   Dashboard properties: {len(unique_props)}\n")

    # Prepare loan data for discovery
    loans_to_search = []
    for loan in unique_props:
        # Skip if already has address in raw data
        if loan.property_address and loan.property_address.strip():
            continue

        loans_to_search.append({
            "property_name": loan.property_name,
            "city": loan.city,
            "state": loan.state,
            "county": getattr(loan, 'county', ''),
            "units": loan.units,
            "original_balance": loan.original_balance,
        })

    print(f"   Properties without addresses: {len(loans_to_search)}")
    print(f"   Properties with addresses: {len(unique_props) - len(loans_to_search)}\n")

    # Run Tier 1 discovery
    print("=" * 80)
    print("🚀 Starting Tier 1 Address Discovery\n")
    print("Sources: County Assessor APIs + Zillow + ApartmentsList + Google Maps\n")
    print("=" * 80 + "\n")

    orchestrator = AddressDiscoveryOrchestrator()

    summary = orchestrator.discover_addresses(
        loans_to_search,
        output_file="tier1_discovery_results.json"
    )

    # Print results
    print("\n" + "=" * 80)
    print("📈 TIER 1 DISCOVERY RESULTS\n")

    print(f"Total properties checked:    {summary['total']}")
    print(f"✓ Addresses found:           {summary['found']} ({summary['coverage']})")
    print(f"✗ Not found:                 {summary['not_found']}")

    # Add found addresses to cache
    if summary['found'] > 0:
        print(f"\n💾 Updating address cache...")
        orchestrator.update_cache(summary['results'])

    print("\n" + "=" * 80)
    print(f"\n✨ Tier 1 discovery complete!")
    print(f"   Results: tier1_discovery_results.json")
    print(f"   Cache: calibration/.cache/address_verification_cache.json\n")

    return summary


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result['found'] > 0 else 1)
