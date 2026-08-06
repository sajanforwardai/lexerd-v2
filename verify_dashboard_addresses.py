#!/usr/bin/env python3
"""Batch verify addresses for all properties in the Maturity Radar dashboard.

Usage:
    export GOOGLE_MAPS_API_KEY="your-key-here"
    python3 verify_dashboard_addresses.py
"""

import sys
from pathlib import Path

# Add lexerd2 to path
lexerd_root = Path(__file__).parent
sys.path.insert(0, str(lexerd_root))
sys.path.insert(0, str(lexerd_root / "maturity-radar"))

from calibration.address_verification import GoogleMapsAddressVerifier
from maturity_radar.data_sources import load_loans


def verify_dashboard_properties():
    """Verify addresses for all properties in the dashboard."""
    print("🔍 Batch Address Verification for Lexerd Dashboard\n")
    print("=" * 60)

    # Initialize verifier
    try:
        verifier = GoogleMapsAddressVerifier()
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("\nSet the API key with:")
        print("  export GOOGLE_MAPS_API_KEY='your-key-here'")
        return

    # Load all properties
    print("\n📊 Loading properties...")
    all_loans, _ = load_loans("auto")
    print(f"   Loaded {len(all_loans)} total properties")

    # Get unique properties by (name, city, state)
    seen = set()
    unique_props = []
    for loan in all_loans:
        key = (loan.property_name, loan.city, loan.state)
        if key not in seen:
            seen.add(key)
            unique_props.append(loan)

    print(f"   Unique properties: {len(unique_props)}")

    # Verify addresses
    print(f"\n🔗 Verifying addresses with Google Maps...")
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
            print(f"[{i:3d}/{len(unique_props)}] SKIP | {prop_name:40s} | Missing market data")
            continue

        # Check if already cached
        cache_key = f"{prop_name}|{city}|{state}".lower()
        cached = verifier.cache.get(cache_key)

        if cached:
            already_cached += 1
            status = "✓ (cached)"
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
        print(f"[{i:3d}/{len(unique_props)}] {pct:5.1f}% | {prop_name:40s} | {city:15s} {state} | {status}")

        # Print summary every 50
        if i % 50 == 0:
            print(f"  → {verified} verified, {already_cached} cached, {failed} failed")

    # Final summary
    print("\n" + "=" * 60)
    print("📈 VERIFICATION COMPLETE\n")
    checkable = len(unique_props) - skipped
    print(f"Total properties found:    {len(unique_props)}")
    print(f"  ⏭️  Skipped (no market):    {skipped}")
    print(f"  ✓ Newly verified:        {verified}")
    print(f"  ✓ Already cached:        {already_cached}")
    print(f"  ✗ Not found/failed:      {failed}")
    if checkable > 0:
        print(f"  Coverage:                {(verified + already_cached) / checkable * 100:.1f}%")

    # Cost estimate
    api_calls = verified
    cost = api_calls * 0.007
    print(f"\n💰 API Cost Estimate:")
    print(f"  Calls made: {api_calls}")
    print(f"  Estimated cost: ${cost:.2f}")

    # Show cached results
    print(f"\n✅ Verified Addresses (showing first 10):")
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
            print()
            count += 1
            if count >= 10:
                break

    print("\n" + "=" * 60)
    print("✨ Done! Addresses cached and ready for dashboard.\n")


if __name__ == "__main__":
    verify_dashboard_properties()
