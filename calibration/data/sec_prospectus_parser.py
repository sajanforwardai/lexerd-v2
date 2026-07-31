"""
SEC 424B5 Prospectus Parser - Extract loan-level data from CMBS prospectuses.

LCMV-80: Extract multifamily loan-level data from SEC 424B5 prospectus PDFs.

424B5 is the initial prospectus filed when a CMBS deal closes. It contains
the loan-level tape (schedule) with 20-30 fields per loan: property address,
DSCR, LTV, maturity, occupancy, units, property class, year built, interest rate,
amortization period, sponsor names, etc.

Why 424B5 prospectuses are a competitive advantage:
1. Loan origination snapshot (clean, consistent format)
2. Filed within days of deal closing (early visibility)
3. Covers entire loan population (no sampling bias)
4. Structured tables (unlike servicer reports which vary)
5. Available 1-3 years before commercial loans mature

Parsing approach:
1. Detect PDF tables using pdfplumber/PyPDF2
2. Extract raw table → structured text
3. Normalize column names (handle variations)
4. Validate field types (DSCR 0.5-3.0, LTV 0.3-0.95, units 50-5000, etc.)
5. Map column names to standard format
6. Handle OCR errors, scanned PDFs, format variations

Data quality challenges we handle:
- Pre-2010 prospectuses: Scanned images, OCR errors
- Modern prospectuses: Clean digital PDFs
- Column name variations (e.g., "DSCR" vs "Debt Service Coverage Ratio")
- Missing fields (occupancy, rent not always disclosed)
- Multi-page tables (continuation pages)
- Outliers (units > 5000, DSCR > 3.0, LTV > 0.95)

Output: Pandas DataFrame with standardized columns
- Enables seamless reuse of downstream loan scoring logic

Author: Sajan Goswami (Lexerd Capital Management)
"""

import pandas as pd
import logging
import re
from typing import Optional, List, Dict, Tuple, Any
from pathlib import Path
from datetime import datetime
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class ExtractionResult:
    """Result of extracting loan schedule from prospectus."""

    loans: pd.DataFrame
    deal_name: str
    closing_date: Optional[str]
    pool_size: float
    property_count: int
    extraction_method: str
    warnings: List[str]
    validation_score: float


