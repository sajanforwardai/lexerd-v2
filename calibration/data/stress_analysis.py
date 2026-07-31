"""
Stress Analysis Module
======================

This module models loan performance under interest rate stress scenarios.

Rate Stress Scenarios:
1. +100 basis points (1%) - Base case stress (Fed's standard)
2. +200 basis points (2%) - Severe stress (high rate environment)

For each scenario, we recalculate:
- Interest expense under new rate
- Debt service coverage ratio (DSCR)
- Break points (where DSCR falls below refi floor)
- Refinance costs and equity compression

This analysis identifies loans most vulnerable to rate increases
and quantifies the potential refinance pressure.

Author: Lexerd Capital Management
Date: 2026-07-31
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class StressScenarioResult:
    """
    Results of stress scenario analysis for a single loan.

    Attributes:
        loan_id: Unique loan identifier
        base_dscr: Current DSCR (no stress)
        stressed_dscr_100bps: DSCR under +100bp rate shock
        stressed_dscr_200bps: DSCR under +200bp rate shock
        breaks_refi_floor_100bps: Does loan fall below 1.25x at +100bps?
        breaks_refi_floor_200bps: Does loan fall below 1.25x at +200bps?
        stress_delta_100bps: Change in DSCR (negative = worse)
        stress_delta_200bps: Change in DSCR
        refinance_cost_100bps: Estimated cost to refi under stress
        refinance_cost_200bps: Estimated cost to refi under stress
        scenario_details: Dict with detailed calculation components
    """
    loan_id: str
    base_dscr: float
    stressed_dscr_100bps: float
    stressed_dscr_200bps: float
    breaks_refi_floor_100bps: bool
    breaks_refi_floor_200bps: bool
    stress_delta_100bps: float
    stress_delta_200bps: float
    refinance_cost_100bps: float
    refinance_cost_200bps: float
    scenario_details: Dict


class StressAnalyzer:
    """
    Analyzes loan vulnerability to interest rate stress.

    Rate stress is a key risk factor for multifamily loans. When rates rise:
    1. DSCR deteriorates (fixed payments, higher rates)
    2. Owners face higher refinance costs
    3. Capital partners/equity investors become necessary

    This analysis quantifies that pressure.

    Constants:
    - Refi floor DSCR: 1.25x (lender minimum)
    - Refinance fees: 3-5% of loan balance
    - Spread premium under stress: 1-2%
    """

    # Refi Floor: Lenders require minimum 1.25x DSCR to refinance
    REFI_FLOOR_DSCR = 1.25

    # Rate Shock Scenarios (in basis points)
    RATE_SHOCK_BASE = 100      # +1% = base case
    RATE_SHOCK_SEVERE = 200    # +2% = severe case

    # Refinance Cost Assumptions
    # These are the out-of-pocket costs to refinance
    REFI_ORIGINATION_FEE_PCT = 0.025  # 2.5% of loan balance
    REFI_SPREAD_PREMIUM_100BPS = 0.01  # +1% spread premium at +100bps
    REFI_SPREAD_PREMIUM_200BPS = 0.02  # +2% spread premium at +200bps

    def stress_scenario_100bps(self, loan: Dict) -> StressScenarioResult:
        """
        Model loan performance under +100 basis point rate shock.

        Scenario: What if interest rates rise 1% from current level?

        Calculation:
        1. Current DSCR = NOI / Current Debt Service
        2. New rate = Current rate + 1%
        3. New Debt Service = Current rate * Loan Balance (simplified)
        4. Stressed DSCR = NOI / New Debt Service

        Interpretation:
        - DSCR >1.25x: Loan still refi-able
        - DSCR 1.10-1.25x: Stressed but not broken
        - DSCR <1.10x: Cannot refinance conventionally

        Use Case:
        Identifies loans vulnerable to modest rate rise (Fed's base case).
        +100bp is about the threshold for conventional refi stress.

        Args:
            loan: Loan record dict with rate, balance, DSCR, NOI

        Returns:
            StressScenarioResult with detailed breakdown
        """
        return self._calculate_stress_scenario(
            loan,
            rate_shock_bps=self.RATE_SHOCK_BASE,
            spread_premium=self.REFI_SPREAD_PREMIUM_100BPS
        )

    def stress_scenario_200bps(self, loan: Dict) -> StressScenarioResult:
        """
        Model loan performance under +200 basis point rate shock.

        Scenario: What if interest rates rise 2% from current level?

        This is the "severe stress" case. If a loan breaks DSCR >1.25x
        at +200bps, it has very little cushion against rate volatility.

        Use Case:
        Identifies deals most vulnerable to rising rate environment.
        These are high-priority refinance targets and capital candidates.

        At +200bps, most below-1.35x DSCR loans will break refi floor,
        creating urgent refinance need.

        Args:
            loan: Loan record dict with rate, balance, DSCR, NOI

        Returns:
            StressScenarioResult with detailed breakdown
        """
        return self._calculate_stress_scenario(
            loan,
            rate_shock_bps=self.RATE_SHOCK_SEVERE,
            spread_premium=self.REFI_SPREAD_PREMIUM_200BPS
        )

    def _calculate_stress_scenario(
        self,
        loan: Dict,
        rate_shock_bps: int,
        spread_premium: float
    ) -> StressScenarioResult:
        """
        Internal method to calculate stress scenario results.

        Process:
        1. Extract loan parameters (rate, balance, NOI, current DSCR)
        2. Calculate stressed debt service (new rate = current + shock)
        3. Recalculate DSCR under stress
        4. Determine if loan breaks refi floor (1.25x)
        5. Estimate refinance costs
        6. Package results

        Args:
            loan: Loan record dict
            rate_shock_bps: Rate shock in basis points (100, 200)
            spread_premium: Additional spread charged by lender

        Returns:
            StressScenarioResult object
        """
        # Extract loan parameters
        # =======================
        loan_id = loan.get('loan_id', 'unknown')
        current_rate = loan.get('current_rate', 0)  # As decimal (e.g., 4.25)
        current_balance = loan.get('current_balance', 0)
        noi = loan.get('noi', 0)  # Net Operating Income
        base_dscr = loan.get('dscr', 1.25)

        # Convert rate shock from bps to decimal
        rate_shock_decimal = rate_shock_bps / 10000.0  # 100bps = 0.01

        # Calculate stressed rate
        stressed_rate = current_rate + rate_shock_decimal

        # Simplified debt service calculation
        # Annual debt service = Loan balance * interest rate
        # (This is simplified; actual calculation uses amortization schedule)
        base_debt_service = current_balance * (current_rate / 100.0)
        stressed_debt_service = current_balance * (stressed_rate / 100.0)

        # Calculate stressed DSCR
        # DSCR = NOI / Debt Service
        if stressed_debt_service > 0 and noi > 0:
            stressed_dscr = noi / stressed_debt_service
        else:
            stressed_dscr = 0.0

        # Calculate DSCR delta (change)
        dscr_delta = stressed_dscr - base_dscr

        # Determine if loan breaks refi floor
        breaks_refi_floor = stressed_dscr < self.REFI_FLOOR_DSCR

        # Calculate refinance costs
        # =======================
        # Components:
        # 1. Origination fee: 2.5% of new loan balance
        # 2. Spread premium: Additional 1-2% depending on stress level
        # Total refinance cost: (2.5% + 1-2%) * loan balance = 3.5%-4.5%

        origination_fee = current_balance * self.REFI_ORIGINATION_FEE_PCT
        spread_cost = current_balance * spread_premium
        total_refinance_cost = origination_fee + spread_cost

        # Package results
        # ===============
        scenario_details = {
            'rate_shock_bps': rate_shock_bps,
            'current_rate': current_rate,
            'stressed_rate': stressed_rate,
            'base_debt_service': base_debt_service,
            'stressed_debt_service': stressed_debt_service,
            'noi': noi,
            'loan_balance': current_balance,
            'origination_fee': origination_fee,
            'spread_premium_pct': spread_premium,
            'spread_cost': spread_cost,
            'refi_floor_dscr': self.REFI_FLOOR_DSCR,
        }

        result = StressScenarioResult(
            loan_id=loan_id,
            base_dscr=base_dscr,
            stressed_dscr_100bps=stressed_dscr if rate_shock_bps == self.RATE_SHOCK_BASE else None,
            stressed_dscr_200bps=stressed_dscr if rate_shock_bps == self.RATE_SHOCK_SEVERE else None,
            breaks_refi_floor_100bps=breaks_refi_floor if rate_shock_bps == self.RATE_SHOCK_BASE else None,
            breaks_refi_floor_200bps=breaks_refi_floor if rate_shock_bps == self.RATE_SHOCK_SEVERE else None,
            stress_delta_100bps=dscr_delta if rate_shock_bps == self.RATE_SHOCK_BASE else None,
            stress_delta_200bps=dscr_delta if rate_shock_bps == self.RATE_SHOCK_SEVERE else None,
            refinance_cost_100bps=total_refinance_cost if rate_shock_bps == self.RATE_SHOCK_BASE else None,
            refinance_cost_200bps=total_refinance_cost if rate_shock_bps == self.RATE_SHOCK_SEVERE else None,
            scenario_details=scenario_details
        )

        return result

    def calculate_refinance_cost(
        self,
        loan: Dict,
        rate_shock: float
    ) -> Dict:
        """
        Estimate cost to refinance under stress.

        Refinance costs have multiple components:
        1. Origination fee: 2-3% of new loan balance (lender cost)
        2. Spread premium: +1-2% over base rate (lender caution)
        3. Discount points: 0-1% (borrower option)
        4. Other fees: ~0.5% (appraisal, title, legal)

        Total: 3-6% of loan balance, typically 4-5%

        Example:
        - $40M loan
        - Refinance cost 4% = $1.6M out-of-pocket
        - This equity compression is a key sourcing signal

        Args:
            loan: Loan record dict
            rate_shock: Rate shock in basis points (100, 200)

        Returns:
            Dict with cost breakdown
        """
        current_balance = loan.get('current_balance', 0)

        # Origination fee: 2.5% (standard)
        origination = current_balance * self.REFI_ORIGINATION_FEE_PCT

        # Spread premium: varies by stress level
        if rate_shock < 100:
            spread_pct = 0.005  # +0.5% at low stress
        elif rate_shock < 150:
            spread_pct = self.REFI_SPREAD_PREMIUM_100BPS  # +1% at 100bps
        else:
            spread_pct = self.REFI_SPREAD_PREMIUM_200BPS  # +2% at 200bps

        spread_cost = current_balance * spread_pct

        # Other costs: ~0.5%
        other_costs = current_balance * 0.005

        total_cost = origination + spread_cost + other_costs
        total_cost_pct = (total_cost / current_balance) * 100

        return {
            'loan_balance': current_balance,
            'origination_fee': origination,
            'origination_fee_pct': self.REFI_ORIGINATION_FEE_PCT * 100,
            'spread_premium': spread_cost,
            'spread_premium_pct': spread_pct * 100,
            'other_costs': other_costs,
            'total_refinance_cost': total_cost,
            'total_cost_percentage': total_cost_pct,
            'out_of_pocket_equity_impact': total_cost,  # All costs reduce available equity
        }

    def analyze_refinance_scenario(self, loan: Dict) -> Dict:
        """
        Comprehensive refinance scenario analysis for a single loan.

        This function:
        1. Calculates base case (+100bps) stress
        2. Calculates severe case (+200bps) stress
        3. Estimates refinance costs
        4. Flags if loan breaks refi floor
        5. Quantifies equity compression

        Returns comprehensive dict for opportunity prioritization.

        Args:
            loan: Loan record dict

        Returns:
            Dict with complete stress analysis and recommendations
        """
        logger.debug(f"Analyzing refinance scenario for {loan.get('loan_id')}")

        # Run both stress scenarios
        base_stress = self.stress_scenario_100bps(loan)
        severe_stress = self.stress_scenario_200bps(loan)

        # Calculate refinance costs
        cost_base = self.calculate_refinance_cost(loan, self.RATE_SHOCK_BASE)
        cost_severe = self.calculate_refinance_cost(loan, self.RATE_SHOCK_SEVERE)

        # Build recommendation
        # ====================
        recommendation = self._build_recommendation(
            base_stress,
            severe_stress,
            cost_base,
            cost_severe
        )

        return {
            'loan_id': loan.get('loan_id'),
            'base_case_stress': {
                'dscr': base_stress.stressed_dscr_100bps,
                'dscr_change': base_stress.stress_delta_100bps,
                'breaks_refi_floor': base_stress.breaks_refi_floor_100bps,
                'refinance_cost': cost_base['total_refinance_cost'],
            },
            'severe_stress': {
                'dscr': severe_stress.stressed_dscr_200bps,
                'dscr_change': severe_stress.stress_delta_200bps,
                'breaks_refi_floor': severe_stress.breaks_refi_floor_200bps,
                'refinance_cost': cost_severe['total_refinance_cost'],
            },
            'recommendation': recommendation,
            'analysis_details': {
                'current_dscr': loan.get('dscr'),
                'current_ltv': loan.get('current_ltv'),
                'loan_balance': loan.get('current_balance'),
            }
        }

    def _build_recommendation(
        self,
        base_stress: StressScenarioResult,
        severe_stress: StressScenarioResult,
        cost_base: Dict,
        cost_severe: Dict
    ) -> str:
        """
        Build text recommendation based on stress analysis.

        Args:
            base_stress: +100bps stress results
            severe_stress: +200bps stress results
            cost_base: Refinance costs at +100bps
            cost_severe: Refinance costs at +200bps

        Returns:
            Recommendation string
        """
        if base_stress.breaks_refi_floor_100bps:
            if severe_stress.breaks_refi_floor_200bps:
                return "CRITICAL: Breaks refi floor at both stress levels. Immediate capital partner needed."
            else:
                return "HIGH RISK: Breaks refi floor at +100bps. Capital partnership recommended."
        elif severe_stress.breaks_refi_floor_200bps:
            return "MODERATE RISK: Only survives base stress. Monitor rate environment."
        else:
            return "LOW STRESS: Withstands both stress scenarios. Conventional refi likely available."
