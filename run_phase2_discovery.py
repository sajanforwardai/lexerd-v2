#!/usr/bin/env python3
"""Run Phase 2 County Assessor Address Discovery on remaining properties"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "maturity-radar"))

from address_discovery_system.sources.county_assessor_phase2 import CountyAssessorPhase2Manager
from maturity_radar.data_sources import load_loans
from maturity_radar.watchlist import build_watchlist
from maturity_radar import DEFAULT_MARKET_RATE, DEFAULT_REFI_DSCR_FLOOR


def main():
    """Run Phase 2 discovery on missing properties"""

    print("\n" + "=" * 80)
    print("🔍 PHASE 2: COUNTY ASSESSOR ADDRESS DISCOVERY")
    print("=" * 80 + "\n")

    # Load Phase 1 results
    print("📊 Loading Phase 1 results...")
    with open('tier1_discovery_results.json', 'r') as f:
        phase1_results = json.load(f)

    found_keys = set()
    for result in phase1_results.get('results', []):
        key = f"{result['property_name']}|{result['city']}|{result['state']}"
        found_keys.add(key)

    print(f"   Phase 1 found: {len(found_keys)} addresses\n")

    # Load all dashboard properties
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

    # Find missing properties (no address in raw data AND not found in Phase 1)
    missing_properties = []
    seen = set()

    for s in wl:
        loan = s.loan
        # Skip if already has address in raw data
        if loan.property_address and loan.property_address.strip():
            continue

        # Check if found in Phase 1
        key = (loan.property_name, loan.city, loan.state)
        if key in seen:
            continue
        seen.add(key)

        search_key = f"{loan.property_name}|{loan.city}|{loan.state}"
        if search_key not in found_keys:
            missing_properties.append({
                "property_name": loan.property_name,
                "city": loan.city,
                "state": loan.state,
                "county": getattr(loan, 'county', ''),
                "units": loan.units,
                "original_balance": loan.original_balance,
            })

    print(f"   Missing properties: {len(missing_properties)}\n")

    # Run Phase 2 discovery
    print("=" * 80)
    print("🚀 Starting Phase 2 County Assessor Discovery\n")
    print("Sources: County Assessor APIs (TX, GA, FL, NC, KS)\n")
    print("=" * 80 + "\n")

    manager = CountyAssessorPhase2Manager()
    phase2_results = {
        "timestamp": datetime.now().isoformat(),
        "phase": "Phase 2 - County Assessor APIs",
        "total": len(missing_properties),
        "found": 0,
        "not_found": 0,
        "results": []
    }

    for i, prop in enumerate(missing_properties, 1):
        result = manager.search(
            county=prop["county"],
            state=prop["state"],
            property_name=prop["property_name"],
            city=prop["city"]
        )

        if result:
            phase2_results["found"] += 1
            phase2_results["results"].append({
                "property_name": prop["property_name"],
                "city": prop["city"],
                "state": prop["state"],
                "address": result.get("address"),
                "confidence_score": result.get("confidence", 0.0),
                "source": result.get("source"),
                "found": True,
            })
            print(f"[{i}/{len(missing_properties)}] ✓ {prop['property_name']}")
            print(f"             → {result.get('address')}")
        else:
            phase2_results["not_found"] += 1
            phase2_results["results"].append({
                "property_name": prop["property_name"],
                "city": prop["city"],
                "state": prop["state"],
                "found": False,
            })
            print(f"[{i}/{len(missing_properties)}] ✗ {prop['property_name']} (not found)")

        if i % 10 == 0:
            print()

    # Calculate coverage
    phase2_coverage = (phase2_results["found"] / phase2_results["total"] * 100) if phase2_results["total"] > 0 else 0
    phase2_results["coverage"] = f"{phase2_coverage:.1f}%"

    # Save Phase 2 results
    print("\n" + "=" * 80)
    print("📈 PHASE 2 DISCOVERY RESULTS\n")

    print(f"Total properties checked: {phase2_results['total']}")
    print(f"✓ Addresses found:        {phase2_results['found']} ({phase2_results['coverage']})")
    print(f"✗ Not found:              {phase2_results['not_found']}")

    # Combined results (Phase 1 + Phase 2)
    combined_found = phase1_results.get('found', 0) + phase2_results['found']
    combined_total = 252
    combined_coverage = (combined_found / combined_total * 100)

    print(f"\n📊 COMBINED RESULTS (Phase 1 + Phase 2):\n")
    print(f"Total dashboard properties: {combined_total}")
    print(f"✓ Total addresses found:    {combined_found} ({combined_coverage:.1f}%)")
    print(f"✗ Still missing:            {combined_total - combined_found}")

    # Save results
    with open('tier2_discovery_results.json', 'w') as f:
        json.dump(phase2_results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"\n✨ Phase 2 discovery complete!")
    print(f"   Phase 2 Results: tier2_discovery_results.json")
    print(f"   Combined Results: {combined_coverage:.1f}% coverage ({combined_found}/252)\n")

    return phase2_results


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result['found'] > 0 else 1)
