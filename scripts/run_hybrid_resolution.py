#!/usr/bin/env python3
"""Run hybrid address resolution: auto + manual separation"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session, get_loans_by_state, update_loan_address
from address_discovery_system.models import Discovery
from address_discovery_system.hybrid_address_resolver import HybridAddressResolver


def main():
    """Run hybrid resolution"""

    print("════════════════════════════════════════════════════════════════════")
    print("HYBRID ADDRESS RESOLUTION")
    print("════════════════════════════════════════════════════════════════════\n")

    session = get_session()

    # Load properties
    all_florida = get_loans_by_state(session, 'FL')
    florida_missing = [p for p in all_florida if not p.property_address]

    print(f"Step 1: Loaded {len(florida_missing)} properties without addresses\n")

    properties = [
        {
            'property_name': p.property_name,
            'city': p.city,
            'county': p.county,
            'state': 'FL',
            'loan_id': p.id
        }
        for p in florida_missing
    ]

    # Run hybrid resolution
    print("Step 2: Running hybrid resolution...\n")
    resolver = HybridAddressResolver()
    results = resolver.batch_resolve(properties)

    # Update database with found addresses
    print("\nStep 3: Updating database with found addresses...\n")

    for result in results['found']:
        loan_id = result.get('loan_id')
        if loan_id:
            update_loan_address(
                session=session,
                loan_id=loan_id,
                address=result['address'],
                source=result['source'],
                confidence=result['confidence']
            )

            discovery = Discovery(
                loan_id=loan_id,
                discovered_address=result['address'],
                source=result['source'],
                confidence=result['confidence'],
                accepted=1
            )
            session.add(discovery)
            session.commit()

            print(f"  ✓ {result['property_name']}: {result['address']}")

    session.close()

    # Export manual verification list
    if results['not_found']:
        print("\nStep 4: Creating manual verification list...\n")
        filename = resolver.export_manual_verification_csv(results['not_found'], 'manual_verification.csv')
        print(f"  ✓ Exported: {filename}")

    # Summary
    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("RESOLUTION COMPLETE")
    print("════════════════════════════════════════════════════════════════════\n")

    summary = results['summary']
    print(f"Results:")
    print(f"  Total properties: {summary['total']}")
    print(f"  Automatically found: {summary['automatically_found']}")
    print(f"  Need manual verification: {summary['needs_manual_verification']}")
    print(f"  Success rate: {summary['success_rate']}\n")

    if results['not_found']:
        print(f"Next steps:")
        print(f"  1. Open: manual_verification.csv")
        print(f"  2. For each property, click Search URL")
        print(f"  3. Find address on Google/Apartments.com/Zillow")
        print(f"  4. Fill in Address column")
        print(f"  5. Run: python scripts/update_fl_addresses_from_csv.py manual_verification.csv\n")

    print("✅ Hybrid resolution complete!\n")


if __name__ == "__main__":
    main()
