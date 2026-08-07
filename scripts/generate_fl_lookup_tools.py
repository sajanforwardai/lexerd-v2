#!/usr/bin/env python3
"""Generate lookup tools for manual Florida property verification"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session, get_loans_by_state
from address_discovery_system.florida_direct_lookup import FloridaDirectLookup


def main():
    """Generate lookup tools"""

    print("════════════════════════════════════════════════════════════════════")
    print("GENERATE FLORIDA PROPERTY LOOKUP TOOLS")
    print("════════════════════════════════════════════════════════════════════\n")

    session = get_session()

    # Get all Florida loans without addresses
    all_florida = get_loans_by_state(session, 'FL')
    florida_missing = [p for p in all_florida if not p.property_address]

    print(f"Step 1: Loaded {len(florida_missing)} Florida properties without addresses\n")

    # Convert to lookup format
    properties = [
        {
            'property_name': p.property_name,
            'city': p.city,
            'county': p.county or 'Unknown',
            'state': 'FL'
        }
        for p in florida_missing
    ]

    # Generate lookup table
    print("Step 2: Creating lookup table...\n")
    lookups = FloridaDirectLookup.batch_create_lookup_table(properties)

    # Export as CSV
    print("Step 3: Exporting to CSV...")
    csv_file = FloridaDirectLookup.export_lookup_csv(properties, 'fl_property_lookup.csv')
    print(f"  ✓ {csv_file}\n")

    # Export as HTML
    print("Step 4: Exporting to HTML (interactive)...")
    html_file = FloridaDirectLookup.export_lookup_html(properties, 'fl_property_lookup.html')
    print(f"  ✓ {html_file}\n")

    # Show sample lookup
    print("Step 5: Sample lookup record:\n")
    sample = lookups[0]
    print(f"  Property: {sample['property_name']}")
    print(f"  Location: {sample['city']}, {sample['county']} County, FL")
    print(f"  Verification sources: {len(sample['verification_sources'])}")
    for i, source in enumerate(sample['verification_sources'], 1):
        print(f"    {i}. {source}")
    print(f"\n  Search links:")
    for name, url in sample['search_links'].items():
        if url:
            print(f"    • {name}: {url[:60]}...")

    # Summary
    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("LOOKUP TOOLS READY")
    print("════════════════════════════════════════════════════════════════════\n")

    print(f"Generated lookup tables for {len(properties)} properties:\n")
    print(f"  📊 CSV Format: fl_property_lookup.csv")
    print(f"     → Easy to share, edit, track in spreadsheet")
    print(f"     → Columns: Property, City, County, Google Maps, Apartments.com, Zillow, etc.\n")

    print(f"  🌐 Interactive HTML: fl_property_lookup.html")
    print(f"     → Open in browser, click links to verify each property")
    print(f"     → 5 search sources per property (Google Maps, Google Search, Apartments.com, Zillow, County Assessor)\n")

    print("VERIFICATION WORKFLOW:\n")
    print("  1. Open fl_property_lookup.html in your browser")
    print("  2. For each property:")
    print("     • Click Google Maps → Visual confirmation of location + address")
    print("     • Click Apartments.com → Property page with street address")
    print("     • Click Zillow → Property details + address")
    print("     • Click County Assessor → Owner/tax records")
    print("  3. Record confirmed address in CSV or database")
    print("  4. Mark as verified in database with confidence=1.0\n")

    print("EXPECTED RESULTS:\n")
    print(f"  • Coverage: 95-100% (manual verification)")
    print(f"  • Confidence: 1.0 (human-verified)")
    print(f"  • Time: ~5-10 min per property = ~2-5 hours for all 33\n")

    print("NEXT STEPS:\n")
    print("  1. Open: fl_property_lookup.html")
    print("  2. Verify 5-10 properties as a pilot")
    print("  3. Record addresses in database via:")
    print("     python scripts/update_fl_addresses.py --csv fl_property_lookup.csv\n")

    session.close()

    print("✅ Lookup tools generated!\n")


if __name__ == "__main__":
    main()
