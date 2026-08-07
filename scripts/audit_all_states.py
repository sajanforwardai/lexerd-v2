#!/usr/bin/env python3
"""Audit address coverage for all 8-state watchlist"""

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session
from address_discovery_system.models import Loan


def audit_state(session, state: str) -> dict:
    """Get audit statistics for a state"""

    all_state = session.query(Loan).filter(Loan.state == state).all()

    with_address = [p for p in all_state if p.property_address]
    without_address = [p for p in all_state if not p.property_address]

    # Confidence distribution
    confidence_buckets = defaultdict(int)
    for prop in with_address:
        confidence = prop.address_confidence or 0
        bucket = int(confidence * 10)
        confidence_buckets[bucket] += 1

    # Source breakdown
    by_source = defaultdict(int)
    for prop in with_address:
        source = prop.address_source or "unknown"
        by_source[source] += 1

    return {
        'total': len(all_state),
        'with_address': len(with_address),
        'without_address': len(without_address),
        'coverage_pct': 100 * len(with_address) / len(all_state) if all_state else 0,
        'confidence_distribution': dict(confidence_buckets),
        'source_distribution': dict(by_source),
        'properties': all_state
    }


def main():
    """Audit all states"""

    session = get_session()

    # 8-state watchlist
    watchlist = ['AL', 'FL', 'GA', 'KS', 'KY', 'LA', 'NC', 'TX']

    print("════════════════════════════════════════════════════════════════════════════════")
    print("ADDRESS COVERAGE AUDIT - ALL 8 STATES")
    print("════════════════════════════════════════════════════════════════════════════════\n")

    results = {}
    total_props = 0
    total_with = 0
    total_without = 0

    # Audit each state
    for state in watchlist:
        print(f"\n{'='*80}")
        print(f"  {state} - ADDRESS COVERAGE AUDIT")
        print(f"{'='*80}\n")

        stats = audit_state(session, state)
        results[state] = stats

        total_props += stats['total']
        total_with += stats['with_address']
        total_without += stats['without_address']

        # Display results
        print(f"Total properties: {stats['total']}")
        print(f"  ✓ With addresses: {stats['with_address']} ({stats['coverage_pct']:.1f}%)")
        print(f"  ✗ Without addresses: {stats['without_address']} ({100-stats['coverage_pct']:.1f}%)\n")

        # Confidence distribution
        if stats['with_address'] > 0:
            print(f"Confidence distribution ({stats['with_address']} properties with addresses):")
            for conf_level in sorted(stats['confidence_distribution'].keys()):
                min_conf = conf_level / 10
                max_conf = (conf_level + 1) / 10
                count = stats['confidence_distribution'][conf_level]
                pct = 100 * count / stats['with_address']
                bar = '█' * int(pct / 5)
                print(f"  {min_conf:.1f}–{max_conf:.1f}: {count:2d} ({pct:5.1f}%) {bar}")

        # Source breakdown
        if stats['with_address'] > 0:
            print(f"\nAddresses by source ({stats['with_address']} total):")
            for source in sorted(stats['source_distribution'].keys()):
                count = stats['source_distribution'][source]
                pct = 100 * count / stats['with_address']
                print(f"  {source:30s}: {count:2d} ({pct:5.1f}%)")

        # Properties without addresses (first 5)
        if stats['without_address'] > 0:
            print(f"\nFirst 5 properties without addresses:")
            for prop in stats['properties'][:5]:
                if not prop.property_address:
                    print(f"  • {prop.property_name:35s} | {prop.city:15s} | {prop.county or 'Unknown'}")
            if stats['without_address'] > 5:
                print(f"  ... and {stats['without_address']-5} more")

    session.close()

    # Summary across all states
    print(f"\n\n{'='*80}")
    print("SUMMARY - ALL 8 STATES")
    print(f"{'='*80}\n")

    print("Coverage by state:")
    print(f"{'STATE':6s} {'TOTAL':7s} {'WITH':7s} {'WITHOUT':10s} {'COVERAGE':12s}")
    print("-" * 48)

    for state in watchlist:
        stats = results[state]
        print(f"{state:6s} {stats['total']:7d} {stats['with_address']:7d} {stats['without_address']:10d} {stats['coverage_pct']:11.1f}%")

    print("-" * 48)
    overall_coverage = 100 * total_with / total_props if total_props else 0
    print(f"{'TOTAL':6s} {total_props:7d} {total_with:7d} {total_without:10d} {overall_coverage:11.1f}%\n")

    # Summary statistics
    print(f"{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}\n")

    print(f"Total properties across 8 states: {total_props}")
    print(f"Properties with addresses: {total_with} ({overall_coverage:.1f}%)")
    print(f"Properties without addresses: {total_without} ({100-overall_coverage:.1f}%)")
    print(f"\nTarget for verification: {total_without} properties")
    print(f"Estimated time to verify (5-10 min each): {total_without*5//60}-{total_without*10//60} hours\n")

    # Confidence summary
    total_confidence_dist = defaultdict(int)
    for state, stats in results.items():
        for conf_level, count in stats['confidence_distribution'].items():
            total_confidence_dist[conf_level] += count

    if total_confidence_dist:
        print(f"Overall confidence distribution ({total_with} properties with addresses):")
        for conf_level in sorted(total_confidence_dist.keys()):
            min_conf = conf_level / 10
            max_conf = (conf_level + 1) / 10
            count = total_confidence_dist[conf_level]
            pct = 100 * count / total_with
            bar = '█' * int(pct / 3)
            print(f"  {min_conf:.1f}–{max_conf:.1f}: {count:3d} ({pct:5.1f}%) {bar}")

    # Source summary
    total_source_dist = defaultdict(int)
    for state, stats in results.items():
        for source, count in stats['source_distribution'].items():
            total_source_dist[source] += count

    if total_source_dist:
        print(f"\nOverall addresses by source ({total_with} total):")
        for source in sorted(total_source_dist.keys()):
            count = total_source_dist[source]
            pct = 100 * count / total_with
            print(f"  {source:30s}: {count:3d} ({pct:5.1f}%)")

    print(f"\n{'='*80}")
    print("✅ AUDIT COMPLETE")
    print(f"{'='*80}\n")

    print("Next steps:")
    print("  1. Start verification workflow for states with lowest coverage")
    print("  2. Use [state]_property_lookup.html for each state")
    print("  3. Run update_[state]_addresses_from_csv.py for batch import")
    print("  4. Re-run this audit to track progress\n")


if __name__ == "__main__":
    main()
