"""Hybrid address resolver: smart matching + manual fallback

Strategy:
1. Use multiple query strategies for each property (property name, keywords, etc.)
2. Identify high-confidence matches automatically
3. Generate focused list for manual verification (with hints from web searches)
4. Batch import results
"""

import requests
import re
from typing import Optional, Dict, List
from urllib.parse import quote
import time


class HybridAddressResolver:
    """Resolve addresses through hybrid automated + manual approach"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def search_apartments_direct(self, property_name: str, city: str) -> Optional[str]:
        """Try direct apartments.com search and extract address from page"""
        try:
            # Search Apartments.com
            search_url = 'https://www.apartments.com/search/'
            params = {'query': f"{property_name} {city}"}

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200 and len(response.text) > 1000:
                # Look for structured data with address
                patterns = [
                    # Pattern 1: Street address, City, State ZIP
                    r'(\d{1,5}\s+[\w\s]+(?:Street|Avenue|Road|Drive|Lane|Boulevard|Court|Way|Circle|Parkway|Lane|Terrace|Trail|Trace|Square|Place|Park),?\s+([A-Za-z\s]+),?\s+FL\s+\d{5})',
                    # Pattern 2: Abbreviated
                    r'(\d{1,5}\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Ct|Way|Cir|Pkwy),?\s+([A-Za-z\s]+),?\s+FL\s+\d{5})',
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, response.text)
                    if matches:
                        return matches[0][0].strip()

        except Exception:
            pass

        return None

    def search_zillow_direct(self, property_name: str, city: str) -> Optional[str]:
        """Try Zillow search for address"""
        try:
            search_url = 'https://www.zillow.com/homes/search/'
            params = {'searchQueryState': f'{{"usersSearchTerm":"{property_name} {city} FL"}}'}

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200 and len(response.text) > 1000:
                # Look for address patterns
                patterns = [
                    r'(\d{1,5}\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Ct|Way)),?\s+([A-Za-z\s]+),?\s+FL\s+(\d{5})',
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, response.text)
                    if matches:
                        street = matches[0][0]
                        city_name = matches[0][1]
                        zip_code = matches[0][2]
                        return f"{street}, {city_name}, FL {zip_code}"

        except Exception:
            pass

        return None

    def resolve_address(
        self,
        property_name: str,
        city: str,
        county: Optional[str] = None
    ) -> Dict:
        """Attempt to resolve address through multiple strategies

        Returns:
            {
                'address': str or None,
                'confidence': float,
                'source': str,
                'status': 'found' | 'partial' | 'not_found',
                'search_url': str (if not found, URL to use for manual lookup)
            }
        """

        # Strategy 1: Direct Apartments.com search
        result = self.search_apartments_direct(property_name, city)
        if result:
            return {
                'address': result,
                'confidence': 0.85,
                'source': 'apartments_com_direct',
                'status': 'found'
            }

        time.sleep(0.5)

        # Strategy 2: Direct Zillow search
        result = self.search_zillow_direct(property_name, city)
        if result:
            return {
                'address': result,
                'confidence': 0.80,
                'source': 'zillow_direct',
                'status': 'found'
            }

        # Not found automatically - return partial with manual verification URL
        manual_search_url = f"https://www.google.com/search?q={quote(property_name)}+{quote(city)}+Florida+address"

        return {
            'address': None,
            'confidence': 0.0,
            'source': 'manual_required',
            'status': 'not_found',
            'search_url': manual_search_url,
            'manual_instructions': f'Search for "{property_name}" in {city}, FL. Use Google Maps or Apartments.com to confirm address.'
        }

    def batch_resolve(
        self,
        properties: List[Dict],
        min_confidence: float = 0.75
    ) -> Dict:
        """Batch resolve properties and separate into found/not_found

        Returns:
            {
                'found': [...list of resolved properties...],
                'not_found': [...list needing manual verification...],
                'summary': {...statistics...}
            }
        """

        found = []
        not_found = []

        for i, prop in enumerate(properties):
            print(f"[{i+1}/{len(properties)}] Resolving: {prop.get('property_name')} ({prop.get('city')})")

            result = self.resolve_address(
                property_name=prop.get('property_name'),
                city=prop.get('city'),
                county=prop.get('county')
            )

            if result['status'] == 'found' and result['confidence'] >= min_confidence:
                print(f"  ✓ Found: {result['address'][:60]}")
                found.append({
                    **prop,
                    'address': result['address'],
                    'confidence': result['confidence'],
                    'source': result['source']
                })
            else:
                print(f"  ⚠️  Manual verification needed")
                not_found.append({
                    **prop,
                    'search_url': result.get('search_url'),
                    'instructions': result.get('manual_instructions')
                })

            if i < len(properties) - 1:
                time.sleep(1)

        return {
            'found': found,
            'not_found': not_found,
            'summary': {
                'total': len(properties),
                'automatically_found': len(found),
                'needs_manual_verification': len(not_found),
                'success_rate': f"{100*len(found)/len(properties):.1f}%"
            }
        }

    def export_manual_verification_csv(self, not_found_list: List[Dict], filename: str = 'manual_verification.csv'):
        """Export list of properties needing manual verification"""
        import csv

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Property Name', 'City', 'County', 'Search URL', 'Address (to fill)', 'Source (to fill)', 'Confidence'])
            writer.writeheader()

            for prop in not_found_list:
                writer.writerow({
                    'Property Name': prop.get('property_name'),
                    'City': prop.get('city'),
                    'County': prop.get('county'),
                    'Search URL': prop.get('search_url', ''),
                    'Address (to fill)': '',
                    'Source (to fill)': '',
                    'Confidence': '1.0'
                })

        return filename
