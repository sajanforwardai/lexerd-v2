#!/usr/bin/env python3
"""Update database with verified Louisiana addresses from CSV"""

import sys
import csv
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session, update_loan_address, search_loans
from address_discovery_system.models import Discovery


def update_from_csv(csv_file: str, confidence: float = 1.0, source: str = 'manual_verification'):
    """Load addresses from CSV and update database"""

    print("════════════════════════════════════════════════════════════════════")
    print("UPDATE LA ADDRESSES FROM CSV")
    print("════════════════════════════════════════════════════════════════════\n")

    # Read CSV
    print(f"Step 1: Reading {csv_file}...\n")
    rows = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"  Loaded {len(rows)} rows\n")

    # Filter to rows with addresses
    with_addresses = [r for r in rows if r.get('Address (to be filled)', '').strip()]
    print(f"Step 2: Found {len(with_addresses)} rows with addresses\n")

    if not with_addresses:
        print("No addresses found in CSV. Make sure 'Address (to be filled)' column is populated.\n")
        return

    # Update database
    session = get_session()
    updated = 0
    errors = 0

    print("Step 3: Updating database...\n")

    for row in with_addresses:
        property_name = row.get('Property Name', '').strip()
        city = row.get('City', '').strip()
        county = row.get('County', '').strip()
        address = row.get('Address (to be filled)', '').strip()
        conf_str = row.get('Confidence', str(confidence)).strip()

        try:
            conf = float(conf_str)
        except ValueError:
            conf = confidence

        if not (property_name and city and address):
            print(f"  ⚠️  Skipping: Missing property_name, city, or address")
            continue

        # Find loan in database
        loans = search_loans(session, property_name=property_name, city=city, state='LA')

        if not loans:
            print(f"  ✗ {property_name} ({city}) — NOT FOUND in database")
            errors += 1
            continue

        # Update each matching loan
        for loan in loans:
            update_loan_address(
                session=session,
                loan_id=loan.id,
                address=address,
                source=source,
                confidence=conf
            )

            # Log discovery
            discovery = Discovery(
                loan_id=loan.id,
                discovered_address=address,
                source=source,
                confidence=conf,
                accepted=1
            )
            session.add(discovery)
            session.commit()

            print(f"  ✓ {property_name} ({city})")
            print(f"    → {address}")
            updated += 1

    session.close()

    # Summary
    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("UPDATE COMPLETE")
    print("════════════════════════════════════════════════════════════════════\n")

    print(f"Updated: {updated} loans")
    print(f"Errors: {errors}")
    print(f"Total: {len(with_addresses)}\n")

    if updated == len(with_addresses):
        print("✅ All addresses successfully updated!\n")
    elif updated > 0:
        print(f"⚠️  {updated}/{len(with_addresses)} addresses updated. Check errors above.\n")
    else:
        print("❌ No addresses updated. Check CSV format and property names.\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_la_addresses_from_csv.py <csv_file> [confidence] [source]")
        print("\nExample:")
        print("  python update_la_addresses_from_csv.py la_property_lookup.csv 1.0 manual_verification")
        sys.exit(1)

    csv_file = sys.argv[1]
    confidence = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    source = sys.argv[3] if len(sys.argv) > 3 else 'manual_verification'

    update_from_csv(csv_file, confidence, source)