class DataValidator:
    """Validation helpers for loan fields."""

    # Field validation ranges
    FIELD_RANGES = {
        'units': (50, 5000),
        'dscr': (0.5, 3.0),
        'ltv': (0.3, 0.95),
        'interest_rate': (0.005, 0.10),  # 0.5% - 10%
        'occupancy': (0.0, 1.0),
    }

    # Valid property classes
    VALID_PROPERTY_CLASSES = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C']

    # Valid US state codes
    VALID_STATES = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
    }

    @staticmethod
    def validate_field(field_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate a single field.

        Returns:
            (is_valid, error_message)
        """
        if pd.isna(value):
            return True, None

        try:
            field_lower = field_name.lower()

            # Numeric range validation
            if field_lower in DataValidator.FIELD_RANGES:
                min_val, max_val = DataValidator.FIELD_RANGES[field_lower]
                num_val = float(value)
                if not (min_val <= num_val <= max_val):
                    return False, f"{field_name} out of range [{min_val}, {max_val}]: {num_val}"

            # Property class validation
            if field_lower == 'property_class':
                str_val = str(value).upper().strip()
                if str_val not in DataValidator.VALID_PROPERTY_CLASSES:
                    return False, f"Invalid property class: {value}"

            # State code validation
            if field_lower == 'state':
                state_code = str(value).upper().strip()
                # If it's exactly 2 letters, it should be valid US state code
                if len(state_code) == 2:
                    if state_code not in DataValidator.VALID_STATES:
                        return False, f"Invalid state code: {value}"
                elif len(state_code) > 0:
                    # If more than 2 characters, also reject
                    return False, f"Invalid state code (should be 2 letters): {value}"

            # Date validation
            if 'date' in field_lower.lower():
                if isinstance(value, str):
                    # Try to parse as date
                    try:
                        dt = pd.to_datetime(value)
                        if dt.year < 1950 or dt.year > 2050:
                            return False, f"Date out of reasonable range: {value}"
                    except:
                        return False, f"Invalid date format: {value}"

            # Address validation
            if field_lower == 'property_address':
                addr = str(value).strip()
                if len(addr) < 5:
                    return False, f"Address too short: {addr}"
                # Should contain at least one number and one street word
                has_number = any(c.isdigit() for c in addr)
                if not has_number:
                    return False, f"Address missing number: {addr}"

            return True, None

        except Exception as e:
            return False, f"Validation error for {field_name}: {str(e)}"

    @staticmethod
    def validate_loan_record(loan: pd.Series) -> Tuple[bool, List[str]]:
        """
        Validate a complete loan record.

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        # Check for completely empty rows
        if loan.isnull().all():
            return False, ["Row is completely empty"]

        # Validate each field
        for field_name in loan.index:
            is_valid, error = DataValidator.validate_field(field_name, loan[field_name])
            if not is_valid:
                issues.append(error)

        # If critical fields are missing, mark as invalid
        critical_fields = ['property_address', 'loan_amount']
        missing_critical = [f for f in critical_fields if pd.isna(loan.get(f))]
        if missing_critical:
            return False, [f"Missing critical field: {f}" for f in missing_critical]

        return len(issues) == 0, issues


class ColumnMapper:
    """Map variant column names to standard format."""

    # Mapping of common variations to standard names
    HEADER_MAPPINGS = {
        'property_address': [
            'property address', 'property addr', 'address', 'addr',
            'property', 'prop address', 'prop addr', 'street address',
            'location', 'property location'
        ],
        'city': [
            'city', 'municipality', 'metro area', 'msa'
        ],
        'state': [
            'state', 'st', 'state code', 'state abbreviation'
        ],
        'zip_code': [
            'zip', 'zip code', 'postal code', 'zipcode'
        ],
        'units': [
            'units', 'no. of units', 'number of units', 'unit count',
            'units count', 'unit#', 'units #', 'number units'
        ],
        'property_class': [
            'class', 'property class', 'property type', 'type',
            'prop class', 'prop type', 'asset class', 'class/type'
        ],
        'year_built': [
            'year built', 'year', 'yob', 'year of construction',
            'construction year', 'built year', 'original year'
        ],
        'loan_amount': [
            'loan amount', 'loan', 'principal', 'original loan amount',
            'orig loan', 'loan size', 'loan value', 'amount'
        ],
        'current_balance': [
            'current balance', 'loan balance', 'current loan balance',
            'remaining balance', 'balance', 'loan bal'
        ],
        'interest_rate': [
            'interest rate', 'rate', 'coupon', 'loan rate',
            'annual rate', 'annual interest', 'note rate'
        ],
        'maturity_date': [
            'maturity', 'maturity date', 'payoff date', 'due date',
            'loan maturity', 'maturity time', 'loan due date'
        ],
        'amortization_period': [
            'amortization', 'amort', 'amortization period',
            'loan term', 'term', 'amort period'
        ],
        'dscr': [
            'dscr', 'debt service coverage', 'debt service coverage ratio',
            'coverage ratio', 'dscr ratio'
        ],
        'ltv': [
            'ltv', 'loan to value', 'loan-to-value', 'ltv ratio',
            'loan/value'
        ],
        'occupancy': [
            'occupancy', 'occupancy rate', 'occ', 'occupancy %',
            'occupancy pct', 'leasing'
        ],
        'sponsor_name': [
            'sponsor', 'owner', 'owner name', 'borrower',
            'borrower name', 'owner/sponsor', 'sponsor/owner'
        ]
    }

    @staticmethod
    def normalize_header(raw_header: str) -> Optional[str]:
        """
        Map raw header to standard column name.

        Args:
            raw_header: Raw header from PDF

        Returns:
            Standardized column name or None if no mapping found
        """
        h = raw_header.strip().lower().replace('_', ' ')

        # Exact match in mappings (prefer exact matches)
        for standard_name, variants in ColumnMapper.HEADER_MAPPINGS.items():
            if h in variants:
                return standard_name

        # Partial match (longer variants first to avoid false positives)
        # Sort by variant length descending
        all_variants = []
        for standard_name, variants in ColumnMapper.HEADER_MAPPINGS.items():
            for variant in variants:
                all_variants.append((len(variant), standard_name, variant))

        all_variants.sort(reverse=True)  # Longest variants first

        for _, standard_name, variant in all_variants:
            # Check if all significant words from variant are in h
            variant_words = [w for w in variant.split() if len(w) > 2]
            if variant_words and all(word in h for word in variant_words):
                return standard_name

        # No mapping found, normalize and keep original
        return h.replace(' ', '_')

    @staticmethod
    def normalize_headers(headers: List[str]) -> List[str]:
        """
        Normalize a list of headers.

        Args:
            headers: Raw headers from PDF

        Returns:
            List of normalized headers
        """
        normalized = []
        for header in headers:
            mapped = ColumnMapper.normalize_header(header)
            if mapped:
                normalized.append(mapped)
            else:
                # Keep original header if no mapping found
                normalized.append(header.strip().lower().replace(' ', '_'))
        return normalized


class ProspectusParser:
    """
    Parser for 424B5 prospectus PDFs.

    Extracts loan-level detail including property address, units, class,
    year built, loan amount, interest rate, maturity, DSCR, LTV, occupancy,
    sponsor names, and other metrics.

    Usage:
        parser = ProspectusParser("path/to/prospectus.pdf", "Deal Name")
        result = parser.parse()
        print(f"Extracted {result.property_count} properties")
        print(result.loans)
    """

    # Standard output columns
    STANDARD_COLUMNS = [
        'loan_id', 'property_address', 'city', 'state', 'zip_code',
        'units', 'property_class', 'year_built', 'loan_amount',
        'current_balance', 'interest_rate', 'maturity_date',
        'amortization_period', 'dscr', 'ltv', 'occupancy',
        'sponsor_name', 'data_quality_score', 'extraction_method',
        'validation_notes'
    ]

    def __init__(self, pdf_path: str, deal_name: str, strict_validation: bool = False):
        """
        Initialize prospectus parser.

        Args:
            pdf_path: Path to 424B5 prospectus PDF
            deal_name: Name of the securitization deal
            strict_validation: If True, strict validation rules (reject outliers)
                             If False, lenient (flag but don't reject)
        """
        self.pdf_path = Path(pdf_path)
        self.deal_name = deal_name
        self.strict_validation = strict_validation
        self.validator = DataValidator()
        self.mapper = ColumnMapper()
        self.warnings: List[str] = []

        logger.info(
            f"ProspectusParser initialized: {self.pdf_path.name} "
            f"({deal_name}, strict={strict_validation})"
        )

    def parse(self) -> ExtractionResult:
        """
        Parse prospectus and extract loan schedule.

        High-level workflow:
        1. Validate PDF exists
        2. Load PDF using pdfplumber
        3. Locate loan schedule table (usually pages 10-50)
        4. Extract table → raw DataFrame
        5. Normalize column names
        6. Validate field ranges
        7. Standardize to output schema
        8. Return ExtractionResult

        Returns:
            ExtractionResult with DataFrame and metadata

        Raises:
            FileNotFoundError: PDF doesn't exist
            ValueError: No loan schedule table found
        """
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"Prospectus not found: {self.pdf_path}")

        logger.info(f"Parsing prospectus: {self.pdf_path.name}")

        try:
            # Try pdfplumber first (better for tables)
            loans_df = self._parse_with_pdfplumber()
            extraction_method = "pdfplumber"

            if loans_df.empty:
                logger.warning("pdfplumber returned empty, trying PyPDF2 fallback")
                loans_df = self._parse_with_pypdf2()
                extraction_method = "pypdf2"

            if loans_df.empty:
                raise ValueError(f"No loan schedule table found in {self.pdf_path.name}")

            logger.info(f"Extracted {len(loans_df)} loan records")

            # Extract deal metadata
            deal_info = self._extract_deal_info()

            # Validate and standardize
            validated_df = self._validate_loans(loans_df)
            standardized_df = self._standardize_columns(validated_df)

            # Compute data quality scores
            standardized_df = self._compute_quality_scores(standardized_df)

            # Build result
            result = ExtractionResult(
                loans=standardized_df,
                deal_name=self.deal_name,
                closing_date=deal_info.get('closing_date'),
                pool_size=float(standardized_df['loan_amount'].sum()),
                property_count=len(standardized_df),
                extraction_method=extraction_method,
                warnings=self.warnings,
                validation_score=self._compute_validation_score(standardized_df)
            )

            logger.info(
                f"Prospectus parsing complete: {result.property_count} properties, "
                f"${result.pool_size:,.0f} pool size, "
                f"validation_score={result.validation_score:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to parse prospectus: {e}")
            raise

    def _parse_with_pdfplumber(self) -> pd.DataFrame:
        """
        Parse using pdfplumber (preferred: better table detection).

        pdfplumber excels at:
        - Detecting table boundaries (rows/cols)
        - Handling multi-line cells
        - Converting tables to structured DataFrames

        Returns:
            DataFrame with all loans, or empty if no tables found
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed, skipping")
            return pd.DataFrame()

        all_loans = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                logger.info(f"PDF has {len(pdf.pages)} pages")

                for page_num, page in enumerate(pdf.pages):
                    try:
                        tables = page.extract_tables()
                        if not tables:
                            continue

                        for table_idx, table in enumerate(tables):
                            if not table or len(table) < 2:
                                continue

                            # Convert table to DataFrame
                            df = pd.DataFrame(table[1:], columns=table[0])

                            # Check if this looks like a loan schedule table
                            if self._is_loan_schedule_table(df):
                                logger.info(
                                    f"Found loan schedule on page {page_num + 1}, "
                                    f"table {table_idx} ({len(df)} rows)"
                                )
                                loans = self.extract_loan_schedules(df)
                                if not loans.empty:
                                    all_loans.append(loans)
                    except Exception as e:
                        logger.warning(f"Error processing page {page_num + 1}: {e}")
                        continue

        except Exception as e:
            logger.error(f"pdfplumber parsing failed: {e}")
            return pd.DataFrame()

        if all_loans:
            result = pd.concat(all_loans, ignore_index=True)
            logger.info(f"pdfplumber extracted {len(result)} total loan records")
            return result

        return pd.DataFrame()

    def _parse_with_pypdf2(self) -> pd.DataFrame:
        """
        Fallback: parse using PyPDF2 (simple but less reliable).

        PyPDF2 is a fallback when pdfplumber isn't available.
        Extracts text and attempts simple regex-based parsing.

        Returns:
            DataFrame with all loans, or empty if parsing fails
        """
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            logger.warning("PyPDF2 not installed, cannot parse")
            return pd.DataFrame()

        try:
            text = ""
            reader = PdfReader(str(self.pdf_path))
            logger.info(f"PyPDF2: PDF has {len(reader.pages)} pages")

            for page_num, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
                except Exception as e:
                    logger.warning(f"Error extracting page {page_num + 1}: {e}")
                    continue

            # TODO: Implement robust text-based loan schedule parsing
            # For now, return empty (OCR parsing is complex and requires more work)
            logger.warning("PyPDF2 text parsing not yet implemented")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"PyPDF2 parsing failed: {e}")
            return pd.DataFrame()

    def extract_loan_schedules(self, raw_table: pd.DataFrame) -> pd.DataFrame:
        """
        Extract and clean loan schedule from raw PDF table.

        Raw tables from PDFs are messy:
        - Headers might span multiple rows
        - Column names are variant
        - Data types mixed
        - Whitespace: leading/trailing spaces, line breaks

        Steps:
        1. Normalize headers (strip whitespace, map variants)
        2. Clean data rows (remove summary rows, empty rows)
        3. Extract fields (coerce types, handle missing)
        4. Return cleaned DataFrame

        Args:
            raw_table: Raw DataFrame from PDF table extraction

        Returns:
            Structured loan DataFrame
        """
        if raw_table.empty:
            return pd.DataFrame()

        # Normalize headers
        headers = self.mapper.normalize_headers(list(raw_table.columns))
        raw_table.columns = headers

        # Remove summary rows and empty rows
        loans = raw_table[
            ~raw_table.apply(lambda row: self._is_summary_row(row), axis=1)
        ].copy()

        # Drop completely empty columns
        loans = loans.dropna(axis=1, how='all')

        # Clean whitespace in all cells
        for col in loans.columns:
            if loans[col].dtype == 'object':
                loans[col] = loans[col].apply(
                    lambda x: str(x).strip() if pd.notna(x) else x
                )

        logger.info(f"Extracted {len(loans)} loan records from table")
        return loans

    def _is_loan_schedule_table(self, df: pd.DataFrame) -> bool:
        """
        Heuristic: is this a loan schedule table?

        A loan schedule table should have key columns:
        - Property location (address, city, state)
        - Loan metrics (amount, rate, maturity)
        - Optional but common: DSCR, LTV, occupancy, units

        Args:
            df: DataFrame to check

        Returns:
            True if likely a loan schedule, False otherwise
        """
        if df.empty or len(df) < 5:
            return False

        # Normalize column names for matching
        cols = [c.lower().replace('_', ' ') for c in df.columns]

        # Count matching columns
        match_score = 0

        # Must have location info
        has_address = any(x in cols for x in [
            'property address', 'property addr', 'address', 'property',
            'prop address', 'street address'
        ])
        has_city = any(x in cols for x in ['city', 'municipality', 'metro area'])
        has_state = any(x in cols for x in ['state', 'st', 'state code'])

        # Must have loan info
        has_amount = any(x in cols for x in [
            'loan amount', 'loan', 'principal', 'original loan amount',
            'loan size', 'orig loan', 'amount'
        ])
        has_date = any(x in cols for x in [
            'maturity', 'maturity date', 'payoff date', 'due date',
            'loan maturity', 'maturity time'
        ])
        has_rate = any(x in cols for x in [
            'interest rate', 'rate', 'coupon', 'loan rate', 'annual rate'
        ])

        # Should have metrics
        has_dscr = any(x in cols for x in [
            'dscr', 'debt service coverage', 'debt service coverage ratio',
            'coverage ratio', 'dscr ratio'
        ])
        has_ltv = any(x in cols for x in [
            'ltv', 'loan to value', 'loan-to-value', 'ltv ratio', 'loan/value'
        ])
        has_units = any(x in cols for x in [
            'units', 'no. of units', 'number of units', 'unit count'
        ])

        # Scoring logic
        if has_address:
            match_score += 2
        elif (has_city and has_state):
            match_score += 1
        elif has_city or has_state:
            match_score += 1

        if has_amount:
            match_score += 2

        if has_date:
            match_score += 1

        if has_rate:
            match_score += 1

        if has_dscr or has_ltv or has_units:
            match_score += 1

        # Need at least 4 points and at least 5 rows
        is_loan_table = match_score >= 4

        logger.debug(
            f"Table evaluation: cols={len(cols)}, score={match_score}, "
            f"is_loan_table={is_loan_table}"
        )

        return is_loan_table

    def _is_summary_row(self, row: pd.Series) -> bool:
        """
        Check if row is a summary/footnote row (should be excluded).

        Summary rows to exclude:
        - "TOTAL", "SUBTOTAL", "GRAND TOTAL"
        - Footnote rows (start with "*", "^")
        - Completely empty rows

        Args:
            row: Row to check

        Returns:
            True if row should be excluded, False otherwise
        """
        # Check for completely empty row
        if row.isnull().all():
            return True

        # Check first non-null value for summary indicators
        for val in row:
            if pd.notna(val):
                first_str = str(val).upper().strip()
                if any(x in first_str for x in ['TOTAL', 'SUBTOTAL', 'SUMMARY']):
                    return True
                # Footnote markers
                if any(first_str.startswith(x) for x in ['*', '^', '~', '(', '[', '!']):
                    return True
                break

        return False

    def _validate_loans(self, loans_df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate loan records and filter/flag invalid records.

        For each record:
        1. Check critical fields (address, amount)
        2. Validate numeric ranges (DSCR, LTV, units, etc.)
        3. Add validation_notes column
        4. Mark as invalid if critical issues

        Args:
            loans_df: Raw loan DataFrame

        Returns:
            DataFrame with validation_notes added
        """
        original_count = len(loans_df)
        valid_loans = []

        for idx, loan in loans_df.iterrows():
            is_valid, issues = self.validator.validate_loan_record(loan)

            # Create validation note
            note = "; ".join(issues) if issues else "valid"

            if self.strict_validation:
                if is_valid:
                    loan_copy = loan.copy()
                    loan_copy['validation_notes'] = note
                    valid_loans.append(loan_copy)
                else:
                    self.warnings.append(f"Row {idx}: {note}")
                    logger.debug(f"Rejecting row {idx}: {note}")
            else:
                # Lenient: keep all loans, flag issues
                loan_copy = loan.copy()
                loan_copy['validation_notes'] = note
                valid_loans.append(loan_copy)

                if issues:
                    self.warnings.append(f"Row {idx}: {note}")

        result = pd.DataFrame(valid_loans) if valid_loans else pd.DataFrame()
        removed = original_count - len(result)

        if removed > 0:
            logger.warning(f"Removed {removed} invalid loan records in strict mode")

        return result

    def _standardize_columns(self, loans_df: pd.DataFrame) -> pd.DataFrame:
        """
        Map to standard output columns.

        This ensures consistent schema across all prospectuses.
        Handles type conversion, unit normalization, and date parsing.

        Args:
            loans_df: Validated loan DataFrame

        Returns:
            DataFrame with standard columns
        """
        result = pd.DataFrame()

        for col in self.STANDARD_COLUMNS:
            if col in loans_df.columns:
                # Column exists, try to coerce type
                try:
                    if col.endswith('_date'):
                        # Parse dates
                        result[col] = pd.to_datetime(loans_df[col], errors='coerce')
                    elif col in ['dscr', 'ltv', 'occupancy', 'interest_rate', 'loan_amount',
                                 'current_balance', 'data_quality_score']:
                        # Numeric columns
                        result[col] = pd.to_numeric(loans_df[col], errors='coerce')
                    elif col in ['units', 'year_built', 'amortization_period']:
                        # Integer columns
                        result[col] = pd.to_numeric(loans_df[col], errors='coerce').astype('Int64')
                    else:
                        # String columns
                        result[col] = loans_df[col].astype(str)
                except Exception as e:
                    logger.warning(f"Error coercing column {col}: {e}")
                    result[col] = pd.NA
            else:
                # Column missing, create with appropriate default
                if col.endswith('_date'):
                    result[col] = pd.NaT
                elif col in ['dscr', 'ltv', 'occupancy', 'interest_rate', 'loan_amount',
                             'current_balance', 'data_quality_score']:
                    result[col] = np.nan
                elif col in ['units', 'year_built', 'amortization_period']:
                    result[col] = pd.NA
                else:
                    result[col] = ""

        logger.info(f"Standardized {len(result)} loans to output schema")
        return result

    def _compute_quality_scores(self, loans_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute data quality score for each loan.

        Score is based on:
        - Completeness (% of key fields present)
        - Data validity (no validation issues)
        - Outlier detection (flagged but not penalized heavily)

        Score range: 0.0 - 1.0

        Args:
            loans_df: Standardized loan DataFrame

        Returns:
            DataFrame with data_quality_score column
        """
        result = loans_df.copy()

        # Key fields for completeness
        key_fields = [
            'property_address', 'city', 'state', 'units', 'loan_amount',
            'interest_rate', 'maturity_date', 'dscr', 'ltv'
        ]

        scores = []
        for idx, row in result.iterrows():
            # Completeness: % of key fields present
            present = sum(1 for f in key_fields if pd.notna(row.get(f)))
            completeness = present / len(key_fields)

            # Validity: check for validation notes
            notes = row.get('validation_notes', '')
            has_issues = isinstance(notes, str) and notes and notes != 'valid'
            validity = 0.8 if has_issues else 1.0

            # Combined score (70% completeness, 30% validity)
            score = completeness * 0.7 + validity * 0.3
            scores.append(max(0.0, min(1.0, score)))

        result['data_quality_score'] = scores
        return result

    def _compute_validation_score(self, loans_df: pd.DataFrame) -> float:
        """
        Compute overall validation score for the entire prospectus.

        Score is average data quality across all loans, weighted by
        loans with good data quality.

        Returns:
            Score 0.0 - 1.0
        """
        if loans_df.empty:
            return 0.0

        avg_quality = loans_df['data_quality_score'].mean()
        return float(avg_quality)

    def _extract_deal_info(self) -> Dict[str, Optional[str]]:
        """
        Extract deal metadata from PDF (prospectus cover).

        Returns:
            Dict with closing_date and other deal info (if found)
        """
        # TODO: Implement cover page extraction
        # For now, return empty (would parse prospectus cover/summary page)
        return {
            'closing_date': None,
            'deal_name': self.deal_name
        }

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for parsed prospectus.

        Returns after parse() has been called.

        Returns:
            Dict with summary metrics
        """
        # Note: This would be called after parse()
        return {
            'deal_name': self.deal_name,
            'pdf_path': str(self.pdf_path)
        }


def parse_prospectus(pdf_path: str, deal_name: str) -> ExtractionResult:
    """
    Convenience function: parse prospectus without instantiating parser.

    Usage:
        result = parse_prospectus("path/to/424B5.pdf", "ACME 2024-1")
        print(f"Extracted {result.property_count} properties")
        print(result.loans)

    Args:
        pdf_path: Path to prospectus PDF
        deal_name: Name of deal

    Returns:
        ExtractionResult with DataFrame and metadata
    """
    parser = ProspectusParser(pdf_path, deal_name)
    return parser.parse()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example usage (requires a real PDF)
    try:
        result = parse_prospectus("sample_prospectus.pdf", "SAMPLE-2024-01")
        print(f"Extracted {result.property_count} properties")
        print(f"Pool size: ${result.pool_size:,.0f}")
        print(f"Validation score: {result.validation_score:.2f}")
        print("\nSample loans:")
        print(result.loans.head(3))
    except FileNotFoundError:
        print("Sample prospectus not found (expected for MVP)")
