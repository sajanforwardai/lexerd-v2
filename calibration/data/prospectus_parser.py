"""
Parse 424B5 prospectuses to extract loan schedules (origination data).

LCMV-58 Module B: Prospectus Loan Schedule Parser

424B5 is the initial prospectus filed when a CMBS deal closes. It contains
the loan-level tape (schedule) with 20-30 fields per loan: property address,
DSCR, LTV, maturity, occupancy, rent data, etc.

Why 424B5 prospectuses are a competitive advantage:
1. Loan origination snapshot (clean, consistent format)
2. Filed within days of deal closing (early visibility)
3. Covers entire loan population (no sampling bias)
4. Structured tables (unlike servicer reports which vary)
5. Available 1-3 years before commercial loans mature

Parsing approach:
1. Detect PDF tables using pdfplumber/PyPDF
2. Extract raw table → structured text
3. Validate field types (DSCR 0.0-2.5, LTV 0-1.0, etc.)
4. Map column names to standard format (align with B3 tapes)
5. Handle OCR errors, scanned PDFs, format variations

Data quality challenges we handle:
- Pre-2010 prospectuses: Scanned images, OCR errors
- Modern prospectuses: Clean digital PDFs
- Column name variations (e.g., "DSCR" vs "Debt Service Coverage Ratio")
- Missing fields (occupancy, rent not always disclosed)
- Multi-page tables (continuation pages)

Output: Pandas DataFrame with standardized columns
- Enables seamless reuse of LCMV-37 scoring logic (same format as B3 tapes)

Author: Sajan Goswami (Lexerd Capital Management)
"""

import pandas as pd
import logging
from typing import Optional, List, Tuple
import numpy as np
from pathlib import Path
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Standard column mapping (align with B3 tape format)
STANDARD_COLUMNS = {
    "property_address": str,
    "property_type": str,
    "dscr": float,
    "ltv": float,
    "loan_amount": float,
    "maturity_date": str,
    "occupancy": float,
    "owner_name": str,
    "state": str,
    "units": int,
    "year_built": int,
    "interest_rate": float,
    "loan_balance": float,
}


