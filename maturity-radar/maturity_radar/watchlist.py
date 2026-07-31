"""Assemble the watchlist: score a loan universe, filter to the box, rank by pressure."""

from datetime import date

from . import DEFAULT_MARKET_RATE, DEFAULT_REFI_DSCR_FLOOR
from .scoring import VALUATION_DATE, score_loan


def _dedupe(loans):
    """Collapse identical records (same property, market, maturity, and balance) that can appear
    when the same loan is disclosed across overlapping filings. Keeps first seen."""
    seen, out = set(), []
    for l in loans:
        key = (l.property_name, l.state, l.city, l.maturity, round(l.current_balance))
        if key in seen:
            continue
        seen.add(key)
        out.append(l)
    return out


def build_watchlist(loans, as_of: date = None,
                    market_rate: float = DEFAULT_MARKET_RATE,
                    floor: float = DEFAULT_REFI_DSCR_FLOOR,
                    states=None, min_score: float = 0.0, top_n: int = None,
                    drop_matured: bool = True):
    """Score every loan, drop already-matured/duplicate records, filter, and rank descending.

    Args:
        loans: iterable of Loan.
        as_of: valuation date (defaults to today).
        states: optional set/list of state codes to keep (e.g. {"TX", "GA"}).
        min_score: drop loans below this pressure score.
        top_n: keep only the top N after ranking.
        drop_matured: exclude loans whose maturity is already in the past.
    """
    as_of = as_of or date.today()
    scored = [score_loan(l, as_of, market_rate, floor) for l in _dedupe(loans)]
    if drop_matured:
        scored = [s for s in scored if s.months_to_maturity >= 0]
    if states:
        keep = set(states)
        scored = [s for s in scored if s.loan.state in keep]
    scored = [s for s in scored if s.pressure_score >= min_score]
    scored.sort(key=lambda s: s.pressure_score, reverse=True)
    if top_n is not None:
        scored = scored[:top_n]
    return scored
