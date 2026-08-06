"""County Property Tax Assessor Lookup - Tier 1A"""

import requests
import time
import logging
from typing import Optional, List
from bs4 import BeautifulSoup
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CountyAssessorLookup:
    """Query county property tax assessor databases for addresses"""

    def __init__(self, county: str, state: str, config: dict):
        """Initialize county assessor lookup

        Args:
            county: County name (e.g., 'Harris')
            state: State code (e.g., 'TX')
            config: County-specific configuration
        """
        self.county = county
        self.state = state
        self.config = config
        self.base_url = config.get("base_url", "")
        self.search_method = config.get("search_method", "web_scrape")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.last_request_time = 0
        self.rate_limit = 1.0  # seconds between requests

    def search(self, property_name: str, city: str) -> Optional[dict]:
        """Search for property in county assessor database

        Args:
            property_name: Property name to search
            city: City to search in

        Returns:
            {address, city, state, units, source} or None
        """
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

        try:
            if self.search_method == "web_scrape":
                return self._search_web_scrape(property_name, city)
            elif self.search_method == "arcgis_api":
                return self._search_arcgis_api(property_name, city)
            else:
                logger.warning(f"Unknown search method: {self.search_method}")
                return None
        except Exception as e:
            logger.error(f"Error searching {self.county}, {self.state}: {e}")
            return None
        finally:
            self.last_request_time = time.time()

    def _search_web_scrape(self, property_name: str, city: str) -> Optional[dict]:
        """Scrape county assessor website for property address

        Args:
            property_name: Property name
            city: City

        Returns:
            {address, city, state, source} or None
        """
        # Build search URL - varies by county
        if self.county == "Harris" and self.state == "TX":
            # Harris County: Direct property search
            search_url = self.base_url
            params = {
                "q": property_name,
                "search_type": "property_name"
            }
            url = search_url + "?" + urlencode(params)

        else:
            # Generic search URL construction
            search_url = self.base_url
            if not search_url.endswith("/"):
                search_url += "/"
            url = search_url

        logger.info(f"Searching {self.county}, {self.state} for '{property_name}'")

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, "html.parser")

            # Look for address patterns in the page
            # Pattern varies by county, so be flexible
            address = self._extract_address_from_html(soup, property_name, city)

            if address:
                return {
                    "address": address,
                    "city": city,
                    "state": self.state,
                    "county": self.county,
                    "source": "county_assessor",
                    "confidence": 0.95,
                }

        except requests.RequestException as e:
            logger.warning(f"Request failed for {self.county}: {e}")

        return None

    def _search_arcgis_api(self, property_name: str, city: str) -> Optional[dict]:
        """Search ArcGIS-based property database

        Args:
            property_name: Property name
            city: City

        Returns:
            {address, city, state, source} or None
        """
        # ArcGIS REST API for property search
        # Example: Fulton County, Georgia uses ArcGIS

        try:
            # Query the ArcGIS service
            params = {
                "where": f"UPPER(PROPERTY_NAME) LIKE '%{property_name.upper()}%'",
                "outFields": "PROPERTY_NAME,PROPERTY_ADDRESS,CITY,ZIP_CODE",
                "returnGeometry": False,
                "f": "json"
            }

            url = self.base_url + "/query"
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get("features"):
                feature = data["features"][0]
                props = feature.get("properties", {})

                address = props.get("PROPERTY_ADDRESS") or props.get("ADDRESS")

                if address:
                    return {
                        "address": address,
                        "city": props.get("CITY", city),
                        "state": self.state,
                        "zip": props.get("ZIP_CODE"),
                        "source": "arcgis_api",
                        "confidence": 0.95,
                    }

        except Exception as e:
            logger.warning(f"ArcGIS API search failed: {e}")

        return None

    @staticmethod
    def _extract_address_from_html(soup: BeautifulSoup, property_name: str,
                                   city: str) -> Optional[str]:
        """Extract address from HTML response

        Args:
            soup: BeautifulSoup parsed HTML
            property_name: Property name (for context)
            city: City (for context)

        Returns:
            Address string or None
        """
        import re

        # Look for common address patterns
        # Pattern: number + street name, city, state zip
        pattern = r'(\d+\s+[\w\s]+(St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Lane|Ln|Way|Court|Ct|Circle|Cir).*?)(?=\n|<|$)'

        # Search in all text content
        text = soup.get_text()
        matches = re.findall(pattern, text, re.IGNORECASE)

        if matches:
            # Return first match (usually most relevant)
            return matches[0][0].strip()

        return None


class CountyAssessorManager:
    """Manage multiple county assessor lookups"""

    def __init__(self, config_dict: dict):
        """Initialize with county configurations

        Args:
            config_dict: County configuration dictionary from config.py
        """
        self.counties = {}
        self._initialize_counties(config_dict)

    def _initialize_counties(self, config_dict: dict):
        """Initialize all configured counties

        Args:
            config_dict: County configuration dictionary
        """
        for county_name, county_config in config_dict.items():
            state = county_config.get("state")
            key = f"{county_name},{state}"
            self.counties[key] = CountyAssessorLookup(county_name, state, county_config)

    def search(self, county: str, state: str, property_name: str,
               city: str) -> Optional[dict]:
        """Search specific county for property address

        Args:
            county: County name
            state: State code
            property_name: Property name
            city: City

        Returns:
            {address, city, state, source} or None
        """
        key = f"{county},{state}"

        if key not in self.counties:
            logger.warning(f"County not configured: {county}, {state}")
            return None

        lookup = self.counties[key]
        return lookup.search(property_name, city)
