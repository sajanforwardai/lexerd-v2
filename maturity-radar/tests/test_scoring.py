"""Scoring-engine tests, verified against hand calculations.

The engine is the automatable core the council said is Sajan's real edge, so it must be
provably correct, not just internally consistent.
"""

from datetime import date

import pytest

from maturity_radar.models import Loan
from maturity_radar.scoring import (
    dscr_stress_sub,
    months_between,
    projected_refi_dscr,
    proximity_sub,
    paydown_to_clear,
    rate_shock_sub,
    score_loan,
)

AS_OF = date(2026, 7, 23)


def wolf_pen():
    # A stressed loan: low in-place rate, near maturity, thin refi coverage.
    return Loan("K068", "Wolf Pen Crossing", "College Station", "Brazos", "TX", 132,
                2016, 9_600_000, 8_900_000, 0.0348, date(2026, 11, 1), True,
                560_000, 1.24, 0.90)


def clean_refi():
    # A control loan that refinances fine: already at a market rate, far maturity.
    return Loan("K102", "Perimeter Bend", "Augusta", "Richmond", "GA", 110,
                2021, 9_100_000, 8_800_000, 0.0585, date(2029, 5, 1), True,
                720_000, 1.40, 0.95)


class TestComponentFunctions:
    def test_months_between(self):
        assert months_between(date(2026, 7, 23), date(2026, 11, 1)) == 4
        assert months_between(date(2026, 7, 1), date(2027, 7, 1)) == 12
        assert months_between(date(2026, 7, 1), date(2026, 3, 1)) == -4  # already matured

    def test_proximity_boundaries(self):
        assert proximity_sub(3) == 1.0
        assert proximity_sub(6) == 1.0
        assert proximity_sub(36) == 0.0
        assert proximity_sub(21) == pytest.approx((36 - 21) / 30)
        assert proximity_sub(-2) == 1.0  # matured

    def test_rate_shock_boundaries(self):
        assert rate_shock_sub(-0.01) == 0.0
        assert rate_shock_sub(0.0) == 0.0
        assert rate_shock_sub(0.03) == 1.0
        assert rate_shock_sub(0.05) == 1.0
        assert rate_shock_sub(0.015) == pytest.approx(0.5)

    def test_projected_refi_dscr(self):
        # 560k NOI / (8.9M * 6%) = 560000 / 534000 = 1.0487
        assert projected_refi_dscr(560_000, 8_900_000, 0.06) == pytest.approx(1.0487, abs=1e-4)

    def test_dscr_stress_boundaries(self):
        assert dscr_stress_sub(1.25, 1.25) == 0.0
        assert dscr_stress_sub(1.40, 1.25) == 0.0     # above floor -> no stress
        assert dscr_stress_sub(1.00, 1.25) == 1.0
        assert dscr_stress_sub(0.90, 1.25) == 1.0     # clamped
        assert dscr_stress_sub(1.125, 1.25) == pytest.approx(0.5, abs=1e-6)

    def test_paydown_to_clear(self):
        # supportable = 560000/(1.25*0.06)=7,466,667; paydown=8.9M-7.4667M=1,433,333
        assert paydown_to_clear(560_000, 8_900_000, 0.06, 1.25) == pytest.approx(1_433_333, abs=50)

    def test_paydown_is_zero_when_loan_already_clears(self):
        assert paydown_to_clear(720_000, 8_800_000, 0.06, 1.25) == 0.0


class TestScoreLoan:
    def test_stressed_loan_scores_high(self):
        s = score_loan(wolf_pen(), AS_OF)
        # hand: 100*(0.30*1.0 + 0.25*0.84 + 0.45*0.8052) = 87.4
        assert s.pressure_score == pytest.approx(87.4, abs=0.3)
        assert s.projected_refi_dscr == pytest.approx(1.0487, abs=1e-3)
        assert s.paydown_to_clear == pytest.approx(1_433_333, abs=100)

    def test_stressed_loan_entry_angle(self):
        s = score_loan(wolf_pen(), AS_OF)
        assert "cultivate" in s.entry_angle.lower() or "recap" in s.entry_angle.lower()

    def test_clean_loan_scores_low(self):
        s = score_loan(clean_refi(), AS_OF)
        assert s.pressure_score < 10
        assert "low priority" in s.entry_angle.lower()

    def test_screen_discriminates(self):
        """The whole point: the stressed loan must outscore the clean one by a wide margin."""
        assert score_loan(wolf_pen(), AS_OF).pressure_score > \
            score_loan(clean_refi(), AS_OF).pressure_score + 50

    def test_why_now_is_populated(self):
        s = score_loan(wolf_pen(), AS_OF)
        assert "matures" in s.why_now and "%" in s.why_now

    def test_higher_market_rate_raises_pressure(self):
        low = score_loan(wolf_pen(), AS_OF, market_rate=0.05)
        high = score_loan(wolf_pen(), AS_OF, market_rate=0.07)
        assert high.pressure_score >= low.pressure_score


class TestGateFixes:
    def test_paydown_capped_at_balance_for_negative_noi(self):
        """Loss-making property: paydown-to-clear can never exceed the loan balance."""
        from maturity_radar.scoring import paydown_to_clear
        pd = paydown_to_clear(noi=-50_000, current_balance=5_000_000, market_rate=0.06, floor=1.25)
        assert pd <= 5_000_000

    def test_paydown_pct_never_exceeds_one(self):
        loan = Loan("X", "Loss Co", "Houston", "Harris", "TX", 100, 2018,
                    5_000_000, 5_000_000, 0.04, date(2027, 6, 1), True, -50_000, 0.5, 0.7)
        s = score_loan(loan, as_of=AS_OF)
        assert s.paydown_pct <= 1.0
