"""
Generate alerts from SEC data (SEC-only opportunities).

LCMV-58 Module F: SEC Alert System

This is Lexerd's first-mover advantage:
- SEC prospectuses published when deal closes
- Freddie Mac B3 only shows their deals (~27% market share)
- SEC CMBS shows private-label deals (40-50% market)

By parsing SEC files, we identify deals months/years before:
- They mature and need refinancing
- Competitors find them
- They hit the open market

Strategy:
1. Score all SEC loans (apply LCMV-37 logic)
2. Filter "SEC-only" deals (not in B3)
3. Rank by opportunity (Tier 1 critical first)
4. Alert sourcing team to reach out directly to lenders/servicers

This enables direct-to-lender sourcing, bypassing brokers and competition.

Author: Sajan Goswami (Lexerd Capital Management)
"""

import pandas as pd
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SecAlertSystem:
    """
    Generate alerts from SEC loan data.

    Usage:
        alerts = SecAlertSystem()
        opportunities = alerts.generate_sec_opportunities(scored_loans)
    """

    def __init__(self, min_opportunity_rank: int = 30):
        """
        Initialize SEC alert system.

        Args:
            min_opportunity_rank: Only alert loans with rank <= threshold
                                 (1=highest, 100=lowest)
        """
        self.min_opportunity_rank = min_opportunity_rank
        logger.info("SecAlertSystem initialized (min_rank=%d)", min_opportunity_rank)

    def generate_sec_opportunities(self, scored_loans: pd.DataFrame) -> List[Dict]:
        """
        Identify SEC-only opportunities (deals not in B3).

        This is Lexerd's first-mover advantage:
        - SEC prospectuses published when deal closes
        - Freddie Mac B3 only shows their deals (~27% market share)
        - SEC CMBS shows private-label deals (40-50% market)

        By parsing SEC files, we identify deals months/years before:
        - They mature and need refinancing
        - Competitors find them
        - They hit the open market

        Strategy:
        1. Score all SEC loans (apply LCMV-37 logic)
        2. Filter "SEC-only" deals (not in B3)
        3. Rank by opportunity (Tier 1 critical first)
        4. Alert sourcing team to reach out directly to lenders/servicers

        Args:
            scored_loans: SEC loans post-scoring (from unified_loan_scorer)

        Returns:
            List of high-opportunity deals ready for outreach:
            - deal_name: Property name
            - loan_id: Loan identifier
            - opportunity_rank: 1-100 (1=highest)
            - maturity_tier: 1, 2, or 3
            - months_to_maturity: Months until maturity
            - lender: Lender name (if available)
            - servicer: Servicer name
            - recommended_action: Specific outreach strategy
        """
        if scored_loans.empty:
            logger.warning("No scored loans provided")
            return []

        # Filter to SEC-only deals
        sec_only = self.identify_sec_only_deals(scored_loans)
        if sec_only.empty:
            logger.info("No SEC-only deals found in scored loans")
            return []

        # Rank SEC opportunities
        ranked = self.rank_sec_opportunities(sec_only)

        # Generate outreach recommendations
        opportunities = []
        for idx, loan in ranked.iterrows():
            if loan.get("opportunity_rank", 100) <= self.min_opportunity_rank:
                opp = {
                    "deal_name": loan.get("property_address", ""),
                    "loan_id": loan.get("loan_id", ""),
                    "opportunity_rank": loan.get("opportunity_rank", 100),
                    "maturity_tier": loan.get("maturity_tier", 3),
                    "months_to_maturity": loan.get("months_to_maturity", 0),
                    "dscr": loan.get("dscr", 0),
                    "ltv": loan.get("ltv", 0),
                    "loan_amount": loan.get("loan_amount", 0),
                    "state": loan.get("state", ""),
                    "property_type": loan.get("property_type", ""),
                    "lender": loan.get("lender_name", "Unknown"),
                    "servicer": loan.get("servicer_name", "Unknown"),
                    "recommended_action": self._recommend_action(loan),
                    "outreach_priority": "CRITICAL" if loan.get("maturity_tier", 3) == 1
                                       else "HIGH" if loan.get("maturity_tier", 3) == 2
                                       else "MEDIUM",
                }
                opportunities.append(opp)

        logger.info("Generated %d SEC-only opportunities for outreach", len(opportunities))
        return opportunities

    def identify_sec_only_deals(self, scored_loans: pd.DataFrame) -> pd.DataFrame:
        """
        Filter to deals NOT in Freddie Mac/Fannie Mae.

        SEC-only deals are our competitive advantage:
        - Freddie Mac B3 only covers GSE channel (~27% of market)
        - SEC covers private-label CMBS (40-50% of market)
        - SEC-only deals are off-market opportunities

        Filtering:
        - loan_source == "SEC-only" (not matched to B3)
        - market_filter_pass == True (meets Lexerd criteria)
        - maturity_tier in [1, 2] (urgent or near-term)

        Args:
            scored_loans: DataFrame with loan_source and scoring results

        Returns:
            DataFrame with SEC-only opportunities
        """
        if "loan_source" not in scored_loans.columns:
            logger.warning("No loan_source column, treating all as SEC-only")
            sec_only = scored_loans.copy()
        else:
            sec_only = scored_loans[scored_loans["loan_source"] == "SEC-only"].copy()

        # Filter to market-qualified deals
        if "market_filter_pass" in scored_loans.columns:
            sec_only = sec_only[sec_only["market_filter_pass"] == True]

        # Focus on urgent/near-term (Tier 1-2)
        if "maturity_tier" in scored_loans.columns:
            sec_only = sec_only[sec_only["maturity_tier"].isin([1, 2])]

        logger.info("Identified %d SEC-only deals (market-qualified, Tier 1-2)",
                   len(sec_only))
        return sec_only

    def rank_sec_opportunities(self, loans: pd.DataFrame) -> pd.DataFrame:
        """
        Rank SEC deals by opportunity (same logic as B3).

        Ranking criteria:
        1. Maturity tier (Tier 1 = most urgent)
        2. Opportunity rank (1-100, where 1 = highest)
        3. Months to maturity (sooner = higher priority)
        4. Refinance risk (high risk = higher priority)

        Args:
            loans: SEC-only loans with scoring results

        Returns:
            DataFrame sorted by opportunity (highest first)
        """
        result = loans.copy()

        # Sort by maturity tier (1 first), then opportunity rank
        sort_cols = ["maturity_tier", "opportunity_rank"]
        sort_ascending = [True, True]

        result = result.sort_values(
            by=sort_cols,
            ascending=sort_ascending,
            na_position="last"
        )

        logger.debug("Ranked %d SEC opportunities", len(result))
        return result

    def generate_outreach_list(
        self,
        top_deals: List[Dict],
        format: str = "csv"
    ) -> str:
        """
        Generate CSV/HTML for sourcing team to use for lender calls.

        Output formats:
        - CSV: For CRM import or manual outreach
        - HTML: For dashboard display / stakeholder review
        - JSON: For API integration

        Args:
            top_deals: List of opportunity dictionaries (from generate_sec_opportunities)
            format: Output format ("csv", "html", or "json")

        Returns:
            Formatted string (CSV, HTML, or JSON)
        """
        if not top_deals:
            logger.warning("No deals to generate outreach list")
            return ""

        df = pd.DataFrame(top_deals)

        if format == "csv":
            return self._format_csv(df)
        elif format == "html":
            return self._format_html(df)
        elif format == "json":
            return df.to_json(orient="records", indent=2)
        else:
            raise ValueError(f"Unknown format: {format}")

    def _format_csv(self, df: pd.DataFrame) -> str:
        """
        Format opportunities as CSV for CRM/outreach.

        Columns:
        - deal_name, loan_id, opportunity_rank
        - maturity_tier, months_to_maturity
        - dscr, ltv, loan_amount
        - state, property_type
        - lender, servicer
        - recommended_action, outreach_priority

        Args:
            df: DataFrame with opportunity data

        Returns:
            CSV string
        """
        # Select columns for export
        export_cols = [
            "outreach_priority",
            "deal_name",
            "loan_id",
            "maturity_tier",
            "months_to_maturity",
            "dscr",
            "ltv",
            "loan_amount",
            "state",
            "property_type",
            "lender",
            "servicer",
            "recommended_action",
        ]

        export_df = df[[c for c in export_cols if c in df.columns]]
        return export_df.to_csv(index=False)

    def _format_html(self, df: pd.DataFrame) -> str:
        """
        Format opportunities as HTML table for dashboard.

        Columns grouped by:
        - Deal info (name, loan_id, tier)
        - Financial metrics (DSCR, LTV, amount)
        - Contact (lender, servicer)
        - Action (recommended_action, priority)

        Args:
            df: DataFrame with opportunity data

        Returns:
            HTML table string
        """
        html = '<table border="1" cellpadding="5" cellspacing="0">\n'
        html += "<thead><tr>"
        for col in df.columns:
            html += f"<th>{col}</th>"
        html += "</tr></thead>\n"

        html += "<tbody>\n"
        for idx, row in df.iterrows():
            html += "<tr>"
            for val in row.values:
                html += f"<td>{val}</td>"
            html += "</tr>\n"
        html += "</tbody>\n"
        html += "</table>"

        return html

    def _recommend_action(self, loan: pd.Series) -> str:
        """
        Generate specific outreach recommendation for a deal.

        Recommendations based on:
        - Maturity tier: How urgent?
        - Refinance risk: How stressed?
        - Opportunity rank: What's the priority?

        Args:
            loan: Loan record (pandas Series)

        Returns:
            Recommendation string (for sourcing team)
        """
        tier = loan.get("maturity_tier", 3)
        risk = loan.get("refinance_risk", "low")
        rank = loan.get("opportunity_rank", 100)

        if tier == 1:
            if risk == "high":
                return "URGENT: High-risk maturity <12mo. Direct servicer outreach."
            else:
                return "URGENT: Maturity <12mo. Lender outreach for early refinance."

        elif tier == 2:
            if risk == "high":
                return "Priority: Monitor 10-D reports. Servicer outreach if delinquency."
            else:
                return "Outreach: 1-2yr maturity window. Lender relationship building."

        else:
            return "Track: Add to pipeline. Monitor maturity clock."


