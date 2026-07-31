"""
Match SEC loans to B3 loans (avoid double-counting).

LCMV-58 Module D: Loan Deduplication & Matching

Problem: Same loan might appear in BOTH channels:
- Some GSE deals are also securitized (rare but happens)
- We need to dedupe to avoid counting twice in scoring pipeline

Matching strategy:
1. Property address (exact or fuzzy match)
2. Loan amount (within 5% tolerance - accounts for paydowns)
3. Owner name (if available in both sources)

If match found:
- Merge records (B3 is primary, SEC adds historical data)
- Flag as "dual-channel" loan

If no match:
- Classify as "SEC-only" (competitive advantage!)
- This is the deal the market doesn't see yet

Why dedup matters:
- Avoids double-scoring same loan in multiple channels
- Identifies "SEC-only" deals (off-market opportunities)
- Enables integrated view of entire loan (both sources)

Author: Sajan Goswami (Lexerd Capital Management)
"""

import pandas as pd
import logging
from typing import Tuple, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LoanDeduplicator:
    """
    Deduplicate and match SEC loans to B3 loans.

    Usage:
        dedup = LoanDeduplicator()
        unified = dedup.match_sec_to_b3_loans(sec_loans, b3_loans)
    """

    def __init__(self, address_fuzzy_threshold: float = 0.85):
        """
        Initialize loan deduplicator.

        Args:
            address_fuzzy_threshold: Similarity threshold for fuzzy address match (0-1)
                                    Default: 0.85 (85% match = duplicate)
        """
        self.address_fuzzy_threshold = address_fuzzy_threshold
        logger.info("LoanDeduplicator initialized (fuzzy_threshold=%.2f)",
                   address_fuzzy_threshold)

    def match_sec_to_b3_loans(
        self,
        sec_loans: pd.DataFrame,
        b3_loans: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Match SEC CMBS loans to Freddie Mac/Fannie Mae B3 loans.

        Problem: Same loan might appear in BOTH channels:
        - Some GSE deals are also securitized (rare but happens)
        - We need to dedupe to avoid counting twice

        Matching strategy:
        1. Property address (exact or fuzzy match)
        2. Loan amount (within 5% tolerance - accounts for paydowns)
        3. Owner name (if available in both sources)

        If match found:
        - Merge records (B3 is primary, SEC adds historical data)
        - Flag as "dual-channel" loan

        If no match:
        - Classify as "SEC-only" (competitive advantage!)
        - This is the deal the market doesn't see yet

        Args:
            sec_loans: Loans from SEC prospectuses (SEC-extracted data)
            b3_loans: Loans from Freddie Mac/Fannie Mae B3 (GSE data)

        Returns:
            Unified DataFrame with:
            - All loans (B3 + SEC-only)
            - "loan_source" column: "GSE-only", "SEC-only", or "dual-channel"
            - "matched_to_b3" column: B3 loan ID if matched, null otherwise
            - Merged fields from both sources where matched
        """
        if sec_loans.empty and b3_loans.empty:
            logger.warning("Both SEC and B3 dataframes are empty")
            return pd.DataFrame()

        if sec_loans.empty:
            logger.info("No SEC loans to match, returning B3 only")
            b3_loans["loan_source"] = "GSE-only"
            return b3_loans

        if b3_loans.empty:
            logger.info("No B3 loans, returning SEC loans")
            sec_loans["loan_source"] = "SEC-only"
            return sec_loans

        # Initialize result dataframe with B3 loans (primary source)
        result = b3_loans.copy()
        result["loan_source"] = "GSE-only"
        result["matched_to_b3"] = None
        result["sec_data"] = None

        # Track matched SEC loans
        matched_sec_indices = set()

        # Try to match each SEC loan to a B3 loan
        for sec_idx, sec_loan in sec_loans.iterrows():
            best_match = None
            best_score = 0

            for b3_idx, b3_loan in b3_loans.iterrows():
                # Calculate match score
                score = self._calculate_match_score(sec_loan, b3_loan)

                if score > best_score:
                    best_score = score
                    best_match = b3_idx

            # If good match found, merge data
            if best_score >= 0.7:  # Threshold: 70% similarity = match
                matched_sec_indices.add(sec_idx)
                result.loc[best_match, "loan_source"] = "dual-channel"
                result.loc[best_match, "matched_to_b3"] = sec_loan.get("loan_id", "")
                result.at[best_match, "sec_data"] = str(sec_loan.to_dict())  # Convert dict to string
                logger.debug("Matched SEC loan %s to B3 loan %s (score: %.2f)",
                           sec_loan.get("loan_id", ""), best_match, best_score)

        # Add unmatched SEC loans as "SEC-only"
        for sec_idx, sec_loan in sec_loans.iterrows():
            if sec_idx not in matched_sec_indices:
                sec_loan_copy = sec_loan.to_dict()
                sec_loan_copy["loan_source"] = "SEC-only"
                sec_loan_copy["matched_to_b3"] = None
                sec_loan_copy["sec_data"] = None
                result = pd.concat([result, pd.DataFrame([sec_loan_copy])],
                                  ignore_index=True)

        logger.info("Deduplication complete: %d dual-channel, %d SEC-only, %d GSE-only",
                   len(result[result["loan_source"] == "dual-channel"]),
                   len(result[result["loan_source"] == "SEC-only"]),
                   len(result[result["loan_source"] == "GSE-only"]))

        return result

    def _calculate_match_score(
        self,
        sec_loan: pd.Series,
        b3_loan: pd.Series
    ) -> float:
        """
        Calculate match score between SEC and B3 loan (0-1).

        Scoring:
        - Address match (exact or fuzzy): 40% weight
        - Loan amount tolerance (within 5%): 40% weight
        - Owner name match: 20% weight

        Total score 1.0 = perfect match, 0.0 = no match.

        Args:
            sec_loan: SEC loan record (pandas Series)
            b3_loan: B3 loan record (pandas Series)

        Returns:
            Match score (0-1)
        """
        score = 0.0

        # Address matching (40% weight)
        sec_addr = str(sec_loan.get("property_address", "")).lower()
        b3_addr = str(b3_loan.get("property_address", "")).lower()

        if sec_addr and b3_addr:
            addr_match = self.fuzzy_match_addresses(sec_addr, b3_addr)
            score += (0.4 * addr_match)

        # Loan amount tolerance (40% weight)
        sec_amt = pd.to_numeric(sec_loan.get("loan_amount", 0), errors="coerce")
        b3_amt = pd.to_numeric(b3_loan.get("loan_amount", 0), errors="coerce")

        if sec_amt > 0 and b3_amt > 0:
            pct_diff = abs(sec_amt - b3_amt) / max(sec_amt, b3_amt)
            # 5% tolerance = 100% match, 20%+ diff = 0% match
            if pct_diff <= 0.05:
                amount_match = 1.0
            elif pct_diff >= 0.20:
                amount_match = 0.0
            else:
                amount_match = 1.0 - (pct_diff / 0.20)
            score += (0.4 * amount_match)

        # Owner name matching (20% weight)
        sec_owner = str(sec_loan.get("owner_name", "")).lower()
        b3_owner = str(b3_loan.get("owner_name", "")).lower()

        if sec_owner and b3_owner:
            owner_match = self.fuzzy_match_addresses(sec_owner, b3_owner)
            score += (0.2 * owner_match)

        return score

    def fuzzy_match_addresses(self, addr1: str, addr2: str) -> float:
        """
        Fuzzy string match for property addresses (handle typos).

        Uses SequenceMatcher (built-in, no dependencies) to calculate
        string similarity. Normalized to 0-1 range.

        Why fuzzy match?
        - Addresses vary: "123 Main St" vs "123 Main Street"
        - Typos: "Apartment" vs "Aparment"
        - Abbreviations: "St" vs "Street", "Apt" vs "Apartment"
        - Case differences: "OAK PARK" vs "Oak Park"

        Args:
            addr1: First address (lowercase)
            addr2: Second address (lowercase)

        Returns:
            Match score (0-1, where 1=identical)
        """
        # Normalize: remove extra spaces, punctuation
        addr1_clean = " ".join(addr1.split()).replace(".", "").replace(",", "")
        addr2_clean = " ".join(addr2.split()).replace(".", "").replace(",", "")

        if addr1_clean == addr2_clean:
            return 1.0

        # Use SequenceMatcher for fuzzy matching
        matcher = SequenceMatcher(None, addr1_clean, addr2_clean)
        return matcher.ratio()

    def classify_loan_source(
        self,
        sec_match: bool,
        b3_match: bool
    ) -> str:
        """
        Classify loan source based on match status.

        Args:
            sec_match: True if loan appears in SEC data
            b3_match: True if loan appears in B3 data

        Returns:
            Classification: "GSE-only", "SEC-only", or "dual-channel"
        """
        if sec_match and b3_match:
            return "dual-channel"
        elif sec_match:
            return "SEC-only"
        elif b3_match:
            return "GSE-only"
        else:
            return "unknown"


def match_sec_to_b3_loans(
    sec_loans: pd.DataFrame,
    b3_loans: pd.DataFrame
) -> pd.DataFrame:
    """
    Convenience function: dedupe without instantiating deduplicator.

    Usage:
        unified = match_sec_to_b3_loans(sec_loans, b3_loans)
    """
    dedup = LoanDeduplicator()
    return dedup.match_sec_to_b3_loans(sec_loans, b3_loans)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example usage
    dedup = LoanDeduplicator()

    # Sample data
    sec_loans = pd.DataFrame([
        {"loan_id": "SEC-001", "property_address": "123 Main St", "loan_amount": 5000000},
        {"loan_id": "SEC-002", "property_address": "456 Oak Ave", "loan_amount": 3000000},
    ])

    b3_loans = pd.DataFrame([
        {"loan_id": "B3-001", "property_address": "123 Main Street", "loan_amount": 5050000},
        {"loan_id": "B3-002", "property_address": "789 Pine Rd", "loan_amount": 2500000},
    ])

    unified = dedup.match_sec_to_b3_loans(sec_loans, b3_loans)
    print(f"Unified {len(unified)} loans:")
    print(unified[["loan_id", "loan_source"]])
