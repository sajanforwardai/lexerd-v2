"""Configuration for Address Discovery System"""

import os

# County Assessor Websites & APIs
COUNTY_ASSESSOR_CONFIG = {
    # TEXAS
    "Harris": {
        "state": "TX",
        "type": "web_api",
        "base_url": "https://hcad.org/property-search/",
        "search_method": "web_scrape",
        "fields": ["address", "city", "zip_code"],
    },
    "Dallas": {
        "state": "TX",
        "type": "web_api",
        "base_url": "https://www.dallascad.org/",
        "search_method": "web_scrape",
    },
    "Tarrant": {
        "state": "TX",
        "type": "web_api",
        "base_url": "https://www.tcad.org/",
        "search_method": "web_scrape",
    },
    "Brazos": {
        "state": "TX",
        "type": "web_api",
        "base_url": "https://www.bcad.org/",
        "search_method": "web_scrape",
    },
    "Galveston": {
        "state": "TX",
        "type": "web_api",
        "base_url": "https://www.galvestoncad.org/",
        "search_method": "web_scrape",
    },

    # GEORGIA
    "Fulton": {
        "state": "GA",
        "type": "web_api",
        "base_url": "https://web.arcgisonline.com/arcgis/rest/services/fultoncounty/parcels/MapServer",
        "search_method": "arcgis_api",
    },
    "Cobb": {
        "state": "GA",
        "type": "web_api",
        "base_url": "https://www.cobbcounty.org/",
        "search_method": "web_scrape",
    },
    "DeKalb": {
        "state": "GA",
        "type": "web_api",
        "base_url": "https://www.dekalbcountyga.gov/",
        "search_method": "web_scrape",
    },
    "Richmond": {
        "state": "GA",
        "type": "web_api",
        "base_url": "https://www.richmondcountyga.com/",
        "search_method": "web_scrape",
    },

    # FLORIDA
    "Miami-Dade": {
        "state": "FL",
        "type": "web_api",
        "base_url": "https://www.miamidade.gov/property/",
        "search_method": "web_scrape",
    },
    "Broward": {
        "state": "FL",
        "type": "web_api",
        "base_url": "https://www.browardproperty.com/",
        "search_method": "web_scrape",
    },
    "Hillsborough": {
        "state": "FL",
        "type": "web_api",
        "base_url": "https://www.hcpafl.org/",
        "search_method": "web_scrape",
    },
    "Orange": {
        "state": "FL",
        "type": "web_api",
        "base_url": "https://ocpafl.org/",
        "search_method": "web_scrape",
    },

    # NORTH CAROLINA
    "Mecklenburg": {
        "state": "NC",
        "type": "web_api",
        "base_url": "https://www.mecknc.gov/taxes/",
        "search_method": "web_scrape",
    },
    "Wake": {
        "state": "NC",
        "type": "web_api",
        "base_url": "https://www.wakegov.com/departments-services/tax-assessor",
        "search_method": "web_scrape",
    },

    # KANSAS
    "Wyandotte": {
        "state": "KS",
        "type": "web_api",
        "base_url": "https://www.wycoassessor.org/",
        "search_method": "web_scrape",
    },

    # LOUISIANA
    "Orleans": {
        "state": "LA",
        "type": "web_api",
        "base_url": "https://www.nola.gov/",
        "search_method": "web_scrape",
    },
}

# Real Estate API Credentials
REAL_ESTATE_APIS = {
    "zillow": {
        "enabled": True,
        "api_key": os.getenv("ZILLOW_API_KEY", ""),
        "base_url": "https://www.zillow.com/api/",
        "rate_limit": 5,  # requests per second
    },
    "apartments_list": {
        "enabled": True,
        "base_url": "https://apartmentslist.com",
        "search_method": "web_scrape",
        "rate_limit": 2,
    },
    "google_maps": {
        "enabled": True,
        "api_key": os.getenv("GOOGLE_MAPS_API_KEY", ""),
        "base_url": "https://maps.googleapis.com/maps/api",
        "rate_limit": 10,
    },
}

# Property Management Companies Database
PROPERTY_MANAGEMENT_SOURCES = [
    {
        "name": "ApartmentsList",
        "url": "https://apartmentslist.com",
        "search_method": "web_scrape",
    },
    {
        "name": "Zillow",
        "url": "https://www.zillow.com/homes/",
        "search_method": "api",
    },
    {
        "name": "CoStar LoopNet",
        "url": "https://www.loopnet.com",
        "search_method": "api",  # Requires membership
        "requires_auth": True,
    },
]

# Validation Rules
VALIDATION_CONFIG = {
    "min_confidence_score": 0.70,  # Minimum confidence to accept result
    "require_unit_count_match": True,  # Require unit count to match
    "require_city_state_match": True,  # Require city/state to match
    "address_format_validation": True,  # Validate address format
}

# Rate Limiting
RATE_LIMIT_CONFIG = {
    "county_assessor": {"requests_per_second": 1, "backoff_multiplier": 2},
    "real_estate_api": {"requests_per_second": 5, "backoff_multiplier": 1.5},
    "web_scraper": {"requests_per_second": 1, "backoff_multiplier": 2},
}

# Logging
LOGGING_CONFIG = {
    "log_file": "/workspace/lexerd2/address_discovery_system.log",
    "log_level": "INFO",
    "verbose": True,
}

# Output
OUTPUT_CONFIG = {
    "cache_file": "/workspace/lexerd2/calibration/.cache/address_verification_cache.json",
    "report_file": "/workspace/lexerd2/address_discovery_report.json",
}
