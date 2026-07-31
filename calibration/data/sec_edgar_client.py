"""
SEC EDGAR API client for CMBS prospectuses and servicer reports.

This module provides the gateway to SEC EDGAR data for the Securitized SEC Loan
Maturity Pipeline (LCMV-58). We query EDGAR for:
1. Form 424B5 (initial prospectuses - loan origination data)
2. Form 10-D (servicer reports - monthly performance updates)

SEC publishes these filings freely; we scrape them to identify maturity signals
and refinancing opportunities that Freddie Mac/Fannie Mae B3 don't show (private-label CMBS).

This is a critical competitive advantage: SEC data covers 40-50% of the multifamily
securitization market that GSE pipelines (B3) miss.

Design philosophy:
- Zero authentication required (SEC data.gov API is public)
- Respectful rate limiting (SEC doesn't have strict limits, but we're good citizens)
- Long cache TTL (365 days, filings don't change)
- Fault-tolerant parsing (SEC filings vary in format; graceful degradation)

Author: Sajan Goswami (Lexerd Capital Management)
"""

import requests
import logging
import re
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import os
from pathlib import Path
import json
from html.parser import HTMLParser

from . import sec_edgar_config as config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# SEC EDGAR API endpoints
SEC_EDGAR_BASE = config.SEC_API_BASE_URL
SEC_FILING_BROWSE_URL = config.SEC_FILING_BROWSE_URL
SEC_ARCHIVE_BASE = config.SEC_ARCHIVE_BASE

# Cache configuration
CACHE_BASE = Path(__file__).parent.parent / "opportunities" / "cache"
CACHE_DIR = CACHE_BASE / config.CACHE_DIR_NAME
CACHE_TTL_DAYS = config.CACHE_TTL_DAYS
CACHE_INDEX_FILE = CACHE_DIR / config.CACHE_INDEX_FILE


