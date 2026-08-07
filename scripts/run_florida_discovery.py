#!/usr/bin/env python3
"""Run Florida County Assessor discovery on all FL properties without addresses"""

import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import (
    get_session, get_loans_by_state, update_loan_address
)
from address_discovery_system.models import Discovery
from address_discovery_system.florida_assessor import FloridaCountyAssessor


def main():
    """Run Florida County Assessor discovery"""

    print("════════════════════════════════════════════════════════════════════")
    print("FLORIDA COUNTY ASSESSOR DISCOVERY")
    print("════════════════════════════════════════════════════════════════════\n")

    session = get_session()

    # Get all Florida loans
    print("Step 1: Loading Florida properties...")
    all_florida = get_loans_by_state(session, 'FL')
    print(f"  Total Florida properties: {len(all_florida)}\n")

    # Filter to those without addresses
    florida_missing = [p for p in all_florida if not p.property_address]
    print(f"Step 2: Properties without addresses: {len(florida_missing)}\n")

    # Group by county
    by_county = defaultdict(list)
    for prop in florida_missing:
        county = prop.county or "Unknown"
        by_county[county].append(prop)

    print("Step 3: Properties by county:\n")
    for county in sorted(by_county.keys()):
        print(f"  {county}: {len(by_county[county])} properties")

    # Initialize assessor
    print("\nStep 4: Initializing Florida County Assessor...\n")
    assessor = FloridaCountyAssessor()
    supported = assessor.list_supported_counties()
    print(f"  Supported counties: {len(supported)}")
    print(f"  {', '.join(supported)}\n")

    # Run discovery by county
    print("Step 5: Running discovery...\n")
    total_found = 0
    total_searched = 0
    results_by_county = {}

    for county in sorted(by_county.keys()):
        properties = by_county[county]
        print(f"\n  ╭─ {county} ({len(properties)} properties)")

        # Prepare search items
        search_items = [
            {
                'property_name': p.property_name,
                'county': county,
                'city': p.city
            }
            for p in properties
        ]

        # Run batch search
        batch_results = assessor.batch_search(search_items)

        # Process results
        found_count = 0
        for result, loan in zip(batch_results, properties):
            total_searched += 1

            if result['address']:
                found_count += 1
                total_found += 1

                # Update database
                update_loan_address(
                    session,
                    loan.id,
                    result['address'],
                    source=result['source'],
                    confidence=result['confidence']
                )

                # Log discovery
                discovery = Discovery(
                    loan_id=loan.id,
                    discovered_address=result['address'],
                    source=result['source'],
                    confidence=result['confidence'],
                    accepted=1
                )
                session.add(discovery)

                print(f"      ✓ {loan.property_name}")
                print(f"        → {result['address']}")
            else:
                print(f"      ✗ {loan.property_name}")

        session.commit()
        print(f"  ╰─ Found: {found_count}/{len(properties)}")
        results_by_county[county] = {'searched': len(properties), 'found': found_count}

    # Summary
    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("DISCOVERY COMPLETE")
    print("════════════════════════════════════════════════════════════════════\n")

    print(f"Total searched: {total_searched}")
    print(f"Total found: {total_found}")
    print(f"Coverage gained: {total_found}/{len(florida_missing)} ({100*total_found/len(florida_missing):.1f}%)\n")

    print("By County:")
    for county in sorted(results_by_county.keys()):
        res = results_by_county[county]
        pct = 100 * res['found'] / res['searched'] if res['searched'] > 0 else 0
        print(f"  {county}: {res['found']}/{res['searched']} ({pct:.0f}%)")

    session.close()

    print("\n✅ Florida discovery complete!\n")


if __name__ == "__main__":
    main()
