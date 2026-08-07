#!/usr/bin/env python3
"""Audit Florida County Assessor discovery results"""

import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session, get_loans_by_state


def main():
    """Audit Florida discovery results"""

    print("════════════════════════════════════════════════════════════════════")
    print("FLORIDA COUNTY ASSESSOR DISCOVERY AUDIT")
    print("════════════════════════════════════════════════════════════════════\n")

    session = get_session()

    # Get all Florida loans
    all_florida = get_loans_by_state(session, 'FL')
    print(f"Total Florida properties: {len(all_florida)}\n")

    # Breakdown by address status
    with_address = [p for p in all_florida if p.property_address]
    without_address = [p for p in all_florida if not p.property_address]
    assessor_source = [p for p in with_address if 'assessor' in (p.address_source or '').lower()]

    print("Address Status:")
    print(f"  ✓ With addresses: {len(with_address)} ({100*len(with_address)/len(all_florida):.1f}%)")
    print(f"    ├─ From assessor scraper: {len(assessor_source)} ({100*len(assessor_source)/len(with_address):.1f}%)")
    print(f"    └─ From other sources: {len(with_address)-len(assessor_source)}")
    print(f"  ✗ Without addresses: {len(without_address)} ({100*len(without_address)/len(all_florida):.1f}%)\n")

    # Coverage by county
    print("Coverage by County (from assessor):\n")
    by_county = defaultdict(lambda: {'total': 0, 'with_address': 0, 'assessor_found': 0})

    for prop in all_florida:
        county = prop.county or "Unknown"
        by_county[county]['total'] += 1
        if prop.property_address:
            by_county[county]['with_address'] += 1
            if 'assessor' in (prop.address_source or '').lower():
                by_county[county]['assessor_found'] += 1

    for county in sorted(by_county.keys()):
        stats = by_county[county]
        coverage = 100 * stats['with_address'] / stats['total']
        assessor_pct = 100 * stats['assessor_found'] / stats['total']
        print(f"  {county:20s}: {stats['with_address']}/{stats['total']} ({coverage:5.1f}%) [Assessor: {stats['assessor_found']}]")

    # Confidence distribution
    print("\n\nAddress Confidence Distribution:\n")
    confidence_buckets = defaultdict(int)
    for prop in with_address:
        confidence = prop.address_confidence or 0
        bucket = int(confidence * 10)
        confidence_buckets[bucket] += 1

    for bucket in sorted(confidence_buckets.keys()):
        min_conf = bucket / 10
        max_conf = (bucket + 1) / 10
        count = confidence_buckets[bucket]
        pct = 100 * count / len(with_address)
        bar = '█' * int(pct / 5)
        print(f"  {min_conf:.1f}–{max_conf:.1f}: {count:2d} ({pct:5.1f}%) {bar}")

    # Source breakdown
    print("\n\nAddresses by Source:\n")
    by_source = defaultdict(int)
    for prop in with_address:
        source = prop.address_source or "unknown"
        by_source[source] += 1

    for source in sorted(by_source.keys()):
        count = by_source[source]
        pct = 100 * count / len(with_address)
        print(f"  {source:30s}: {count:2d} ({pct:5.1f}%)")

    # Properties still needing addresses
    if without_address:
        print("\n\nProperties Without Addresses:\n")
        for prop in without_address[:10]:
            print(f"  • {prop.property_name:35s} ({prop.county:15s}, {prop.city})")
        if len(without_address) > 10:
            print(f"  ... and {len(without_address)-10} more")

    # Summary
    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("SUMMARY")
    print("════════════════════════════════════════════════════════════════════\n")

    print(f"Florida Dashboard Coverage:")
    print(f"  Overall: {100*len(with_address)/len(all_florida):.1f}% ({len(with_address)}/{len(all_florida)})")
    print(f"  From assessor scraper: {100*len(assessor_source)/len(all_florida):.1f}% ({len(assessor_source)}/{len(all_florida)})")
    print(f"  Coverage gap: {100*len(without_address)/len(all_florida):.1f}% ({len(without_address)} properties)\n")

    if without_address:
        print("Next Steps:")
        print(f"  1. Run Selenium scraper for {len(without_address)} remaining properties")
        print("  2. Review scraper results with confidence thresholds")
        print("  3. Manual verification for <0.75 confidence matches")
        print("  4. Batch email to county assessors for unmatched properties\n")

    session.close()

    print("✅ Audit complete!\n")


if __name__ == "__main__":
    main()
