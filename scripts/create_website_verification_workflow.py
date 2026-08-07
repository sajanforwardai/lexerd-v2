#!/usr/bin/env python3
"""
Create comprehensive website verification workflow
Generates: HTML lookup tools, CSV tracking sheets for all 251+ properties without websites
"""

import sys
import csv
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session
from address_discovery_system.models import Loan


def create_state_website_csv(state: str, properties: list) -> str:
    """Create website verification CSV for a state"""

    csv_path = Path(f"{state.lower()}_website_lookup.csv")

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'Property Name',
            'City',
            'County',
            'State',
            'Google Search Link',
            'Apartments.com Link',
            'Management Company Link',
            'Property Website (to be filled)',
            'Website Type',
            'Phone Number',
            'Email Address',
            'Management Company',
            'Confidence',
            'Source',
            'Notes'
        ])
        writer.writeheader()

        for prop in properties:
            # Create search URLs
            google_search = f"https://www.google.com/search?q={prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}+website"
            apartments = f"https://www.apartments.com/search/?q={prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}"
            management_search = f"https://www.google.com/search?q={prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+property+management+company"

            writer.writerow({
                'Property Name': prop.property_name,
                'City': prop.city or '',
                'County': prop.county or '',
                'State': state,
                'Google Search Link': google_search,
                'Apartments.com Link': apartments,
                'Management Company Link': management_search,
                'Property Website (to be filled)': '',
                'Website Type': 'official',
                'Phone Number': '',
                'Email Address': '',
                'Management Company': '',
                'Confidence': '1.0',
                'Source': 'manual_verification',
                'Notes': ''
            })

    return str(csv_path)


