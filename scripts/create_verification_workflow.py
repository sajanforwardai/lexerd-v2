#!/usr/bin/env python3
"""
Create complete verification workflow for all 251 missing properties
Generates: CSVs, HTML lookup tools, batch import guides
"""

import sys
import csv
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session
from address_discovery_system.models import Loan


def create_state_csv(state: str, properties: list) -> str:
    """Create verification CSV for a state"""

    csv_path = Path(f"{state.lower()}_property_lookup.csv")

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'Property Name',
            'City',
            'County',
            'State',
            'Google Maps Link',
            'Apartments.com Link',
            'Zillow Link',
            'County Assessor Link',
            'Address (to be filled)',
            'Confidence',
            'Source',
            'Notes'
        ])
        writer.writeheader()

        for prop in properties:
            # Create search URLs
            google_maps = f"https://www.google.com/maps/search/{prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}"
            apartments = f"https://www.apartments.com/search/?q={prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}"
            zillow = f"https://www.zillow.com/homes/for_sale/?searchQueryState=%7B%22usersSearchTerm%22:%22{prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}%22%7D"

            # County assessor link (generic for now)
            county_assessor = f"https://google.com/search?q={prop.county or 'unknown'}+county+assessor+{state}"

            writer.writerow({
                'Property Name': prop.property_name,
                'City': prop.city or '',
                'County': prop.county or '',
                'State': state,
                'Google Maps Link': google_maps,
                'Apartments.com Link': apartments,
                'Zillow Link': zillow,
                'County Assessor Link': county_assessor,
                'Address (to be filled)': '',
                'Confidence': '1.0',
                'Source': 'manual_verification',
                'Notes': ''
            })

    return str(csv_path)