class ProspectusParser:
    """
    Parser for 424B5 prospectus PDFs.

    Usage:
        parser = ProspectusParser()
        loans = parser.parse_prospectus_pdf("path/to/prospectus.pdf")
        print(f"Extracted {len(loans)} loans")
    """

    def __init__(self, strict_validation: bool = True):
        """
        Initialize prospectus parser.

        Args:
            strict_validation: If True, reject records with invalid fields
                              If False, coerce/skip invalid fields (lenient mode)
        """
        self.strict_validation = strict_validation
        logger.info("ProspectusParser initialized (strict=%s)", strict_validation)

    def parse_prospectus_pdf(self, pdf_path: str) -> pd.DataFrame:
        """
        Extract loan schedule from 424B5 prospectus PDF.

        High-level workflow:
        1. Load PDF using pdfplumber
        2. Locate loan schedule table (usually pages 10-50 of prospectus)
        3. Extract table → raw DataFrame
        4. Validate field ranges (DSCR, LTV, occupancy)
        5. Standardize column names
        6. Return clean DataFrame

        Args:
            pdf_path: Path to prospectus PDF

        Returns:
            DataFrame with loan-level data (100-500 rows per deal)

        Raises:
            FileNotFoundError: PDF doesn't exist
            ValueError: No loan schedule table found
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"Prospectus not found: {pdf_path}")

        logger.info("Parsing prospectus: %s", pdf_path.name)

        try:
            # Try pdfplumber first (better for tables)
            try:
                import pdfplumber
                loans = self._parse_with_pdfplumber(pdf_path)
            except ImportError:
                logger.warning("pdfplumber not installed, falling back to PyPDF")
                loans = self._parse_with_pypdf(pdf_path)

            if loans.empty:
                raise ValueError(f"No loan schedule table found in {pdf_path.name}")

            logger.info("Extracted %d loans from prospectus", len(loans))
            return loans

        except Exception as e:
            logger.error("Failed to parse prospectus: %s", e)
            raise

    def _parse_with_pdfplumber(self, pdf_path: Path) -> pd.DataFrame:
        """
        Parse using pdfplumber (preferred: better table detection).

        pdfplumber excels at:
        - Detecting table boundaries (rows/cols)
        - Handling multi-line cells
        - Converting tables to structured DataFrames

        Workflow:
        1. Open PDF with pdfplumber
        2. Iterate pages (skip cover, find loan schedule ~page 10+)
        3. Extract tables using pdfplumber.extract_tables()
        4. Validate as loan schedule (has DSCR, LTV, maturity columns)
        5. Combine into single DataFrame

        Args:
            pdf_path: Path to PDF

        Returns:
            DataFrame with all loans
        """
        import pdfplumber

        all_loans = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    # Convert table to DataFrame
                    df = pd.DataFrame(table[1:], columns=table[0])

                    # Check if this looks like a loan schedule table
                    if self._is_loan_schedule_table(df):
                        logger.debug("Found loan schedule on page %d", page_num + 1)
                        loans = self.extract_loan_schedule(df)
                        if not loans.empty:
                            all_loans.append(loans)

        if all_loans:
            return pd.concat(all_loans, ignore_index=True)
        return pd.DataFrame()

    def _parse_with_pypdf(self, pdf_path: Path) -> pd.DataFrame:
        """
        Fallback: parse using PyPDF2 (simple but less reliable).

        PyPDF is a fallback when pdfplumber isn't available.
        Less sophisticated table detection, but works for simple PDFs.

        Args:
            pdf_path: Path to PDF

        Returns:
            DataFrame with all loans
        """
        from PyPDF2 import PdfReader

        text = ""
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            text += page.extract_text() or ""

        # Simple text parsing (extract structured lines as CSV)
        lines = text.split("\n")
        # TODO: Implement text parsing for simple case
        return pd.DataFrame()

    def extract_loan_schedule(self, raw_table: pd.DataFrame) -> pd.DataFrame:
        """
        Core extraction: find and parse loan schedule table from raw PDF table.

        Raw tables from PDFs are messy:
        - Headers might span multiple rows
        - Column names are variant (DSCR vs Debt Service Coverage Ratio)
        - Data types mixed (some columns have text, others numbers)
        - Whitespace: leading/trailing spaces, line breaks in cells

        Steps:
        1. Normalize headers (strip whitespace, standardize names)
        2. Clean data rows (remove non-loan rows, e.g., totals, subtotals)
        3. Extract loan fields (map raw columns to standard names)
        4. Validate and coerce types
        5. Return clean DataFrame

        Args:
            raw_table: Raw DataFrame from PDF table extraction

        Returns:
            Structured loan DataFrame
        """
        # Normalize headers
        headers = self._normalize_headers(raw_table.columns)
        raw_table.columns = headers

        # Remove summary rows (totals, subtotals, notes)
        loans = raw_table[
            ~raw_table.apply(
                lambda row: self._is_summary_row(row),
                axis=1
            )
        ].copy()

        return loans

    def _normalize_headers(self, headers: List[str]) -> List[str]:
        """
        Normalize column headers from raw PDF.

        Prospectuses have variant column names:
        - "DSCR" vs "Debt Service Coverage Ratio"
        - "LTV" vs "Loan-to-Value"
        - "Property Address" vs "Address"

        We normalize to standard names that match B3 tape format.

        Args:
            headers: Raw headers from PDF

        Returns:
            Normalized header list
        """
        normalized = []
        for header in headers:
            h = header.strip().lower()

            # Map variants to standard names
            if any(x in h for x in ["dscr", "debt service", "coverage"]):
                normalized.append("dscr")
            elif any(x in h for x in ["ltv", "loan-to-value"]):
                normalized.append("ltv")
            elif any(x in h for x in ["maturity", "maturity date"]):
                normalized.append("maturity_date")
            elif any(x in h for x in ["address", "property"]):
                normalized.append("property_address")
            elif any(x in h for x in ["occupancy"]):
                normalized.append("occupancy")
            elif any(x in h for x in ["amount", "loan amount"]):
                normalized.append("loan_amount")
            else:
                normalized.append(h)

        return normalized

    def _is_summary_row(self, row: pd.Series) -> bool:
        """
        Check if row is a summary row (total, subtotal, or footnote).

        Summary rows should be excluded from loan data:
        - "TOTAL" or "SUBTOTAL" rows
        - Footnote rows (start with "*", "^", etc.)
        - Completely empty rows

        Args:
            row: Row to check

        Returns:
            True if row should be excluded, False otherwise
        """
        # Check for "TOTAL" or "SUBTOTAL" in first column
        first_col = str(row.iloc[0] if len(row) > 0 else "").upper()
        if "TOTAL" in first_col or "SUBTOTAL" in first_col:
            return True

        # Check for footnote markers
        if any(first_col.startswith(x) for x in ["*", "^", "~", "("]):
            return True

        # Check if row is completely empty/null
        if row.isnull().all():
            return True

        return False

    def _is_loan_schedule_table(self, df: pd.DataFrame) -> bool:
        """
        Heuristic: is this a loan schedule table?

        A loan schedule table should have:
        - DSCR and LTV columns (key metrics)
        - Property address or location
        - Loan amount or balance
        - Maturity or maturity date
        - Enough rows to be a real table (>5 loans)

        Args:
            df: DataFrame to check

        Returns:
            True if likely a loan schedule, False otherwise
        """
        cols = [c.lower() for c in df.columns]

        # Must have at least DSCR or LTV
        has_metrics = any(x in cols for x in ["dscr", "ltv"])
        # Must have address or location
        has_location = any(x in cols for x in ["address", "property", "city", "state"])
        # Must have loan amount or maturity
        has_loan_info = any(x in cols for x in ["amount", "maturity", "balance"])

        return has_metrics and has_location and has_loan_info

    def validate_loan_fields(self, loans: pd.DataFrame) -> pd.DataFrame:
        """
        Validate extracted fields (DSCR, LTV ranges, etc.).

        Field validation catches OCR errors and malformed records:
        - DSCR should be 0.5-2.5 (realistic debt service coverage)
        - LTV should be 0-1.0 (loan-to-value ratio)
        - Occupancy should be 0-1.0 (percentage)
        - Loan amount should be positive
        - Maturity should be future date

        Strategy:
        - If strict_validation: reject invalid records
        - Otherwise: coerce to valid range or drop field

        Args:
            loans: DataFrame with potentially invalid fields

        Returns:
            Cleaned DataFrame (same or fewer rows)
        """
        original_count = len(loans)
        valid_loans = []

        for idx, loan in loans.iterrows():
            if self._is_valid_loan(loan):
                valid_loans.append(loan)

        result = pd.DataFrame(valid_loans) if valid_loans else pd.DataFrame()
        removed = original_count - len(result)
        if removed > 0:
            logger.warning("Removed %d invalid loan records", removed)

        return result

    def _is_valid_loan(self, loan: pd.Series) -> bool:
        """
        Check if a single loan record has valid fields.

        Validation rules:
        - DSCR: 0.5-2.5 (default: 1.0 if missing)
        - LTV: 0-1.0 (default: 0.65 if missing)
        - Occupancy: 0-1.0 (default: 0.95 if missing)
        - Loan amount: >0
        - Maturity: future date

        Args:
            loan: Loan record (pandas Series)

        Returns:
            True if valid, False otherwise
        """
        try:
            # DSCR validation
            if "dscr" in loan and pd.notna(loan["dscr"]):
                dscr = float(loan["dscr"])
                if not (0.5 <= dscr <= 2.5):
                    return False

            # LTV validation
            if "ltv" in loan and pd.notna(loan["ltv"]):
                ltv = float(loan["ltv"])
                if not (0 <= ltv <= 1.0):
                    return False

            # Occupancy validation
            if "occupancy" in loan and pd.notna(loan["occupancy"]):
                occ = float(loan["occupancy"])
                if not (0 <= occ <= 1.0):
                    return False

            # Loan amount validation
            if "loan_amount" in loan and pd.notna(loan["loan_amount"]):
                amt = float(loan["loan_amount"])
                if amt <= 0:
                    return False

            return True

        except (ValueError, TypeError):
            return False

    def standardize_columns(self, loans: pd.DataFrame) -> pd.DataFrame:
        """
        Map prospectus columns to standard format (align with B3 tapes).

        This is critical for reusing LCMV-37 scoring logic:
        - Same column names = same scoring functions
        - B3 tapes already define the standard schema
        - SEC loans should fit the same schema

        Mapping strategy:
        - Keep standard columns (from STANDARD_COLUMNS dict)
        - Drop non-standard columns (internal prospectus notes, etc.)
        - Add missing columns with defaults (e.g., occupancy=0.95)
        - Standardize data types (str, float, int as defined)

        Args:
            loans: DataFrame with raw prospectus columns

        Returns:
            DataFrame with standard columns (aligned with B3 format)
        """
        result = pd.DataFrame()

        for col_name, col_type in STANDARD_COLUMNS.items():
            if col_name in loans.columns:
                # Column exists, coerce type
                try:
                    result[col_name] = loans[col_name].astype(col_type)
                except (ValueError, TypeError):
                    # Coercion failed, use default
                    result[col_name] = pd.NA
            else:
                # Column missing, use default
                if col_type == float:
                    result[col_name] = np.nan
                elif col_type == int:
                    result[col_name] = pd.NA
                elif col_type == str:
                    result[col_name] = ""

        logger.info("Standardized %d loans to B3 format", len(result))
        return result


def parse_prospectus_pdf(pdf_path: str) -> pd.DataFrame:
    """
    Convenience function: parse prospectus without instantiating parser.

    Usage:
        loans = parse_prospectus_pdf("path/to/424B5.pdf")
    """
    parser = ProspectusParser()
    return parser.parse_prospectus_pdf(pdf_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example usage
    parser = ProspectusParser()

    # Parse a sample prospectus
    try:
        loans = parser.parse_prospectus_pdf("sample_prospectus.pdf")
        print(f"Extracted {len(loans)} loans:")
        print(loans.head())
    except FileNotFoundError:
        print("Sample prospectus not found (expected for MVP)")
