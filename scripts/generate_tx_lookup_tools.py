#!/usr/bin/env python3
"""Generate lookup tools for manual Texas property verification"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session, get_loans_by_state
from address_discovery_system.florida_direct_lookup import FloridaDirectLookup


def main():
    """Generate lookup tools for Texas"""

    print("════════════════════════════════════════════════════════════════════")
    print("GENERATE TEXAS PROPERTY LOOKUP TOOLS")
    print("════════════════════════════════════════════════════════════════════\n")

    session = get_session()

    # Get all Texas loans without addresses
    all_texas = get_loans_by_state(session, 'TX')
    texas_missing = [p for p in all_texas if not p.property_address]

    print(f"Step 1: Loaded {len(texas_missing)} Texas properties without addresses\n")

    # Convert to lookup format
    properties = [
        {
            'property_name': p.property_name,
            'city': p.city,
            'county': p.county or 'Unknown',
            'state': 'TX'
        }
        for p in texas_missing
    ]

    # Generate lookup table
    print("Step 2: Creating lookup table...\n")
    lookups = FloridaDirectLookup.batch_create_lookup_table(properties)

    # Export as CSV
    print("Step 3: Exporting to CSV...")
    csv_file = FloridaDirectLookup.export_lookup_csv(properties, 'tx_property_lookup.csv')
    print(f"  ✓ {csv_file}\n")

    # Export as HTML
    print("Step 4: Exporting to HTML (interactive)...")
    html_file = FloridaDirectLookup.export_lookup_html(properties, 'tx_property_lookup.html')
    print(f"  ✓ {html_file}\n")

    # Show sample lookup
    print("Step 5: Sample lookup record:\n")
    sample = lookups[0]
    print(f"  Property: {sample['property_name']}")
    print(f"  Location: {sample['city']}, {sample['county']} County, TX")
    print(f"  Verification sources: {len(sample['verification_sources'])}")
    for i, source in enumerate(sample['verification_sources'], 1):
        print(f"    {i}. {source}")

    # Summary
    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("LOOKUP TOOLS READY")
    print("════════════════════════════════════════════════════════════════════\n")

    print(f"Generated lookup tables for {len(properties)} Texas properties:\n")
    print(f"  📊 CSV Format: tx_property_lookup.csv")
    print(f"     → Easy to share, edit, track in spreadsheet\n")
    print(f"  🌐 Interactive HTML: tx_property_lookup.html")
    print(f"     → Open in browser, click links to verify each property\n")

    print("VERIFICATION WORKFLOW:\n")
    print("  1. Open tx_property_lookup.html in your browser")
    print("  2. For each property, click links to verify address")
    print("  3. Record addresses in CSV")
    print("  4. Run: python scripts/update_tx_addresses_from_csv.py tx_property_lookup.csv\n")

    print("EXPECTED RESULTS:\n")
    print(f"  • Coverage: 95-100% (manual verification)")
    print(f"  • Confidence: 1.0 (human-verified)")
    print(f"  • Time: ~5-10 min per property = ~15-30 hours for all 146\n")

    session.close()

    print("✅ Lookup tools generated!\n")


if __name__ == "__main__":
    main()
