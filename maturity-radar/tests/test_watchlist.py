"""Watchlist assembly tests: ranking, filtering, and that the sample universe behaves."""

from maturity_radar.sample_data import sample_loans
from maturity_radar.watchlist import build_watchlist


class TestWatchlist:
    def test_ranks_descending(self):
        wl = build_watchlist(sample_loans())
        scores = [s.pressure_score for s in wl]
        assert scores == sorted(scores, reverse=True)

    def test_state_filter(self):
        tx = build_watchlist(sample_loans(), states={"TX"})
        assert all(s.loan.state == "TX" for s in tx)
        ga = build_watchlist(sample_loans(), states={"GA"})
        assert all(s.loan.state == "GA" for s in ga)

    def test_min_score_filter(self):
        wl = build_watchlist(sample_loans(), min_score=50)
        assert all(s.pressure_score >= 50 for s in wl)

    def test_top_n(self):
        wl = build_watchlist(sample_loans(), top_n=5)
        assert len(wl) == 5

    def test_control_loan_ranks_last(self):
        """The clean-refi control loan must sink to the bottom of the list."""
        wl = build_watchlist(sample_loans())
        assert "control" in wl[-1].loan.property_name.lower()

    def test_top_loans_are_actually_stressed(self):
        wl = build_watchlist(sample_loans(), top_n=5)
        for s in wl:
            assert s.projected_refi_dscr < 1.25  # every top loan fails a clean refi

    def test_universe_has_both_markets(self):
        states = {s.loan.state for s in build_watchlist(sample_loans())}
        assert states == {"TX", "GA"}


class TestGateFixes:
    def test_dedupes_identical_loans(self):
        from datetime import date
        from maturity_radar.models import Loan
        from maturity_radar.watchlist import build_watchlist
        dup = Loan("A", "Twin Towers", "Houston", "Harris", "TX", 100, 2018,
                   5_000_000, 5_000_000, 0.04, date(2027, 6, 1), True, 300_000, 1.2, 0.9)
        dup2 = Loan("B", "Twin Towers", "Houston", "Harris", "TX", 100, 2018,
                    5_000_000, 5_000_000, 0.04, date(2027, 6, 1), True, 300_000, 1.2, 0.9)
        wl = build_watchlist([dup, dup2])
        assert len(wl) == 1

    def test_drops_matured_loans(self):
        from datetime import date
        from maturity_radar.models import Loan
        from maturity_radar.watchlist import build_watchlist
        past = Loan("P", "Old Deal", "Dallas", "Dallas", "TX", 100, 2015,
                    4_000_000, 4_000_000, 0.04, date(2020, 1, 1), True, 250_000, 1.2, 0.9)
        assert build_watchlist([past]) == []
