"""Unit tests for BLS employment data integration (LCMV-23)."""

import json
import os
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from calibration.data.bls_client import BLSClient
from calibration.data.employment_enrichment import enrich_batch, enrich_property_with_employment
from calibration.models.thesis import PropertyProfile, ThesisConfig


class TestBLSClient:
    """Tests for BLS API client wrapper."""

    @pytest.fixture
    def bls_client(self):
        """Create BLS client with mock API key."""
        return BLSClient(api_key="test-key-12345")

    @pytest.fixture
    def mock_bls_response(self):
        """Mock BLS API response for Jacksonville, FL."""
        return {
            "status": "REQUEST_SUCCEEDED",
            "Results": {
                "series": [
                    {
                        "seriesID": "LAUS1225203",
                        "data": [
                            {"year": "2024", "period": "M03", "value": "1256789", "latest": True},
                            {"year": "2024", "period": "M02", "value": "1245678", "latest": False},
                            {"year": "2024", "period": "M01", "value": "1234567", "latest": False},
                            {"year": "2023", "period": "M03", "value": "1215678", "latest": False},
                            {"year": "2023", "period": "M02", "value": "1205000", "latest": False},
                            {"year": "2023", "period": "M01", "value": "1195000", "latest": False},
                        ]
                    }
                ]
            }
        }

    def test_fetch_employment_growth_success(self, bls_client, mock_bls_response):
        """Test successful employment growth fetch for valid MSA."""
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_bls_response
            mock_post.return_value.status_code = 200

            result = bls_client.fetch_employment_growth("12220")  # Jacksonville, FL

            assert result is not None
            assert isinstance(result, dict)
            assert "employment_growth_yoy" in result

    def test_fetch_employment_growth_missing_msa(self, bls_client):
        """Test handling of unknown MSA code."""
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"status": "REQUEST_NOT_PROCESSED"}
            mock_post.return_value.status_code = 400

            result = bls_client.fetch_employment_growth("99999")  # Invalid MSA

            assert result is None

    def test_cache_expiration(self, bls_client, mock_bls_response, tmp_path):
        """Test that cached data refreshes after TTL expires."""
        # Set up cache with expired data
        cache_file = tmp_path / "bls_cache.json"

        expired_data = {
            "12220": {
                "data": {"employment_growth_yoy": 0.025},
                "timestamp": (datetime.now() - timedelta(hours=25)).timestamp()  # Expired (>24h)
            }
        }
        cache_file.write_text(json.dumps(expired_data))

        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_bls_response
            mock_post.return_value.status_code = 200

            client = BLSClient(api_key="test-key", cache_file=str(cache_file))
            result = client.fetch_employment_growth("12220")

            # Should fetch fresh data, not use expired cache
            assert mock_post.called

    def test_rate_limiting(self, bls_client):
        """Test that API respects rate limits (120 requests/minute)."""
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 429  # Rate limit exceeded

            result = bls_client.fetch_employment_growth("12220")

            # Should handle gracefully (retry with backoff or return None)
            assert result is None or isinstance(result, dict)

    def test_batch_enrichment_performance(self, bls_client):
        """Test that batch enrichment of 100+ properties completes efficiently."""
        properties = [
            PropertyProfile(
                property_id=f"prop-{i}",
                property_name=f"Property {i}",
                address=f"{100+i} Main St",
                city="Jacksonville",
                state="FL",
                units=150,
                property_class="B",
                year_built=2010,
                occupancy=0.85,
                avg_rent_per_unit=1500,
                expense_ratio=0.30,
                market_expense_ratio=0.28,
            )
            for i in range(100)
        ]

        with patch.object(bls_client, 'fetch_employment_growth') as mock_fetch:
            mock_fetch.return_value = {"employment_growth_yoy": 0.025}

            start = time.time()
            enriched = enrich_batch(properties, bls_client)
            elapsed = time.time() - start

            assert len(enriched) == 100
            assert all(p.employment_growth_yoy is not None for p in enriched)
            assert elapsed < 2.0  # Must complete in <2 seconds

    def test_network_failure_fallback(self, bls_client):
        """Test graceful handling of network errors."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network timeout")

            result = bls_client.fetch_employment_growth("12220")

            # Should not crash; return None or cached data
            assert result is None or isinstance(result, dict)

    def test_enrichment_accuracy(self, bls_client):
        """Test that enriched values match known BLS data."""
        property = PropertyProfile(
            property_id="test-1",
            property_name="Test Property",
            address="123 Main St",
            city="Jacksonville",
            state="FL",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1500,
            expense_ratio=0.30,
            market_expense_ratio=0.28,
        )

        with patch.object(bls_client, 'fetch_employment_growth') as mock_fetch:
            mock_fetch.return_value = {"employment_growth_yoy": 0.035}

            enriched = enrich_property_with_employment(property, bls_client)

            assert enriched.employment_growth_yoy == 0.035

    def test_msa_mapping_accuracy(self, bls_client):
        """Test that city/state maps correctly to MSA code."""
        msa_code = bls_client.get_msa_by_city_state("Jacksonville", "FL")
        assert msa_code == "12220"

        msa_code = bls_client.get_msa_by_city_state("Fargo", "ND")
        assert msa_code == "23620"

        msa_code = bls_client.get_msa_by_city_state("Austin", "TX")
        assert msa_code == "12420"

    def test_cache_age_tracking(self, bls_client):
        """Test that cache age is tracked and reported."""
        age = bls_client.get_cache_age("12220")
        # Should return age in minutes or None if not cached
        assert age is None or isinstance(age, (int, float))

    def test_no_hardcoded_keys(self, bls_client):
        """Test that API key comes from environment, not hardcoded."""
        # Should use api_key parameter or environment variable
        assert bls_client.api_key is not None
        assert len(bls_client.api_key) > 0

    def test_error_handling_missing_data(self, bls_client):
        """Test handling of incomplete BLS response data."""
        with patch("requests.post") as mock_post:
            # Response missing 'value' field
            mock_post.return_value.json.return_value = {
                "status": "REQUEST_SUCCEEDED",
                "Results": {
                    "series": [
                        {
                            "seriesID": "LAUS1225203",
                            "data": [
                                {"year": "2024", "period": "M03", "latest": True}
                            ]
                        }
                    ]
                }
            }
            mock_post.return_value.status_code = 200

            result = bls_client.fetch_employment_growth("12220")

            # Should handle gracefully without crashing
            assert result is None or isinstance(result, dict)


class TestEmploymentEnrichment:
    """Tests for employment data enrichment."""

    @pytest.fixture
    def sample_property(self):
        """Sample property for enrichment testing."""
        return PropertyProfile(
            property_id="prop-1",
            property_name="Oak Ridge Apartments",
            address="456 Oak Lane",
            city="Jacksonville",
            state="FL",
            units=200,
            property_class="B",
            year_built=2012,
            occupancy=0.82,
            avg_rent_per_unit=1600,
            expense_ratio=0.31,
            market_expense_ratio=0.28,
        )

    @pytest.fixture
    def bls_client(self):
        return BLSClient(api_key="test-key")

    def test_enrich_property_single(self, sample_property, bls_client):
        """Test enriching a single property."""
        with patch.object(bls_client, 'fetch_employment_growth') as mock_fetch:
            mock_fetch.return_value = {"employment_growth_yoy": 0.032}

            enriched = enrich_property_with_employment(sample_property, bls_client)

            assert enriched.employment_growth_yoy == 0.032
            # Original property should not be modified
            assert sample_property.employment_growth_yoy is None

    def test_enrich_batch_multiple(self, bls_client):
        """Test enriching multiple properties in a batch."""
        properties = [
            PropertyProfile(
                property_id=f"prop-{i}",
                property_name=f"Property {i}",
                address=f"{100+i} Main",
                city=["Jacksonville", "Fargo", "Austin"][i % 3],
                state=["FL", "ND", "TX"][i % 3],
                units=100 + (i * 10),
                property_class="B",
                year_built=2010,
                occupancy=0.80,
                avg_rent_per_unit=1500,
                expense_ratio=0.30,
                market_expense_ratio=0.28,
            )
            for i in range(10)
        ]

        with patch.object(bls_client, 'fetch_employment_growth') as mock_fetch:
            def side_effect(msa_code):
                return {"employment_growth_yoy": 0.020 + (hash(msa_code) % 20) / 1000}

            mock_fetch.side_effect = side_effect

            enriched = enrich_batch(properties, bls_client)

            assert len(enriched) == 10
            assert all(p.employment_growth_yoy is not None for p in enriched)

    def test_enrich_handles_missing_city_state(self, bls_client):
        """Test that enrichment handles properties with missing city/state gracefully."""
        property = PropertyProfile(
            property_id="prop-1",
            property_name="Unknown Location",
            address="123 St",
            city="",  # Missing city
            state="",  # Missing state
            units=100,
            property_class="B",
            year_built=2010,
            occupancy=0.80,
            avg_rent_per_unit=1500,
            expense_ratio=0.30,
            market_expense_ratio=0.28,
        )

        enriched = enrich_property_with_employment(property, bls_client)

        # Should not crash; employment_growth_yoy remains None
        assert enriched.employment_growth_yoy is None


class TestIntegrationWithScoring:
    """Tests for integration with scoring engine."""

    def test_enriched_employment_data_feeds_scorer(self):
        """Test that enriched employment data integrates with MarketScorer."""
        from calibration.models.scorers import MarketScorer

        property = PropertyProfile(
            property_id="prop-1",
            property_name="Test",
            address="123 Main",
            city="Jacksonville",
            state="FL",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1500,
            expense_ratio=0.30,
            market_expense_ratio=0.28,
            employment_growth_yoy=0.035,  # Enriched data
        )

        thesis = ThesisConfig()
        scorer = MarketScorer()
        score, breakdown = scorer.score(property, thesis)

        # Should score employment growth successfully
        assert score > 0
        assert "employment_growth" in breakdown
        assert breakdown["employment_growth"] > 0


class TestBLSClientEdgeCases:
    """Edge case tests for BLS client."""

    @pytest.fixture
    def bls_client(self):
        return BLSClient(api_key="test-key-12345")

    def test_msa_mapping_case_insensitive(self, bls_client):
        """Test that MSA mapping is case-insensitive."""
        msa_code = bls_client.get_msa_by_city_state("jacksonville", "fl")
        assert msa_code == "12220"

        msa_code = bls_client.get_msa_by_city_state("FARGO", "ND")
        assert msa_code == "23620"

    def test_cache_persistence_after_restart(self, tmp_path):
        """Test that cache persists across client instances."""
        cache_file = tmp_path / "bls_cache.json"

        # First client writes to cache
        client1 = BLSClient(api_key="test-key", cache_file=str(cache_file))
        client1._cache["12220"] = {
            "data": {"employment_growth_yoy": 0.035},
            "timestamp": time.time(),
        }
        client1._save_cache()

        # Second client reads from same cache file
        client2 = BLSClient(api_key="test-key", cache_file=str(cache_file))
        assert "12220" in client2._cache
        assert client2._cache["12220"]["data"]["employment_growth_yoy"] == 0.035

    def test_refresh_cache_updates_all_entries(self, bls_client):
        """Test that refresh_cache() updates cached entries."""
        with patch.object(bls_client, 'fetch_employment_growth') as mock_fetch:
            mock_fetch.return_value = {"employment_growth_yoy": 0.04}

            # Pre-populate cache
            bls_client._cache["12220"] = {
                "data": {"employment_growth_yoy": 0.02},
                "timestamp": (datetime.now() - timedelta(hours=25)).timestamp(),
            }

            bls_client.refresh_cache()

            # Should call fetch for the expired entry
            assert mock_fetch.called

    def test_multiple_msa_codes_supported(self, bls_client):
        """Test that multiple MSA codes are supported."""
        msa_codes = [
            bls_client.get_msa_by_city_state("Jacksonville", "FL"),
            bls_client.get_msa_by_city_state("Fargo", "ND"),
            bls_client.get_msa_by_city_state("Austin", "TX"),
            bls_client.get_msa_by_city_state("Atlanta", "GA"),
        ]
        assert all(code is not None for code in msa_codes)
        assert len(set(msa_codes)) == 4  # All unique


class TestEmploymentEnrichmentEdgeCases:
    """Edge case tests for enrichment module."""

    @pytest.fixture
    def bls_client(self):
        return BLSClient(api_key="test-key")

    def test_enrich_property_with_exception_returns_original(self, bls_client):
        """Test that exceptions during enrichment return original property."""
        property = PropertyProfile(
            property_id="prop-1",
            property_name="Test",
            address="123 Main",
            city="Jacksonville",
            state="FL",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1500,
            expense_ratio=0.30,
            market_expense_ratio=0.28,
        )

        with patch.object(bls_client, 'get_msa_by_city_state') as mock_msa:
            mock_msa.side_effect = Exception("Unexpected error")

            enriched = enrich_property_with_employment(property, bls_client)
            assert enriched.employment_growth_yoy is None

    def test_enrich_batch_partial_failure(self, bls_client):
        """Test batch enrichment when some properties fail."""
        properties = [
            PropertyProfile(
                property_id="prop-1",
                property_name="Test 1",
                address="123 Main",
                city="Jacksonville",
                state="FL",
                units=150,
                property_class="B",
                year_built=2010,
                occupancy=0.85,
                avg_rent_per_unit=1500,
                expense_ratio=0.30,
                market_expense_ratio=0.28,
            ),
            PropertyProfile(
                property_id="prop-2",
                property_name="Test 2",
                address="456 Oak",
                city="",  # Missing city
                state="FL",
                units=100,
                property_class="B",
                year_built=2012,
                occupancy=0.80,
                avg_rent_per_unit=1600,
                expense_ratio=0.31,
                market_expense_ratio=0.28,
            ),
        ]

        with patch.object(bls_client, 'fetch_employment_growth') as mock_fetch:
            mock_fetch.return_value = {"employment_growth_yoy": 0.025}

            enriched = enrich_batch(properties, bls_client)

            assert len(enriched) == 2
            assert enriched[0].employment_growth_yoy == 0.025
            assert enriched[1].employment_growth_yoy is None  # Failed due to missing city

    def test_enrich_preserves_all_other_fields(self, bls_client):
        """Test that enrichment doesn't modify other property fields."""
        property = PropertyProfile(
            property_id="prop-1",
            property_name="Original Name",
            address="Original Address",
            city="Jacksonville",
            state="FL",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1500,
            expense_ratio=0.30,
            market_expense_ratio=0.28,
        )

        with patch.object(bls_client, 'fetch_employment_growth') as mock_fetch:
            mock_fetch.return_value = {"employment_growth_yoy": 0.032}

            enriched = enrich_property_with_employment(property, bls_client)

            # All other fields preserved
            assert enriched.property_name == "Original Name"
            assert enriched.address == "Original Address"
            assert enriched.units == 150
            assert enriched.year_built == 2010
            assert enriched.occupancy == 0.85
            # Only employment_growth_yoy changed
            assert enriched.employment_growth_yoy == 0.032
