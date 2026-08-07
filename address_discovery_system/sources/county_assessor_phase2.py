"""Phase 2: Enhanced County Assessor API Integration"""

import requests
import time
import logging
from typing import Optional, List, Dict
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CountyAssessorPhase2:
    """Query county property tax assessor APIs for Phase 2 addresses"""

    def __init__(self):
        """Initialize Phase 2 county assessor lookups"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.rate_limit = 2.0  # seconds between requests
        self.last_request_time = 0

    def search(self, county: str, state: str, property_name: str, city: str) -> Optional[dict]:
        """Search county assessor database for property address

        Args:
            county: County name
            state: State code
            property_name: Property name
            city: City

        Returns:
            {address, city, state, confidence, source} or None
        """
        # Throttle requests
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

        try:
            # Route to appropriate county API
            if state == "TX":
                return self._search_texas_county(county, property_name, city)
            elif state == "GA":
                return self._search_georgia_county(county, property_name, city)
            elif state == "FL":
                return self._search_florida_county(county, property_name, city)
            elif state == "NC":
                return self._search_nc_county(county, property_name, city)
            elif state == "KS":
                return self._search_kansas_county(county, property_name, city)
            else:
                return None

        except Exception as e:
            logger.warning(f"County API search failed for {county}, {state}: {e}")
            return None
        finally:
            self.last_request_time = time.time()

    def _search_texas_county(self, county: str, property_name: str, city: str) -> Optional[dict]:
        """Search Texas county assessor API (TCAD, HCAD, etc.)"""

        county_apis = {
            "Harris": "https://hcad.org/api/v1/search",
            "Dallas": "https://www.dallascad.org/api/search",
            "Tarrant": "https://www.tcad.org/api/property",
            "Bexar": "https://www.bcad.org/api/search",
            "Fort Bend": "https://www.fbcad.org/api/search",
            "Montgomery": "https://www.mcad.org/api/search",
        }

        if county not in county_apis:
            return None

        try:
            url = county_apis[county]
            params = {
                "q": property_name,
                "city": city,
                "limit": 5
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("results"):
                result = data["results"][0]
                return {
                    "address": result.get("address", ""),
                    "city": result.get("city", city),
                    "state": "TX",
                    "confidence": 0.92,
                    "source": f"county_assessor_{county}",
                }

        except Exception as e:
            logger.debug(f"Texas county API error: {e}")

        return None

    def _search_georgia_county(self, county: str, property_name: str, city: str) -> Optional[dict]:
        """Search Georgia county assessor API"""

        county_apis = {
            "Fulton": "https://web.arcgisonline.com/arcgis/rest/services/fultoncounty/parcels",
            "Cobb": "https://www.cobbcounty.org/api/property",
            "DeKalb": "https://www.dekalbcountyga.gov/api/search",
        }

        if county not in county_apis:
            return None

        try:
            url = county_apis[county]
            params = {
                "where": f"NAME LIKE '%{property_name}%'",
                "outFields": "ADDRESS,CITY",
                "f": "json"
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("features"):
                attrs = data["features"][0].get("attributes", {})
                return {
                    "address": attrs.get("ADDRESS", ""),
                    "city": attrs.get("CITY", city),
                    "state": "GA",
                    "confidence": 0.90,
                    "source": f"county_assessor_{county}",
                }

        except Exception as e:
            logger.debug(f"Georgia county API error: {e}")

        return None

    def _search_florida_county(self, county: str, property_name: str, city: str) -> Optional[dict]:
        """Search Florida county property appraiser API"""

        county_apis = {
            "Okaloosa": "https://www.okaloosapa.gov/api/search",
            "Miami-Dade": "https://www.miamidade.gov/api/property",
            "Broward": "https://www.browardproperty.com/api/search",
        }

        if county not in county_apis:
            return None

        try:
            url = county_apis[county]
            params = {
                "q": property_name,
                "city": city
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("results"):
                result = data["results"][0]
                return {
                    "address": result.get("address", ""),
                    "city": result.get("city", city),
                    "state": "FL",
                    "confidence": 0.91,
                    "source": f"county_assessor_{county}",
                }

        except Exception as e:
            logger.debug(f"Florida county API error: {e}")

        return None

    def _search_nc_county(self, county: str, property_name: str, city: str) -> Optional[dict]:
        """Search North Carolina county GIS API"""

        try:
            # NC uses NCDOT GIS for property lookups
            url = f"https://gis.ncdot.gov/arcgis/rest/services/{county}County/MapServer"
            params = {
                "where": f"PROPERTY_NAME LIKE '%{property_name}%'",
                "outFields": "ADDRESS,CITY",
                "f": "json"
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("features"):
                attrs = data["features"][0].get("attributes", {})
                return {
                    "address": attrs.get("ADDRESS", ""),
                    "city": attrs.get("CITY", city),
                    "state": "NC",
                    "confidence": 0.88,
                    "source": f"county_assessor_{county}",
                }

        except Exception as e:
            logger.debug(f"NC county API error: {e}")

        return None

    def _search_kansas_county(self, county: str, property_name: str, city: str) -> Optional[dict]:
        """Search Kansas county assessor API"""

        county_apis = {
            "Shawnee": "https://www.snco.org/assessor/api/search",
            "Geary": "https://www.gearycountyks.org/assessor/api/search",
        }

        if county not in county_apis:
            return None

        try:
            url = county_apis[county]
            params = {
                "q": property_name,
                "city": city
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("results"):
                result = data["results"][0]
                return {
                    "address": result.get("address", ""),
                    "city": result.get("city", city),
                    "state": "KS",
                    "confidence": 0.89,
                    "source": f"county_assessor_{county}",
                }

        except Exception as e:
            logger.debug(f"Kansas county API error: {e}")

        return None


class CountyAssessorPhase2Manager:
    """Manage Phase 2 county assessor lookups"""

    def __init__(self):
        self.lookup = CountyAssessorPhase2()

    def search(self, county: str, state: str, property_name: str, city: str) -> Optional[dict]:
        """Search for property in county assessor

        Args:
            county: County name
            state: State code
            property_name: Property name
            city: City

        Returns:
            {address, city, state, confidence, source} or None
        """
        return self.lookup.search(county, state, property_name, city)
