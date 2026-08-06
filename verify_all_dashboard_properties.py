#!/usr/bin/env python3
"""Verify addresses for ALL 280 properties displayed on the Maturity Radar dashboard.

This script loads the exact properties shown in the dashboard and verifies each one.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "maturity-radar"))

from calibration.address_verification import GoogleMapsAddressVerifier
from maturity_radar.data_sources import load_loans
from maturity_radar.watchlist import build_watchlist
from maturity_radar import DEFAULT_MARKET_RATE, DEFAULT_REFI_DSCR_FLOOR


def verify_all_dashboard_properties():
    """Verify addresses for ALL properties in the dashboard watchlist."""
    print("🔍 Complete Dashboard Address Verification\n")
    print("=" * 60)

    # Initialize verifier
    try:
        verifier = GoogleMapsAddressVerifier()
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("\nSet the API key with:")
        print("  export GOOGLE_MAPS_API_KEY='your-key-here'")
        return

    # Load all properties and build watchlist
    print("\n📊 Loading dashboard properties...")
    all_loans, _ = load_loans("auto")
    print(f"   Total properties in system: {len(all_loans)}")

    # Build watchlist with default filters (all states, all pressure bands)
    _state_map = {
        "Alabama": "AL", "Florida": "FL", "Georgia": "GA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "North Carolina": "NC", "Texas": "TX",
    }
    states = list(_state_map.values())

    market_rate = DEFAULT_MARKET_RATE
    floor = DEFAULT_REFI_DSCR_FLOOR

    wl = build_watchlist(all_loans, states=set(states), market_rate=market_rate, floor=floor, min_score=0)

    print(f"   Dashboard watchlist: {len(wl)} properties")
    print(f"   Default market rate: {market_rate*100:.2f}%")
    print(f"   Default DSCR floor: {floor:.2f}x")

    # Get unique properties from watchlist
    seen = set()
    unique_props = []
    for s in wl:
        loan = s.loan
        key = (loan.property_name, loan.city, loan.state)
        if key not in seen:
            seen.add(key)
            unique_props.append(loan)

    print(f"   Unique properties: {len(unique_props)}")

    # Verify all dashboard properties
    print(f"\n🔗 Verifying all {len(unique_props)} dashboard properties...")
    print("=" * 60)

    verified = 0
    failed = 0
    already_cached = 0
    skipped = 0

    for i, loan in enumerate(unique_props, 1):
        prop_name = loan.property_name
        city = loan.city
        state = loan.state

        # Skip if missing city or state
        if not city or not state or city == "(multiple)" or not state.strip():
            skipped += 1
            print(f"[{i:3d}/{len(unique_props)}] SKIP | {prop_name:40s} | Missing market")
            continue

        # Check if already cached
        cache_key = f"{prop_name}|{city}|{state}".lower()
        cached = verifier.cache.get(cache_key)

        if cached:
            already_cached += 1
            status = f"✓ (cached) {cached.address}"
        else:
            # Verify
            result = verifier.verify(prop_name, city, state)
            if result:
                verified += 1
                status = f"✓ {result.address}"
            else:
                failed += 1
                status = "✗ Not found"

        # Print progress
        pct = (i / len(unique_props)) * 100
        print(f"[{i:3d}/{len(unique_props)}] {pct:5.1f}% | {prop_name:40s} | {status}")

        # Print summary every 50
        if i % 50 == 0:
            print(f"  → {verified} verified, {already_cached} cached, {failed} failed, {skipped} skipped")

    # Final summary
    print("\n" + "=" * 60)
    print("📈 VERIFICATION COMPLETE\n")
    checkable = len(unique_props) - skipped
    print(f"Total dashboard properties: {len(unique_props)}")
    print(f"  ⏭️  Skipped (no market):    {skipped}")
    print(f"  ✓ Newly verified:         {verified}")
    print(f"  ✓ Already cached:         {already_cached}")
    print(f"  ✗ Not found/failed:       {failed}")
    if checkable > 0:
        coverage = (verified + already_cached) / checkable * 100
        print(f"  Coverage:                 {coverage:.1f}%")

    # Cost estimate
    api_calls = verified
    cost = api_calls * 0.007
    print(f"\n💰 API Cost:")
    print(f"  New API calls: {api_calls}")
    print(f"  Estimated cost: ${cost:.2f}")

    # Show verified results
    print(f"\n✅ Verified Addresses (showing first 15):")
    print("=" * 60)
    count = 0
    for loan in unique_props:
        cache_key = f"{loan.property_name}|{loan.city}|{loan.state}".lower()
        cached = verifier.cache.get(cache_key)
        if cached:
            print(f"{loan.property_name:40s}")
            print(f"  → {cached.address}")
            if cached.phone:
                print(f"  📞 {cached.phone}")
            if cached.website:
                print(f"  🌐 {cached.website}")
            print()
            count += 1
            if count >= 15:
                break

    print("=" * 60)
    print("✨ Done! All dashboard properties verified and cached.\n")
    print("Dashboard users can now click 'Verify Address' for instant results!")


if __name__ == "__main__":
    verify_all_dashboard_properties()
