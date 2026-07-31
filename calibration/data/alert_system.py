"""
Alert System Module
===================

This module generates opportunity rankings and alert reports for the sourcing team.

The alert system:
1. Ranks deals by Lexerd sourcing opportunity
2. Generates structured alert reports
3. Prioritizes outreach by investment tier
4. Provides market context and refinance pressure metrics

The output is an actionable report for the sourcing team to use for
deal identification and outreach prioritization.

Author: Lexerd Capital Management
Date: 2026-07-31
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class OpportunityRank:
    """
    Ranked opportunity record for sourcing outreach.

    Attributes:
        rank: Rank position (1 = highest opportunity)
        loan_id: Unique loan identifier
        opportunity_score: Composite opportunity score (0-100)
        risk_tier: Risk tier (1=Critical, 2=High, 3=Monitor)
        property_address: Property street address
        units: Number of units
        property_class: Property class (A/B/C)
        market: Market/MSA
        current_balance: Current loan balance
        dscr: Current DSCR
        ltv: Current LTV
        months_to_maturity: Months until maturity
        dscr_stress_100bps: DSCR under +100bps stress
        dscr_stress_200bps: DSCR under +200bps stress
        owner_contact: Owner/operator contact info if available
        lender_contact: Lender contact info if available
        sourcing_notes: Recommended sourcing approach
    """
    rank: int
    loan_id: str
    opportunity_score: float
    risk_tier: int
    property_address: str
    units: int
    property_class: str
    market: str
    current_balance: float
    dscr: float
    ltv: float
    months_to_maturity: float
    dscr_stress_100bps: Optional[float]
    dscr_stress_200bps: Optional[float]
    owner_contact: Optional[str]
    lender_contact: Optional[str]
    sourcing_notes: str


class AlertSystem:
    """
    Generates opportunity alerts and sourcing reports.

    This system takes scored/filtered loans and transforms them into
    actionable alerts for the sourcing team.

    Alert Structure:
    1. Tier 1 (Critical): Scores 75-100
       - Immediate refinance pressure
       - High motivation to accept capital partnership
       - Action: Daily outreach targets

    2. Tier 2 (High): Scores 60-75
       - Near-term refinance risk
       - Moderate motivation to seek capital
       - Action: Weekly pipeline review

    3. Tier 3 (Monitor): Scores 40-60
       - Future opportunity
       - Building sourcing relationships
       - Action: Monthly pipeline tracking

    Each alert includes:
    - Property details (address, units, class, vintage)
    - Loan metrics (DSCR, LTV, maturity)
    - Market context (employment growth, cap rate)
    - Refinance pressure (stressed DSCR at +100/+200bps)
    - Recommended sourcing approach
    """

    # Tier thresholds (from maturity_scorer)
    TIER_1_MIN_SCORE = 75
    TIER_2_MIN_SCORE = 60
    TIER_3_MIN_SCORE = 40

    def rank_by_opportunity(self, loans: List[Dict]) -> List[OpportunityRank]:
        """
        Rank deals by Lexerd sourcing opportunity.

        Opportunity score combines:
        1. Risk tier (Tier 1 Critical = 100, Tier 2 High = 75)
           - More stressed = more likely to accept capital solution
           - Tier weights opportunity favorably

        2. Market growth signal (employment + population growth)
           - Strong market = easier to create value through operations
           - Weak market = need other levers (capital stack optimization)

        3. DSCR spread (distance below 1.25x refi floor)
           - Larger spread = more distress = more motivated seller
           - 1.35x → 1.25x = 10bps spread (moderate distress)
           - 1.10x → 1.25x = 150bps spread (severe distress)

        4. Maturity urgency (12m = 100, 36m = 50)
           - Closer to maturity = more pressing need
           - Creates timeline pressure for decision

        Opportunity score = (tier_score * 0.40) + (market_score * 0.20) +
                           (dscr_spread_score * 0.25) + (maturity_score * 0.15)

        Top 100 deals = highest opportunity_score
        These are the leads to pursue first.

        Args:
            loans: List of loan dicts (should be pre-filtered by tier)

        Returns:
            List of OpportunityRank objects sorted by opportunity_score
        """
        logger.info(f"Ranking {len(loans)} loans by opportunity")

        ranked = []

        for idx, loan in enumerate(loans):
            # Extract key scoring components
            tier = loan.get('tier', 4)
            dscr = loan.get('dscr', 1.5)
            ltv = loan.get('current_ltv', 0.5)
            months_to_maturity = loan.get('months_to_maturity', 60)

            # Calculate component scores
            # ===========================

            # Tier score: Tier 1=100, Tier 2=75, Tier 3=50, other=25
            tier_scores = {1: 100, 2: 75, 3: 50, 4: 25}
            tier_score = tier_scores.get(tier, 25)

            # Market score: Placeholder for actual market growth data
            # In production, fetch from BLS/Census enrichment pipeline
            market_growth_score = 60  # Placeholder (0-100 scale)

            # DSCR spread score: How far below refi floor?
            dscr_refi_floor = 1.25
            dscr_spread = max(0, dscr_refi_floor - dscr)
            # Map: 0bps spread = 0, 300bps spread = 100
            dscr_spread_bps = dscr_spread * 10000
            dscr_spread_score = min(100, (dscr_spread_bps / 300) * 100)

            # Maturity urgency score
            if months_to_maturity <= 12:
                maturity_score = 100
            elif months_to_maturity <= 24:
                maturity_score = 80
            elif months_to_maturity <= 36:
                maturity_score = 50
            else:
                maturity_score = 0

            # Calculate composite opportunity score
            opportunity_score = (
                (tier_score * 0.40) +
                (market_growth_score * 0.20) +
                (dscr_spread_score * 0.25) +
                (maturity_score * 0.15)
            )

            # Build opportunity rank
            rank_obj = OpportunityRank(
                rank=idx + 1,  # Will be updated after sorting
                loan_id=loan.get('loan_id', 'unknown'),
                opportunity_score=opportunity_score,
                risk_tier=tier,
                property_address=loan.get('property_address', 'Unknown'),
                units=loan.get('units', 0),
                property_class=loan.get('property_class', 'U'),
                market=loan.get('msa_code', 'Unknown'),
                current_balance=loan.get('current_balance', 0),
                dscr=dscr,
                ltv=ltv,
                months_to_maturity=months_to_maturity,
                dscr_stress_100bps=loan.get('dscr_stress_100bps'),
                dscr_stress_200bps=loan.get('dscr_stress_200bps'),
                owner_contact=loan.get('owner_contact'),
                lender_contact=loan.get('lender_contact'),
                sourcing_notes=self._generate_sourcing_notes(loan, opportunity_score)
            )

            ranked.append(rank_obj)

        # Sort by opportunity score (highest first)
        ranked.sort(key=lambda x: x.opportunity_score, reverse=True)

        # Update ranks after sorting
        for idx, rank_obj in enumerate(ranked):
            rank_obj.rank = idx + 1

        logger.info(f"Ranked {len(ranked)} opportunities (top score: {ranked[0].opportunity_score:.1f})")

        return ranked

    def _generate_sourcing_notes(self, loan: Dict, opportunity_score: float) -> str:
        """
        Generate recommended sourcing approach for a deal.

        Args:
            loan: Loan record dict
            opportunity_score: Calculated opportunity score

        Returns:
            Recommended sourcing strategy text
        """
        tier = loan.get('tier', 4)
        dscr = loan.get('dscr', 1.5)
        ltv = loan.get('current_ltv', 0.5)

        notes = []

        if tier == 1:
            notes.append("TIER 1 PRIORITY: High refinance stress. Daily outreach candidate.")
        elif tier == 2:
            notes.append("TIER 2 HIGH: Emerging refinance risk. Include in weekly pipeline.")
        else:
            notes.append("TIER 3 MONITOR: Future opportunity. Build relationship.")

        if dscr < 1.10:
            notes.append("Critical DSCR. Likely seeking capital urgently.")
        elif dscr < 1.25:
            notes.append("Stressed DSCR. Cannot refi conventionally.")

        if ltv > 0.75:
            notes.append("High LTV. Owner needs equity partner.")

        return " ".join(notes)

    def generate_alert_report(self, ranked_loans: List[OpportunityRank]) -> Dict:
        """
        Generate structured alert report for sourcing team.

        Output: Comprehensive dict with:
        - Tier 1 opportunities (CRITICAL - immediate action)
        - Tier 2 opportunities (HIGH - near-term risk)
        - Tier 3 monitoring (FUTURE - watch trend)
        - Summary statistics

        Each deal includes:
        - Property details (address, units, class, year built)
        - Loan metrics (DSCR, LTV, maturity date)
        - Market context (MSA code, employment growth)
        - Refinance pressure (stressed DSCR at +100bps, +200bps)
        - Recommended sourcing approach

        Sourcing team uses this to prioritize outreach.

        Args:
            ranked_loans: List of OpportunityRank objects (pre-sorted)

        Returns:
            Dict with report structure and alert tiers
        """
        logger.info(f"Generating alert report for {len(ranked_loans)} opportunities")

        # Separate into tiers
        tier1 = [l for l in ranked_loans if l.risk_tier == 1]
        tier2 = [l for l in ranked_loans if l.risk_tier == 2]
        tier3 = [l for l in ranked_loans if l.risk_tier == 3]

        logger.info(f"Alert Distribution:")
        logger.info(f"  Tier 1 (Critical): {len(tier1)}")
        logger.info(f"  Tier 2 (High): {len(tier2)}")
        logger.info(f"  Tier 3 (Monitor): {len(tier3)}")

        # Generate report
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_opportunities': len(ranked_loans),
            'summary': {
                'tier_1_count': len(tier1),
                'tier_2_count': len(tier2),
                'tier_3_count': len(tier3),
                'top_100_avg_score': self._calculate_avg_score(ranked_loans[:100]),
            },
            'tier_1_critical': self._format_tier(tier1[:50]),  # Top 50 Tier 1
            'tier_2_high': self._format_tier(tier2[:100]),     # Top 100 Tier 2
            'tier_3_monitor': self._format_tier(tier3[:100]),  # Top 100 Tier 3
            'top_100_leads': [
                self._loan_to_dict(l) for l in ranked_loans[:100]
            ]
        }

        return report

    def _format_tier(self, loans: List[OpportunityRank]) -> List[Dict]:
        """
        Format tier-specific loan data for report.

        Args:
            loans: List of OpportunityRank objects

        Returns:
            List of dicts formatted for reporting
        """
        return [
            {
                'rank': loan.rank,
                'loan_id': loan.loan_id,
                'opportunity_score': round(loan.opportunity_score, 1),
                'property': {
                    'address': loan.property_address,
                    'units': loan.units,
                    'class': loan.property_class,
                    'market': loan.market,
                },
                'metrics': {
                    'current_balance': f"${loan.current_balance/1e6:.1f}M",
                    'dscr': round(loan.dscr, 2),
                    'ltv': f"{loan.ltv*100:.1f}%",
                    'months_to_maturity': int(loan.months_to_maturity),
                },
                'stress_analysis': {
                    'dscr_at_100bps': round(loan.dscr_stress_100bps, 2) if loan.dscr_stress_100bps else 'N/A',
                    'dscr_at_200bps': round(loan.dscr_stress_200bps, 2) if loan.dscr_stress_200bps else 'N/A',
                },
                'sourcing_notes': loan.sourcing_notes,
            }
            for loan in loans
        ]

    def _loan_to_dict(self, loan: OpportunityRank) -> Dict:
        """
        Convert OpportunityRank object to dict for JSON serialization.

        Args:
            loan: OpportunityRank object

        Returns:
            Dict representation
        """
        return {
            'rank': loan.rank,
            'loan_id': loan.loan_id,
            'opportunity_score': round(loan.opportunity_score, 1),
            'risk_tier': loan.risk_tier,
            'current_balance': loan.current_balance,
            'dscr': round(loan.dscr, 2),
            'ltv': round(loan.ltv, 3),
            'months_to_maturity': int(loan.months_to_maturity),
        }

    def _calculate_avg_score(self, loans: List[OpportunityRank]) -> float:
        """
        Calculate average opportunity score for a set of loans.

        Args:
            loans: List of OpportunityRank objects

        Returns:
            Average opportunity score
        """
        if not loans:
            return 0.0
        return sum(l.opportunity_score for l in loans) / len(loans)

    def export_alert_report_csv(self, ranked_loans: List[OpportunityRank], filepath: str):
        """
        Export alert report to CSV for spreadsheet usage.

        Args:
            ranked_loans: List of OpportunityRank objects
            filepath: Output CSV file path
        """
        import csv

        logger.info(f"Exporting alert report to {filepath}")

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Rank', 'Loan ID', 'Opportunity Score', 'Risk Tier',
                'Property Address', 'Units', 'Class', 'Market',
                'Current Balance ($M)', 'DSCR', 'LTV (%)', 'Months to Maturity',
                'DSCR @+100bps', 'DSCR @+200bps', 'Sourcing Notes'
            ])

            # Data rows
            for loan in ranked_loans[:500]:  # Top 500
                writer.writerow([
                    loan.rank,
                    loan.loan_id,
                    f"{loan.opportunity_score:.1f}",
                    f"Tier {loan.risk_tier}",
                    loan.property_address,
                    loan.units,
                    loan.property_class,
                    loan.market,
                    f"{loan.current_balance/1e6:.1f}",
                    f"{loan.dscr:.2f}",
                    f"{loan.ltv*100:.1f}",
                    int(loan.months_to_maturity),
                    f"{loan.dscr_stress_100bps:.2f}" if loan.dscr_stress_100bps else "N/A",
                    f"{loan.dscr_stress_200bps:.2f}" if loan.dscr_stress_200bps else "N/A",
                    loan.sourcing_notes,
                ])

        logger.info(f"Alert report exported: {filepath}")