def generate_sec_opportunities(scored_loans: pd.DataFrame) -> List[Dict]:
    """
    Convenience function: generate opportunities without instantiating system.

    Usage:
        opps = generate_sec_opportunities(scored_loans)
    """
    alert_system = SecAlertSystem()
    return alert_system.generate_sec_opportunities(scored_loans)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example usage
    alerts = SecAlertSystem()

    # Sample scored loans
    sample_loans = pd.DataFrame([
        {
            "loan_id": "SEC-001",
            "property_address": "123 Main St Apts",
            "loan_source": "SEC-only",
            "market_filter_pass": True,
            "maturity_tier": 1,
            "months_to_maturity": 6,
            "opportunity_rank": 15,
            "dscr": 0.95,
            "ltv": 0.72,
            "loan_amount": 5_000_000,
            "state": "CA",
            "property_type": "Multifamily",
            "lender_name": "JP Morgan",
            "servicer_name": "Berkadia",
            "refinance_risk": "high",
        },
        {
            "loan_id": "SEC-002",
            "property_address": "456 Oak Complex",
            "loan_source": "SEC-only",
            "market_filter_pass": True,
            "maturity_tier": 2,
            "months_to_maturity": 18,
            "opportunity_rank": 35,
            "dscr": 1.15,
            "ltv": 0.65,
            "loan_amount": 3_500_000,
            "state": "TX",
            "property_type": "Multifamily",
            "lender_name": "Deutsche Bank",
            "servicer_name": "Brookfield",
            "refinance_risk": "medium",
        },
    ])

    opps = alerts.generate_sec_opportunities(sample_loans)
    print(f"Generated {len(opps)} opportunities")
    for opp in opps:
        print(f"  {opp['deal_name']}: {opp['recommended_action']}")

    # Export to CSV
    csv_output = alerts.generate_outreach_list(opps, format="csv")
    print("\nOutreach List (CSV):")
    print(csv_output)
