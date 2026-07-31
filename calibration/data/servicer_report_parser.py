"""
Parse 10-D servicer reports to extract monthly loan performance data.

LCMV-58 Module C: Servicer Report Extractor

10-D reports are filed monthly/quarterly by CMBS servicers. They track:
- Current loan balance (updated monthly, accounts for paydowns)
- Payment status (performing / 30+ / 60+ / 90+ / default)
- Occupancy trends (if disclosed)
- Rent collections (if disclosed)
- Loan modifications / extensions / payoffs (material events)

Why 10-D reports are critical:
1. Performance snapshot (updated monthly, unlike prospectuses)
2. Delinquency detection (60+/90+ days behind = early distress signal)
3. Modification tracking (extensions reveal refinancing pressures)
4. Occupancy trends (declining occupancy predicts distress)
5. Available 1-3 years before maturity

Key insight: 10-D shows loan EVOLUTION over time. Compare 10-D across months
to identify deterioration pattern (DSCR declining, occupancy dropping, etc.).

Data format challenges:
- Most 10-D reports use HTML tables (easier than PDF, but format varies)
- Some servicers more detailed than others (data quality varies)
- Required fields: payment status, occupancy (if disclosed)
- Optional fields: rent collections, property level detail

Output: Pandas DataFrame with:
- Loan identifier (matched to prospectus tape)
- Performance metrics (payment status, occupancy, balance)
- Modification flags (extension, payoff, etc.)

Author: Sajan Goswami (Lexerd Capital Management)
"""

import pandas as pd
import logging
from typing import Optional, List, Dict, Union
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Delinquency status codes
DELINQUENCY_STATUS = {
    "PERFORMING": "performing",
    "30+": "30plus",
    "60+": "60plus",
    "90+": "90plus",
    "DEFAULT": "default",
}


