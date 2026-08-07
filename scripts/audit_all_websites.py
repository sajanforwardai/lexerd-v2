#!/usr/bin/env python3
"""Audit website coverage for all 8-state watchlist"""

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session
from address_discovery_system.models import Loan
from address_discovery_system.website_database import get_website_session
from address_discovery_system.website_model import Website


def audit_state_websites(session, state: str) -> dict:
    """Get website statistics for a state"""

    all_state = session.query(Loan).filter(Loan.state == state).all()

    # Get websites from website table
    website_session = get_website_session()
    all_loan_ids = [p.id for p in all_state]
    websites = website_session.query(Website).filter(Website.loan_id.in_(all_loan_ids)).all()
    website_session.close()

    loan_ids_with_websites = set(w.loan_id for w in websites)

    with_website = [p for p in all_state if p.id in loan_ids_with_websites]
    without_website = [p for p in all_state if p.id not in loan_ids_with_websites]

    # Website type breakdown
    by_type = defaultdict(int)
    for website in websites:
        if website.loan_id in loan_ids_with_websites:
            by_type[website.website_type or 'unknown'] += 1

    # Source breakdown
    by_source = defaultdict(int)
    for website in websites:
        by_source[website.website_source or 'unknown'] += 1

    return {
        'total': len(all_state),
        'with_website': len(with_website),
        'without_website': len(without_website),
        'coverage_pct': 100 * len(with_website) / len(all_state) if all_state else 0,
        'type_distribution': dict(by_type),
        'source_distribution': dict(by_source),
        'properties': all_state,
        'properties_with': with_website,
        'properties_without': without_website,
    }


def main():
    """Audit all websites"""

    session = get_session()

    # 8-state watchlist
    watchlist = ['AL', 'FL', 'GA', 'KS', 'KY', 'LA', 'NC', 'TX']

    print("════════════════════════════════════════════════════════════════════════════════")
    print("WEBSITE DISCOVERY AUDIT - ALL 8 STATES")
    print("════════════════════════════════════════════════════════════════════════════════\n")

    results = {}
    total_props = 0
    total_with = 0
    total_without = 0

    # Audit each state
    for state in watchlist:
        print(f"\n{'='*80}")
        print(f"  {state} - WEBSITE DISCOVERY AUDIT")
        print(f"{'='*80}\n")

        stats = audit_state_websites(session, state)
        results[state] = stats

        total_props += stats['total']
        total_with += stats['with_website']
        total_without += stats['without_website']

        # Display results
        print(f"Total properties: {stats['total']}")
        print(f"  ✓ With websites: {stats['with_website']} ({stats['coverage_pct']:.1f}%)")
        print(f"  ✗ Without websites: {stats['without_website']} ({100-stats['coverage_pct']:.1f}%)\n")

        # Website type distribution
        if stats['with_website'] > 0:
            print(f"Website types ({stats['with_website']} properties with websites):")
            for website_type in sorted(stats['type_distribution'].keys()):
                count = stats['type_distribution'][website_type]
                pct = 100 * count / stats['with_website']
                print(f"  {website_type:20s}: {count:2d} ({pct:5.1f}%)")

        # Source breakdown
        if stats['with_website'] > 0:
            print(f"\nWebsites by source ({stats['with_website']} total):")
            for source in sorted(stats['source_distribution'].keys()):
                count = stats['source_distribution'][source]
                pct = 100 * count / stats['with_website']
                print(f"  {source:30s}: {count:2d} ({pct:5.1f}%)")

        # Properties without websites (first 5)
        if stats['without_website'] > 0:
            print(f"\nFirst 5 properties without websites:")
            for prop in stats['properties_without'][:5]:
                print(f"  • {prop.property_name:35s} | {prop.city:15s} | {prop.county or 'Unknown'}")
            if stats['without_website'] > 5:
                print(f"  ... and {stats['without_website']-5} more")

    session.close()

    # Summary across all states
    print(f"\n\n{'='*80}")
    print("SUMMARY - ALL 8 STATES")
    print(f"{'='*80}\n")

    print("Website coverage by state:")
    print(f"{'STATE':6s} {'TOTAL':7s} {'WITH':7s} {'WITHOUT':10s} {'COVERAGE':12s}")
    print("-" * 48)

    for state in watchlist:
        stats = results[state]
        print(f"{state:6s} {stats['total']:7d} {stats['with_website']:7d} {stats['without_website']:10d} {stats['coverage_pct']:11.1f}%")

    print("-" * 48)
    overall_coverage = 100 * total_with / total_props if total_props else 0
    print(f"{'TOTAL':6s} {total_props:7d} {total_with:7d} {total_without:10d} {overall_coverage:11.1f}%\n")

    # Summary statistics
    print(f"{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}\n")

    print(f"Total properties across 8 states: {total_props}")
    print(f"Properties with websites: {total_with} ({overall_coverage:.1f}%)")
    print(f"Properties without websites: {total_without} ({100-overall_coverage:.1f}%)")
    print(f"\nTarget for website discovery: {total_without} properties")
    print(f"Estimated time to research (3-5 min each): {total_without*3//60}-{total_without*5//60} hours\n")

    # Website type summary
    total_type_dist = defaultdict(int)
    for state, stats in results.items():
        for website_type, count in stats['type_distribution'].items():
            total_type_dist[website_type] += count

    if total_type_dist:
        print(f"Overall website types ({total_with} properties with websites):")
        for website_type in sorted(total_type_dist.keys()):
            count = total_type_dist[website_type]
            pct = 100 * count / total_with
            print(f"  {website_type:20s}: {count:3d} ({pct:5.1f}%)")

    # Source summary
    total_source_dist = defaultdict(int)
    for state, stats in results.items():
        for source, count in stats['source_distribution'].items():
            total_source_dist[source] += count

    if total_source_dist:
        print(f"\nOverall websites by source ({total_with} total):")
        for source in sorted(total_source_dist.keys()):
            count = total_source_dist[source]
            pct = 100 * count / total_with
            print(f"  {source:30s}: {count:3d} ({pct:5.1f}%)")

    print(f"\n{'='*80}")
    print("✅ AUDIT COMPLETE")
    print(f"{'='*80}\n")

    print("Next steps:")
    print("  1. Start website discovery with states at 0% coverage")
    print("  2. Use [state]_website_lookup.html for each state")
    print("  3. Run update_[state]_websites_from_csv.py for batch import")
    print("  4. Re-run this audit to track progress\n")


if __name__ == "__main__":
    main()
