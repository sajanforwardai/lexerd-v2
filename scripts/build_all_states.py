#!/usr/bin/env python3
"""Build address discovery system for all 8-state watchlist"""

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.database import get_session
from address_discovery_system.models import Loan
from address_discovery_system.florida_direct_lookup import FloridaDirectLookup


def deduplicate_state(session, state: str) -> int:
    """Remove duplicates for a state"""
    all_state = session.query(Loan).filter(Loan.state == state).all()

    groups = defaultdict(list)
    for prop in all_state:
        key = (prop.property_name.lower().strip(), prop.city.lower().strip())
        groups[key].append(prop)

    duplicates_to_remove = []
    for key, props in groups.items():
        if len(props) > 1:
            with_addr = [p for p in props if p.property_address]
            if with_addr:
                keep = with_addr[0]
            else:
                keep = props[0]

            for p in props:
                if p.id != keep.id:
                    duplicates_to_remove.append(p.id)

    # Remove duplicates
    for dup_id in duplicates_to_remove:
        loan = session.query(Loan).filter(Loan.id == dup_id).first()
        if loan:
            session.delete(loan)

    session.commit()
    return len(duplicates_to_remove)


def generate_lookup_tools(session, state: str):
    """Generate lookup tools for a state"""
    from address_discovery_system.models import Loan

    all_state = session.query(Loan).filter(Loan.state == state).all()
    state_missing = [p for p in all_state if not p.property_address]

    properties = [
        {
            'property_name': p.property_name,
            'city': p.city,
            'county': p.county or 'Unknown',
            'state': state
        }
        for p in state_missing
    ]

    # Generate CSV
    csv_file = f'{state.lower()}_property_lookup.csv'
    FloridaDirectLookup.export_lookup_csv(properties, csv_file)

    # Generate HTML
    html_file = f'{state.lower()}_property_lookup.html'
    FloridaDirectLookup.export_lookup_html(properties, html_file)

    return len(properties), csv_file, html_file


def main():
    """Process all remaining states"""

    session = get_session()

    # 8-state watchlist (already done: FL, TX)
    watchlist = ['AL', 'GA', 'KS', 'KY', 'LA', 'NC']
    done_states = ['FL', 'TX']

    print("════════════════════════════════════════════════════════════════════")
    print("BUILD ADDRESS DISCOVERY FOR ALL REMAINING STATES")
    print("════════════════════════════════════════════════════════════════════\n")

    print(f"Already completed: {', '.join(done_states)}\n")
    print(f"Processing: {', '.join(watchlist)}\n")

    results = {}

    for state in watchlist:
        print(f"\n─── {state} ───")

        # Get properties
        all_state = session.query(Loan).filter(Loan.state == state).all()
        print(f"Total: {len(all_state)} properties")

        # Deduplicate
        removed = deduplicate_state(session, state)
        if removed:
            print(f"Removed duplicates: {removed}")
            # Re-query after dedup
            all_state = session.query(Loan).filter(Loan.state == state).all()

        # Generate tools
        without_addr = sum(1 for p in all_state if not p.property_address)
        if without_addr > 0:
            count, csv_f, html_f = generate_lookup_tools(session, state)
            print(f"Generated lookup tools: {count} properties")
            print(f"  • {csv_f}")
            print(f"  • {html_f}")
            results[state] = {'total': len(all_state), 'missing': count, 'removed': removed}
        else:
            print(f"All properties have addresses ✓")
            results[state] = {'total': len(all_state), 'missing': 0, 'removed': removed}

    session.close()

    # Summary
    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("SUMMARY - ALL STATES")
    print("════════════════════════════════════════════════════════════════════\n")

    total_props = 0
    total_missing = 0
    total_removed = 0

    for state in sorted(results.keys()):
        r = results[state]
        total_props += r['total']
        total_missing += r['missing']
        total_removed += r['removed']
        print(f"{state}: {r['total']:3d} total | {r['missing']:3d} missing | {r['removed']:2d} removed")

    print(f"\nTOTAL: {total_props} properties")
    print(f"MISSING ADDRESSES: {total_missing} ({100*total_missing/total_props:.1f}%)")
    print(f"DUPLICATES REMOVED: {total_removed}\n")

    print("✅ All states processed!\n")
    print("Next steps:")
    print("  1. Verify addresses using state-specific HTML tools")
    print("  2. Use import scripts to batch update database")
    print("  3. Run audit scripts to check coverage\n")


if __name__ == "__main__":
    main()