class ServicerReportParser:
    """
    Parser for 10-D servicer reports.

    Usage:
        parser = ServicerReportParser()
        performance = parser.parse_servicer_report("path/to/10-D.html")
        print(f"Extracted performance for {len(performance)} loans")
    """

    def __init__(self, extract_occupancy: bool = True):
        """
        Initialize servicer report parser.

        Args:
            extract_occupancy: Whether to extract occupancy data (if available)
        """
        self.extract_occupancy = extract_occupancy
        logger.info("ServicerReportParser initialized (occupancy=%s)", extract_occupancy)

    def parse_servicer_report(self, html_or_pdf: Union[str, bytes]) -> pd.DataFrame:
        """
        Extract loan performance data from 10-D servicer report.

        10-D reports are filed monthly/quarterly by servicers. They track:
        - Current loan balance (updated monthly)
        - Payment status (performing / 30+ / 60+ / 90+ / default)
        - Occupancy trends (if disclosed)
        - Rent collections (if disclosed)
        - Loan modifications / extensions / payoffs

        This is DIFFERENT from 424B5 (snapshot at origination).
        10-D shows loan EVOLUTION over time - identifies deterioration.

        Use case:
        - Identify loans declining toward distress
        - Track maturity extensions (servicer report signals extension)
        - Detect early-stage delinquencies (60+ days behind)

        Format varies by servicer but standardized by SEC regulations.
        Most 10-D forms use HTML tables (easier to parse than PDFs).

        Args:
            html_or_pdf: 10-D document (HTML string or PDF bytes)

        Returns:
            DataFrame with loan performance data (current status)

        Raises:
            ValueError: Unable to parse document or extract performance tables
        """
        try:
            if isinstance(html_or_pdf, bytes):
                # PDF case: convert to text (simplified)
                html_text = self._extract_text_from_pdf(html_or_pdf)
            else:
                html_text = html_or_pdf

            # Extract performance tables from HTML
            tables = self.extract_performance_tables(html_text)
            if not tables:
                # Return empty DataFrame instead of raising error (graceful degradation)
                logger.warning("No performance tables found in servicer report")
                return pd.DataFrame()

            # Combine all tables into single DataFrame
            performance_data = pd.concat(tables, ignore_index=True)

            # Calculate delinquency status
            performance_data = self.calculate_delinquency_status(performance_data)

            # Identify loan modifications (extensions, payoffs)
            performance_data["modifications"] = performance_data.apply(
                lambda row: self.identify_loan_modifications([row]),
                axis=1
            )

            logger.info("Extracted performance data for %d loans", len(performance_data))
            return performance_data

        except Exception as e:
            logger.error("Failed to parse servicer report: %s", e)
            raise

    def extract_performance_tables(self, html: str) -> List[pd.DataFrame]:
        """
        Extract payment status, occupancy, and other performance tables from HTML.

        10-D reports structure performance data in HTML tables:
        - Performance summary table (payment status by loan)
        - Occupancy table (if disclosure-compliant)
        - Modifications/events table (extensions, payoffs, etc.)

        Parsing strategy:
        1. Find all HTML tables (via regex or BeautifulSoup if available)
        2. Check if table is performance table (has payment status columns)
        3. Convert to DataFrame
        4. Validate and return

        Args:
            html: HTML content as string

        Returns:
            List of DataFrames, each containing a performance table

        Raises:
            ValueError: If no performance tables found
        """
        tables = []

        # Try BeautifulSoup first
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            for table in soup.find_all('table'):
                # Convert table to DataFrame
                rows = []
                for tr in table.find_all('tr'):
                    row = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    rows.append(row)

                if rows:
                    df = pd.DataFrame(rows[1:], columns=rows[0])
                    # Check if this is a performance table
                    if self._is_performance_table(df):
                        tables.append(df)

        except ImportError:
            # Fallback: simple regex-based HTML table parsing
            logger.warning("BeautifulSoup not available, using fallback parsing")
            # TODO: Implement regex-based HTML table parsing

        return tables

    def _is_performance_table(self, df: pd.DataFrame) -> bool:
        """
        Heuristic: is this a loan performance table?

        A performance table should have:
        - Payment status column (Performing, 30+, 60+, 90+, Default)
        - Loan identifier (loan number, property, etc.)
        - Current balance or amount
        - (Optional) Occupancy percentage

        Args:
            df: DataFrame to check

        Returns:
            True if likely a performance table, False otherwise
        """
        cols = [c.lower() for c in df.columns]

        # Must have payment status
        has_status = any(x in cols for x in ["status", "payment", "delinquency"])
        # Must have loan identifier
        has_loan_id = any(x in cols for x in ["loan", "property", "address", "name"])
        # Must have amount
        has_amount = any(x in cols for x in ["balance", "amount", "outstanding"])

        return has_status and has_loan_id and has_amount

    def calculate_delinquency_status(self, loans: pd.DataFrame) -> pd.DataFrame:
        """
        Flag delinquencies (60+, 90+, default).

        Delinquency status is critical for identifying distressed loans:
        - Performing: 0-30 days late
        - 60+ days: Material distress signal
        - 90+ days: Severe distress
        - Default: Formal default (foreclosure, workout)

        Strategy:
        - Parse payment status column
        - Standardize status codes
        - Add delinquency flag
        - Log high-delinquency deals

        Args:
            loans: DataFrame with payment status column

        Returns:
            DataFrame with delinquency_status column added
        """
        if "status" not in loans.columns and "payment_status" not in loans.columns:
            logger.warning("No payment status column found")
            loans["delinquency_status"] = "unknown"
            return loans

        status_col = "status" if "status" in loans.columns else "payment_status"

        def classify_status(status_str: str) -> str:
            status_str = str(status_str).upper()
            if "DEFAULT" in status_str or "FORECLOSURE" in status_str:
                return "default"
            elif "90+" in status_str:
                return "90plus"
            elif "60+" in status_str:
                return "60plus"
            elif "30+" in status_str:
                return "30plus"
            else:
                return "performing"

        loans["delinquency_status"] = loans[status_col].apply(classify_status)

        # Log high-delinquency loans
        high_delq = loans[loans["delinquency_status"].isin(["60plus", "90plus", "default"])]
        if len(high_delq) > 0:
            logger.warning("Found %d delinquent loans (60+ days)", len(high_delq))

        return loans

    def identify_loan_modifications(self, loans: List[Dict]) -> List[Dict]:
        """
        Identify extension, modification, payoff events.

        Loan modifications are material events that signal refinancing activity:
        - Extension: Maturity pushed back (refinancing pressure)
        - Modification: Terms changed (rates, amortization, etc.)
        - Payoff: Loan paid in full (redemption)
        - Partial payoff: Partial reduction (partial refinancing)

        These events are flagged in servicer reports and indicate:
        - Lender's willingness to extend (vs. want to collect now)
        - Refinancing activity (precursor to maturity pressure)
        - Loan performance change (modification = lender concerned about payoff)

        Args:
            loans: List of loan records to check

        Returns:
            List of modification dictionaries with event type and date
        """
        modifications = []

        for loan in loans:
            # Look for modification keywords in servicer notes
            if "notes" in loan:
                notes = str(loan.get("notes", "")).upper()
                if "EXTENSION" in notes or "EXTEND" in notes:
                    modifications.append({
                        "event_type": "extension",
                        "loan_id": loan.get("loan_id", "unknown"),
                    })
                if "PAYOFF" in notes or "PAID" in notes:
                    modifications.append({
                        "event_type": "payoff",
                        "loan_id": loan.get("loan_id", "unknown"),
                    })
                if "MODIFICATION" in notes or "MODIFIED" in notes:
                    modifications.append({
                        "event_type": "modification",
                        "loan_id": loan.get("loan_id", "unknown"),
                    })

        return modifications

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF (fallback for PDF servicer reports).

        Some servicers file 10-D as PDF instead of HTML. We extract text
        and try to parse tables from text.

        Args:
            pdf_bytes: PDF content as bytes

        Returns:
            Extracted text

        Raises:
            ImportError: If no PDF library available
        """
        try:
            from PyPDF2 import PdfReader
            from io import BytesIO

            reader = PdfReader(BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text

        except ImportError:
            logger.error("PyPDF2 not installed, cannot extract PDF text")
            raise ImportError("PyPDF2 required for PDF parsing")


def parse_servicer_report(html_or_pdf: Union[str, bytes]) -> pd.DataFrame:
    """
    Convenience function: parse servicer report without instantiating parser.

    Usage:
        performance = parse_servicer_report(html_content)
    """
    parser = ServicerReportParser()
    return parser.parse_servicer_report(html_or_pdf)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example usage
    parser = ServicerReportParser()

    # Sample HTML (in real case, loaded from 10-D filing)
    sample_html = """
    <table>
        <tr><th>Loan ID</th><th>Property</th><th>Status</th><th>Balance</th><th>Occupancy</th></tr>
        <tr><td>L001</td><td>Maple Apartments</td><td>Performing</td><td>$5,000,000</td><td>95%</td></tr>
        <tr><td>L002</td><td>Oak Complex</td><td>60+ Days</td><td>$4,500,000</td><td>78%</td></tr>
    </table>
    """

    try:
        performance = parser.parse_servicer_report(sample_html)
        print(f"Extracted performance for {len(performance)} loans")
        if not performance.empty:
            print(performance)
    except ValueError as e:
        print(f"Sample parsing: {e}")
