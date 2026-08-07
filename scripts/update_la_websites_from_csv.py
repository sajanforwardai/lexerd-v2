#!/usr/bin/env python3
"""Update database with verified Louisiana websites from CSV"""

import sys
import csv
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.website_database import get_website_session, update_loan_website
from address_discovery_system.database import search_loans


def update_websites_from_csv(csv_file: str, confidence: float = 1.0, source: str = 'manual_verification'):
    """Load websites from CSV and update database"""

    print("════════════════════════════════════════════════════════════════════")
    print("UPDATE LA WEBSITES FROM CSV")
    print("════════════════════════════════════════════════════════════════════\n")

    # Read CSV
    print(f"Step 1: Reading {csv_file}...\n")
    rows = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"  Loaded {len(rows)} rows\n")

    # Filter to rows with websites
    with_websites = [r for r in rows if r.get('Property Website (to be filled)', '').strip()]
    print(f"Step 2: Found {len(with_websites)} rows with websites\n")

    if not with_websites:
        print("No websites found in CSV. Make sure 'Property Website (to be filled)' column is populated.\n")
        return

    # Update database
    session = get_website_session()
    updated = 0
    errors = 0

    print("Step 3: Updating database...\n")

    for row in with_websites:
        property_name = row.get('Property Name', '').strip()
        city = row.get('City', '').strip()
        county = row.get('County', '').strip()
        website_url = row.get('Property Website (to be filled)', '').strip()
        website_type = row.get('Website Type', 'official').strip()
        phone = row.get('Phone Number', '').strip()
        email = row.get('Email Address', '').strip()
        management_company = row.get('Management Company', '').strip()
        conf_str = row.get('Confidence', str(confidence)).strip()

        try:
            conf = float(conf_str)
        except ValueError:
            conf = confidence

        if not (property_name and city and website_url):
            print(f"  ⚠️  Skipping: Missing property_name, city, or website")
            continue

        # Find loan in database
        loans = search_loans(session, property_name=property_name, city=city, state='LA')

        if not loans:
            print(f"  ✗ {property_name} ({city}) — NOT FOUND in database")
            errors += 1
            continue

        # Update each matching loan
        for loan in loans:
            update_loan_website(
                session=session,
                loan_id=loan.id,
                website_url=website_url,
                website_type=website_type,
                source=source,
                confidence=conf,
                phone=phone if phone else None,
                email=email if email else None,
                management_company=management_company if management_company else None
            )

            print(f"  ✓ {property_name} ({city})")
            print(f"    → {website_url}")
            if phone:
                print(f"    📞 {phone}")
            if management_company:
                print(f"    🏢 {management_company}")
            updated += 1

    session.close()

    # Summary
    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("UPDATE COMPLETE")
    print("════════════════════════════════════════════════════════════════════\n")

    print(f"Updated: {updated} loans")
    print(f"Errors: {errors}")
    print(f"Total: {len(with_websites)}\n")

    if updated == len(with_websites):
        print("✅ All websites successfully updated!\n")
    elif updated > 0:
        print(f"⚠️  {updated}/{len(with_websites)} websites updated. Check errors above.\n")
    else:
        print("❌ No websites updated. Check CSV format and property names.\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_la_websites_from_csv.py <csv_file> [confidence] [source]")
        print("\nExample:")
        print("  python update_la_websites_from_csv.py la_website_lookup.csv 1.0 manual_verification")
        sys.exit(1)

    csv_file = sys.argv[1]
    confidence = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    source = sys.argv[3] if len(sys.argv) > 3 else 'manual_verification'

    update_websites_from_csv(csv_file, confidence, source)