def create_state_html(state: str, properties: list) -> str:
    """Create HTML lookup tool for a state"""

    html_path = Path(f"{state.lower()}_property_lookup.html")

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{state} Property Address Lookup Tool</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        .subtitle {{ color: #666; margin-bottom: 20px; font-size: 14px; }}
        .stats {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 20px; }}
        .stat {{ flex: 1; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #2563eb; }}
        .stat-label {{ color: #666; font-size: 12px; margin-top: 5px; }}
        table {{ width: 100%; background: white; border-collapse: collapse; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        thead {{ background: #2563eb; color: white; }}
        th {{ padding: 12px; text-align: left; font-weight: 600; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f9fafb; }}
        .property-name {{ font-weight: 500; color: #333; }}
        .city {{ color: #666; font-size: 13px; }}
        .links {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        a {{ display: inline-block; padding: 6px 12px; background: #2563eb; color: white; text-decoration: none; border-radius: 4px; font-size: 12px; transition: background 0.2s; }}
        a:hover {{ background: #1d4ed8; }}
        a.google {{ background: #ea4335; }}
        a.google:hover {{ background: #c5221f; }}
        a.apartments {{ background: #f4a460; }}
        a.apartments:hover {{ background: #e89350; }}
        a.zillow {{ background: #0074e4; }}
        a.zillow:hover {{ background: #0059b8; }}
        a.assessor {{ background: #059669; }}
        a.assessor:hover {{ background: #047857; }}
        .instructions {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 15px; margin-bottom: 20px; border-radius: 4px; }}
        .instructions h3 {{ color: #2563eb; margin-bottom: 10px; }}
        .instructions ol {{ margin-left: 20px; color: #666; font-size: 14px; }}
        .instructions li {{ margin-bottom: 8px; }}
        .status {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }}
        .status.missing {{ background: #fee2e2; color: #991b1b; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{state} Property Address Lookup Tool</h1>
        <p class="subtitle">Click links to verify property addresses in real-time</p>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">{len(properties)}</div>
                <div class="stat-label">Properties to Verify</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len([p for p in properties])}</div>
                <div class="stat-label">Needing Addresses</div>
            </div>
        </div>

        <div class="instructions">
            <h3>How to use this tool</h3>
            <ol>
                <li>Find your property in the table below</li>
                <li>Click on "Google Maps", "Apartments.com", or "County Assessor" to search</li>
                <li>Copy the verified address back into the CSV file ({state.lower()}_property_lookup.csv)</li>
                <li>Run: <code>python scripts/update_{state.lower()}_addresses_from_csv.py {state.lower()}_property_lookup.csv</code></li>
            </ol>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Property Name</th>
                    <th>City / County</th>
                    <th>Search Links</th>
                </tr>
            </thead>
            <tbody>
'''

    for prop in sorted(properties, key=lambda p: p.property_name):
        google_maps_url = f"https://www.google.com/maps/search/{prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}"
        apartments_url = f"https://www.apartments.com/search/?q={prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}"
        zillow_url = f"https://www.zillow.com/homes/for_sale/?searchQueryState=%7B%22usersSearchTerm%22:%22{prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}%22%7D"
        assessor_url = f"https://google.com/search?q={prop.county or 'unknown'}+county+assessor+{state}+property+search"

        html_content += f'''                <tr>
                    <td>
                        <div class="property-name">{prop.property_name}</div>
                        <div class="city">{prop.city or "Unknown"}</div>
                    </td>
                    <td>
                        <div class="city">{prop.county or "Unknown"} County</div>
                        <span class="status missing">Address Missing</span>
                    </td>
                    <td>
                        <div class="links">
                            <a href="{google_maps_url}" target="_blank" class="google">🔍 Google Maps</a>
                            <a href="{apartments_url}" target="_blank" class="apartments">🏢 Apartments.com</a>
                            <a href="{zillow_url}" target="_blank" class="zillow">🏠 Zillow</a>
                            <a href="{assessor_url}" target="_blank" class="assessor">📋 Assessor</a>
                        </div>
                    </td>
                </tr>
'''

    html_content += '''            </tbody>
        </table>
    </div>
</body>
</html>
'''

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return str(html_path)


def main():
    """Create verification workflow"""

    session = get_session()

    print("════════════════════════════════════════════════════════════════════════════════")
    print("CREATE VERIFICATION WORKFLOW FOR ALL 251 MISSING PROPERTIES")
    print("════════════════════════════════════════════════════════════════════════════════\n")

    # Get all properties without addresses
    all_loans = session.query(Loan).all()
    all_props = [p for p in all_loans if not p.property_address]

    # Group by state
    by_state = defaultdict(list)
    for prop in all_props:
        by_state[prop.state].append(prop)

    print(f"Total properties to verify: {len(all_props)}\n")
    print("Creating verification tools...\n")

    for state in sorted(by_state.keys()):
        props = by_state[state]
        print(f"  {state}: {len(props)} properties")

        # Create CSV
        csv_path = create_state_csv(state, props)
        print(f"    ✓ {csv_path}")

        # Create HTML
        html_path = create_state_html(state, props)
        print(f"    ✓ {html_path}\n")

    session.close()

    print("\n" + "════════════════════════════════════════════════════════════════════════════════")
    print("VERIFICATION WORKFLOW READY")
    print("════════════════════════════════════════════════════════════════════════════════\n")

    print("Tools created for each state:")
    for state in sorted(by_state.keys()):
        print(f"  • {state}: {state.lower()}_property_lookup.html + {state.lower()}_property_lookup.csv")

    print("\n\nNext steps:")
    print("  1. Open [state]_property_lookup.html in your browser")
    print("  2. Click the search links to verify each property address")
    print("  3. Copy the verified address into the CSV file")
    print("  4. Run: python scripts/update_[state]_addresses_from_csv.py [state]_property_lookup.csv")
    print("  5. Repeat for each state")
    print("\nEstimated time: 5-10 minutes per property × 251 properties = 20-40 hours\n")


if __name__ == "__main__":
    main()
