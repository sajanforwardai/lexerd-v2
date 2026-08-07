"""Enhanced Florida County Assessor scraper with actual HTML parsing

Scrapes property appraiser records from major Florida counties using BeautifulSoup.
Supports: Miami-Dade, Broward, Orange, Hillsborough, Duval, Lee, Sarasota
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, List
from urllib.parse import urlencode, quote
import time
import re


class FloridaCountyAssessorEnhanced:
    """Enhanced scraper with actual county-specific parsing logic"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def search_miami_dade(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Miami-Dade County Property Appraiser database"""
        try:
            # Miami-Dade uses PERS (Property Evaluation and Record Search)
            url = 'https://www.miamidade.gov/pa/propertysearch/index.html'
            # This would require JavaScript execution; fallback to search URL
            search_url = f'https://www.miamidade.gov/pa/apps/pa/General/Datacollection/Search?SearchType=apn'

            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return {
                    'address': None,
                    'confidence': 0.3,
                    'source': 'miami_dade_assessor',
                    'status': 'requires_javascript',
                    'note': f'Search at {search_url}?PropertyAddress={quote(property_name)}'
                }
        except Exception:
            pass
        return None

    def search_broward(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Broward County Property Appraiser database"""
        try:
            # Broward has a simpler web interface
            base_url = 'https://www.broward.org/PD/AssessorsOffice/'
            search_params = {
                'SearchType': 'address',
                'SearchValue': property_name
            }

            if city:
                search_params['City'] = city

            search_url = f'{base_url}Pages/Search.aspx?' + urlencode(search_params)
            response = self.session.get(search_url, timeout=self.timeout)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Look for result links or tables
                results = soup.find_all(['tr', 'div'], class_=['result', 'property-result'])

                if results:
                    # Extract first result
                    result_text = results[0].get_text(strip=True)
                    # Parse address pattern: "123 Main St, City, FL 12345"
                    match = re.search(r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Circle|Court|Lane))', result_text)
                    if match:
                        address = match.group(1)
                        return {
                            'address': address,
                            'confidence': 0.75,
                            'source': 'broward_assessor',
                            'status': 'found'
                        }
        except Exception:
            pass
        return None

    def search_orange(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Orange County (Orlando) Property Appraiser database"""
        try:
            base_url = 'https://epass.ocpafl.org/ePass/Search/'
            search_params = {'OwnerName': property_name}

            if city:
                search_params['City'] = city

            search_url = base_url + 'QuickSearch.aspx?' + urlencode(search_params)
            response = self.session.get(search_url, timeout=self.timeout)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Orange County displays results in a data grid
                rows = soup.find_all('tr', class_='DataGridRow')

                for row in rows[:1]:  # Get first match
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        # Structure: [ID, Address, Owner, ...]
                        address = cells[1].get_text(strip=True)
                        if address:
                            return {
                                'address': address,
                                'confidence': 0.80,
                                'source': 'orange_assessor',
                                'status': 'found'
                            }
        except Exception:
            pass
        return None

    def search_hillsborough(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Hillsborough County (Tampa) Property Appraiser database"""
        try:
            # Hillsborough has a search-by-owner endpoint
            search_url = 'https://apps.hcpafl.org/Asp/OwnerSearch.asp'
            params = {'owner': property_name}

            if city:
                params['City'] = city

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Look for property links in results
                prop_links = soup.find_all('a', href=re.compile(r'ParcelSearch\.asp'))

                if prop_links:
                    # Get property details
                    parcel_url = 'https://apps.hcpafl.org/Asp/' + prop_links[0].get('href')
                    parcel_response = self.session.get(parcel_url, timeout=self.timeout)

                    if parcel_response.status_code == 200:
                        parcel_soup = BeautifulSoup(parcel_response.content, 'html.parser')
                        # Extract address from property detail page
                        address_element = parcel_soup.find('td', string=re.compile(r'Site Address|Property Address'))
                        if address_element and address_element.find_next('td'):
                            address = address_element.find_next('td').get_text(strip=True)
                            return {
                                'address': address,
                                'confidence': 0.85,
                                'source': 'hillsborough_assessor',
                                'status': 'found'
                            }
        except Exception:
            pass
        return None

    def search_duval(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Duval County (Jacksonville) Property Appraiser database"""
        try:
            # Duval County has a web search interface
            search_url = 'https://webpub.duvalassessor.com/Map/'
            params = {
                'SearchType': 'Owner',
                'SearchValue': property_name
            }

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Look for results table
                result_rows = soup.find_all('tr', class_=['even', 'odd'])

                for row in result_rows[:1]:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        address = cells[1].get_text(strip=True)
                        if address and address.lower() not in ['address', '']:
                            return {
                                'address': address,
                                'confidence': 0.80,
                                'source': 'duval_assessor',
                                'status': 'found'
                            }
        except Exception:
            pass
        return None

    def search_lee(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Lee County (Fort Myers) Property Appraiser database"""
        try:
            # Lee County has a public search tool
            base_url = 'https://www.leecountyfl.gov/pa'
            search_url = f'{base_url}/property-search'

            params = {'q': property_name}
            if city:
                params['city'] = city

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Look for property links in results
                prop_entries = soup.find_all('div', class_=['property-result', 'search-result'])

                if prop_entries:
                    result_text = prop_entries[0].get_text()
                    # Extract address using regex pattern
                    match = re.search(r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Circle|Court)[\w\s]*(?:,\s*\w+)?)', result_text)
                    if match:
                        address = match.group(1)
                        return {
                            'address': address,
                            'confidence': 0.75,
                            'source': 'lee_assessor',
                            'status': 'found'
                        }
        except Exception:
            pass
        return None

    def search_sarasota(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Sarasota County Property Appraiser database"""
        try:
            # Sarasota County search interface
            search_url = 'https://www.sarasotacountyassessor.org/search'

            params = {'PropertyName': property_name}
            if city:
                params['City'] = city

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Look for address in results
                results = soup.find_all('div', class_='property-record')

                if results:
                    result_html = results[0].get_text()
                    # Extract street address
                    match = re.search(r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Circle|Court))', result_html)
                    if match:
                        address = match.group(1)
                        return {
                            'address': address,
                            'confidence': 0.80,
                            'source': 'sarasota_assessor',
                            'status': 'found'
                        }
        except Exception:
            pass
        return None

    def search_by_county(self, property_name: str, county: str, city: Optional[str] = None) -> Optional[Dict]:
        """Route search to appropriate county scraper"""
        county_lower = county.lower()

        if 'miami-dade' in county_lower or 'miamidade' in county_lower:
            return self.search_miami_dade(property_name, city)
        elif 'broward' in county_lower:
            return self.search_broward(property_name, city)
        elif 'orange' in county_lower:
            return self.search_orange(property_name, city)
        elif 'hillsborough' in county_lower:
            return self.search_hillsborough(property_name, city)
        elif 'duval' in county_lower:
            return self.search_duval(property_name, city)
        elif 'lee' in county_lower:
            return self.search_lee(property_name, city)
        elif 'sarasota' in county_lower:
            return self.search_sarasota(property_name, city)
        else:
            return None

    def batch_search(self, properties: List[Dict]) -> List[Dict]:
        """Batch search with rate limiting"""
        results = []

        for i, prop in enumerate(properties):
            if i > 0:
                time.sleep(2)  # 2 second delay between requests

            result = self.search_by_county(
                property_name=prop.get('property_name'),
                county=prop.get('county'),
                city=prop.get('city')
            )

            results.append({
                'property_name': prop.get('property_name'),
                'county': prop.get('county'),
                'city': prop.get('city'),
                'address': result.get('address') if result else None,
                'confidence': result.get('confidence', 0.0) if result else 0.0,
                'source': result.get('source') if result else 'florida_assessor',
                'status': result.get('status', 'not_found') if result else 'error'
            })

        return results
