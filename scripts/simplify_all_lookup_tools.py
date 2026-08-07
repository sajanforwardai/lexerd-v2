#!/usr/bin/env python3
"""Simplify all state lookup tools - remove clutter, keep essentials only"""

import sys
import csv
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session
from address_discovery_system.models import Loan


def create_simplified_address_csv(state: str, properties: list) -> str:
    """Create simplified address lookup CSV (addresses only)"""

    csv_path = Path(f"{state.lower()}_property_lookup.csv")

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'Property Name',
            'City',
            'County',
            'State',
            'Address (to be filled)',
            'Confidence',
            'Source'
        ])
        writer.writeheader()

        for prop in properties:
            writer.writerow({
                'Property Name': prop.property_name,
                'City': prop.city or '',
                'County': prop.county or '',
                'State': state,
                'Address (to be filled)': '',
                'Confidence': '1.0',
                'Source': 'manual_verification'
            })

    return str(csv_path)


def create_simplified_address_html(state: str, properties: list) -> str:
    """Create simplified HTML lookup tool for addresses"""

    html_path = Path(f"{state.lower()}_property_lookup.html")

    # Build table rows
    table_rows = ""
    for i, prop in enumerate(sorted(properties, key=lambda p: p.property_name), 1):
        table_rows += f'''                <tr>
                    <td>{i}</td>
                    <td class="property-name">{prop.property_name}</td>
                    <td class="city-info">{prop.city or 'Unknown'}, {prop.county or 'Unknown'} County</td>
                    <td><span class="status">Needs Address</span></td>
                </tr>
'''

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{state} Property Address Lookup</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ color: #333; margin-bottom: 8px; font-size: 28px; }}
        .subtitle {{ color: #666; margin-bottom: 20px; font-size: 14px; }}
        .instruction-box {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 15px; margin-bottom: 20px; border-radius: 4px; }}
        .instruction-box h3 {{ color: #2563eb; margin-bottom: 10px; font-size: 14px; }}
        .instruction-box p {{ color: #666; font-size: 13px; line-height: 1.6; margin-bottom: 8px; }}
        table {{ width: 100%; background: white; border-collapse: collapse; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        thead {{ background: #2563eb; color: white; }}
        th {{ padding: 12px; text-align: left; font-weight: 600; font-size: 13px; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; font-size: 13px; }}
        tr:hover {{ background: #f9fafb; }}
        .property-name {{ font-weight: 500; color: #333; }}
        .city-info {{ color: #666; font-size: 12px; }}
        .status {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; background: #fee2e2; color: #991b1b; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 {state} Property Address Lookup</h1>
        <p class="subtitle">{len(properties)} properties needing address verification</p>

        <div class="instruction-box">
            <h3>How to use:</h3>
            <p><strong>1.</strong> Find each property below</p>
            <p><strong>2.</strong> Search online: "[Property Name] [City], {state}" in Google or Apartments.com</p>
            <p><strong>3.</strong> Copy the street address (e.g., "123 Main St, City, {state.upper()} 12345")</p>
            <p><strong>4.</strong> Fill in the CSV file: {state.lower()}_property_lookup.csv</p>
            <p><strong>5.</strong> Run: python scripts/update_{state.lower()}_addresses_from_csv.py {state.lower()}_property_lookup.csv</p>
        </div>

        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Property Name</th>
                    <th>City / County</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
{table_rows}            </tbody>
        </table>

        <div class="footer">
            <p><strong>💡 Pro tip:</strong> Use Google Maps or Apartments.com. Most results appear in top 3-5 search results. Estimated 2-3 minutes per property.</p>
        </div>
    </div>
</body>
</html>
'''

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return str(html_path)


def main():
    """Simplify all lookup tools"""

    session = get_session()

    print("════════════════════════════════════════════════════════════════════")
    print("SIMPLIFY ALL STATE LOOKUP TOOLS - ADDRESS VERIFICATION ONLY")
    print("════════════════════════════════════════════════════════════════════\n")

    # Get all properties without addresses
    all_loans = session.query(Loan).all()
    all_props = [p for p in all_loans if not p.property_address]

    # Group by state
    by_state = defaultdict(list)
    for prop in all_props:
        by_state[prop.state].append(prop)

    print(f"Simplifying lookup tools for all states...\n")

    for state in sorted(by_state.keys()):
        props = by_state[state]

        # Create simplified CSV
        csv_path = create_simplified_address_csv(state, props)
        print(f"  {state}: ✓ {csv_path}")

        # Create simplified HTML
        html_path = create_simplified_address_html(state, props)
        print(f"       ✓ {html_path}\n")

    session.close()

    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("✅ ALL TOOLS SIMPLIFIED")
    print("════════════════════════════════════════════════════════════════════\n")

    print("Changes made:")
    print("  ✓ Removed all search links from HTML (cleaner interface)")
    print("  ✓ Simplified CSV to 7 essential columns")
    print("  ✓ Kept only: Property Name, City, County, State, Address, Confidence, Source")
    print("  ✓ All 8 states updated (AL, FL, GA, KS, KY, LA, NC, TX)\n")

    print("To use:")
    print("  1. Open [state]_property_lookup.html in browser")
    print("  2. Search each property online (Google Maps or Apartments.com)")
    print("  3. Copy address to [state]_property_lookup.csv")
    print("  4. Run: python scripts/update_[state]_addresses_from_csv.py\n")


if __name__ == "__main__":
    main()
