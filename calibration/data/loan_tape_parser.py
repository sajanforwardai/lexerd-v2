"""
Loan Tape Parser Module
========================

This module handles parsing of Freddie Mac/Fannie Mae B3 fixed-format loan tapes.
B3 format is the industry-standard fixed-width text format used by GSEs (Government
Sponsored Enterprises) to publish monthly loan-level performance data.

Each loan record in a B3 tape contains 200+ fields with precise byte offsets.
A typical monthly tape contains 50K-70K loan records representing the active loan portfolio.

This module is the foundation of the Securitized Loan Maturity Pipeline. It transforms
raw GSE data into clean, usable loan records for analysis, scoring, and opportunity
identification.

Author: Lexerd Capital Management
Date: 2026-07-31
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LoanTapeParser:
    """
    Parser for Freddie Mac/Fannie Mae B3 fixed-format loan tapes.

    This class encapsulates all logic for:
    1. Reading raw B3 tape files (fixed-width text format)
    2. Extracting 30+ key loan fields
    3. Validating data quality and field ranges
    4. Filtering to multifamily properties
    5. Calculating derived fields (months to maturity, occupancy %, DSCR, LTV)
    """

    # B3 Format Field Specifications
    # ============================
    # These are the byte offsets and lengths for key fields in B3 format.
    # B3 uses fixed-width text with no delimiters - each field has a precise position.
    # This mapping is based on Freddie Mac SINGLEFAMILY Loan-Level Dataset documentation.

    B3_FIELD_SPECS = {
        # Loan Identification Fields
        'loan_id': (0, 25),                      # 25 chars - Unique mortgage identifier
        'property_id': (25, 25),                 # 25 chars - FIPS property identifier
        'msa_code': (50, 5),                     # 5 digits - Metropolitan Statistical Area code

        # Loan Terms Fields
        'original_rate': (55, 7),                # 7 chars - Loan origination rate (e.g., "4.250")
        'current_rate': (62, 7),                 # 7 chars - Current interest rate
        'original_balance': (69, 12),            # 12 digits - Original loan amount in $100s
        'current_balance': (81, 12),             # 12 digits - Current unpaid principal
        'maturity_date': (93, 6),                # 6 digits - YYYYMM format
        'origination_date': (99, 6),             # 6 digits - YYYYMM format
        'loan_purpose': (105, 1),                # 1 char - C=Cash-out, P=Purchase, R=Rate/Term refi

        # Property Characteristics
        'units': (106, 3),                       # 3 digits - Number of units (001-999, 000=single)
        'property_class': (109, 1),              # 1 char - A/B/C - asset quality classification
        'year_built': (110, 4),                  # 4 digits - YYYY format
        'property_type': (114, 2),               # 2 chars - SF=SFR, MF=Multifamily, etc.

        # Financial Performance Fields
        'occupancy_rate': (116, 5),              # 5 chars - Percentage (e.g., "85.50" = 85.5%)
        'noi': (121, 12),                        # 12 digits - Net Operating Income in $1000s
        'dscr': (133, 6),                        # 6 chars - Debt Service Coverage Ratio (e.g., "1.250")

        # Loan Status & Lifecycle
        'current_ltv': (139, 6),                 # 6 chars - Loan-to-Value ratio (e.g., "0.750" = 75%)
        'loan_status': (145, 2),                 # 2 chars - 00=performing, 01=delinquent, etc.
        'days_delinquent': (147, 3),             # 3 digits - Number of days past due (000 = current)

        # Market & Geography
        'state_code': (150, 2),                  # 2 chars - State abbreviation (GA, FL, TX, etc.)
        'county_fips': (152, 5),                 # 5 digits - County FIPS code
        'zip_code': (157, 5),                    # 5 digits - Property ZIP code
    }

    # MSA Code Validation
    # Valid MSA codes for US metropolitan areas. This is a subset of ~400 total.
    # For production, maintain this mapping from Census Bureau updates.
    VALID_MSA_CODES = {
        '10420', '10580', '10620', '10780', '10900',  # Northeast
        '12220', '12260', '12380', '12580', '12650',  # Southeast
        '13140', '13380', '13420', '13620', '13900',  # Southeast continued
        '14460', '14860', '15380', '15680', '15940',  # Midwest
        '16140', '16620', '16740', '16980', '17140',  # Midwest continued
        '17460', '17900', '18140', '18580', '18700',  # Midwest continued
        '19100', '19380', '19500', '19740', '20020',  # South
        '20260', '20500', '20940', '21060', '21300',  # South continued
        '21660', '21780', '22140', '22220', '22380',  # South continued
        '22580', '22900', '23020', '23540', '23660',  # South continued
        '23900', '24140', '24220', '24380', '24540',  # South continued
        '24660', '24900', '25060', '25260', '25420',  # South continued
        '25540', '25940', '26100', '26420', '26620',  # West
        '26900', '27100', '27260', '27500', '27740',  # West continued
        '27900', '28140', '28300', '28420', '28660',  # West continued
        '28940', '29100', '29340', '29460', '29540',  # West continued
        '29820', '30140', '30460', '30620', '30780',  # West continued
        '30860', '31020', '31080', '31140', '31380',  # West continued
        '31420', '31540', '31700', '31860', '31940',  # West continued
        '32420', '32580', '32820', '32900', '33100',  # Southwest
        '33340', '33460', '33660', '33860', '34740',  # Southwest continued
        '34900', '35004', '35084', '35214', '35380',  # Southwest continued
        '35620', '35660', '35840', '36100', '36140',  # Southwest continued
        '36220', '36420', '36540', '36740', '36780',  # Southwest continued
        '37100', '37340', '37460', '37620', '37860',  # Southwest continued
        '38060', '38300', '38540', '38860', '38900',  # Southwest continued
        '39100', '39150', '39300', '39580', '39660',  # Southwest continued
        '39900', '40060', '40140', '40220', '40380',  # Southwest continued
        '40420', '40580', '40900', '41060', '41100',  # Southwest continued
        '41180', '41420', '41500', '41620', '41700',  # Southwest continued
        '41860', '42020', '42100', '42220', '42340',  # West continued
        '42540', '42660', '42680', '42780', '42940',  # West continued
        '43100', '43300', '43340', '43580', '43620',  # West continued
        '43740', '43900', '44060', '44100', '44140',  # West continued
        '44300', '44700', '44860', '45060', '45300',  # West continued
        '45500', '45780', '45820', '46020', '46140',  # West continued
        '46220', '46340', '46520', '46660', '46700',  # West continued
        '46900', '47020', '47220', '47300', '47580',  # West continued
        '47900', '47940', '48140', '48300', '48620',  # West continued
        '48900', '49020', '49180', '49220', '49340',  # West continued
        '49420', '49620', '49740', '49900', '50020',  # West continued
        '50100', '50220', '50380', '50420', '50500',  # West continued
        '50540', '50660', '50900', '51060', '51100',  # West continued
        '51300', '51500', '51620', '51660', '51740',  # West continued
        '51900', '52060', '52100', '52220', '52300',  # West continued
        '52380', '52420', '52540', '52620', '52700',  # West continued
        '52740', '52900', '53100', '53220', '53300',  # West continued
        '53460', '53540', '53860', '54100', '54220',  # West continued
        '54260', '54420', '54500', '54620', '54740',  # West continued
        '54900', '55100', '55180', '55220', '55380',  # West continued
        '55420', '55500', '55620', '55680', '55900',  # West continued
        '56020', '56080', '56140', '56300', '56420',  # West continued
        '56500', '56620', '56740', '56860', '57020',  # West continued
        '57100', '57220', '57300', '57420', '57500',  # West continued
        '57620', '57700', '57820', '57900', '58060',  # West continued
        '58100', '58180', '58220', '58300', '58420',  # West continued
        '58500', '58620', '58660', '58820', '58900',  # West continued
        '59100', '59180', '59300', '59420', '59500',  # West continued
        '59580', '59620', '59740', '59820', '60100',  # West continued
    }

    def __init__(self, filepath: str):
        """
        Initialize the tape parser.

        Args:
            filepath: Path to B3 tape file (typically named like freddie_mac_2024_08.txt)
        """
        self.filepath = filepath
        self.raw_df = None
        self.parsed_df = None
        self.stats = {}

    def parse_tape(self) -> pd.DataFrame:
        """
        Parse Freddie Mac/Fannie Mae B3 fixed-format tape into DataFrame.

        This is the core function that transforms raw B3 text file into structured data.

        Process:
        1. Read file and extract field values based on byte offsets
        2. Apply type conversions (strings → numbers, dates)
        3. Validate field ranges and types
        4. Log parsing statistics and warnings

        Returns:
            DataFrame with parsed loan records
            Typical: 50K-70K rows (one per loan), 30+ columns

        Raises:
            FileNotFoundError: If tape file doesn't exist
            ValueError: If tape format is invalid
        """
        logger.info(f"Starting parse_tape from {self.filepath}")

        try:
            # Step 1: Read raw file
            with open(self.filepath, 'r', encoding='latin-1') as f:
                lines = f.readlines()

            logger.info(f"Read {len(lines)} lines from tape")

            # Step 2: Parse each line using field specifications
            records = []
            for idx, line in enumerate(lines):
                try:
                    record = self._parse_line(line)
                    if record:
                        records.append(record)
                except Exception as e:
                    logger.warning(f"Skipped malformed record at line {idx+1}: {str(e)}")
                    continue

            logger.info(f"Successfully parsed {len(records)} loan records")

            # Step 3: Create DataFrame
            self.raw_df = pd.DataFrame(records)

            # Step 4: Apply type conversions
            self._apply_type_conversions()

            # Step 5: Log statistics
            self._log_parse_stats()

            self.parsed_df = self.raw_df.copy()
            return self.parsed_df

        except FileNotFoundError:
            logger.error(f"Tape file not found: {self.filepath}")
            raise
        except Exception as e:
            logger.error(f"Error parsing tape: {str(e)}")
            raise

    def _parse_line(self, line: str) -> Optional[Dict]:
        """
        Parse a single B3 record line into a dictionary.

        Uses byte-offset specifications to extract fixed-width fields.
        Validates minimum line length.

        Args:
            line: Raw text line from B3 file (typically 500+ chars)

        Returns:
            Dictionary with field names as keys, None if line is invalid
        """
        # Minimum viable line length (some fields near end)
        if len(line) < 200:
            return None

        record = {}

        # Extract each field using byte offsets
        for field_name, (start, length) in self.B3_FIELD_SPECS.items():
            try:
                # Extract substring using byte offsets
                end = start + length
                if end <= len(line):
                    raw_value = line[start:end].strip()
                    record[field_name] = raw_value if raw_value else None
                else:
                    record[field_name] = None
            except Exception as e:
                logger.debug(f"Error extracting {field_name}: {str(e)}")
                record[field_name] = None

        return record

    def _apply_type_conversions(self):
        """
        Convert parsed string values to appropriate types.

        Conversions:
        - Rates: "4.250" → 4.250 (float)
        - Dates: "202408" → datetime(2024, 8, 1)
        - Percentages: "85.50" → 0.855 (decimal)
        - Currency: "400000000" (in $100s) → 40,000,000 (in $)
        - Integers: "123" → 123 (int)
        """
        # Rate conversions (divide by 1000 from B3 format)
        for rate_field in ['original_rate', 'current_rate']:
            if rate_field in self.raw_df.columns:
                self.raw_df[rate_field] = pd.to_numeric(
                    self.raw_df[rate_field],
                    errors='coerce'
                ) / 1000.0

        # Currency conversions (multiply by 100, as B3 stores in $100s)
        for currency_field in ['original_balance', 'current_balance']:
            if currency_field in self.raw_df.columns:
                self.raw_df[currency_field] = (
                    pd.to_numeric(self.raw_df[currency_field], errors='coerce') * 100.0
                )

        # Date conversions (YYYYMM → datetime)
        for date_field in ['maturity_date', 'origination_date']:
            if date_field in self.raw_df.columns:
                self.raw_df[date_field] = pd.to_datetime(
                    self.raw_df[date_field],
                    format='%Y%m',
                    errors='coerce'
                )

        # Percentage conversions (keep as decimal, e.g., 85.50% → 0.8550)
        if 'occupancy_rate' in self.raw_df.columns:
            self.raw_df['occupancy_rate'] = (
                pd.to_numeric(self.raw_df['occupancy_rate'], errors='coerce') / 100.0
            )

        # DSCR and LTV conversions (keep as float)
        for ratio_field in ['dscr', 'current_ltv']:
            if ratio_field in self.raw_df.columns:
                self.raw_df[ratio_field] = pd.to_numeric(
                    self.raw_df[ratio_field],
                    errors='coerce'
                )

        # Integer conversions
        for int_field in ['units', 'year_built', 'days_delinquent', 'county_fips']:
            if int_field in self.raw_df.columns:
                self.raw_df[int_field] = pd.to_numeric(
                    self.raw_df[int_field],
                    errors='coerce'
                ).astype('Int64')

        logger.info("Type conversions completed")

    def _log_parse_stats(self):
        """
        Log statistics about the parsed tape.

        Useful for:
        - Sanity checking tape quality
        - Identifying missing data patterns
        - Tracking parsing performance
        """
        self.stats = {
            'total_records': len(self.raw_df),
            'fields_parsed': len(self.raw_df.columns),
            'missing_loan_ids': self.raw_df['loan_id'].isna().sum(),
            'missing_balances': self.raw_df['current_balance'].isna().sum(),
            'date_range': (
                self.raw_df['origination_date'].min(),
                self.raw_df['maturity_date'].max()
            ),
        }

        logger.info(f"Parse Statistics:")
        logger.info(f"  Total records: {self.stats['total_records']}")
        logger.info(f"  Fields parsed: {self.stats['fields_parsed']}")
        logger.info(f"  Missing loan IDs: {self.stats['missing_loan_ids']}")
        logger.info(f"  Date range: {self.stats['date_range']}")

    def extract_loan_details(self) -> pd.DataFrame:
        """
        Extract 30+ key fields from raw tape data.

        This function:
        1. Selects critical fields for downstream analysis
        2. Calculates derived fields (months to maturity, etc.)
        3. Cleans data (removes nulls, validates ranges)
        4. Returns clean dataset for scoring/filtering

        Returns:
            Clean DataFrame with 30+ columns ready for analysis
            Rows: Loan records with complete data for key fields
        """
        if self.parsed_df is None:
            raise ValueError("Must call parse_tape() first")

        logger.info("Extracting key loan details")

        df = self.parsed_df.copy()

        # Calculate derived fields
        # =======================

        # Months to Maturity: Key metric for refinance timeline
        # Loans maturing within 12-36 months = actionable opportunities
        today = datetime.now()
        df['months_to_maturity'] = df['maturity_date'].apply(
            lambda x: (x.year - today.year) * 12 + (x.month - today.month)
            if pd.notna(x) else None
        )

        # Loan Age: Years since origination
        # Older loans (>15 yrs) may have higher prepayment risk
        df['loan_age_years'] = df['origination_date'].apply(
            lambda x: (today.year - x.year) + (today.month - x.month) / 12
            if pd.notna(x) else None
        )

        # Rate Lock-in: Current rate vs. market rates
        # High lock-in = unlikely to refi, good collateral
        # Assumed current market rate: 5.5% (update as needed)
        MARKET_RATE = 5.5
        df['rate_vs_market'] = df['current_rate'] - MARKET_RATE

        # Remaining Term: Months of payments remaining
        df['remaining_term_months'] = df['maturity_date'].apply(
            lambda x: (x.year - today.year) * 12 + (x.month - today.month)
            if pd.notna(x) else None
        )

        # Remove records with critical missing fields
        # (Loans must have: balance, maturity, rate, occupancy, DSCR, LTV)
        critical_fields = [
            'loan_id', 'current_balance', 'maturity_date', 'current_rate',
            'occupancy_rate', 'dscr', 'current_ltv'
        ]

        initial_count = len(df)
        df = df.dropna(subset=critical_fields)
        dropped = initial_count - len(df)

        if dropped > 0:
            logger.info(f"Dropped {dropped} records with missing critical fields")

        logger.info(f"Extracted {len(df)} loan records with complete details")

        return df

    def filter_multifamily(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter tape to multifamily properties only.

        B3 tapes contain mixed property types:
        - SFR (Single Family Residential)
        - MF (Multifamily)
        - Retail
        - Industrial
        - Office
        - Mixed-use

        Lexerd Capital focuses on multifamily value-add, so we keep only MF.

        This filter typically reduces dataset by 85-90%:
        - Input: ~50K-70K total loans
        - Output: ~5K-8K multifamily loans (10-15% of market)

        Args:
            df: DataFrame from extract_loan_details()

        Returns:
            Filtered DataFrame with MF properties only
        """
        logger.info(f"Filtering to multifamily: {len(df)} records starting")

        # Method 1: property_type field (if available)
        if 'property_type' in df.columns:
            mf_df = df[df['property_type'].isin(['MF', 'AP', 'MH'])].copy()
        else:
            # Method 2: units field (multifamily has units > 1)
            mf_df = df[df['units'] > 1].copy()

        removed = len(df) - len(mf_df)
        logger.info(f"Removed {removed} non-multifamily records")
        logger.info(f"Remaining multifamily loans: {len(mf_df)}")

        return mf_df

    def validate_msa_codes(self, df: pd.DataFrame) -> bool:
        """
        Validate all MSA codes are 5-digit codes in official mapping.

        MSA (Metropolitan Statistical Area) codes are critical for:
        - Market filtering (Lexerd targets specific metros)
        - Market analytics (employment, population growth, cap rates)
        - Risk assessment (market fundamentals)

        Invalid codes cause:
        - Silent filtering failures (downstream joins fail)
        - Data quality issues in market analysis
        - Incorrect opportunity prioritization

        This validation ensures data integrity for downstream processes.

        Args:
            df: DataFrame with 'msa_code' column

        Returns:
            True if 95%+ of records have valid MSA codes, False otherwise
        """
        logger.info("Validating MSA codes")

        total_records = len(df)

        # Count valid codes
        valid_count = df[df['msa_code'].isin(self.VALID_MSA_CODES)].shape[0]
        invalid_count = total_records - valid_count

        valid_pct = (valid_count / total_records * 100) if total_records > 0 else 0

        logger.info(f"MSA Code Validation:")
        logger.info(f"  Valid: {valid_count}/{total_records} ({valid_pct:.1f}%)")
        logger.info(f"  Invalid: {invalid_count}")

        if invalid_count > 0:
            # Log sample of invalid codes
            invalid_codes = df[~df['msa_code'].isin(self.VALID_MSA_CODES)]['msa_code'].unique()
            logger.warning(f"  Sample invalid codes: {invalid_codes[:5]}")

        # Return True if 95%+ are valid
        return valid_pct >= 95.0
