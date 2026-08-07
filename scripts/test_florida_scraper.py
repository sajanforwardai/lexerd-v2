#!/usr/bin/env python3
"""Test Florida County Assessor scraper on sample properties"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.florida_assessor_enhanced import FloridaCountyAssessorEnhanced


def main():
    """Test the scraper on sample properties"""

    print("════════════════════════════════════════════════════════════════════")
    print("FLORIDA COUNTY ASSESSOR SCRAPER — TEST")
    print("════════════════════════════════════════════════════════════════════\n")

    assessor = FloridaCountyAssessorEnhanced()

    # Test properties from our database
    test_properties = [
        {
            'property_name': 'Clubside Apartments',
            'county': 'Sarasota',
            'city': 'Venice'
        },
        {
            'property_name': 'Beach Bluff Apartments',
            'county': 'Duval',
            'city': 'Jacksonville'
        },
        {
            'property_name': 'Warehouse Lofts',
            'county': 'Hillsborough',
            'city': 'Tampa'
        },
        {
            'property_name': 'Edison Grand',
            'county': 'Lee',
            'city': 'Fort Myers'
        },
        {
            'property_name': 'Innovo at Sunrise',
            'county': 'Broward',
            'city': 'Sunrise'
        },
        {
            'property_name': 'Danube Apartments',
            'county': 'Orange',
            'city': 'Orlando'
        },
    ]

    print("Testing scraper on 6 properties from our database:\n")

    for prop in test_properties:
        print(f"Searching: {prop['property_name']} ({prop['county']} County)")
        print(f"  Location: {prop['city']}, FL")

        result = assessor.search_by_county(
            property_name=prop['property_name'],
            county=prop['county'],
            city=prop['city']
        )

        if result:
            print(f"  Status: {result.get('status', 'unknown')}")
            print(f"  Address: {result.get('address', 'Not found')}")
            print(f"  Confidence: {result.get('confidence', 0):.0%}")
            print(f"  Source: {result.get('source')}")
            if 'note' in result:
                print(f"  Note: {result.get('note')}")
        else:
            print(f"  Status: Error or not found")

        print()

    # Batch test
    print("════════════════════════════════════════════════════════════════════")
    print("BATCH SEARCH TEST")
    print("════════════════════════════════════════════════════════════════════\n")

    batch_results = assessor.batch_search(test_properties)

    print("Results Summary:\n")
    found_count = 0
    for result in batch_results:
        status = "✓" if result['address'] else "✗"
        print(f"{status} {result['property_name']} ({result['county']})")
        if result['address']:
            found_count += 1
            print(f"  → {result['address']}")
        else:
            print(f"  Status: {result['status']}")

    print(f"\nTotal found: {found_count}/{len(batch_results)}")
    print(f"Coverage: {100*found_count/len(batch_results):.1f}%\n")

    print("✅ Scraper test complete!\n")
    print("Note: Some results may show 'requires_javascript' or 'not_found'")
    print("because these county systems require interactive access or have")
    print("dynamic content. Next step: integrate with Selenium for JavaScript-heavy sites.\n")


if __name__ == "__main__":
    main()