def create_state_website_html(state: str, properties: list) -> str:
    """Create HTML lookup tool for website discovery"""

    html_path = Path(f"{state.lower()}_website_lookup.html")

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{state} Property Website Discovery Tool</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        .subtitle {{ color: #666; margin-bottom: 20px; font-size: 14px; }}
        .stats {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 20px; }}
        .stat {{ flex: 1; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #7c3aed; }}
        .stat-label {{ color: #666; font-size: 12px; margin-top: 5px; }}
        table {{ width: 100%; background: white; border-collapse: collapse; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        thead {{ background: #7c3aed; color: white; }}
        th {{ padding: 12px; text-align: left; font-weight: 600; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f9fafb; }}
        .property-name {{ font-weight: 500; color: #333; }}
        .city {{ color: #666; font-size: 13px; }}
        .links {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        a {{ display: inline-block; padding: 6px 12px; background: #7c3aed; color: white; text-decoration: none; border-radius: 4px; font-size: 12px; transition: background 0.2s; }}
        a:hover {{ background: #6d28d9; }}
        a.google {{ background: #ea4335; }}
        a.google:hover {{ background: #c5221f; }}
        a.apartments {{ background: #f4a460; }}
        a.apartments:hover {{ background: #e89350; }}
        a.management {{ background: #0891b2; }}
        a.management:hover {{ background: #0e7490; }}
        .instructions {{ background: #f3e8ff; border-left: 4px solid #7c3aed; padding: 15px; margin-bottom: 20px; border-radius: 4px; }}
        .instructions h3 {{ color: #7c3aed; margin-bottom: 10px; }}
        .instructions ol {{ margin-left: 20px; color: #666; font-size: 14px; }}
        .instructions li {{ margin-bottom: 8px; line-height: 1.5; }}
        .status {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }}
        .status.missing {{ background: #fce7f3; color: #be185d; }}
        .tips {{ background: #ecfdf5; border-left: 4px solid #10b981; padding: 12px; margin-top: 12px; border-radius: 4px; font-size: 13px; }}
        .tips strong {{ color: #10b981; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🌐 {state} Property Website Discovery Tool</h1>
        <p class="subtitle">Find official websites and contact information for all properties</p>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">{len(properties)}</div>
                <div class="stat-label">Properties to Research</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len([p for p in properties])}</div>
                <div class="stat-label">Needing Websites</div>
            </div>
        </div>

        <div class="instructions">
            <h3>How to use this tool</h3>
            <ol>
                <li>Find your property in the table below</li>
                <li>Click search links to find the property's official website</li>
                <li>Note: Google Search and Apartments.com are fastest (2-3 min per property)</li>
                <li>Also look for: phone number, email, management company name</li>
                <li>Copy information into the CSV file ({state.lower()}_website_lookup.csv)</li>
                <li>Run: <code>python scripts/update_{state.lower()}_websites_from_csv.py {state.lower()}_website_lookup.csv</code></li>
            </ol>
            <div class="tips">
                <strong>💡 Pro tip:</strong> Most properties have websites on Apartments.com or their management company's site. Start there, then verify with Google Search.
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Property Name</th>
                    <th>City / County</th>
                    <th>Find Website</th>
                </tr>
            </thead>
            <tbody>
'''

    for prop in sorted(properties, key=lambda p: p.property_name):
        google_search_url = f"https://www.google.com/search?q={prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}+website"
        apartments_url = f"https://www.apartments.com/search/?q={prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+{state}"
        management_url = f"https://www.google.com/search?q={prop.property_name.replace(' ', '+')}+{prop.city.replace(' ', '+')}+property+management+company"

        html_content += f'''                <tr>
                    <td>
                        <div class="property-name">{prop.property_name}</div>
                        <div class="city">{prop.city or "Unknown"}</div>
                    </td>
                    <td>
                        <div class="city">{prop.county or "Unknown"} County</div>
                        <span class="status missing">Website Missing</span>
                    </td>
                    <td>
                        <div class="links">
                            <a href="{google_search_url}" target="_blank" class="google">🔍 Google</a>
                            <a href="{apartments_url}" target="_blank" class="apartments">🏢 Apartments.com</a>
                            <a href="{management_url}" target="_blank" class="management">🏛️ Management</a>
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
    """Create website verification workflow"""

    session = get_session()

    print("════════════════════════════════════════════════════════════════════════════════")
    print("CREATE WEBSITE VERIFICATION WORKFLOW FOR ALL 283 PROPERTIES")
    print("════════════════════════════════════════════════════════════════════════════════\n")

    # Get all properties (we want websites for all, even if they have addresses)
    all_loans = session.query(Loan).all()
    all_props = all_loans  # Get websites for ALL properties

    # Group by state
    by_state = defaultdict(list)
    for prop in all_props:
        by_state[prop.state].append(prop)

    print(f"Total properties for website research: {len(all_props)}\n")
    print("Creating website verification tools...\n")

    for state in sorted(by_state.keys()):
        props = by_state[state]
        print(f"  {state}: {len(props)} properties")

        # Create CSV
        csv_path = create_state_website_csv(state, props)
        print(f"    ✓ {csv_path}")

        # Create HTML
        html_path = create_state_website_html(state, props)
        print(f"    ✓ {html_path}\n")

    session.close()

    print("\n" + "════════════════════════════════════════════════════════════════════════════════")
    print("WEBSITE VERIFICATION WORKFLOW READY")
    print("════════════════════════════════════════════════════════════════════════════════\n")

    print("Tools created for each state:")
    for state in sorted(by_state.keys()):
        print(f"  • {state}: {state.lower()}_website_lookup.html + {state.lower()}_website_lookup.csv")

    print("\n\nNext steps:")
    print("  1. Open [state]_website_lookup.html in your browser")
    print("  2. Click search links to find each property's official website")
    print("  3. Record: website URL, phone number, email, management company")
    print("  4. Fill in the CSV file")
    print("  5. Run: python scripts/update_[state]_websites_from_csv.py [state]_website_lookup.csv")
    print("  6. Repeat for each state")
    print("\nEstimated time: 3-5 minutes per property × 283 properties = 14-23 hours\n")


if __name__ == "__main__":
    main()
