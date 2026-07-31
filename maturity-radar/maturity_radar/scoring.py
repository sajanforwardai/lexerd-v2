"""The refinance-pressure scoring engine — the automatable core and Sajan's KBRA edge.

The credit insight that separates this from a naive "distress = seller" screen: a low in-place
DSCR is not the signal. The signal is the *projected* DSCR at today's rate. A loan covering fine
at 3.6% can be un-refinanceable at 6% — and the gap between them, expressed as the equity paydown
needed to clear a lender's DSCR floor, is what times the conversation with the owner.

All functions are pure and take an explicit ``as_of`` date so results are deterministic and
testable — nothing here calls date.today().
"""

from datetime import date

from . import DEFAULT_MARKET_RATE, DEFAULT_REFI_DSCR_FLOOR
from .models import Loan, ScoredLoan

VALUATION_DATE = date.today()   # advances with the calendar; tests pass an explicit as_of

# Composite weights — the three drivers the strategy names. They sum to 1.0.
W_PROXIMITY = 0.30
W_RATE_SHOCK = 0.25
W_DSCR_STRESS = 0.45


def months_between(start: date, end: date) -> int:
    """Whole months from start to end (negative if end is in the past)."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def proximity_sub(months: int) -> float:
    """1.0 for a loan maturing within ~6 months (or already matured), decaying to 0.0 at
    36 months. Beyond three years the refinance is not a near-term forcing event."""
    if months <= 6:
        return 1.0
    if months >= 36:
        return 0.0
    return (36 - months) / 30.0


def rate_shock_sub(rate_gap: float) -> float:
    """1.0 when today's rate is 300+ bps above the in-place note rate, 0.0 at no gap.
    A negative gap (in-place rate already above market) means no refinance pain."""
    if rate_gap <= 0:
        return 0.0
    if rate_gap >= 0.03:
        return 1.0
    return rate_gap / 0.03


def projected_refi_dscr(noi: float, current_balance: float, market_rate: float) -> float:
    """DSCR if the loan were refinanced today at its current balance, interest-only.

    Interest-only is the conservative, transparent proxy; amortizing debt service would be
    higher, so this is the *kindest* view of the refinance and still catches the stressed loans.
    """
    debt_service = current_balance * market_rate
    if debt_service == 0:
        return float("inf")
    return noi / debt_service


def dscr_stress_sub(proj_dscr: float, floor: float) -> float:
    """0.0 when the loan refinances at or above the DSCR floor, ramping to 1.0 at 1.0x
    coverage (can't even cover the new interest)."""
    if proj_dscr >= floor:
        return 0.0
    if proj_dscr <= 1.0:
        return 1.0
    return (floor - proj_dscr) / (floor - 1.0)


def paydown_to_clear(noi: float, current_balance: float, market_rate: float, floor: float) -> float:
    """Equity paydown needed so the refinanced loan clears the DSCR floor at today's rate.

    Solve NOI / (new_loan x rate) = floor  ->  new_loan = NOI / (floor x rate).
    Paydown = current balance - that supportable loan (never negative).
    """
    supportable = noi / (floor * market_rate)
    # Cap at the balance: you cannot pay down more than the loan. For NOI <= 0 the property is
    # unrefinanceable at any positive leverage, so the paydown-to-clear is the whole balance.
    return min(current_balance, max(0.0, current_balance - supportable))


def _entry_angle(proj_dscr: float, months: int, floor: float) -> str:
    if proj_dscr >= floor:
        return "Refinances cleanly — low priority (watch)"
    if proj_dscr < 1.0:
        return "Cannot cover new debt — rescue equity / pref, or distressed sale"
    # between 1.0 and the floor: a real paydown gap
    if months <= 18:
        return "Paydown gap, near maturity — cultivate now; purchase or recap"
    return "Paydown gap, early — start relationship; recap or future purchase"


def _why_now(loan: Loan, s_months: int, rate_gap: float, proj: float,
             paydown: float, pay_pct: float, floor: float) -> str:
    mat = loan.maturity.strftime("%b %Y")
    bal = f"${loan.current_balance/1e6:.1f}M"
    if proj >= floor:
        return (f"{bal} at {loan.note_rate*100:.1f}% matures {mat}; refinances near {proj:.2f}x "
                f"at today's rate — little pressure.")
    return (f"{bal} at {loan.note_rate*100:.1f}% matures {mat} ({s_months} mo); in-place DSCR "
            f"{loan.most_recent_dscr:.2f}x, but refis to {proj:.2f}x at ~6% — needs a "
            f"~${paydown/1e6:.1f}M paydown ({pay_pct*100:.0f}% of balance) to clear {floor:.2f}x. "
            f"Cultivate ahead of the maturity.")


def score_loan(loan: Loan, as_of: date = VALUATION_DATE,
               market_rate: float = DEFAULT_MARKET_RATE,
               floor: float = DEFAULT_REFI_DSCR_FLOOR) -> ScoredLoan:
    """Score one loan's refinance pressure and assign a cultivation angle."""
    months = months_between(as_of, loan.maturity)
    rate_gap = market_rate - loan.note_rate
    proj = projected_refi_dscr(loan.most_recent_noi, loan.current_balance, market_rate)
    paydown = paydown_to_clear(loan.most_recent_noi, loan.current_balance, market_rate, floor)
    pay_pct = paydown / loan.current_balance if loan.current_balance else 0.0

    prox = proximity_sub(months)
    shock = rate_shock_sub(rate_gap)
    stress = dscr_stress_sub(proj, floor)
    score = 100 * (W_PROXIMITY * prox + W_RATE_SHOCK * shock + W_DSCR_STRESS * stress)

    return ScoredLoan(
        loan=loan,
        months_to_maturity=months,
        rate_gap=rate_gap,
        projected_refi_dscr=proj,
        paydown_to_clear=paydown,
        paydown_pct=pay_pct,
        proximity_sub=prox,
        rate_shock_sub=shock,
        dscr_stress_sub=stress,
        pressure_score=round(score, 1),
        entry_angle=_entry_angle(proj, months, floor),
        why_now=_why_now(loan, months, rate_gap, proj, paydown, pay_pct, floor),
    )
