"""BLS API wrapper for employment data enrichment (LCMV-23)."""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


# MSA code mapping: city, state -> BLS MSA code
MSA_CODES = {
    ("Jacksonville", "FL"): "12220",
    ("Fargo", "ND"): "23620",
    ("Austin", "TX"): "12420",
    ("Atlanta", "GA"): "12060",
    ("Miami", "FL"): "33124",
    ("Tampa", "FL"): "45300",
    ("Orlando", "FL"): "36100",
    ("Charlotte", "NC"): "16740",
    ("Raleigh", "NC"): "39580",
    ("Nashville", "TN"): "34980",
    ("Memphis", "TN"): "32820",
    ("Phoenix", "AZ"): "38060",
    ("Denver", "CO"): "19740",
    ("Dallas", "TX"): "19100",
    ("Houston", "TX"): "26420",
    ("San Antonio", "TX"): "41700",
    ("Kansas City", "MO"): "28140",
    ("New Orleans", "LA"): "35380",
    ("Birmingham", "AL"): "12260",
    ("Mobile", "AL"): "33660",
    ("Charleston", "SC"): "16700",
}


class BLSClient:
    """Client for Bureau of Labor Statistics employment data API."""

    def __init__(self, api_key: Optional[str] = None, cache_file: Optional[str] = None):
        """
        Initialize BLS client.

        Args:
            api_key: BLS API key (if None, reads from BLS_API_KEY env var)
            cache_file: Path to cache JSON file (default: ~/.bls_cache.json)
        """
        self.api_key = api_key or os.getenv("BLS_API_KEY", "")
        self.base_url = "https://api.bls.gov/publicAPI/v2/timeseries/"
        self.cache_file = cache_file or str(Path.home() / ".bls_cache.json")
        self.cache_ttl_hours = 24
        self._cache: dict[str, dict[str, Any]] = self._load_cache()
        self.rate_limit_delay = 1.0 / 2.0  # 120 requests/minute = 0.5 second delay

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        """Load cache from disk."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
        return {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.cache_file) or ".", exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(self._cache, f)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _is_cache_valid(self, msa_code: str) -> bool:
        """Check if cached data is still valid."""
        if msa_code not in self._cache:
            return False

        cached = self._cache[msa_code]
        if "timestamp" not in cached:
            return False

        age_hours = (datetime.now().timestamp() - cached["timestamp"]) / 3600
        return age_hours < self.cache_ttl_hours

    def fetch_employment_growth(self, msa_code: str) -> Optional[dict[str, float]]:
        """
        Fetch employment growth for a given MSA code.

        BLS Series ID format: LAUS{MSA_CODE}03
        - L = Labor force
        - A = All
        - U = Unemployment
        - S = State/Metro

        Args:
            msa_code: BLS MSA code (e.g., "12220" for Jacksonville, FL)

        Returns:
            Dict with 'employment_growth_yoy' (float), or None on error
        """
        # Check cache first
        if self._is_cache_valid(msa_code):
            logger.debug(f"Using cached employment data for MSA {msa_code}")
            return self._cache[msa_code].get("data")

        # Rate limiting
        time.sleep(self.rate_limit_delay)

        try:
            series_id = f"LAUS{msa_code}03"

            payload = {
                "seriesid": [series_id],
                "startyear": 2022,
                "endyear": 2024,
                "registrationkey": self.api_key,
            }

            response = requests.post(self.base_url, json=payload, timeout=10)

            if response.status_code == 429:
                logger.warning(f"Rate limited by BLS API for MSA {msa_code}")
                return None

            if response.status_code != 200:
                logger.warning(f"BLS API error {response.status_code} for MSA {msa_code}")
                return None

            data = response.json()

            if data.get("status") != "REQUEST_SUCCEEDED":
                logger.warning(f"BLS request failed for MSA {msa_code}")
                return None

            # Parse the response
            results = data.get("Results", {}).get("series", [])
            if not results:
                logger.warning(f"No data returned for MSA {msa_code}")
                return None

            series = results[0]
            series_data = series.get("data", [])

            if not series_data:
                logger.warning(f"No series data for MSA {msa_code}")
                return None

            # Calculate YoY growth from the most recent two years
            current_year_data = [d for d in series_data if d.get("year") == "2024"]
            prior_year_data = [d for d in series_data if d.get("year") == "2023"]

            if not current_year_data or not prior_year_data:
                logger.warning(f"Insufficient data for YoY calculation for MSA {msa_code}")
                return None

            # Get latest value from each year
            current_value = None
            prior_value = None

            for d in sorted(current_year_data, key=lambda x: x.get("period", ""), reverse=True):
                if "value" in d and d["value"]:
                    try:
                        current_value = int(d["value"])
                        break
                    except (ValueError, TypeError):
                        continue

            for d in sorted(prior_year_data, key=lambda x: x.get("period", ""), reverse=True):
                if "value" in d and d["value"]:
                    try:
                        prior_value = int(d["value"])
                        break
                    except (ValueError, TypeError):
                        continue

            if current_value is None or prior_value is None or prior_value == 0:
                logger.warning(f"Invalid data for YoY calculation for MSA {msa_code}")
                return None

            # Calculate YoY growth rate
            growth_rate = (current_value - prior_value) / prior_value

            result = {"employment_growth_yoy": growth_rate}

            # Cache the result
            self._cache[msa_code] = {
                "data": result,
                "timestamp": datetime.now().timestamp(),
                "series_id": series_id,
            }
            self._save_cache()

            logger.info(f"Fetched employment growth for MSA {msa_code}: {growth_rate:.4f}")
            return result

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching data for MSA {msa_code}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error fetching data for MSA {msa_code}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching employment data for MSA {msa_code}: {e}")
            return None

    def get_msa_by_city_state(self, city: str, state: str) -> Optional[str]:
        """
        Get MSA code for a given city and state.

        Args:
            city: City name (e.g., "Jacksonville")
            state: State abbreviation (e.g., "FL")

        Returns:
            MSA code (e.g., "12220"), or None if not found
        """
        key = (city.title(), state.upper())
        return MSA_CODES.get(key)

    def get_cache_age(self, msa_code: str) -> Optional[int]:
        """
        Get age of cached data in minutes.

        Args:
            msa_code: BLS MSA code

        Returns:
            Age in minutes, or None if not cached
        """
        if msa_code not in self._cache:
            return None

        cached = self._cache[msa_code]
        if "timestamp" not in cached:
            return None

        age_minutes = (datetime.now().timestamp() - cached["timestamp"]) / 60
        return int(age_minutes)

    def refresh_cache(self) -> None:
        """Refresh all cached MSA codes."""
        logger.info("Refreshing employment data cache")
        for msa_code in list(self._cache.keys()):
            self.fetch_employment_growth(msa_code)
