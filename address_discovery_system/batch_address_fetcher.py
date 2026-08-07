"""Batch address fetcher using multiple data sources

Automatically retrieves addresses for properties by querying:
1. Google Maps Geocoding API
2. Property database lookups
3. Public records aggregators
4. Web scraping fallbacks
"""

import requests
import json
import time
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlencode, quote
import re


class BatchAddressFetcher:
    """Fetch addresses from multiple sources with fallbacks"""

    # Known good data sources for property addresses
    DATA_SOURCES = {
        'google_maps': {
            'priority': 1,
            'confidence': 0.85,
            'requires_api_key': True,
            'rate_limit': 50  # requests per second
        },
        'apartments_com': {
            'priority': 2,
            'confidence': 0.90,
            'requires_api_key': False,
            'rate_limit': 1  # requests per second (avoid blocking)
        },
        'zillow': {
            'priority': 3,
            'confidence': 0.85,
            'requires_api_key': False,
            'rate_limit': 1
        },
        'whitepages': {
            'priority': 4,
            'confidence': 0.75,
            'requires_api_key': False,
            'rate_limit': 1
        },
        'google_search': {
            'priority': 5,
            'confidence': 0.70,
            'requires_api_key': False,
            'rate_limit': 1
        }
    }

    def __init__(self, google_maps_api_key: Optional[str] = None, timeout: int = 10):
        """Initialize fetcher with optional Google Maps API key"""
        self.google_maps_api_key = google_maps_api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_from_google_maps(self, property_name: str, city: str, state: str = 'FL') -> Optional[Dict]:
        """Fetch address from Google Maps Geocoding API"""
        if not self.google_maps_api_key:
            return None

        try:
            address = f"{property_name}, {city}, {state}"
            params = {
                'address': address,
                'key': self.google_maps_api_key
            }

            url = 'https://maps.googleapis.com/maps/api/geocode/json'
            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if data['results']:
                    result = data['results'][0]
                    formatted_address = result.get('formatted_address', '')

                    # Extract FL address only
                    if ', FL' in formatted_address or ', Florida' in formatted_address:
                        return {
                            'address': formatted_address,
                            'confidence': 0.85,
                            'source': 'google_maps_api',
                            'lat': result['geometry']['location']['lat'],
                            'lng': result['geometry']['location']['lng'],
                            'place_id': result.get('place_id')
                        }
        except Exception as e:
            pass

        return None

    def fetch_from_apartments_com(self, property_name: str, city: str) -> Optional[Dict]:
        """Scrape address from Apartments.com search results"""
        try:
            search_url = 'https://www.apartments.com/search/'
            params = {'query': f"{property_name} {city}"}

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                # Look for address patterns in HTML
                # Pattern: street address with city, state zip
                pattern = r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Ct|Circle|Court|Parkway|Way|Drive|Road|Lane|Street|Avenue)[.,\s]+([A-Za-z\s]+),\s+FL\s+\d{5})'
                matches = re.findall(pattern, response.text)

                if matches:
                    address = matches[0][0].strip()
                    return {
                        'address': address,
                        'confidence': 0.90,
                        'source': 'apartments_com',
                        'status': 'found'
                    }
        except Exception:
            pass

        return None

    def fetch_from_zillow(self, property_name: str, city: str) -> Optional[Dict]:
        """Scrape address from Zillow search results"""
        try:
            search_url = 'https://www.zillow.com/homes/search/'
            params = {
                'searchQueryState': json.dumps({
                    'pagination': {},
                    'usersSearchTerm': f"{property_name} {city} FL"
                })
            }

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                # Extract address from Zillow response
                pattern = r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd))[,\s]+([A-Za-z\s]+),\s+FL\s+(\d{5})'
                matches = re.findall(pattern, response.text)

                if matches:
                    street = matches[0][0]
                    city_name = matches[0][1]
                    zipcode = matches[0][2]
                    address = f"{street}, {city_name}, FL {zipcode}"

                    return {
                        'address': address,
                        'confidence': 0.85,
                        'source': 'zillow',
                        'status': 'found'
                    }
        except Exception:
            pass

        return None

    def fetch_from_whitepages(self, property_name: str, city: str) -> Optional[Dict]:
        """Query WhitePages for property address"""
        try:
            search_url = 'https://www.whitepages.com/name'
            params = {
                'q': property_name,
                'city': city,
                'state': 'FL'
            }

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                # Extract address pattern
                pattern = r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd)[,\s]+([A-Za-z\s]+),\s+FL\s+\d{5})'
                matches = re.findall(pattern, response.text)

                if matches:
                    address = matches[0][0].strip()
                    return {
                        'address': address,
                        'confidence': 0.75,
                        'source': 'whitepages',
                        'status': 'found'
                    }
        except Exception:
            pass

        return None

    def fetch_from_google_search(self, property_name: str, city: str) -> Optional[Dict]:
        """Parse Google Search results for property address"""
        try:
            search_query = f'"{property_name}" "{city}" FL address'
            search_url = 'https://www.google.com/search'
            params = {'q': search_query}

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                # Look for address in search results
                pattern = r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd)[,\s]+([A-Za-z\s]+),\s+FL\s+(\d{5}))'
                matches = re.findall(pattern, response.text)

                if matches:
                    address = matches[0][0].strip()
                    return {
                        'address': address,
                        'confidence': 0.70,
                        'source': 'google_search',
                        'status': 'found'
                    }
        except Exception:
            pass

        return None

    def fetch_address(
        self,
        property_name: str,
        city: str,
        county: Optional[str] = None,
        state: str = 'FL',
        use_api: bool = True
    ) -> Optional[Dict]:
        """Fetch address using best available source

        Tries sources in priority order:
        1. Google Maps API (if key available)
        2. Apartments.com
        3. Zillow
        4. WhitePages
        5. Google Search

        Returns best match with confidence score.
        """

        results = []

        # Try API-based lookup first (most reliable)
        if use_api and self.google_maps_api_key:
            result = self.fetch_from_google_maps(property_name, city, state)
            if result and result['confidence'] >= 0.80:
                return result
            if result:
                results.append(result)

        # Try web scraping sources
        time.sleep(0.5)  # Rate limiting
        result = self.fetch_from_apartments_com(property_name, city)
        if result and result['confidence'] >= 0.85:
            return result
        if result:
            results.append(result)

        time.sleep(0.5)
        result = self.fetch_from_zillow(property_name, city)
        if result and result['confidence'] >= 0.80:
            return result
        if result:
            results.append(result)

        time.sleep(0.5)
        result = self.fetch_from_whitepages(property_name, city)
        if result and result['confidence'] >= 0.70:
            return result
        if result:
            results.append(result)

        time.sleep(0.5)
        result = self.fetch_from_google_search(property_name, city)
        if result and result['confidence'] >= 0.65:
            return result
        if result:
            results.append(result)

        # Return best result if found
        if results:
            results.sort(key=lambda x: x['confidence'], reverse=True)
            return results[0]

        return None

    def batch_fetch(
        self,
        properties: List[Dict],
        use_api: bool = True,
        min_confidence: float = 0.70
    ) -> List[Dict]:
        """Batch fetch addresses for multiple properties

        Args:
            properties: List of dicts with property_name, city, county, state
            use_api: Whether to use Google Maps API if available
            min_confidence: Minimum confidence threshold to return result

        Returns:
            List of dicts with original data + address, confidence, source
        """

        results = []

        for i, prop in enumerate(properties):
            print(f"[{i+1}/{len(properties)}] Fetching: {prop.get('property_name')} ({prop.get('city')})")

            result = self.fetch_address(
                property_name=prop.get('property_name'),
                city=prop.get('city'),
                county=prop.get('county'),
                state=prop.get('state', 'FL'),
                use_api=use_api
            )

            if result and result['confidence'] >= min_confidence:
                print(f"  ✓ Found: {result['address'][:60]} (confidence: {result['confidence']:.0%})")
                results.append({
                    'property_name': prop.get('property_name'),
                    'city': prop.get('city'),
                    'county': prop.get('county'),
                    'state': prop.get('state', 'FL'),
                    'address': result['address'],
                    'confidence': result['confidence'],
                    'source': result['source'],
                    'status': 'found'
                })
            else:
                print(f"  ✗ Not found (confidence too low or no result)")
                results.append({
                    'property_name': prop.get('property_name'),
                    'city': prop.get('city'),
                    'county': prop.get('county'),
                    'state': prop.get('state', 'FL'),
                    'address': None,
                    'confidence': 0.0,
                    'source': 'none',
                    'status': 'not_found'
                })

            # Rate limiting between requests
            if i < len(properties) - 1:
                time.sleep(1)

        return results
