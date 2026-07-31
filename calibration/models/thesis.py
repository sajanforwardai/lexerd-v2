"""Lexerd 3M Model thesis configuration and scoring models."""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ConfidenceGrade(str, Enum):
    """Confidence grades for scored properties."""
    A = "A"  # 90–100: Strong fit
    B = "B"  # 75–89: Good fit
    C = "C"  # 60–74: Moderate fit
    D = "D"  # <60: Weak fit


@dataclass
class ThesisConfig:
    """
    Lexerd's investment thesis parameters (3M Model: Market/Model/Management).
    All parameters are tunable and affect final scoring instantly.
    """

    # Geographic & Market Parameters
    target_markets: list[str] | None = None  # e.g., ['GA', 'FL', 'AL', 'SC', 'NC', 'TX', 'KS']
    min_population: int | None = None  # MSA population threshold (e.g., None = no min, 1_000_000 = <1M)
    max_population: int = 1_000_000  # Max MSA population for secondary market

    # Employment Growth Parameters
    min_employment_growth_yoy: float = 0.02  # 2% YoY
    employment_anchor_types: list[str] | None = None  # e.g., ['military', 'medical', 'university', 'manufacturing']

    # Population & Valuation Parameters
    min_population_growth_yoy: float = 0.015  # 1.5% YoY
    min_cap_rate_spread_bps: int = 200  # >200bps above national avg

    # Refinance Signal Parameters
    min_maturity_years: float = 1.0
    max_maturity_years: float = 3.0

    # Financial Constraints
    min_equity: float = 2_000_000  # $2M
    max_equity: float = 20_000_000  # $20M
    min_capital: float = 10_000_000  # $10M
    max_capital: float = 100_000_000  # $100M
    max_acq_price: float = 50_000_000  # <$50M

    # Property Profile Parameters (Model: value-add opportunity)
    min_units: int = 70
    max_units: int = 300
    property_classes: list[str] | None = None  # e.g., ['A', 'A-', 'B', 'B+', 'B-', 'C']
    min_property_age_years: int = 10
    max_property_age_years: int = 30

    # Operational Value-Add Signals
    min_occupancy: float = 0.80  # 80%
    max_occupancy: float = 0.95  # 95% (below market = upside)
    min_expense_ratio_above_benchmark: float = 0.05  # 5% above benchmark (28% + 5% = 33%)

    # Management & Integration Parameters
    require_third_party_management: bool = True
    support_first_communities_integration: bool = True  # Can integrate with existing partner

    # Scoring Weights (3M Model)
    market_weight: float = 0.30  # Market: 30%
    model_weight: float = 0.40  # Model: 40%
    management_weight: float = 0.30  # Management: 30%

    # Target Return
    target_irr_pct: float = 12.0  # 12%+ levered IRR

    def __post_init__(self):
        """Set defaults for list fields."""
        if self.target_markets is None:
            self.target_markets = ['GA', 'FL', 'AL', 'SC', 'NC', 'TX', 'KS']
        if self.employment_anchor_types is None:
            self.employment_anchor_types = ['military', 'medical', 'university', 'manufacturing']
        if self.property_classes is None:
            self.property_classes = ['A', 'A-', 'B', 'B+', 'B-', 'C']

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)


@dataclass
class PropertyProfile:
    """Input property data for scoring."""

    property_id: str
    property_name: str
    address: str
    city: str
    state: str
    units: int
    property_class: str
    year_built: int
    occupancy: float  # 0.0–1.0
    avg_rent_per_unit: float
    expense_ratio: float  # 0.0–1.0
    market_expense_ratio: float  # Benchmark for market

    # Market fundamentals (for Market score)
    employment_growth_yoy: float | None = None  # 0.025 = 2.5%
    population_growth_yoy: float | None = None  # 0.018 = 1.8%
    market_cap_rate: float | None = None  # 0.08 = 8.0%
    employment_anchors: list[str] | None = None  # ['military', 'medical']

    # Optional: enriched data
    market_rent_per_unit: float | None = None  # For rent gap calculation
    noi: float | None = None
    management_type: str | None = None  # 'Third-party' or 'Owner-managed'
    loan_maturity_years: float | None = None  # 1–3 years = signal
    dscr: float | None = None  # Debt service coverage ratio
    purchase_price: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    def rent_gap_pct(self) -> float:
        """Rent below market as percentage. Positive = upside."""
        if not self.market_rent_per_unit or self.market_rent_per_unit == 0:
            return 0
        return (self.market_rent_per_unit - self.avg_rent_per_unit) / self.market_rent_per_unit

    def expense_gap_pct(self) -> float:
        """Expense ratio gap above benchmark as percentage."""
        return self.expense_ratio - self.market_expense_ratio

    def property_age(self) -> int:
        """Property age in years."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).year - self.year_built


@dataclass
class ScoreResult:
    """Scoring output for a property."""

    property_id: str
    market_score: float  # 0–100
    model_score: float  # 0–100
    management_score: float  # 0–100
    final_fit_score: float  # 0–100 (weighted combination)
    confidence_grade: ConfidenceGrade  # A, B, C, D

    # Breakdown (for transparency)
    market_breakdown: dict[str, float]  # {'employment_growth': 25, 'cap_rate_spread': 30, ...}
    model_breakdown: dict[str, float]  # {'units': 20, 'occupancy': 20, ...}
    management_breakdown: dict[str, float]  # {'pm_type': 20, 'integration_fit': 20, ...}

    # Fit assessment
    fit_rationale: str  # Human-readable explanation of score
    key_strengths: list[str]  # What this property does well
    key_weaknesses: list[str]  # What this property lacks

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        data = asdict(self)
        data['confidence_grade'] = self.confidence_grade.value
        return data
