"""Google Maps Address Verification Service.

Verifies property addresses by searching Google Maps Places API and matching
against property name, location, and unit count.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests


@dataclass
class VerifiedAddress:
    """Result of address verification."""
    address: str
    lat: float
    lon: float
    place_id: str
    property_name: str
    phone: Optional[str] = None
    website: Optional[str] = None
    confidence_score: float = 0.0
    source: str = "Google Maps"
    verified_at: str = ""

    def to_dict(self):
        return {
            "address": self.address,
            "lat": self.lat,
            "lon": self.lon,
            "place_id": self.place_id,
            "property_name": self.property_name,
            "phone": self.phone,
            "website": self.website,
            "confidence_score": self.confidence_score,
            "source": self.source,
            "verified_at": self.verified_at,
        }


class AddressVerificationCache:
    """Simple JSON-based cache for verification results."""

    def __init__(self, cache_dir: str = "/workspace/lexerd2/calibration/.cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "address_verification_cache.json"

    def get(self, key: str) -> Optional[VerifiedAddress]:
        """Retrieve cached address verification."""
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file) as f:
                cache = json.load(f)
            if key in cache:
                data = cache[key]
                return VerifiedAddress(**data)
        except Exception:
            pass
        return None

    def set(self, key: str, value: VerifiedAddress):
        """Store address verification in cache."""
        try:
            cache = {}
            if self.cache_file.exists():
                with open(self.cache_file) as f:
                    cache = json.load(f)
            cache[key] = value.to_dict()
            with open(self.cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception:
            pass

    def clear(self):
        """Clear the cache."""
        if self.cache_file.exists():
            self.cache_file.unlink()


class GoogleMapsAddressVerifier:
    """Verify property addresses using Google Maps Places API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Google Maps API key.

        Args:
            api_key: Google Maps API key. If None, reads from GOOGLE_MAPS_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google Maps API key required. Set GOOGLE_MAPS_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self.cache = AddressVerificationCache()
        self.base_url = "https://maps.googleapis.com/maps/api"

    def _search_place(self, query: str) -> Optional[dict]:
        """Search for a place using Google Maps Text Search API.

        Args:
            query: Search query (e.g., "Oak Ridge Apartments Jacksonville Florida")

        Returns:
            Place details or None if not found.
        """
        try:
            url = f"{self.base_url}/place/textsearch/json"
            params = {
                "query": query,
                "key": self.api_key,
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get("results"):
                return data["results"][0]
        except Exception as e:
            print(f"Error searching place: {e}")
        return None

    def _get_place_details(self, place_id: str) -> Optional[dict]:
        """Get detailed information about a place.

        Args:
            place_id: Google Maps place ID

        Returns:
            Place details or None if not found.
        """
        try:
            url = f"{self.base_url}/place/details/json"
            params = {
                "place_id": place_id,
                "fields": "formatted_address,name,geometry,formatted_phone_number,website,url",
                "key": self.api_key,
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get("result"):
                return data["result"]
        except Exception as e:
            print(f"Error getting place details: {e}")
        return None

    def _calculate_confidence(
        self, query_name: str, place_name: str, query_type: str = "apartments"
    ) -> float:
        """Calculate confidence score based on name similarity.

        Args:
            query_name: Original property name from data
            place_name: Property name from Google Maps
            query_type: Type of property (apartments, multifamily, etc.)

        Returns:
            Confidence score 0.0-1.0
        """
        query_lower = query_name.lower().strip()
        place_lower = place_name.lower().strip()

        # Exact match
        if query_lower == place_lower:
            return 1.0

        # Query is substring of place (e.g., "Oak Ridge" in "Oak Ridge Apartments")
        if query_lower in place_lower:
            return 0.95

        # Place is substring of query (reverse)
        if place_lower in query_lower:
            return 0.90

        # Fuzzy: significant overlap
        query_words = set(query_lower.split())
        place_words = set(place_lower.split())
        overlap = len(query_words & place_words) / max(len(query_words), len(place_words))
        return max(0.5, overlap)

    def verify(
        self, property_name: str, city: str, state: str, unit_count: Optional[int] = None
    ) -> Optional[VerifiedAddress]:
        """Verify property address using Google Maps.

        Args:
            property_name: Property name (e.g., "Oak Ridge Apartments")
            city: City (e.g., "Jacksonville")
            state: State code (e.g., "FL")
            unit_count: Optional unit count for additional verification

        Returns:
            VerifiedAddress if found and matched, None otherwise.
        """
        cache_key = f"{property_name}|{city}|{state}".lower()

        # Check cache first
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Build search query
        query = f"{property_name} apartments {city} {state}"

        # Search
        place = self._search_place(query)
        if not place:
            return None

        place_id = place.get("place_id")
        if not place_id:
            return None

        # Get detailed information
        details = self._get_place_details(place_id)
        if not details:
            return None

        # Extract data
        address = details.get("formatted_address", "")
        location = details.get("geometry", {}).get("location", {})
        lat = location.get("lat", 0.0)
        lon = location.get("lng", 0.0)
        phone = details.get("formatted_phone_number")
        website = details.get("website")
        place_name = details.get("name", property_name)

        # Verify it's in the right market
        if city.lower() not in address.lower():
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(property_name, place_name)

        # Create result
        result = VerifiedAddress(
            address=address,
            lat=lat,
            lon=lon,
            place_id=place_id,
            property_name=place_name,
            phone=phone,
            website=website,
            confidence_score=confidence,
            verified_at=datetime.now().isoformat(),
        )

        # Cache it
        self.cache.set(cache_key, result)

        return result


def verify_address(
    property_name: str, city: str, state: str, api_key: Optional[str] = None
) -> Optional[VerifiedAddress]:
    """Convenience function to verify an address.

    Args:
        property_name: Property name
        city: City
        state: State code
        api_key: Optional Google Maps API key

    Returns:
        VerifiedAddress if found, None otherwise.
    """
    try:
        verifier = GoogleMapsAddressVerifier(api_key)
        return verifier.verify(property_name, city, state)
    except Exception as e:
        print(f"Error verifying address: {e}")
        return None
