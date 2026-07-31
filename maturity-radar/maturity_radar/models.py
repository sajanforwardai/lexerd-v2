"""Data structures, modeled on Freddie Mac Multifamily loan-level disclosure.

These are the fields that come off a Freddie K-Deal / SBL disclosure file — the exact data
Sajan surveilled at KBRA. Owner fields are the human-in-the-loop enrichment layer, filled by
hand for the top of the list rather than scraped across hundreds of counties.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Loan:
    """One securitized multifamily loan, as it appears in GSE disclosure."""

    loan_id: str
    property_name: str
    city: str
    county: str
    state: str
    units: int

    origination_year: int
    original_balance: float
    current_balance: float
    note_rate: float            # decimal, e.g. 0.036
    maturity: date
    interest_only: bool

    most_recent_noi: float      # annual, from the latest disclosure
    most_recent_dscr: float     # as reported (in-place)
    occupancy: float            # decimal

    # ── Provenance ──
    program: str = ""           # "Conduit" | "Agency" — securitization program
    deal: str = ""              # Freddie K/SBL deal name (from MLPD Dealname)
    source_url: str = ""        # link to the loan's disclosure source

    # ── Human-in-the-loop owner enrichment (top of list only) ──
    owner_entity: str = ""      # LLC on title (county assessor)
    owner_mailing: str = ""     # mailing address / registered agent
    principal_hint: str = ""    # best available human lead; "" when unresolved


@dataclass
class ScoredLoan:
    """A loan enriched with refinance-pressure analytics and a cultivation angle."""

    loan: Loan
    months_to_maturity: int
    rate_gap: float                 # market rate minus note rate
    projected_refi_dscr: float      # NOI / (current balance x market rate)
    paydown_to_clear: float         # equity needed to refinance at the DSCR floor
    paydown_pct: float              # that paydown as a share of current balance

    proximity_sub: float            # 0..1 component scores
    rate_shock_sub: float
    dscr_stress_sub: float
    pressure_score: float           # 0..100 composite

    entry_angle: str                # purchase / recap / rescue-equity / low-priority
    why_now: str

    # convenience passthroughs
    @property
    def name(self) -> str:
        return self.loan.property_name

    @property
    def market(self) -> str:
        return f"{self.loan.city}, {self.loan.state}"
