"""Tests for address verification module."""

import pytest

from calibration.address_verification import (
    AddressVerificationCache,
    GoogleMapsAddressVerifier,
    VerifiedAddress,
)


class TestAddressVerificationCache:
    """Test the caching layer."""

    def test_cache_set_and_get(self, tmp_path):
        """Test storing and retrieving from cache."""
        cache = AddressVerificationCache(str(tmp_path))

        # Create a test address
        addr = VerifiedAddress(
            address="123 Main St, Austin TX",
            lat=30.2672,
            lon=-97.7431,
            place_id="test_place_123",
            property_name="Test Apartments",
            confidence_score=0.95,
        )

        # Store it
        key = "test|austin|tx"
        cache.set(key, addr)

        # Retrieve it
        retrieved = cache.get(key)
        assert retrieved is not None
        assert retrieved.address == "123 Main St, Austin TX"
        assert retrieved.confidence_score == 0.95

    def test_cache_miss(self, tmp_path):
        """Test cache miss returns None."""
        cache = AddressVerificationCache(str(tmp_path))
        result = cache.get("nonexistent")
        assert result is None


class TestVerifiedAddress:
    """Test the VerifiedAddress dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        addr = VerifiedAddress(
            address="123 Main St",
            lat=30.0,
            lon=-97.0,
            place_id="test",
            property_name="Test",
            confidence_score=0.9,
        )
        d = addr.to_dict()
        assert d["address"] == "123 Main St"
        assert d["confidence_score"] == 0.9


class TestGoogleMapsAddressVerifier:
    """Test address verification (mocked to avoid API calls)."""

    def test_missing_api_key(self):
        """Test that missing API key raises error."""
        with pytest.raises(ValueError, match="API key required"):
            GoogleMapsAddressVerifier(api_key=None)

    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        verifier = GoogleMapsAddressVerifier(api_key="test_key")

        # Exact match
        score = verifier._calculate_confidence("Oak Ridge", "Oak Ridge")
        assert score == 1.0

        # Substring match
        score = verifier._calculate_confidence("Oak Ridge", "Oak Ridge Apartments")
        assert score >= 0.9

        # Reverse substring
        score = verifier._calculate_confidence("Oak Ridge Apartments", "Oak Ridge")
        assert score >= 0.85

        # Fuzzy match
        score = verifier._calculate_confidence("Oak Ridge", "The Ridge")
        assert 0.5 <= score <= 1.0

    def test_api_key_from_environment(self, monkeypatch):
        """Test reading API key from environment variable."""
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "env_test_key")
        verifier = GoogleMapsAddressVerifier()
        assert verifier.api_key == "env_test_key"
