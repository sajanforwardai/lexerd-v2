"""
Prospectus schemas and data validators.

LCMV-80: Data type mappings, expected column names, validation rules,
and output schema for SEC prospectus parsing.

This module defines:
1. Expected column name variations (common across prospectuses)
2. Data type mappings
3. Field-level validation rules
4. Output schema (standardized fields)
5. Data quality expectations

Author: Sajan Goswami (Lexerd Capital Management)
"""

from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import pandas as pd
from dataclasses import dataclass


class PropertyClass(str, Enum):
    """Standard property class categories."""

    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"

    @classmethod
    def from_string(cls, value: str) -> Optional['PropertyClass']:
        """Parse property class from string."""
        if not value:
            return None
        val = value.strip().upper()
        for member in cls:
            if member.value == val:
                return member
        return None


class ValidationRule:
    """Field-level validation rule."""

    def __init__(
        self,
        field_name: str,
        field_type: type,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        required: bool = False,
        allowed_values: Optional[List[str]] = None,
        pattern: Optional[str] = None,
        description: str = ""
    ):
        """
        Create validation rule.

        Args:
            field_name: Name of field
            field_type: Expected data type (int, float, str, datetime)
            min_value: Minimum allowed value (for numeric fields)
            max_value: Maximum allowed value (for numeric fields)
            required: Whether field is required (not null)
            allowed_values: List of allowed values (for categorical fields)
            pattern: Regex pattern to match (for string fields)
            description: Human-readable description
        """
        self.field_name = field_name
        self.field_type = field_type
        self.min_value = min_value
        self.max_value = max_value
        self.required = required
        self.allowed_values = allowed_values
        self.pattern = pattern
        self.description = description

    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate a value against this rule.

        Returns:
            (is_valid, error_message)
        """
        # Check required
        if self.required and (value is None or pd.isna(value)):
            return False, f"{self.field_name} is required"

        # Allow null values if not required
        if pd.isna(value):
            return True, None

        # Check type
        try:
            if self.field_type == float:
                value = float(value)
            elif self.field_type == int:
                value = int(value)
            elif self.field_type == str:
                value = str(value)
        except (ValueError, TypeError):
            return False, f"{self.field_name} must be {self.field_type.__name__}"

        # Check range (numeric)
        if self.field_type in (float, int):
            if self.min_value is not None and value < self.min_value:
                return False, f"{self.field_name} below minimum {self.min_value}: {value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"{self.field_name} above maximum {self.max_value}: {value}"

        # Check allowed values (categorical)
        if self.allowed_values and self.field_type == str:
            if value not in self.allowed_values:
                return False, f"{self.field_name} not in allowed values: {value}"

        # Check pattern (regex)
        if self.pattern and self.field_type == str:
            import re
            if not re.match(self.pattern, value):
                return False, f"{self.field_name} does not match pattern: {value}"

        return True, None


# Field validation rules
FIELD_RULES: Dict[str, ValidationRule] = {
    'loan_id': ValidationRule(
        'loan_id',
        str,
        required=False,
        description="Unique loan identifier"
    ),
    'property_address': ValidationRule(
        'property_address',
        str,
        required=True,
        description="Street address of property"
    ),
    'city': ValidationRule(
        'city',
        str,
        required=False,
        description="City/municipality"
    ),
    'state': ValidationRule(
        'state',
        str,
        required=False,
        pattern=r'^[A-Z]{2}$',
        description="2-letter state code"
    ),
    'zip_code': ValidationRule(
        'zip_code',
        str,
        required=False,
        pattern=r'^\d{5}(?:-\d{4})?$',
        description="5 or 9-digit ZIP code"
    ),
    'units': ValidationRule(
        'units',
        int,
        min_value=50,
        max_value=5000,
        required=False,
        description="Number of residential units"
    ),
    'property_class': ValidationRule(
        'property_class',
        str,
        required=False,
        allowed_values=['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C'],
        description="Property class (A/B/C)"
    ),
    'year_built': ValidationRule(
        'year_built',
        int,
        min_value=1900,
        max_value=2025,
        required=False,
        description="Original construction year"
    ),
    'loan_amount': ValidationRule(
        'loan_amount',
        float,
        min_value=1000000,  # $1M minimum
        max_value=1000000000,  # $1B maximum
        required=True,
        description="Original loan amount"
    ),
    'current_balance': ValidationRule(
        'current_balance',
        float,
        min_value=0,
        required=False,
        description="Current loan balance"
    ),
    'interest_rate': ValidationRule(
        'interest_rate',
        float,
        min_value=0.005,  # 0.5%
        max_value=0.10,  # 10%
        required=False,
        description="Annual interest rate (decimal)"
    ),
    'maturity_date': ValidationRule(
        'maturity_date',
        str,
        required=False,
        description="Loan maturity/payoff date (ISO format)"
    ),
    'amortization_period': ValidationRule(
        'amortization_period',
        int,
        min_value=1,
        max_value=40,
        required=False,
        description="Amortization period in years"
    ),
    'dscr': ValidationRule(
        'dscr',
        float,
        min_value=0.5,
        max_value=3.0,
        required=False,
        description="Debt Service Coverage Ratio"
    ),
    'ltv': ValidationRule(
        'ltv',
        float,
        min_value=0.3,
        max_value=0.95,
        required=False,
        description="Loan-to-Value ratio (0-1)"
    ),
    'occupancy': ValidationRule(
        'occupancy',
        float,
        min_value=0.0,
        max_value=1.0,
        required=False,
        description="Occupancy rate (0-1)"
    ),
    'sponsor_name': ValidationRule(
        'sponsor_name',
        str,
        required=False,
        description="Owner/sponsor name"
    ),
    'data_quality_score': ValidationRule(
        'data_quality_score',
        float,
        min_value=0.0,
        max_value=1.0,
        required=False,
        description="Data quality score (0-1)"
    ),
    'extraction_method': ValidationRule(
        'extraction_method',
        str,
        required=False,
        allowed_values=['pdfplumber', 'pypdf2', 'ocr', 'manual'],
        description="Method used to extract data"
    ),
    'validation_notes': ValidationRule(
        'validation_notes',
        str,
        required=False,
        description="Data quality notes/warnings"
    ),
}


@dataclass
class ColumnMapping:
    """Mapping of column variants to standard name."""

    standard_name: str
    variants: List[str]
    field_type: type
    required: bool = False

    def matches(self, header: str) -> bool:
        """Check if header matches any variant."""
        h = header.strip().lower().replace('_', ' ')
        return h in self.variants


# Expected column names and variants
COLUMN_MAPPINGS: List[ColumnMapping] = [
    ColumnMapping('property_address', [
        'property address', 'property addr', 'address', 'addr',
        'property', 'prop address', 'prop addr', 'street address',
        'location', 'property location', 'address 1'
    ], str, required=True),

    ColumnMapping('city', [
        'city', 'municipality', 'metro area', 'msa', 'town'
    ], str),

    ColumnMapping('state', [
        'state', 'st', 'state code', 'state abbreviation', 'state code'
    ], str),

    ColumnMapping('zip_code', [
        'zip', 'zip code', 'postal code', 'zipcode', 'zip_code'
    ], str),

    ColumnMapping('units', [
        'units', 'no. of units', 'number of units', 'unit count',
        'units count', 'unit#', 'units #', 'number units', 'no units'
    ], int),

    ColumnMapping('property_class', [
        'class', 'property class', 'property type', 'type',
        'prop class', 'prop type', 'asset class', 'class/type'
    ], str),

    ColumnMapping('year_built', [
        'year built', 'year', 'yob', 'year of construction',
        'construction year', 'built year', 'original year', 'year constructed'
    ], int),

    ColumnMapping('loan_amount', [
        'loan amount', 'loan', 'principal', 'original loan amount',
        'orig loan', 'loan size', 'loan value', 'amount', 'orig amount'
    ], float, required=True),

    ColumnMapping('current_balance', [
        'current balance', 'loan balance', 'current loan balance',
        'remaining balance', 'balance', 'loan bal', 'current bal'
    ], float),

    ColumnMapping('interest_rate', [
        'interest rate', 'rate', 'coupon', 'loan rate',
        'annual rate', 'annual interest', 'note rate', 'interest'
    ], float),

    ColumnMapping('maturity_date', [
        'maturity', 'maturity date', 'payoff date', 'due date',
        'loan maturity', 'maturity time', 'loan due date', 'maturity_date'
    ], str),

    ColumnMapping('amortization_period', [
        'amortization', 'amort', 'amortization period',
        'loan term', 'term', 'amort period', 'amort term'
    ], int),

    ColumnMapping('dscr', [
        'dscr', 'debt service coverage', 'debt service coverage ratio',
        'coverage ratio', 'dscr ratio'
    ], float),

    ColumnMapping('ltv', [
        'ltv', 'loan to value', 'loan-to-value', 'ltv ratio', 'loan/value'
    ], float),

    ColumnMapping('occupancy', [
        'occupancy', 'occupancy rate', 'occ', 'occupancy %',
        'occupancy pct', 'leasing', 'occupancy rate', 'occ %'
    ], float),

    ColumnMapping('sponsor_name', [
        'sponsor', 'owner', 'owner name', 'borrower',
        'borrower name', 'owner/sponsor', 'sponsor/owner', 'sponsor name'
    ], str),
]


@dataclass
class OutputSchema:
    """Schema for output DataFrame."""

    columns: List[str]
    dtypes: Dict[str, str]
    required_columns: List[str]

    def validate_dataframe(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate DataFrame against schema.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check required columns
        for col in self.required_columns:
            if col not in df.columns:
                errors.append(f"Missing required column: {col}")

        # Check column types (lenient - just warn on mismatch)
        for col in df.columns:
            if col in self.dtypes:
                # Try to coerce type
                try:
                    expected_dtype = self.dtypes[col]
                    if expected_dtype == 'float':
                        pd.to_numeric(df[col], errors='coerce')
                    elif expected_dtype == 'int':
                        pd.to_numeric(df[col], errors='coerce', downcast='integer')
                    # String type is lenient
                except Exception as e:
                    errors.append(f"Type mismatch in column {col}: {e}")

        return len(errors) == 0, errors


# Standard output schema
OUTPUT_SCHEMA = OutputSchema(
    columns=[
        'loan_id', 'property_address', 'city', 'state', 'zip_code',
        'units', 'property_class', 'year_built', 'loan_amount',
        'current_balance', 'interest_rate', 'maturity_date',
        'amortization_period', 'dscr', 'ltv', 'occupancy',
        'sponsor_name', 'data_quality_score', 'extraction_method',
        'validation_notes'
    ],
    dtypes={
        'loan_id': 'str',
        'property_address': 'str',
        'city': 'str',
        'state': 'str',
        'zip_code': 'str',
        'units': 'int',
        'property_class': 'str',
        'year_built': 'int',
        'loan_amount': 'float',
        'current_balance': 'float',
        'interest_rate': 'float',
        'maturity_date': 'str',  # ISO date format
        'amortization_period': 'int',
        'dscr': 'float',
        'ltv': 'float',
        'occupancy': 'float',
        'sponsor_name': 'str',
        'data_quality_score': 'float',
        'extraction_method': 'str',
        'validation_notes': 'str',
    },
    required_columns=[
        'property_address', 'loan_amount'
    ]
)


# Data quality thresholds
@dataclass
class DataQualityThresholds:
    """Data quality expectations and thresholds."""

    # Minimum data quality score for loan to be "good quality"
    min_quality_score: float = 0.7

    # Minimum proportion of loans that should have DSCR
    min_dscr_coverage: float = 0.8

    # Minimum proportion of loans that should have LTV
    min_ltv_coverage: float = 0.8

    # Maximum proportion of loans with validation warnings
    max_warning_rate: float = 0.2

    # Minimum proportion of key fields populated
    min_completeness: float = 0.75


DEFAULT_QUALITY_THRESHOLDS = DataQualityThresholds()


def get_field_rule(field_name: str) -> Optional[ValidationRule]:
    """Get validation rule for a field."""
    return FIELD_RULES.get(field_name)


def get_column_mapping(header: str) -> Optional[ColumnMapping]:
    """Find column mapping for a header."""
    h = header.strip().lower().replace('_', ' ')
    for mapping in COLUMN_MAPPINGS:
        if h in mapping.variants:
            return mapping
    return None


if __name__ == "__main__":
    # Test schema validation
    print("Output Schema Validation")
    print("=" * 50)

    # Test with sample data
    sample_data = {
        'property_address': ['123 Main St', '456 Oak Ave'],
        'city': ['Boston', 'NYC'],
        'state': ['MA', 'NY'],
        'units': [100, 150],
        'loan_amount': [5000000, 7500000],
        'dscr': [1.25, 1.35],
        'ltv': [0.65, 0.70],
    }

    df = pd.DataFrame(sample_data)
    is_valid, errors = OUTPUT_SCHEMA.validate_dataframe(df)
    print(f"Valid: {is_valid}")
    if errors:
        for error in errors:
            print(f"  - {error}")

    # Test field validation
    print("\nField Validation Rules")
    print("=" * 50)
    for field_name, rule in FIELD_RULES.items():
        print(f"{field_name:30} {rule.field_type.__name__:10} {rule.description}")
