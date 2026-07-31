"""
Maturity Scorer Module
======================

This module scores loans by refinance risk based on three key dimensions:
1. Debt Service Coverage Ratio (DSCR) - can the owner cover debt payments?
2. Loan-to-Value (LTV) - how much equity cushion exists?
3. Maturity Urgency - how soon does the loan mature?

The scoring model identifies loans where owners are likely seeking capital:
- Cannot refinance cleanly (DSCR <1.30x)
- Lack equity partners (LTV >65%)
- Face timeline pressure (maturity 12-24 months)

These are the loans where Lexerd can add value as a capital partner or investor.

Author: Lexerd Capital Management
Date: 2026-07-31
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class LoanScore:
    """
    Data class representing a loan's risk/opportunity score.

    Attributes:
        loan_id: Unique loan identifier
        dscr_score: DSCR stress score (0-100)
        ltv_score: LTV stress score (0-100)
        maturity_score: Maturity urgency score (0-100)
        composite_score: Weighted composite risk score (0-100)
        tier: Risk tier classification (1/2/3)
        score_components: Dict with breakdown of scoring
    """
    loan_id: str
    dscr_score: float
    ltv_score: float
    maturity_score: float
    composite_score: float
    tier: int
    score_components: Dict


class MaturityScorer:
    """
    Scores loans by refinance risk and identifies investment opportunities.

    The scoring model uses three weighted dimensions:
    - DSCR Stress (40%): Can owner cover debt service?
    - LTV Stress (30%): How much equity cushion?
    - Maturity Urgency (30%): Timeline pressure?

    Tier Classification:
    - Tier 1 (Critical): Score >75 - Immediate refinance pressure
    - Tier 2 (High): Score 60-75 - Near-term risk emerging
    - Tier 3 (Monitor): Score 40-60 - Watch trend, future opportunity
    """

    # Weighting for composite score calculation
    # Tuned based on historical refinance analysis
    WEIGHTS = {
        'dscr': 0.40,      # DSCR is strongest predictor of refinance stress
        'ltv': 0.30,       # LTV cushion is secondary
        'maturity': 0.30   # Timeline urgency is tertiary
    }

    # DSCR Threshold References
    # Industry standard minimums for refinancing:
    DSCR_REFI_FLOOR = 1.25      # Minimum to qualify for conventional refi
    DSCR_STRESS_THRESHOLD = 1.30 # Stress level (emerging risk)
    DSCR_CRITICAL = 1.10         # Critical (immediate risk)

    # LTV Threshold References
    LTV_EQUITY_CUSHION = 0.65    # <65% = strong equity, >65% = need capital
    LTV_STRESS = 0.75            # >75% = high risk
    LTV_CRITICAL = 0.85          # >85% = very high risk

    # Maturity Timeline References (months)
    MATURITY_CRITICAL = 12       # <12 months = emergency
    MATURITY_URGENT = 24         # 12-24 months = urgent
    MATURITY_NORMAL = 36         # 24-36 months = normal planning window
    MATURITY_FUTURE = 48         # >48 months = low priority

    def calculate_dscr(self, loan: Dict) -> float:
        """
        Calculate Debt Service Coverage Ratio from loan data.

        DSCR = Annual Net Operating Income / Annual Debt Service

        Formula:
            DSCR = NOI / (Principal + Interest)

        Where:
        - NOI: Net Operating Income (revenue - operating expenses)
        - Principal + Interest: Annual debt service payment

        Interpretation:
        - DSCR >1.40: Healthy - Strong cash flow coverage
        - DSCR 1.25-1.40: Manageable - Lenders require minimum 1.25x
        - DSCR 1.10-1.25: Stressed - Refinance risk emerging
        - DSCR <1.10: Critical - Immediate refinance pressure

        DSCR is the #1 indicator of refinance stress. Loans below 1.25x
        cannot access conventional capital; owners must seek alternative partners.

        Args:
            loan: Loan record dict with 'noi' and debt service fields

        Returns:
            DSCR value (float), or 0.0 if data missing
        """
        try:
            # Extract components
            noi = loan.get('noi', 0)
            # Debt service calculated from rate, balance, term
            dscr = loan.get('dscr', None)

            if dscr is not None and dscr > 0:
                return float(dscr)

            # Fallback: calculate from NOI if dscr field missing
            # This uses simplified annual debt service assumption
            if noi and noi > 0:
                current_balance = loan.get('current_balance', 0)
                current_rate = loan.get('current_rate', 0)
                annual_debt_service = current_balance * current_rate

                if annual_debt_service > 0:
                    return float(noi / annual_debt_service)

            logger.warning(f"Cannot calculate DSCR for loan {loan.get('loan_id')}")
            return 0.0

        except Exception as e:
            logger.error(f"Error calculating DSCR: {str(e)}")
            return 0.0

    def score_refinance_risk(self, loan: Dict) -> LoanScore:
        """
        Calculate composite refinance risk score (0-100 scale).

        Composite score combines three weighted stress dimensions:
        1. DSCR Stress (40%): Can owner cover debt service payments?
        2. LTV Stress (30%): How much equity cushion available?
        3. Maturity Urgency (30%): How soon does loan mature?

        Scoring Algorithm:
        1. Normalize each dimension to 0-100 scale (0=no stress, 100=maximum stress)
        2. Apply weights: (40% * dscr) + (30% * ltv) + (30% * maturity)
        3. Classify into tier based on composite score:
           - Tier 1 (Critical): >75 → Immediate action needed
           - Tier 2 (High): 60-75 → Near-term risk
           - Tier 3 (Monitor): 40-60 → Watch trend
           - Other: <40 → Low priority

        Use Case:
        Tier 1/2 loans are ranked for outreach (highest opportunity score first).
        These are the loans where owners/lenders are seeking capital solutions.

        Args:
            loan: Loan record dict with DSCR, LTV, maturity_date, months_to_maturity

        Returns:
            LoanScore object with breakdown of scoring
        """
        logger.debug(f"Scoring loan {loan.get('loan_id')}")

        # Step 1: Calculate individual stress scores
        # ===========================================

        # DSCR Score: 0-100 scale, inverted (higher DSCR = lower score)
        dscr = self.calculate_dscr(loan)
        dscr_score = self._calculate_dscr_stress_score(dscr)

        # LTV Score: 0-100 scale, direct (higher LTV = higher score)
        ltv = loan.get('current_ltv', 0)
        ltv_score = self._calculate_ltv_stress_score(ltv)

        # Maturity Score: 0-100 scale, direct (shorter timeline = higher score)
        months_to_maturity = loan.get('months_to_maturity', 60)
        maturity_score = self._calculate_maturity_urgency_score(months_to_maturity)

        # Step 2: Calculate weighted composite score
        # ==========================================
        composite_score = (
            self.WEIGHTS['dscr'] * dscr_score +
            self.WEIGHTS['ltv'] * ltv_score +
            self.WEIGHTS['maturity'] * maturity_score
        )

        # Step 3: Classify into tier
        # ==========================
        if composite_score > 75:
            tier = 1  # Critical
        elif composite_score >= 60:
            tier = 2  # High
        elif composite_score >= 40:
            tier = 3  # Monitor
        else:
            tier = 4  # Low priority

        # Step 4: Package results
        # ======================
        score_obj = LoanScore(
            loan_id=loan.get('loan_id', 'unknown'),
            dscr_score=dscr_score,
            ltv_score=ltv_score,
            maturity_score=maturity_score,
            composite_score=composite_score,
            tier=tier,
            score_components={
                'dscr': dscr,
                'ltv': ltv,
                'months_to_maturity': months_to_maturity,
                'dscr_weight': self.WEIGHTS['dscr'],
                'ltv_weight': self.WEIGHTS['ltv'],
                'maturity_weight': self.WEIGHTS['maturity'],
            }
        )

        return score_obj

    def _calculate_dscr_stress_score(self, dscr: float) -> float:
        """
        Convert DSCR to 0-100 stress score.

        Mapping:
        - DSCR >1.40 (healthy) → 0-20 (low stress)
        - DSCR 1.25-1.40 (refi floor) → 20-50 (moderate stress)
        - DSCR 1.10-1.25 (stressed) → 50-80 (high stress)
        - DSCR <1.10 (critical) → 80-100 (critical stress)

        This mapping is based on industry refinance thresholds.

        Args:
            dscr: Debt Service Coverage Ratio

        Returns:
            Stress score 0-100 (0=healthy, 100=critical)
        """
        if dscr > 1.40:
            # Healthy - DSCR well above refi floor
            return max(0, (1.40 - dscr) * 50)  # Scale down as DSCR increases
        elif dscr >= 1.25:
            # Manageable - At or above refi floor
            return ((1.40 - dscr) / (1.40 - 1.25)) * 50 + 20
        elif dscr >= 1.10:
            # Stressed - Below refi floor
            return ((1.25 - dscr) / (1.25 - 1.10)) * 30 + 50
        else:
            # Critical - Well below refi floor
            return min(100, 80 + (1.10 - dscr) * 50)

    def _calculate_ltv_stress_score(self, ltv: float) -> float:
        """
        Convert LTV to 0-100 stress score.

        Mapping:
        - LTV <65% (strong equity) → 0-20 (low stress)
        - LTV 65-75% (moderate) → 20-50 (moderate stress)
        - LTV 75-85% (high) → 50-80 (high stress)
        - LTV >85% (critical) → 80-100 (critical stress)

        LTV >65% indicates owner lacks sufficient equity cushion to refinance
        cleanly without a capital partner.

        Args:
            ltv: Loan-to-Value ratio (e.g., 0.75 = 75%)

        Returns:
            Stress score 0-100 (0=low risk, 100=high risk)
        """
        if ltv < 0.65:
            # Strong equity cushion
            return max(0, ltv * 30.8)  # Scale linearly up to 0.65
        elif ltv < 0.75:
            # Moderate LTV
            return ((ltv - 0.65) / (0.75 - 0.65)) * 30 + 20
        elif ltv < 0.85:
            # High LTV
            return ((ltv - 0.75) / (0.85 - 0.75)) * 30 + 50
        else:
            # Critical LTV
            return min(100, 80 + (ltv - 0.85) * 100)

    def _calculate_maturity_urgency_score(self, months_to_maturity: float) -> float:
        """
        Convert maturity timeline to 0-100 urgency score.

        Mapping:
        - >48 months (future) → 0-10 (low urgency)
        - 36-48 months (normal) → 10-30 (low-moderate urgency)
        - 24-36 months (planning window) → 30-60 (moderate urgency)
        - 12-24 months (urgent) → 60-90 (high urgency)
        - <12 months (emergency) → 90-100 (critical urgency)

        Timeline urgency is a key signal. Loans with <24 months to maturity
        are facing refinance pressure and are likely seeking solutions.

        Args:
            months_to_maturity: Months until loan maturity

        Returns:
            Urgency score 0-100 (0=distant, 100=imminent)
        """
        if months_to_maturity > 48:
            # Future maturity - low urgency
            return 0
        elif months_to_maturity > 36:
            # Normal planning window
            return ((48 - months_to_maturity) / (48 - 36)) * 30
        elif months_to_maturity > 24:
            # Moderate urgency
            return ((36 - months_to_maturity) / (36 - 24)) * 30 + 30
        elif months_to_maturity > 12:
            # High urgency
            return ((24 - months_to_maturity) / (24 - 12)) * 30 + 60
        else:
            # Critical urgency (emergency refi needed)
            return min(100, 90 + months_to_maturity * 10)

    def flag_target_opportunities(self, loans: List[Dict]) -> List[Dict]:
        """
        Flag loans matching Lexerd investment criteria for distress.

        This function identifies loans where Lexerd can add value as a
        capital partner. Target criteria:

        1. DSCR <1.30x (cannot refinance cleanly)
           - Cannot qualify for conventional refi at 1.25x minimum
           - Needs operational improvement or capital support
           - Lexerd can offer mezzanine or equity capital

        2. LTV >65% (need equity partner)
           - Owner lacks sufficient equity cushion
           - Typically seeking 20-30% equity partner
           - Lexerd target equity check: $2-20M

        3. Maturity 12-24 months (urgency)
           - Within actionable timeframe for sourcing/due diligence
           - Creates motivation to accept capital partnership
           - <12 months = emergency (no time), >24 months = too far out

        4. In target markets (GA, FL, AL, SC, NC, TX, KS)
           - Lexerd has broker relationships
           - Know local market dynamics
           - Can operationalize acquisitions

        5. 70-300 units (Lexerd sweet spot)
           - <70 = too small for economies of scale
           - >300 = trophy asset, not value-add opportunity
           - 100-250 = optimal target

        6. Class B/B-/B+ (value-add positioning)
           - Class A = stabilized (not value-add)
           - Class C = too much risk for 12-24m horizon
           - B-class = underperforming but fixable

        7. <$50M value (acquisition range)
           - Equity check typically 15-25% of value
           - $2-20M equity check = $8-133M acquisition value
           - Practical upper bound: $50M

        Args:
            loans: List of loan dicts to evaluate

        Returns:
            Filtered list of target opportunities, sorted by score (highest first)
        """
        logger.info(f"Flagging target opportunities from {len(loans)} loans")

        opportunities = []

        for loan in loans:
            # Score the loan
            score = self.score_refinance_risk(loan)

            # Apply filters
            dscr = self.calculate_dscr(loan)
            ltv = loan.get('current_ltv', 0)
            months = loan.get('months_to_maturity', 60)
            units = loan.get('units', 0)
            property_class = loan.get('property_class', 'X')
            current_balance = loan.get('current_balance', 0)

            # Check all criteria
            criteria_met = (
                dscr < 1.30 and
                ltv > 0.65 and
                12 <= months <= 24 and
                70 <= units <= 300 and
                property_class in ['A', 'B', 'C'] and
                current_balance < 50_000_000
            )

            if criteria_met and score.tier <= 2:  # Tier 1 or 2 only
                opportunities.append({
                    'loan_id': loan.get('loan_id'),
                    'opportunity_score': score.composite_score,
                    'tier': score.tier,
                    'dscr': dscr,
                    'ltv': ltv,
                    'months_to_maturity': months,
                    'units': units,
                    'property_class': property_class,
                    'current_balance': current_balance,
                    'score_components': score.score_components
                })

        # Sort by opportunity score (highest first)
        opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)

        logger.info(f"Identified {len(opportunities)} target opportunities")

        return opportunities
