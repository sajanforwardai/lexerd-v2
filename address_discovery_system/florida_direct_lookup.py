"""Direct lookup for Florida properties using Google Maps + County Assessor links

Strategy: For each property, generate direct links to:
1. Google Maps search (to verify the property exists and get street address)
2. County assessor website search (to verify owner records)
3. Property tax record databases

This enables manual verification with high confidence (1.0).
"""

from typing import Dict, List, Optional
from urllib.parse import urlencode, quote


class FloridaDirectLookup:
    """Generate verification links for manual property lookup"""

    # County assessor direct search URLs (tested working)
    COUNTY_SEARCH_URLS = {
        'Alachua': 'https://www.acpafl.org/',
        'Bay': 'https://www.baycountyfl.gov/Departments/PropertyAppraiser',
        'Broward': 'https://www.broward.org/PD/AssessorsOffice/Pages/Search.aspx',
        'Columbia': 'https://www.columbiacountyfl.com/departments/property-appraiser',
        'Duval': 'https://webpub.duvalassessor.com/Map/',
        'Escambia': 'https://www.escambiaassessor.com/',
        'Hillsborough': 'https://apps.hcpafl.org/Asp/GeneralSearch.asp',
        'Lee': 'https://www.leecountyfl.gov/pa/property-search',
        'Miami-Dade': 'https://www.miamidade.gov/pa/propertysearch/index.html',
        'Okaloosa': 'https://www.okaloosaassessor.com/',
        'Orange': 'https://epass.ocpafl.org/ePass/Search/QuickSearch.aspx',
        'Osceola': 'https://www.osceolacountyfl.com/Department/PropertyAppraiser',
        'Pinellas': 'https://www.pcpafl.org/onlineservices/search.html',
        'Sarasota': 'https://www.sarasotacountyassessor.org/Search/Search',
    }

    @staticmethod
    def google_maps_url(property_name: str, city: str, state: str = 'FL') -> str:
        """Generate Google Maps search URL for property verification"""
        query = f"{property_name} {city} {state}"
        return f"https://www.google.com/maps/search/{quote(query)}"

    @staticmethod
    def google_search_url(property_name: str, city: str, state: str = 'FL') -> str:
        """Generate Google Search URL for address verification"""
        query = f'"{property_name}" "{city}" "{state}" address'
        return f"https://www.google.com/search?q={quote(query)}"

    @staticmethod
    def apartments_com_url(property_name: str, city: str) -> str:
        """Generate Apartments.com search URL"""
        query = f"{property_name} {city}"
        return f"https://www.apartments.com/search/?query={quote(query)}"

    @staticmethod
    def zillow_url(property_name: str, city: str, state: str = 'FL') -> str:
        """Generate Zillow search URL"""
        query = f"{property_name} {city} {state}"
        return f"https://www.zillow.com/homes/{quote(query)}_rb/"

    @staticmethod
    def county_assessor_url(county: str) -> str:
        """Get county assessor search URL"""
        return FloridaDirectLookup.COUNTY_SEARCH_URLS.get(county, '')

    @staticmethod
    def create_lookup_record(
        property_name: str,
        city: str,
        county: str,
        state: str = 'FL'
    ) -> Dict:
        """Create a complete lookup record with all search links"""

        return {
            'property_name': property_name,
            'city': city,
            'county': county,
            'state': state,
            'search_links': {
                'google_maps': FloridaDirectLookup.google_maps_url(property_name, city, state),
                'google_search': FloridaDirectLookup.google_search_url(property_name, city, state),
                'apartments_com': FloridaDirectLookup.apartments_com_url(property_name, city),
                'zillow': FloridaDirectLookup.zillow_url(property_name, city, state),
                'county_assessor': FloridaDirectLookup.county_assessor_url(county),
            },
            'verification_sources': [
                'Google Maps (visual + address)',
                'Google Search (web results)',
                'Apartments.com (property page + address)',
                'Zillow (property details + address)',
                'County Assessor (owner + tax records)',
            ]
        }

    @staticmethod
    def batch_create_lookup_table(properties: List[Dict]) -> List[Dict]:
        """Create lookup table for batch of properties"""
        results = []
        for prop in properties:
            record = FloridaDirectLookup.create_lookup_record(
                property_name=prop.get('property_name'),
                city=prop.get('city'),
                county=prop.get('county'),
                state=prop.get('state', 'FL')
            )
            results.append(record)
        return results

    @staticmethod
    def export_lookup_csv(properties: List[Dict], filename: str = 'fl_property_lookup.csv'):
        """Export lookup table as CSV for easy reference"""
        import csv

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Property Name',
                'City',
                'County',
                'Google Maps',
                'Google Search',
                'Apartments.com',
                'Zillow',
                'County Assessor',
                'Confidence',
                'Address (to be filled)',
                'Source (to be filled)'
            ])

            # Rows
            for prop in properties:
                lookup = FloridaDirectLookup.create_lookup_record(
                    property_name=prop.get('property_name'),
                    city=prop.get('city'),
                    county=prop.get('county')
                )

                writer.writerow([
                    lookup['property_name'],
                    lookup['city'],
                    lookup['county'],
                    lookup['search_links']['google_maps'],
                    lookup['search_links']['google_search'],
                    lookup['search_links']['apartments_com'],
                    lookup['search_links']['zillow'],
                    lookup['search_links']['county_assessor'],
                    'Manual',  # Confidence level for manual verification
                    '',  # Address to be filled in
                    '',  # Source to be filled in
                ])

        return filename

    @staticmethod
    def export_lookup_html(properties: List[Dict], filename: str = 'fl_property_lookup.html'):
        """Export lookup table as interactive HTML"""

        lookups = FloridaDirectLookup.batch_create_lookup_table(properties)

        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Florida Property Lookup Tool</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            margin: 0;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 30px;
        }
        h1 {
            color: #333;
            margin-top: 0;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .property {
            margin-bottom: 30px;
            padding: 20px;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            background: #fafafa;
        }
        .property-header {
            font-size: 16px;
            font-weight: 600;
            color: #333;
            margin-bottom: 12px;
        }
        .property-info {
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
            font-size: 14px;
        }
        .info-item {
            flex: 1;
        }
        .info-label {
            color: #666;
            font-weight: 500;
        }
        .info-value {
            color: #333;
            margin-top: 3px;
        }
        .links {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }
        .link-btn {
            display: inline-block;
            padding: 10px 15px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 500;
            text-align: center;
            transition: background 0.2s;
        }
        .link-btn:hover {
            background: #5568d3;
        }
        .link-btn.secondary {
            background: #6c757d;
        }
        .link-btn.secondary:hover {
            background: #5a6268;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 Florida Property Lookup Tool</h1>
        <p>Click links below to verify property addresses. Record found addresses in the database.</p>
"""

        for lookup in lookups:
            html += f"""
        <div class="property">
            <div class="property-header">{lookup['property_name']}</div>
            <div class="property-info">
                <div class="info-item">
                    <div class="info-label">City</div>
                    <div class="info-value">{lookup['city']}, {lookup['county']} County, FL</div>
                </div>
            </div>
            <div class="links">
                <a href="{lookup['search_links']['google_maps']}" target="_blank" class="link-btn">🗺️ Google Maps</a>
                <a href="{lookup['search_links']['google_search']}" target="_blank" class="link-btn">🔍 Google Search</a>
                <a href="{lookup['search_links']['apartments_com']}" target="_blank" class="link-btn">🏢 Apartments.com</a>
                <a href="{lookup['search_links']['zillow']}" target="_blank" class="link-btn">🏠 Zillow</a>
                <a href="{lookup['search_links']['county_assessor']}" target="_blank" class="link-btn secondary">📋 County Assessor</a>
            </div>
        </div>
"""

        html += """
    </div>
</body>
</html>
"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)

        return filename
