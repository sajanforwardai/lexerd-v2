#!/usr/bin/env python3
"""Run batch address fetcher on all 30 Florida properties"""

import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session, get_loans_by_state, update_loan_address
from address_discovery_system.models import Discovery
from address_discovery_system.batch_address_fetcher import BatchAddressFetcher


def main():
    """Run batch address fetcher"""

    print("════════════════════════════════════════════════════════════════════")
    print("BATCH ADDRESS FETCHER - FLORIDA PROPERTIES")
    print("════════════════════════════════════════════════════════════════════\n")

    session = get_session()

    # Get all Florida loans without addresses
    all_florida = get_loans_by_state(session, 'FL')
    florida_missing = [p for p in all_florida if not p.property_address]

    print(f"Step 1: Loaded {len(florida_missing)} Florida properties without addresses\n")

    # Convert to fetcher format
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

    # Initialize fetcher with Google Maps API key if available
    google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    if google_maps_api_key:
        print("Step 2: Initializing fetcher with Google Maps API key\n")
    else:
        print("Step 2: Initializing fetcher (no Google Maps API key - using web sources)\n")

    fetcher = BatchAddressFetcher(google_maps_api_key=google_maps_api_key)

    # Run batch fetch
    print("Step 3: Running batch address fetch...\n")
    results = fetcher.batch_fetch(properties, use_api=bool(google_maps_api_key))

    # Process results and update database
    print("\nStep 4: Updating database with found addresses...\n")

    updated = 0
    found = 0

    for result in results:
        if result['status'] == 'found' and result['address']:
            found += 1

            # Find loan by ID
            loan_id = result.get('loan_id')
            if loan_id:
                update_loan_address(
                    session=session,
                    loan_id=loan_id,
                    address=result['address'],
                    source=result['source'],
                    confidence=result['confidence']
                )

                # Log discovery
                discovery = Discovery(
                    loan_id=loan_id,
                    discovered_address=result['address'],
                    source=result['source'],
                    confidence=result['confidence'],
                    accepted=1
                )
                session.add(discovery)
                session.commit()

                print(f"  ✓ Updated: {result['property_name']}")
                print(f"    → {result['address']}")
                print(f"    → Confidence: {result['confidence']:.0%}, Source: {result['source']}\n")
                updated += 1

    session.close()

    # Summary
    print("════════════════════════════════════════════════════════════════════")
    print("BATCH FETCH COMPLETE")
    print("════════════════════════════════════════════════════════════════════\n")

    print(f"Results:")
    print(f"  Total properties: {len(properties)}")
    print(f"  Addresses found: {found}")
    print(f"  Database updated: {updated}")
    print(f"  Success rate: {100*found/len(properties):.1f}%\n")

    if found < len(properties):
        remaining = len(properties) - found
        print(f"Remaining properties without addresses: {remaining}")
        print("Next step: Use manual verification tool (fl_property_lookup.html)\n")

    print("✅ Batch fetch complete!\n")


if __name__ == "__main__":
    main()
