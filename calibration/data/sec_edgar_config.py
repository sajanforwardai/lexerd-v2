"""
SEC EDGAR Configuration for CMBS Deal Discovery.

This module contains CIKs for major CMBS issuers and configuration for
querying SEC EDGAR filings (424B5 prospectuses and 10-D servicer reports).

CMBS issuers tracked:
- JPMorgan Chase (Investment Bank, major CMBS originator)
- Bank of America / Merrill Lynch
- Wells Fargo Securities
- UBS Investment Bank
- Barclays Capital
- Citigroup
- Deutsche Bank
- RBC Capital Markets
- MSCI (now part of Invesco CMBS)
- LendingTree / Apollo Commercial Real Estate Finance

Data sources:
- CIKs from SEC EDGAR database (https://www.sec.gov/cgi-bin/browse-edgar)
- Updated quarterly with new issuers
- Maintained in /workspace/corpus/finance/ as intelligence corpus

Author: Sajan Goswami (Lexerd Capital Management)
"""

# Major CMBS Issuers - CIK mapping
# Format: "Friendly Name": "CIK Number"
# CIKs obtained from SEC EDGAR company search
CMBS_ISSUER_CIKS = {
    "JPMorgan Chase": "0000048104",
    "Bank of America": "0000070858",
    "Wells Fargo": "0000072971",
    "UBS Investment Bank": "0001410145",
    "Barclays Capital": "0000884903",
    "Citigroup": "0000831001",
    "Deutsche Bank": "0001033159",
    "RBC Capital Markets": "0000933567",
    "Invesco": "0000022985",
    "GSAMP Mortgage Loan Trust": "0001413289",
    "Merrill Lynch Mortgage Investors": "0001018724",
    "Securitized Asset Backed Receivables": "0001397145",
    "American Capital Trust": "0001563365",
}

# Multifamily loan keywords for filtering
# Used to identify CMBS deals with multifamily/apartment exposure
MULTIFAMILY_KEYWORDS = [
    "multifamily",
    "apartment",
    "residential",
    "housing",
    "rental",
    "MFH",  # Abbreviation for multifamily housing
    "affordable housing",
    "student housing",
    "senior housing",
    "55+",
]

# Alternative keywords that may appear in prospectuses
# Lower confidence keywords (used with AND logic with primary keywords)
SECONDARY_KEYWORDS = [
    "loan",
    "property",
    "collateral",
    "borrower",
    "sponsor",
]

# SEC EDGAR API Configuration
SEC_API_BASE_URL = "https://data.sec.gov/submissions"
SEC_FILING_BROWSE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"
SEC_CIKS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

# HTTP Headers for SEC requests
# SEC expects User-Agent; they may rate limit aggressive scrapers
SEC_HEADERS = {
    "User-Agent": "Lexerd Capital Management (CMBS Opportunity Analysis) +contact@lexerd.local",
    "Accept": "text/html,application/json",
}

# Rate limiting configuration
# SEC doesn't publish strict rate limits, but we self-throttle
# Typical: 10 requests/second is considered aggressive
# We target: 1 request/second (very conservative)
RATE_LIMIT_REQUESTS_PER_SECOND = 1
RATE_LIMIT_BURST_SIZE = 5  # Allow brief bursts

# Form types for CMBS research
FORM_TYPES = {
    "424B5": "Final Prospectus (SEC requirement for public debt issuance)",
    "424B2": "Prospectus (alternative, less common for CMBS)",
    "S-3": "Registration Statement (used by REIT/fund issuers)",
    "10-D": "Asset-Backed Securities Periodic Report (monthly servicer reports)",
    "10-K": "Annual Report (REIT annual filings)",
    "8-K": "Current Report on Material Events (distress signals, extensions, payoffs)",
}

# Cache configuration
CACHE_DIR_NAME = "sec_prospectuses"
CACHE_TTL_DAYS = 365  # SEC filings never change; cache aggressively
CACHE_INDEX_FILE = "sec_filings_index.json"

# Filing date ranges for queries
# Default: Last 4 years (covers current market + recent history)
DEFAULT_QUERY_START_YEAR = 2022
DEFAULT_QUERY_END_YEAR = 2025

# Search configuration
# How many results per API call (SEC limits to 100)
RESULTS_PER_PAGE = 100
MAX_PAGES_PER_QUERY = 10  # Limit to 1000 results per query to avoid huge result sets

# Timeout configuration (seconds)
API_REQUEST_TIMEOUT = 10
PDF_DOWNLOAD_TIMEOUT = 30

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2  # Exponential backoff: 1s, 2s, 4s

# Logging configuration
LOG_LEVEL = "INFO"

# Directory structure for cached filings
# {CACHE_DIR}/{ISSUER_NAME}/{YEAR}/{FORM_TYPE}_{ACCESSION}.pdf
# Example: sec_prospectuses/jpmorganchase/2024/424B5_0000012345-24-001234.pdf
