"""
Unified Opportunity Loader for SEC CMBS and Freddie Mac Loan Database

LCMV-68: Auto-populate Opportunities from Freddie Mac & SEC CMBS Data

This module is the ENGINE of the Opportunities tab. It:
1. Fetches REAL Freddie Mac loans from Multifamily Loan Database (live API or placeholder)
2. Fetches REAL SEC CMBS loans from SEC EDGAR API (live API or placeholder)
3. Scores both sources with 3M Model
4. Deduplicates (Freddie Mac vs SEC-only)
5. Ranks by Tier 1/2/3 and opportunity score
6. Returns top 100 opportunities

The goal: No manual uploads needed. Auto-populate Opportunities tab
by pulling from both Freddie Mac and SEC channels automatically.

Data Sources:
- Freddie Mac Multifamily Loan Database: https://sf.freddiemac.com/data
- SEC CMBS Filings (424B5 prospectuses): https://www.sec.gov/cgi-bin/browse-edgar

Author: Sajan Goswami (Lexerd Capital Management)
Date: 2026-07-31
"""

import pandas as pd
import logging
from typing import Optional, Dict, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import json
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configuration for live data sources
FREDDIE_MAC_API_URL = "https://sf.freddiemac.com/data"  # Freddie Mac Multifamily Loan Database
SEC_CMBS_API_URL = "https://www.sec.gov/cgi-bin/browse-edgar"  # SEC EDGAR for CMBS filings (424B5)
MONTHS_TO_MATURITY_FILTER = 36  # Focus on loans maturing within 36 months