class SecEdgarTableParser(HTMLParser):
    """HTML parser for SEC EDGAR filing tables."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.cells = []
        self.rows = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.cells = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self.in_table = False
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self.cells:
                self.rows.append(self.cells)
        elif tag in ("td", "th") and self.in_cell:
            self.in_cell = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cells.append(data.strip())


class SecEdgarClient:
    """
    Client for querying SEC EDGAR filings related to CMBS deals.

    Usage:
        client = SecEdgarClient()
        deals = client.query_cmbs_deals(years=[2024, 2023])
        for deal in deals:
            prospectus = client.download_prospectus(deal['filing_url'])
    """

    def __init__(
        self,
        cache_enabled: bool = True,
        rate_limit_seconds: float = None,
        cache_dir: Optional[Path] = None
    ) -> None:
        """
        Initialize SEC EDGAR client.

        Args:
            cache_enabled: Whether to use local file caching (default: True)
            rate_limit_seconds: Seconds between API calls (respect SEC servers).
                               If None, uses config default.
            cache_dir: Custom cache directory. If None, uses default.
        """
        self.cache_enabled = cache_enabled
        self.rate_limit_seconds = rate_limit_seconds or (1.0 / config.RATE_LIMIT_REQUESTS_PER_SECOND)
        self.cache_dir = cache_dir or CACHE_DIR
        self.last_request_time: float = 0
        self._cache_index: Dict = {}

        if cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_cache_index()

        logger.info(
            "SecEdgarClient initialized (cache=%s, rate_limit=%.2f req/sec)",
            cache_enabled,
            1.0 / self.rate_limit_seconds if self.rate_limit_seconds > 0 else float('inf')
        )

    def query_cmbs_deals(
        self,
        keywords: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        form_types: Optional[List[str]] = None,
        ciks: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Query SEC EDGAR for CMBS deals with multifamily loans.

        This is the primary gateway to SEC data pipeline. We query EDGAR for:
        1. Form 424B5 (initial prospectuses - loan origination data, filed when deal closes)
        2. Form 10-D (servicer reports - monthly performance updates)
        3. Form 8-K (material events - distress signals, extensions, payoffs)

        SEC publishes filings when deals close (424B5) and servicers file monthly (10-D),
        giving us early visibility into refinancing needs before they hit the market.

        Data access is 100% free and public via data.sec.gov API.
        No rate limits enforced, but we self-throttle to ~1 request/second (good citizenship).

        Args:
            keywords: Search terms (e.g., ["multifamily", "apartment", "residential"])
                      If None, defaults to config.MULTIFAMILY_KEYWORDS
            years: Year range (e.g., [2024, 2023] for recent deals, or [2020, 2021, 2022]
                   for backfill). If None, defaults to last 4 years.
            form_types: Form types to query (default: ["424B5", "10-D"]).
                       Can add "8-K" for distress events.
            ciks: Specific CIKs to query. If None, queries major issuers from config.

        Returns:
            List of dictionaries, each containing:
            - deal_name: Official deal name (e.g., "One Liberty Properties")
            - cik: CIK number (issuer identifier)
            - accession: Accession number (document ID)
            - filing_url: URL to download filing
            - form_type: Form type (424B5, 10-D, or 8-K)
            - filing_date: Date filed (YYYY-MM-DD)
            - cache_path: Local cache path if downloaded

        Raises:
            requests.RequestException: Network error querying SEC API
        """
        keywords = keywords or config.MULTIFAMILY_KEYWORDS
        years = years or list(range(config.DEFAULT_QUERY_START_YEAR, config.DEFAULT_QUERY_END_YEAR + 1))
        form_types = form_types or ["424B5", "10-D"]
        ciks = ciks or list(config.CMBS_ISSUER_CIKS.values())

        deals = []

        # Query each CIK separately for best results
        for cik in ciks:
            for form_type in form_types:
                deals.extend(
                    self._query_by_cik_and_form(
                        cik=cik,
                        form_type=form_type,
                        years=years,
                        keywords=keywords
                    )
                )

        logger.info("Found %d CMBS deals matching query", len(deals))
        return deals

    def _query_by_cik_and_form(
        self,
        cik: str,
        form_type: str,
        years: List[int],
        keywords: List[str]
    ) -> List[Dict]:
        """
        Internal: Query SEC EDGAR for specific CIK + form type.

        Why separate method?
        - SEC API requires multiple queries to cover all CIKs
        - Each query may have pagination (handle 1000+ results)
        - Centralized error handling + caching strategy
        - Keywords used for post-filtering only

        Args:
            cik: SEC CIK number (e.g., "0001493410")
            form_type: SEC form type (e.g., "424B5", "10-D", "8-K")
            years: List of years to query
            keywords: Keywords for filtering results

        Returns:
            List of filing dictionaries
        """
        cache_key = f"{cik}_{form_type}_{min(years)}_{max(years)}"
        cache_path = self.cache_dir / f"{cache_key}.json"

        # Check cache before querying
        if self.cache_enabled and cache_path.exists():
            if self._cache_valid(cache_path):
                logger.debug("Cache hit: %s", cache_key)
                try:
                    with open(cache_path) as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning("Cache file corrupted: %s", e)

        # Query SEC EDGAR with retry logic
        deals = self._query_with_retry(cik, form_type, years)

        # Filter by keywords
        filtered_deals = self._filter_by_keywords(deals, keywords)

        # Cache results
        if self.cache_enabled:
            try:
                with open(cache_path, 'w') as f:
                    json.dump(filtered_deals, f, indent=2, default=str)
            except IOError as e:
                logger.warning("Failed to write cache: %s", e)

        logger.info(
            "Queried CIK=%s, form=%s, years=%s: %d results (%d after filter)",
            cik, form_type, years, len(deals), len(filtered_deals)
        )
        return filtered_deals

    def _query_with_retry(
        self,
        cik: str,
        form_type: str,
        years: List[int],
        max_retries: int = config.MAX_RETRIES
    ) -> List[Dict]:
        """
        Query SEC EDGAR with exponential backoff retry logic.

        Args:
            cik: SEC CIK number
            form_type: SEC form type
            years: Years to query
            max_retries: Maximum number of retry attempts

        Returns:
            List of filing dictionaries
        """
        for attempt in range(max_retries):
            try:
                return self._query_sec_edgar(cik, form_type, years)
            except requests.RequestException as e:
                wait_time = config.RETRY_BACKOFF_FACTOR ** attempt
                if attempt < max_retries - 1:
                    logger.warning(
                        "Query failed (attempt %d/%d), retrying in %.1f seconds: %s",
                        attempt + 1, max_retries, wait_time, e
                    )
                    time.sleep(wait_time)
                else:
                    logger.error("Query failed after %d attempts: %s", max_retries, e)
                    return []

    def _query_sec_edgar(
        self,
        cik: str,
        form_type: str,
        years: List[int]
    ) -> List[Dict]:
        """
        Query SEC EDGAR API directly.

        Args:
            cik: SEC CIK number
            form_type: SEC form type
            years: Years to query

        Returns:
            List of filing dictionaries
        """
        url = SEC_FILING_BROWSE_URL
        deals = []

        # Query for each year (to handle date filtering)
        for year in years:
            params = {
                "action": "getcompany",
                "CIK": cik,
                "type": form_type,
                "dateb": f"{year}-12-31",
                "datea": f"{year}-01-01",
                "owner": "exclude",
                "count": config.RESULTS_PER_PAGE,
            }

            self._respect_rate_limit()
            response = requests.get(
                url,
                params=params,
                headers=config.SEC_HEADERS,
                timeout=config.API_REQUEST_TIMEOUT
            )
            response.raise_for_status()

            # Parse HTML response
            parsed_deals = self._parse_edgar_table(response.text, form_type)
            deals.extend(parsed_deals)

        return deals

    def _filter_by_keywords(self, deals: List[Dict], keywords: List[str]) -> List[Dict]:
        """
        Filter deals by keywords (case-insensitive).

        Args:
            deals: List of filing dictionaries
            keywords: Keywords to match in deal_name

        Returns:
            Filtered list of filings
        """
        if not keywords:
            return deals

        filtered = []
        keywords_lower = [kw.lower() for kw in keywords]

        for deal in deals:
            deal_name = deal.get('deal_name', '').lower()
            if any(kw in deal_name for kw in keywords_lower):
                filtered.append(deal)

        return filtered

    def _parse_edgar_table(self, html: str, form_type: str) -> List[Dict]:
        """
        Parse SEC EDGAR HTML response table.

        SEC filings are published as HTML tables. We extract:
        - CIK (Central Index Key - issuer identifier)
        - Company name (deal name)
        - Filing URL
        - Filing date
        - Accession number

        SEC HTML structure is stable and well-formatted. We use regex + simple parsing
        to avoid heavyweight HTML parsers.

        Args:
            html: HTML response from SEC EDGAR
            form_type: Form type (for validation)

        Returns:
            List of parsed filing dictionaries
        """
        deals = []

        # Extract CIK from page (usually in form field)
        cik_match = re.search(r'<input[^>]*name="CIK"[^>]*value="(\d+)"', html)
        cik = cik_match.group(1) if cik_match else None

        # Find all rows in the filing table
        # SEC format: <td> cells with Accession #, Filing Date, Company, Form Type, etc.
        row_pattern = r'<tr[^>]*>(.+?)</tr>'
        rows = re.findall(row_pattern, html, re.DOTALL)

        for row in rows:
            # Extract cells
            cells = re.findall(r'<td[^>]*>(.+?)</td>', row, re.DOTALL)
            if len(cells) < 4:
                continue

            # SEC table format: Accession # | Filing Date | Company | Form Type | ...
            # Extract data from cells
            accession = self._clean_html(cells[0]).strip()
            filing_date = self._clean_html(cells[1]).strip()
            company = self._clean_html(cells[2]).strip()
            form = self._clean_html(cells[3]).strip() if len(cells) > 3 else form_type

            # Validate
            if not accession or not filing_date or not company:
                continue

            # Build filing URL
            accession_clean = accession.replace('-', '')
            filing_url = f"{SEC_ARCHIVE_BASE}/{cik}/{accession_clean}/{accession}.txt"

            deal = {
                'cik': cik,
                'accession': accession,
                'deal_name': company,
                'form_type': form,
                'filing_date': filing_date,
                'filing_url': filing_url,
            }

            deals.append(deal)

        return deals

    def _clean_html(self, html: str) -> str:
        """
        Remove HTML tags from text.

        Args:
            html: HTML string

        Returns:
            Cleaned text
        """
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        # Remove tags
        html = re.sub(r'<[^>]+>', '', html)
        # Decode entities
        html = html.replace('&nbsp;', ' ')
        html = html.replace('&lt;', '<')
        html = html.replace('&gt;', '>')
        html = html.replace('&amp;', '&')
        # Clean whitespace
        html = ' '.join(html.split())
        return html

    def download_prospectus(
        self,
        filing_url: str,
        deal_name: Optional[str] = None,
        cache: bool = True
    ) -> Tuple[Optional[bytes], Optional[Path]]:
        """
        Download 424B5 prospectus PDF from SEC.

        Why prospectuses matter:
        - 424B5 is filed when a deal closes (origination snapshot)
        - Contains loan-level tape with 30+ fields per loan
        - Clean, structured data (unlike servicer reports, which vary)
        - We extract: property address, DSCR, LTV, maturity, property type

        Args:
            filing_url: URL to SEC filing
            deal_name: Deal name for cache file naming
            cache: Whether to cache the downloaded file

        Returns:
            Tuple of (PDF bytes, cache path)
            Returns (None, None) on error

        Raises:
            requests.RequestException: Network error downloading filing
        """
        cache_path = None

        if cache and self.cache_enabled:
            cache_path = self._get_cache_path(filing_url, deal_name)
            if cache_path.exists() and self._cache_valid(cache_path):
                logger.debug("Cache hit for prospectus: %s", cache_path)
                try:
                    return cache_path.read_bytes(), cache_path
                except IOError as e:
                    logger.warning("Failed to read cached file: %s", e)

        try:
            self._respect_rate_limit()
            response = requests.get(
                filing_url,
                headers=config.SEC_HEADERS,
                timeout=config.PDF_DOWNLOAD_TIMEOUT
            )
            response.raise_for_status()

            content = response.content
            logger.debug("Downloaded prospectus from %s", filing_url)

            # Cache the file
            if cache and self.cache_enabled and cache_path:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(content)
                    self._update_cache_index(filing_url, cache_path, deal_name)
                    logger.debug("Cached prospectus to %s", cache_path)
                except IOError as e:
                    logger.warning("Failed to cache prospectus: %s", e)

            return content, cache_path

        except requests.RequestException as e:
            logger.error("Failed to download prospectus: %s", e)
            return None, None

    def download_servicer_report(
        self,
        filing_url: str,
        deal_name: Optional[str] = None,
        cache: bool = True
    ) -> Tuple[Optional[bytes], Optional[Path]]:
        """
        Download 10-D servicer report from SEC.

        Why servicer reports matter:
        - Filed monthly/quarterly by CMBS servicers
        - Track current loan performance (updated regularly)
        - Show delinquencies, occupancy, loan modifications
        - We extract: payment status, occupancy, extensions/payoffs

        Args:
            filing_url: URL to SEC filing
            deal_name: Deal name for cache file naming
            cache: Whether to cache the downloaded file

        Returns:
            Tuple of (report bytes, cache path)
            Returns (None, None) on error

        Raises:
            requests.RequestException: Network error downloading filing
        """
        cache_path = None

        if cache and self.cache_enabled:
            cache_path = self._get_cache_path(filing_url, deal_name, "10d")
            if cache_path.exists() and self._cache_valid(cache_path):
                logger.debug("Cache hit for servicer report: %s", cache_path)
                try:
                    return cache_path.read_bytes(), cache_path
                except IOError as e:
                    logger.warning("Failed to read cached file: %s", e)

        try:
            self._respect_rate_limit()
            response = requests.get(
                filing_url,
                headers=config.SEC_HEADERS,
                timeout=config.PDF_DOWNLOAD_TIMEOUT
            )
            response.raise_for_status()

            content = response.content
            logger.debug("Downloaded servicer report from %s", filing_url)

            # Cache the file
            if cache and self.cache_enabled and cache_path:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(content)
                    self._update_cache_index(filing_url, cache_path, deal_name)
                    logger.debug("Cached servicer report to %s", cache_path)
                except IOError as e:
                    logger.warning("Failed to cache servicer report: %s", e)

            return content, cache_path

        except requests.RequestException as e:
            logger.error("Failed to download servicer report: %s", e)
            return None, None

    def search_by_cik(self, cik: str) -> List[Dict]:
        """
        Search SEC filings by CIK number (issuer identifier).

        CIK = Central Index Key assigned by SEC to all issuers.
        Used when you know the deal issuer and want all their filings.

        Args:
            cik: CIK number (e.g., "0001493410")

        Returns:
            List of all filings by that issuer
        """
        try:
            self._respect_rate_limit()
            url = f"{SEC_EDGAR_BASE}/CIK{cik}.json"
            response = requests.get(
                url,
                headers=config.SEC_HEADERS,
                timeout=config.API_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            # Extract filing information
            filings = []
            for filing in data.get("filings", {}).get("recent", {}).get("filings", []):
                filings.append({
                    "accession": filing.get("accessionNumber"),
                    "form_type": filing.get("form"),
                    "filing_date": filing.get("filingDate"),
                    "url": f"https://www.sec.gov/Archives/{filing.get('accessionNumber')}/",
                })

            logger.info("Found %d filings for CIK %s", len(filings), cik)
            return filings

        except requests.RequestException as e:
            logger.error("Failed to search by CIK: %s", e)
            return []

    def get_cache_status(self) -> Dict[str, any]:
        """
        Get cache status and statistics.

        Returns:
            Dictionary with cache info:
            - total_files: Number of cached files
            - total_size_mb: Total cache size in MB
            - oldest_file: Age of oldest cached file
            - newest_file: Age of newest cached file
        """
        if not self.cache_dir.exists():
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'oldest_file': None,
                'newest_file': None,
                'cache_dir': str(self.cache_dir),
            }

        files = list(self.cache_dir.rglob('*'))
        pdf_files = [f for f in files if f.is_file() and f.suffix == '.pdf']

        if not pdf_files:
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'oldest_file': None,
                'newest_file': None,
                'cache_dir': str(self.cache_dir),
            }

        total_size = sum(f.stat().st_size for f in pdf_files)
        mtimes = [(f, f.stat().st_mtime) for f in pdf_files]
        mtimes.sort(key=lambda x: x[1])

        oldest = datetime.fromtimestamp(mtimes[0][1]) if mtimes else None
        newest = datetime.fromtimestamp(mtimes[-1][1]) if mtimes else None

        return {
            'total_files': len(pdf_files),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'oldest_file': oldest.isoformat() if oldest else None,
            'newest_file': newest.isoformat() if newest else None,
            'cache_dir': str(self.cache_dir),
        }

    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear cache files.

        Args:
            older_than_days: Only delete files older than N days.
                            If None, clears all cached files.

        Returns:
            Number of files deleted
        """
        if not self.cache_dir.exists():
            return 0

        deleted_count = 0
        cutoff_time = datetime.now() - timedelta(days=older_than_days or 0)

        for file_path in self.cache_dir.rglob('*.pdf'):
            if older_than_days is None or datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_time:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except OSError as e:
                    logger.warning("Failed to delete cache file %s: %s", file_path, e)

        # Clear cache index if clearing all
        if older_than_days is None:
            self._cache_index = {}
            if CACHE_INDEX_FILE.exists():
                try:
                    CACHE_INDEX_FILE.unlink()
                except OSError as e:
                    logger.warning("Failed to delete cache index: %s", e)

        logger.info("Cleared %d cache files", deleted_count)
        return deleted_count

    def _respect_rate_limit(self) -> None:
        """
        Enforce self-imposed rate limit between SEC API calls.

        Why self-throttle?
        - SEC doesn't have strict API limits, but they're public infrastructure
        - We're good citizens: ~1 request/second = respectful, not aggressive
        - Prevents blocking if/when SEC implements rate limiting
        """
        elapsed = datetime.now().timestamp() - self.last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self.last_request_time = datetime.now().timestamp()

    def _cache_valid(self, cache_path: Path) -> bool:
        """
        Check if cache file is still valid (within TTL).

        SEC filings don't change once published. We cache with 365-day TTL
        because the data is immutable (SEC archives are permanent).

        Args:
            cache_path: Path to cache file

        Returns:
            True if cache is within TTL, False otherwise
        """
        if not cache_path.exists():
            return False

        try:
            file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            return file_age < timedelta(days=CACHE_TTL_DAYS)
        except OSError:
            return False

    def _get_cache_path(
        self,
        filing_url: str,
        deal_name: Optional[str] = None,
        suffix: str = "424b5"
    ) -> Path:
        """
        Generate cache path for a filing.

        Format: cache_dir/{issuer_normalized}/{year}/{form_type}_{accession}.pdf

        Args:
            filing_url: SEC filing URL
            deal_name: Deal name for filename
            suffix: File suffix (form type abbreviation)

        Returns:
            Path object for cache file
        """
        # Extract accession number from URL
        # Format: .../data/CIK/ACCESSION/
        match = re.search(r'/(\d{10}-\d{2}-\d{6})/', filing_url)
        accession = match.group(1).replace('-', '') if match else hashlib.md5(filing_url.encode()).hexdigest()[:12]

        # Extract CIK
        cik_match = re.search(r'/data/(\d+)/', filing_url)
        cik = cik_match.group(1) if cik_match else "unknown"

        # Create normalized filename
        if deal_name:
            # Sanitize deal name for filename
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', deal_name.replace(' ', '_'))[:50]
            filename = f"{accession}_{safe_name}_{suffix}.pdf"
        else:
            filename = f"{accession}_{suffix}.pdf"

        return self.cache_dir / cik / filename

    def _load_cache_index(self) -> None:
        """Load cache index from disk."""
        if CACHE_INDEX_FILE.exists():
            try:
                with open(CACHE_INDEX_FILE) as f:
                    self._cache_index = json.load(f)
                logger.debug("Loaded cache index with %d entries", len(self._cache_index))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load cache index: %s", e)
                self._cache_index = {}

    def _update_cache_index(
        self,
        filing_url: str,
        cache_path: Path,
        deal_name: Optional[str] = None
    ) -> None:
        """
        Update cache index with downloaded file metadata.

        Args:
            filing_url: SEC filing URL
            cache_path: Local cache path
            deal_name: Deal name
        """
        try:
            CACHE_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._cache_index[filing_url] = {
                'cache_path': str(cache_path),
                'deal_name': deal_name,
                'downloaded_at': datetime.now().isoformat(),
            }
            with open(CACHE_INDEX_FILE, 'w') as f:
                json.dump(self._cache_index, f, indent=2)
        except IOError as e:
            logger.warning("Failed to update cache index: %s", e)


# Convenience functions for direct use
def query_cmbs_deals(**kwargs) -> List[Dict]:
    """
    Convenience function: query CMBS deals without instantiating client.

    Usage:
        deals = query_cmbs_deals(years=[2024, 2023])
    """
    client = SecEdgarClient()
    return client.query_cmbs_deals(**kwargs)


def download_prospectus(filing_url: str, cache: bool = True) -> Tuple[Optional[bytes], Optional[Path]]:
    """
    Convenience function: download a prospectus without instantiating client.

    Usage:
        content, path = download_prospectus("https://www.sec.gov/Archives/...")
    """
    client = SecEdgarClient(cache_enabled=cache)
    return client.download_prospectus(filing_url, cache=cache)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    client = SecEdgarClient()

    # Query recent CMBS deals (2024-2025 multifamily)
    print("Querying SEC EDGAR for multifamily CMBS deals...")
    deals = client.query_cmbs_deals(
        years=[2024, 2025],
        keywords=["multifamily", "apartment"],
        form_types=["424B5"]
    )
    print(f"Found {len(deals)} CMBS deals\n")

    # Show first 3 deals
    for i, deal in enumerate(deals[:3], 1):
        print(f"Deal {i}: {deal['deal_name']}")
        print(f"  CIK: {deal['cik']}")
        print(f"  Filing Date: {deal['filing_date']}")
        print(f"  Form: {deal['form_type']}")
        print(f"  URL: {deal['filing_url']}\n")

    # Cache status
    cache_status = client.get_cache_status()
    print(f"Cache Status: {cache_status['total_files']} files, {cache_status['total_size_mb']}MB")
