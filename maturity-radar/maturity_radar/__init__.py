"""Maturity Radar — a refinance-pressure watchlist for small multifamily.

Not a "motivated-seller list." A cultivation queue: it flags owners whose loans mature into
a refinance they will struggle to clear, so a buyer can build the relationship 12+ months
before the forcing event — where the entry may be a purchase OR rescue equity / pref / recap.

Scoped per the 5-round council (CONDITIONAL_GO, 73%): the scoring engine is the automatable
core; owner enrichment is human-in-the-loop; coverage is securitized loans only.
"""

VALUATION_DATE_ISO = "2026-07-23"
DEFAULT_MARKET_RATE = 0.06      # today's ~agency multifamily refinance rate
DEFAULT_REFI_DSCR_FLOOR = 1.25  # coverage a lender requires to refinance
