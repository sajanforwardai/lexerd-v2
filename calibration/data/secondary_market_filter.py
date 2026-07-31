"""
Secondary Market Filter Module
================================

This module filters loans to Lexerd's specific investment criteria and target markets.

The filtering pipeline applies a series of logical gates to progressively narrow
the dataset from ~50K total loans down to ~100-500 priority opportunities.

Each filter is cumulative - loans must pass ALL criteria to be considered targets.

Author: Lexerd Capital Management
Date: 2026-07-31
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FilterStats:
    """
    Statistics on filtering process.

    Tracks how many loans are removed at each step and final count.
    """
    initial_count: int
    after_geography: int
    after_property_type: int
    after_unit_count: int
    after_property_class: int
    after_acquisition_value: int
    after_maturity: int
    after_dscr: int
    after_ltv: int
    final_count: int


class SecondaryMarketFilter:
    """
    Applies Lexerd investment criteria filters in sequence.

    Target Market & Investment Criteria:
    ===================================

    Geographic Markets (7 target states):
    - GA, FL, AL, SC, NC, TX, KS
    Reason: Lexerd has broker relationships, knows market dynamics,
            established sourcing networks in these markets.

    Property Type:
    - Multifamily only (apartments, garden, mid-rise)
    Reason: Lexerd's core expertise is MF value-add; other property types
            require different operational capabilities and market knowledge.

    Unit Count:
    - 70-300 units
    Reason: <70 units lacks economies of scale for value-add operations
            >300 units is stabilized trophy asset (not value-add opportunity)

    Property Class:
    - B, B-, B+
    Reason: Class A is already stabilized, no operational value-add
            Class C carries too much risk for 12-24 month investment horizon

    Acquisition Value:
    - <$50M
    Reason: Typical equity checks are 15-25% of property value
            Lexerd target equity: $2-20M
            Max implied acquisition: ~$130M, but practical limit: $50M

    Maturity Window:
    - 12-36 months remaining
    Reason: <12 months = emergency (no time for due diligence/operations)
            >36 months = too far out to be actionable (refinance not urgent)

    DSCR:
    - <1.35x
    Reason: >1.35x loans can probably refinance without capital partner
            <1.35x loans are stressed, need alternative solutions

    LTV:
    - >65%
    Reason: <65% LTV means owner has significant equity cushion
            >65% LTV means owner lacks capital to fill refinance gap
    """

    # Geographic Filter: Target states
    TARGET_STATES = {'GA', 'FL', 'AL', 'SC', 'NC', 'TX', 'KS'}

    # Unit count filter
    MIN_UNITS = 70
    MAX_UNITS = 300

    # Property class filter (B-class and variations)
    TARGET_PROPERTY_CLASSES = {'B', 'B-', 'B+', 'B/B-', 'B/B+'}

    # Acquisition value filter
    MAX_ACQUISITION_VALUE = 50_000_000  # $50M

    # Maturity filter
    MIN_MONTHS_TO_MATURITY = 12  # Must mature within next 12-36 months
    MAX_MONTHS_TO_MATURITY = 36  # (not too close, not too far)

    # DSCR filter
    MAX_DSCR = 1.35  # Only stressed loans (can't refi conventionally)

    # LTV filter
    MIN_LTV = 0.65  # Only loans where owner needs capital

    def __init__(self):
        """Initialize the filter with criteria thresholds."""
        self.stats = None

    def apply_lexerd_filters(self, loans: List[Dict]) -> tuple[List[Dict], FilterStats]:
        """
        Apply all Lexerd investment criteria filters in sequence.

        Filtering Pipeline (each step is cumulative):
        1. Geographic: Target states only
        2. Property type: Multifamily only
        3. Unit count: 70-300 units
        4. Property class: B/B-/B+ only
        5. Acquisition value: <$50M
        6. Maturity window: 12-36 months
        7. DSCR: <1.35x (stressed)
        8. LTV: >65% (needs capital)

        Each filter removes non-matching loans. The result is a focused list
        of high-priority opportunities for sourcing/outreach.

        Args:
            loans: List of loan dicts from pipeline

        Returns:
            Tuple of:
            - Filtered list of target opportunities (sorted by priority)
            - FilterStats showing removals at each step
        """
        logger.info(f"Starting filter pipeline with {len(loans)} loans")

        stats = FilterStats(
            initial_count=len(loans),
            after_geography=0,
            after_property_type=0,
            after_unit_count=0,
            after_property_class=0,
            after_acquisition_value=0,
            after_maturity=0,
            after_dscr=0,
            after_ltv=0,
            final_count=0
        )

        # Create working set
        working_loans = loans.copy()

        # Step 1: Geographic Filter
        # ========================
        logger.info("Applying geographic filter...")
        working_loans = [
            loan for loan in working_loans
            if loan.get('state_code', '').upper() in self.TARGET_STATES
        ]
        stats.after_geography = len(working_loans)
        logger.info(f"  After geography filter: {stats.after_geography} loans")

        # Step 2: Property Type Filter
        # ============================
        logger.info("Applying property type filter...")
        # Keep multifamily only (either from property_type or units>1)
        working_loans = [
            loan for loan in working_loans
            if (loan.get('property_type', 'SF') == 'MF' or
                loan.get('units', 0) > 1)
        ]
        stats.after_property_type = len(working_loans)
        logger.info(f"  After property type filter: {stats.after_property_type} loans")

        # Step 3: Unit Count Filter
        # =========================
        logger.info(f"Applying unit count filter ({self.MIN_UNITS}-{self.MAX_UNITS})...")
        working_loans = [
            loan for loan in working_loans
            if self.MIN_UNITS <= loan.get('units', 0) <= self.MAX_UNITS
        ]
        stats.after_unit_count = len(working_loans)
        logger.info(f"  After unit count filter: {stats.after_unit_count} loans")

        # Step 4: Property Class Filter
        # =============================
        logger.info("Applying property class filter (B-class)...")
        working_loans = [
            loan for loan in working_loans
            if loan.get('property_class', 'X') in self.TARGET_PROPERTY_CLASSES
        ]
        stats.after_property_class = len(working_loans)
        logger.info(f"  After property class filter: {stats.after_property_class} loans")

        # Step 5: Acquisition Value Filter
        # ================================
        logger.info(f"Applying acquisition value filter (<${self.MAX_ACQUISITION_VALUE/1e6:.0f}M)...")
        working_loans = [
            loan for loan in working_loans
            if loan.get('current_balance', 0) < self.MAX_ACQUISITION_VALUE
        ]
        stats.after_acquisition_value = len(working_loans)
        logger.info(f"  After acquisition value filter: {stats.after_acquisition_value} loans")

        # Step 6: Maturity Window Filter
        # ==============================
        logger.info(f"Applying maturity filter ({self.MIN_MONTHS_TO_MATURITY}-{self.MAX_MONTHS_TO_MATURITY} months)...")
        working_loans = [
            loan for loan in working_loans
            if self.MIN_MONTHS_TO_MATURITY <= loan.get('months_to_maturity', 60) <= self.MAX_MONTHS_TO_MATURITY
        ]
        stats.after_maturity = len(working_loans)
        logger.info(f"  After maturity filter: {stats.after_maturity} loans")

        # Step 7: DSCR Filter
        # ==================
        logger.info(f"Applying DSCR filter (<{self.MAX_DSCR}x)...")
        working_loans = [
            loan for loan in working_loans
            if loan.get('dscr', 2.0) < self.MAX_DSCR
        ]
        stats.after_dscr = len(working_loans)
        logger.info(f"  After DSCR filter: {stats.after_dscr} loans")

        # Step 8: LTV Filter
        # =================
        logger.info(f"Applying LTV filter (>{self.MIN_LTV:.0%})...")
        working_loans = [
            loan for loan in working_loans
            if loan.get('current_ltv', 0) > self.MIN_LTV
        ]
        stats.after_ltv = len(working_loans)
        logger.info(f"  After LTV filter: {stats.after_ltv} loans")

        # Final: Sort by DSCR (lower = more distressed = higher priority)
        # ==============================================================
        working_loans.sort(
            key=lambda x: (x.get('dscr', 2.0), -x.get('current_ltv', 0))
        )

        stats.final_count = len(working_loans)

        # Log summary
        # ===========
        logger.info(f"\nFilter Pipeline Summary:")
        logger.info(f"  Initial: {stats.initial_count}")
        logger.info(f"  Removed (geography): {stats.initial_count - stats.after_geography}")
        logger.info(f"  Removed (property type): {stats.after_geography - stats.after_property_type}")
        logger.info(f"  Removed (unit count): {stats.after_property_type - stats.after_unit_count}")
        logger.info(f"  Removed (class): {stats.after_unit_count - stats.after_property_class}")
        logger.info(f"  Removed (value): {stats.after_property_class - stats.after_acquisition_value}")
        logger.info(f"  Removed (maturity): {stats.after_acquisition_value - stats.after_maturity}")
        logger.info(f"  Removed (DSCR): {stats.after_maturity - stats.after_dscr}")
        logger.info(f"  Removed (LTV): {stats.after_dscr - stats.after_ltv}")
        logger.info(f"  Final target opportunities: {stats.final_count}")

        self.stats = stats
        return working_loans, stats

    def get_filter_summary(self) -> Dict:
        """
        Get human-readable summary of filter criteria.

        Returns:
            Dictionary describing all filter thresholds
        """
        return {
            'target_states': sorted(list(self.TARGET_STATES)),
            'unit_range': f"{self.MIN_UNITS}-{self.MAX_UNITS}",
            'property_classes': sorted(list(self.TARGET_PROPERTY_CLASSES)),
            'max_acquisition_value': f"${self.MAX_ACQUISITION_VALUE/1e6:.0f}M",
            'maturity_months': f"{self.MIN_MONTHS_TO_MATURITY}-{self.MAX_MONTHS_TO_MATURITY}",
            'max_dscr': self.MAX_DSCR,
            'min_ltv': f"{self.MIN_LTV:.0%}",
        }

    def get_filter_stats_summary(self) -> str:
        """
        Get human-readable summary of filter stats.

        Returns:
            Formatted string with filter progression
        """
        if not self.stats:
            return "No filter results available"

        s = self.stats
        return f"""
Filter Results Summary:
=======================
Initial loans:              {s.initial_count:,}
After geography:            {s.after_geography:,} (-{s.initial_count - s.after_geography:,})
After property type:        {s.after_property_type:,} (-{s.after_geography - s.after_property_type:,})
After unit count:           {s.after_unit_count:,} (-{s.after_property_type - s.after_unit_count:,})
After property class:       {s.after_property_class:,} (-{s.after_unit_count - s.after_property_class:,})
After acquisition value:    {s.after_acquisition_value:,} (-{s.after_property_class - s.after_acquisition_value:,})
After maturity window:      {s.after_maturity:,} (-{s.after_acquisition_value - s.after_maturity:,})
After DSCR threshold:       {s.after_dscr:,} (-{s.after_maturity - s.after_dscr:,})
After LTV threshold:        {s.after_ltv:,} (-{s.after_dscr - s.after_ltv:,})
=======================
FINAL OPPORTUNITIES:        {s.final_count:,}

Conversion Rate: {s.final_count / s.initial_count * 100:.2f}% of initial loans pass all filters
"""