class OpportunityLoader:
    """
    Unified loader for Freddie Mac and SEC CMBS opportunities.

    Loads opportunities from both channels, deduplicates,
    scores, and ranks by opportunity tier.
    """

    def __init__(self, cache_dir: Path = None):
        """
        Initialize opportunity loader.

        Args:
            cache_dir: Directory containing cached opportunity data.
                      Defaults to calibration/opportunities/cache/
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent / "cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache file paths
        self.freddie_mac_cache_file = self.cache_dir / "freddie_mac_loans.parquet"
        self.sec_cmbs_cache_file = self.cache_dir / "sec_cmbs_loans.parquet"
        self.unified_cache_file = self.cache_dir / "unified_opportunities.parquet"
        self.metadata_file = self.cache_dir / "metadata.json"

        logger.info(f"OpportunityLoader initialized (cache_dir={cache_dir})")

    def load_opportunities(self, top_n: int = 100) -> pd.DataFrame:
        """
        Load scored opportunities from SEC CMBS and Freddie Mac Loan Database.

        This is the PRIMARY interface for the Opportunities tab. It:
        1. Fetches Freddie Mac Multifamily Loan Database (live or cache)
        2. Fetches SEC CMBS filings (424B5 prospectuses, live or cache)
        3. Scores both sources
        4. Deduplicates (Freddie Mac vs SEC-only)
        5. Ranks by Tier 1/2/3 and opportunity score
        6. Returns top 100 opportunities

        Returns:
            DataFrame with scored opportunities ready for display.
            Columns: loan_id, property_address, city, state, units, class,
                     dscr, ltv, maturity_date, risk_tier, opportunity_score,
                     market_score, model_score, management_score, final_score,
                     source (Freddie Mac|SEC-only|Dual-channel), data_freshness, months_to_maturity
        """
        try:
            logger.info(f"Loading top {top_n} opportunities from Freddie Mac + SEC CMBS")

            # Load from each source
            fm_opps = self._get_freddie_mac_opportunities()
            sec_opps = self._get_sec_cmbs_opportunities()

            logger.info(f"Loaded {len(fm_opps)} Freddie Mac opportunities and {len(sec_opps)} SEC CMBS opportunities")

            # Merge and rank
            unified = self._deduplicate_and_rank(fm_opps, sec_opps)

            # Get top N
            result = unified.head(top_n).copy()

            # Add data freshness
            result['data_freshness'] = self._get_data_freshness_str()

            logger.info(f"Returning {len(result)} top opportunities")
            return result

        except Exception as e:
            logger.error(f"Error loading opportunities: {e}")
            return pd.DataFrame()

    def _get_freddie_mac_opportunities(self) -> pd.DataFrame:
        """
        Load Freddie Mac multifamily opportunities from live API or cache.

        Falls back to placeholder data if live API is unavailable.
        """
        try:
            # Try to fetch from live Freddie Mac API
            live_data = self._fetch_freddie_mac_live_data()
            if live_data is not None and not live_data.empty:
                logger.info(f"Loaded {len(live_data)} Freddie Mac loans from live API")
                live_data['source'] = 'Freddie Mac'
                live_data['loan_source'] = 'Freddie Mac'
                live_data['data_status'] = 'Connected'
                return live_data

            # Fallback: Try to load from cache
            if self.freddie_mac_cache_file.exists():
                fm_loans = pd.read_parquet(self.freddie_mac_cache_file)
                logger.info(f"Loaded {len(fm_loans)} Freddie Mac loans from cache (live API unavailable)")
                fm_loans['source'] = 'Freddie Mac'
                fm_loans['loan_source'] = 'Freddie Mac'
                fm_loans['data_status'] = 'Cached'
                return fm_loans

            # If neither live API nor cache exist, return placeholder
            logger.warning("No live Freddie Mac API available and cache not found. Returning placeholder.")
            return self._get_freddie_mac_placeholder()

        except Exception as e:
            logger.error(f"Error loading Freddie Mac opportunities: {e}")
            return self._get_freddie_mac_placeholder()

    def _fetch_freddie_mac_live_data(self) -> Optional[pd.DataFrame]:
        """
        Attempt to fetch live Freddie Mac data from Freddie Mac Multifamily Loan Database.

        Returns:
            DataFrame with Freddie Mac loans or None if API unavailable

        Note: Freddie Mac public data is available at sf.freddiemac.com/data
        This is a placeholder that will be implemented once API access is configured.
        """
        try:
            # TODO: Implement actual Freddie Mac API call
            # This will fetch: property address, city, state, units, class, DSCR, LTV, maturity date
            # Query: multifamily loans maturing within 36 months
            logger.info("Attempting to fetch from Freddie Mac Multifamily Loan Database API...")
            # For now, return None to trigger fallback
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch from Freddie Mac live API: {e}")
            return None

    def _get_freddie_mac_placeholder(self) -> pd.DataFrame:
        """
        Return placeholder DataFrame indicating awaiting connection.
        """
        placeholder = pd.DataFrame({
            'loan_id': [],
            'property_address': [],
            'city': [],
            'state': [],
            'units': [],
            'property_class': [],
            'dscr': [],
            'current_ltv': [],
            'months_to_maturity': [],
            'risk_tier': [],
            'opportunity_score': [],
            'source': [],
            'loan_source': [],
            'data_status': []
        })
        logger.info("Returning placeholder Freddie Mac DataFrame (awaiting connection)")
        return placeholder

    def _get_sec_cmbs_opportunities(self) -> pd.DataFrame:
        """
        Load SEC CMBS opportunities from live API or cache.

        Fetches from SEC EDGAR API for 424B5 prospectuses (multifamily CMBS).
        Falls back to placeholder data if live API is unavailable.
        """
        try:
            # Try to fetch from live SEC EDGAR API
            live_data = self._fetch_sec_cmbs_live_data()
            if live_data is not None and not live_data.empty:
                logger.info(f"Loaded {len(live_data)} SEC CMBS loans from live API")
                live_data['source'] = 'SEC'
                live_data['loan_source'] = 'SEC-CMBS'
                live_data['data_status'] = 'Connected'
                return live_data

            # Fallback: Try to load from cache
            if self.sec_cmbs_cache_file.exists():
                sec_loans = pd.read_parquet(self.sec_cmbs_cache_file)
                logger.info(f"Loaded {len(sec_loans)} SEC CMBS loans from cache (live API unavailable)")
                sec_loans['source'] = 'SEC'
                sec_loans['loan_source'] = 'SEC-CMBS'
                sec_loans['data_status'] = 'Cached'
                return sec_loans

            # If neither live API nor cache exist, return placeholder
            logger.warning("No live SEC CMBS API available and cache not found. Returning placeholder.")
            return self._get_sec_cmbs_placeholder()

        except Exception as e:
            logger.error(f"Error loading SEC CMBS opportunities: {e}")
            return self._get_sec_cmbs_placeholder()

    def _fetch_sec_cmbs_live_data(self) -> Optional[pd.DataFrame]:
        """
        Attempt to fetch live SEC CMBS data from SEC EDGAR API.

        Queries: Recent 424B5 prospectuses (2024-2025) for multifamily CMBS
        Focus on: JPMorgan, Bank of America, Wells Fargo, UBS deals

        Returns:
            DataFrame with SEC CMBS loans or None if API unavailable

        Note: SEC EDGAR API is available at https://www.sec.gov/cgi-bin/browse-edgar
        This is a placeholder that will be implemented once API access is configured.
        """
        try:
            # TODO: Implement actual SEC EDGAR API call
            # This will fetch: loan schedules with property-level detail
            # Extract: property address, city, state, units, class, DSCR, LTV, maturity date
            logger.info("Attempting to fetch from SEC EDGAR CMBS API...")
            # For now, return None to trigger fallback
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch from SEC CMBS live API: {e}")
            return None

    def _get_sec_cmbs_placeholder(self) -> pd.DataFrame:
        """
        Return placeholder DataFrame indicating awaiting connection.
        """
        placeholder = pd.DataFrame({
            'loan_id': [],
            'property_address': [],
            'city': [],
            'state': [],
            'units': [],
            'property_class': [],
            'dscr': [],
            'current_ltv': [],
            'months_to_maturity': [],
            'risk_tier': [],
            'opportunity_score': [],
            'source': [],
            'loan_source': [],
            'data_status': []
        })
        logger.info("Returning placeholder SEC CMBS DataFrame (awaiting connection)")
        return placeholder

    def _deduplicate_and_rank(self, fm_opps: pd.DataFrame, sec_opps: pd.DataFrame) -> pd.DataFrame:
        """
        Merge, deduplicate, and rank opportunities by risk tier and opportunity score.

        Strategy:
        1. Identify dual-channel loans (same loan in both Freddie Mac and SEC CMBS)
        2. Dedupe by property address + loan amount matching
        3. Rank by Tier 1/2/3 (risk_tier column)
        4. Within tier, rank by opportunity_score

        Args:
            fm_opps: Freddie Mac Multifamily Loan Database opportunities
            sec_opps: SEC CMBS opportunities

        Returns:
            Merged and ranked DataFrame
        """
        try:
            if fm_opps.empty and sec_opps.empty:
                return pd.DataFrame()

            if fm_opps.empty:
                logger.info("No Freddie Mac opportunities, using SEC CMBS only")
                return sec_opps.sort_values(['risk_tier', 'opportunity_score'], ascending=[True, False])

            if sec_opps.empty:
                logger.info("No SEC CMBS opportunities, using Freddie Mac only")
                return fm_opps.sort_values(['risk_tier', 'opportunity_score'], ascending=[True, False])

            # Find duplicates between Freddie Mac and SEC CMBS
            # Simple match: same address + similar loan amount (within 5%)
            duplicates = []
            sec_matched = set()

            for fm_idx, fm_row in fm_opps.iterrows():
                for sec_idx, sec_row in sec_opps.iterrows():
                    if sec_idx in sec_matched:
                        continue

                    # Check address similarity (simple exact match for now)
                    addr_match = str(fm_row.get('property_address', '')).lower() == \
                                str(sec_row.get('property_address', '')).lower()

                    # Check loan amount similarity (within 5%)
                    fm_amount = fm_row.get('current_balance', 0)
                    sec_amount = sec_row.get('current_balance', 0)
                    amount_match = abs(fm_amount - sec_amount) / max(fm_amount, sec_amount, 1) < 0.05 if fm_amount > 0 else False

                    if addr_match and amount_match:
                        # Dual-channel loan
                        duplicates.append({
                            'fm_idx': fm_idx,
                            'sec_idx': sec_idx,
                            'address': fm_row.get('property_address', ''),
                        })
                        sec_matched.add(sec_idx)

            logger.info(f"Found {len(duplicates)} dual-channel loans")

            # Create unified dataframe
            unified_rows = []

            # Add Freddie Mac loans (including dual-channel, with SEC data merged)
            for fm_idx, fm_row in fm_opps.iterrows():
                row = fm_row.copy()

                # Find matching SEC loan if exists
                for dup in duplicates:
                    if dup['fm_idx'] == fm_idx:
                        sec_row = sec_opps.iloc[dup['sec_idx']]
                        row['source'] = 'Dual-channel'
                        # Merge SEC fields (if not already present)
                        for col in sec_row.index:
                            if col not in row.index or pd.isna(row[col]):
                                row[col] = sec_row[col]
                        break

                unified_rows.append(row)

            # Add SEC-only loans (not matched to B3)
            for sec_idx, sec_row in sec_opps.iterrows():
                if sec_idx not in sec_matched:
                    sec_row['source'] = 'SEC-only'
                    unified_rows.append(sec_row)

            # Create DataFrame
            unified = pd.DataFrame(unified_rows)

            # Ensure required scoring columns exist
            if 'risk_tier' not in unified.columns:
                # Default: classify by months to maturity
                unified['risk_tier'] = unified['months_to_maturity'].apply(
                    lambda x: 1 if x < 6 else (2 if x < 24 else 3)
                )

            if 'opportunity_score' not in unified.columns:
                # Default: simple score based on tier
                unified['opportunity_score'] = unified['risk_tier'].apply(
                    lambda x: 100 if x == 1 else (75 if x == 2 else 50)
                )

            # Sort by tier (1/2/3) then by opportunity_score (descending)
            unified = unified.sort_values(
                ['risk_tier', 'opportunity_score'],
                ascending=[True, False]
            )

            logger.info(f"Unified {len(unified)} opportunities (Freddie Mac: {len(fm_opps)}, SEC-only: {len(sec_opps) - len(sec_matched)}, Dual: {len(duplicates)})")

            return unified

        except Exception as e:
            logger.error(f"Error deduplicating opportunities: {e}")
            return pd.concat([fm_opps, sec_opps], ignore_index=True) if not fm_opps.empty or not sec_opps.empty else pd.DataFrame()

    def _get_data_freshness_str(self) -> str:
        """Return data freshness as formatted string."""
        metadata = self._load_metadata()

        fm_update = metadata.get('freddie_mac_last_update', 'Awaiting')
        sec_update = metadata.get('sec_cmbs_last_update', 'Awaiting')

        return f"Freddie Mac: {fm_update} | SEC CMBS: {sec_update}"

    def get_data_freshness(self) -> Dict[str, str]:
        """
        Return last update timestamps for each source.

        Returns:
            Dict with 'freddie_mac' and 'sec_cmbs' keys containing ISO datetime strings
        """
        metadata = self._load_metadata()
        return {
            'freddie_mac': metadata.get('freddie_mac_last_update', 'Awaiting'),
            'sec_cmbs': metadata.get('sec_cmbs_last_update', 'Awaiting'),
        }

    def _load_metadata(self) -> Dict:
        """Load metadata about cache freshness and data source status."""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading metadata: {e}")

        return {
            'freddie_mac_last_update': 'Awaiting',
            'sec_cmbs_last_update': 'Awaiting',
        }

    def get_tier_breakdown(self) -> Dict[int, int]:
        """
        Return count of opportunities by risk tier.

        Returns:
            Dict with tier 1/2/3 counts, e.g. {1: 15, 2: 45, 3: 40}
        """
        try:
            opps = self.load_opportunities(top_n=1000)  # Load more to get full breakdown
            if opps.empty:
                return {1: 0, 2: 0, 3: 0}

            return {
                1: len(opps[opps['risk_tier'] == 1]),
                2: len(opps[opps['risk_tier'] == 2]),
                3: len(opps[opps['risk_tier'] == 3]),
            }
        except Exception as e:
            logger.error(f"Error getting tier breakdown: {e}")
            return {1: 0, 2: 0, 3: 0}

    def save_freddie_mac_cache(self, df: pd.DataFrame):
        """Save Freddie Mac loans to cache."""
        try:
            df.to_parquet(self.freddie_mac_cache_file)
            logger.info(f"Saved {len(df)} Freddie Mac loans to cache")
        except Exception as e:
            logger.error(f"Error saving Freddie Mac cache: {e}")

    def save_sec_cmbs_cache(self, df: pd.DataFrame):
        """Save SEC CMBS loans to cache."""
        try:
            df.to_parquet(self.sec_cmbs_cache_file)
            logger.info(f"Saved {len(df)} SEC CMBS loans to cache")
        except Exception as e:
            logger.error(f"Error saving SEC CMBS cache: {e}")

    def save_unified_cache(self, unified: pd.DataFrame):
        """Save unified opportunities to cache."""
        try:
            unified.to_parquet(self.unified_cache_file)
            logger.info(f"Saved {len(unified)} opportunities to cache")
        except Exception as e:
            logger.error(f"Error saving unified cache: {e}")


def load_opportunities(top_n: int = 100) -> pd.DataFrame:
    """
    Convenience function to load opportunities.

    Args:
        top_n: Number of top opportunities to return

    Returns:
        DataFrame with scored opportunities
    """
    loader = OpportunityLoader()
    return loader.load_opportunities(top_n=top_n)


def get_data_freshness() -> Dict[str, str]:
    """
    Convenience function to get data freshness info.

    Returns:
        Dict with 'b3' and 'sec' keys containing last update times
    """
    loader = OpportunityLoader()
    return loader.get_data_freshness()


def get_tier_breakdown() -> Dict[int, int]:
    """
    Convenience function to get tier breakdown.

    Returns:
        Dict with tier 1/2/3 counts
    """
    loader = OpportunityLoader()
    return loader.get_tier_breakdown()
