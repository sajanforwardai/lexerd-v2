"""Dashboard Loan Filter — Keep only 8-state watchlist loans"""

from typing import List, Tuple


DASHBOARD_STATES = {"AL", "FL", "GA", "KS", "KY", "LA", "NC", "TX"}
"""8-state watchlist: Alabama, Florida, Georgia, Kansas, Kentucky, Louisiana, North Carolina, Texas"""


def filter_dashboard_loans(loans) -> List:
    """Filter loans to keep only those in the 8-state dashboard.

    Removes:
    - Loans outside the 8-state watchlist
    - Portfolio-based properties (with 'portfolio' in name)
    - Duplicate entries (keeps first occurrence only)

    Args:
        loans: List of loan objects with state attribute

    Returns:
        Filtered list of unique, non-portfolio loans in dashboard states
    """
    seen = {}
    filtered = []

    for loan in loans:
        # 1. Filter by state
        if loan.state not in DASHBOARD_STATES:
            continue

        # 2. Skip portfolio properties
        if 'portfolio' in (loan.property_name or "").lower():
            continue

        # 3. Skip duplicates
        key = (loan.property_name, loan.city, loan.state)
        if key in seen:
            continue

        seen[key] = True
        filtered.append(loan)

    return filtered


def get_dashboard_stats(loans) -> dict:
    """Get statistics for filtered dashboard loans.

    Args:
        loans: List of loan objects

    Returns:
        Dictionary with filtering statistics
    """
    total_input = len(loans)
    filtered = filter_dashboard_loans(loans)
    total_output = len(filtered)

    removed_state = sum(1 for l in loans if l.state not in DASHBOARD_STATES)
    removed_portfolio = sum(1 for l in loans if l.state in DASHBOARD_STATES and 'portfolio' in (l.property_name or "").lower())

    return {
        'total_input': total_input,
        'total_output': total_output,
        'removed_by_state': removed_state,
        'removed_by_portfolio': removed_portfolio,
        'removed_by_duplicate': removed_state + removed_portfolio + removed_state + removed_portfolio - total_input + total_output,
        'retention_rate': (total_output / total_input * 100) if total_input > 0 else 0,
    }
