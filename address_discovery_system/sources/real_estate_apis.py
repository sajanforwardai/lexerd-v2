"""Real Estate API Integration - Tier 1B (Zillow, ApartmentsList, Google Maps)"""

import requests
import time
import logging
from typing import Optional, List
from bs4 import BeautifulSoup
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealEstateAPILookup:
    """Search real estate aggregator APIs for property addresses"""

    def __init__(self, api_name: str, config: dict):
        """Initialize API lookup

        Args:
            api_name: Name of API (zillow, apartments_list, google_maps)
            config: API configuration with keys, URLs, etc.
        """
        self.api_name = api_name
        self.config = config
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.last_request_time = 0
        self.rate_limit = 1.0 / config.get("rate_limit", 5)  # Convert requests/sec to seconds/request

    def search(self, property_name: str, city: str, state: str,
               units: Optional[int] = None) -> Optional[dict]:
        """Search API for property address

        Args:
            property_name: Property name
            city: City
            state: State code
            units: Expected unit count (for validation)

        Returns:
            {address, city, state, units, phone, source, confidence} or None
        """
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

        try:
            if self.api_name == "zillow":
                return self._search_zillow(property_name, city, state, units)
            elif self.api_name == "apartments_list":
                return self._search_apartments_list(property_name, city, state, units)
            elif self.api_name == "google_maps":
                return self._search_google_maps(property_name, city, state, units)
            else:
                logger.warning(f"Unknown API: {self.api_name}")
                return None
        except Exception as e:
            logger.error(f"Error searching {self.api_name}: {e}")
            return None
        finally:
            self.last_request_time = time.time()

    def _search_zillow(self, property_name: str, city: str, state: str,
                       units: Optional[int] = None) -> Optional[dict]:
        """Search Zillow for multifamily property

        Args:
            property_name: Property name
            city: City
            state: State code
            units: Expected unit count

        Returns:
            Property data or None
        """
        logger.info(f"Searching Zillow for '{property_name}' in {city}, {state}")

        # Note: Zillow requires authentication for most APIs
        # This implementation shows the structure; actual API keys needed

        if not self.api_key:
            logger.warning("Zillow API key not configured")
            # Fall back to web scraping
            return self._scrape_zillow_web(property_name, city, state)

        try:
            # Use Zillow API if available
            params = {
                "q": f"{property_name} {city} {state}",
                "status": "ForRent",
                "home_type": "apartments",
            }

            # Zillow API endpoint (structure varies by API version)
            url = f"{self.base_url}search"
            headers = {"Authorization": f"Bearer {self.api_key}"}

            response = self.session.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get("results"):
                result = data["results"][0]
                return {
                    "address": result.get("address"),
                    "city": result.get("city"),
                    "state": result.get("state"),
                    "zip": result.get("zipcode"),
                    "units": result.get("bedrooms"),
                    "phone": result.get("phone"),
                    "url": result.get("url"),
                    "source": "zillow",
                    "confidence": 0.85,
                }

        except Exception as e:
            logger.warning(f"Zillow API search failed: {e}")

        return None

    def _scrape_zillow_web(self, property_name: str, city: str, state: str) -> Optional[dict]:
        """Scrape Zillow web results (fallback when API unavailable)

        Args:
            property_name: Property name
            city: City
            state: State code

        Returns:
            Property data or None
        """
        try:
            logger.info(f"Scraping Zillow web for '{property_name}'")

            # Build URL with proper query string encoding
            search_term = f"{property_name} {city} {state}"
            url = f"https://www.zillow.com/search/?q={search_term.replace(' ', '+')}&home_type=apartments"

            # Rate limit web scraping heavily
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            # Parse HTML for listings
            soup = BeautifulSoup(response.content, "html.parser")

            # Look for property listings in page
            listings = soup.find_all("article", class_="property-card")

            for listing in listings:
                address_elem = listing.find("address")
                if address_elem:
                    address = address_elem.get_text().strip()
                    if city.lower() in address.lower():
                        return {
                            "address": address,
                            "city": city,
                            "state": state,
                            "source": "zillow_web",
                            "confidence": 0.80,
                        }

        except Exception as e:
            logger.warning(f"Zillow web scrape failed: {e}")

        return None

    def _search_apartments_list(self, property_name: str, city: str, state: str,
                                units: Optional[int] = None) -> Optional[dict]:
        """Search ApartmentsList for property

        Args:
            property_name: Property name
            city: City
            state: State code
            units: Expected unit count

        Returns:
            Property data or None
        """
        logger.info(f"Searching ApartmentsList for '{property_name}' in {city}, {state}")

        try:
            # ApartmentsList search
            url = "https://apartmentslist.com/search"
            params = {
                "q": property_name,
                "location": f"{city}, {state}",
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Look for property listing
            for listing in soup.find_all("div", class_="property-card"):
                name = listing.find("h2")
                address_elem = listing.find("p", class_="address")

                if name and address_elem:
                    if property_name.lower() in name.get_text().lower():
                        address = address_elem.get_text().strip()

                        return {
                            "address": address,
                            "city": city,
                            "state": state,
                            "source": "apartments_list",
                            "confidence": 0.80,
                        }

        except Exception as e:
            logger.warning(f"ApartmentsList search failed: {e}")

        return None

    def _search_google_maps(self, property_name: str, city: str, state: str,
                            units: Optional[int] = None) -> Optional[dict]:
        """Search Google Maps for property

        Args:
            property_name: Property name
            city: City
            state: State code
            units: Expected unit count

        Returns:
            Property data or None
        """
        logger.info(f"Searching Google Maps for '{property_name}'")

        if not self.api_key:
            logger.warning("Google Maps API key not configured")
            return None

        try:
            from calibration.address_verification import GoogleMapsAddressVerifier

            verifier = GoogleMapsAddressVerifier(api_key=self.api_key)
            result = verifier.verify(property_name, city, state)

            if result:
                return {
                    "address": result.address,
                    "city": city,
                    "state": state,
                    "phone": result.phone,
                    "lat": result.lat,
                    "lon": result.lon,
                    "place_id": result.place_id,
                    "source": "google_maps",
                    "confidence": 0.85,
                }

        except Exception as e:
            logger.warning(f"Google Maps search failed: {e}")

        return None


class RealEstateAPIManager:
    """Manage multiple real estate API lookups"""

    def __init__(self, config_dict: dict):
        """Initialize with API configurations

        Args:
            config_dict: API configuration dictionary from config.py
        """
        self.apis = {}
        self._initialize_apis(config_dict)

    def _initialize_apis(self, config_dict: dict):
        """Initialize all configured APIs

        Args:
            config_dict: API configuration dictionary
        """
        for api_name, api_config in config_dict.items():
            if api_config.get("enabled", False):
                self.apis[api_name] = RealEstateAPILookup(api_name, api_config)
                logger.info(f"Initialized {api_name} API")

    def search(self, property_name: str, city: str, state: str,
               units: Optional[int] = None) -> List[dict]:
        """Search all configured APIs for property address

        Args:
            property_name: Property name
            city: City
            state: State code
            units: Expected unit count

        Returns:
            List of results: [{address, city, state, source, confidence}, ...]
        """
        results = []

        for api_name, api_client in self.apis.items():
            result = api_client.search(property_name, city, state, units)
            if result:
                results.append(result)
                logger.info(f"Found result from {api_name}: {result.get('address')}")

        return results
