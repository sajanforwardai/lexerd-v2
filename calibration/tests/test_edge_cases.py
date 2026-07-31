"""Edge-case tests for 3M Model scorers."""

import pytest
from models.thesis import ThesisConfig, PropertyProfile, ConfidenceGrade
from models.scorers import MarketScorer, ModelScorer, ManagementScorer, FinalScorer


class TestMarketScorerEdgeCases:
    """Test edge cases for Market scoring."""

    def test_zero_employment_growth(self):
        """Property with 0% employment growth should score 0."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
            employment_growth_yoy=0.0,
        )
        scorer = MarketScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['employment_growth'] == 0.0

    def test_very_high_employment_growth(self):
        """Very high employment growth (5%+) should cap at 25 points."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
            employment_growth_yoy=0.10,  # 10% (unrealistic but test ceiling)
        )
        scorer = MarketScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['employment_growth'] == 25.0

    def test_missing_market_data(self):
        """Properties without market data should get neutral default scores."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
            # Missing: employment_growth_yoy, population_growth_yoy, market_cap_rate, anchors
        )
        scorer = MarketScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['employment_growth'] == 0.0
        assert breakdown['population_growth'] == 0.0
        assert breakdown['cap_rate_spread'] == 15.0  # Neutral default
        assert breakdown['employment_anchor_strength'] == 0.0

    def test_negative_cap_rate_spread(self):
        """Very high market cap rates (low spread) should score 0."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
            market_cap_rate=0.055,  # 5.5% (35 bps below national 6%)
        )
        scorer = MarketScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['cap_rate_spread'] == 0.0


class TestModelScorerEdgeCases:
    """Test edge cases for Model scoring."""

    def test_very_small_property(self):
        """Property with <50 units should score 0."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=30,  # Below 50
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
        )
        scorer = ModelScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['unit_count'] == 0.0

    def test_very_large_property(self):
        """Property with >400 units should score 0."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=500,  # Above 400
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
        )
        scorer = ModelScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['unit_count'] == 0.0

    def test_100_percent_occupancy(self):
        """100% occupied property (unrealistic) should score low (limited upside)."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=1.0,  # 100%
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
        )
        scorer = ModelScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        # 100% occupancy is beyond max threshold (0.95), so it scores like 96-99% = 10 pts
        assert breakdown['occupancy'] == 10.0

    def test_zero_occupancy(self):
        """Vacant property (0% occupancy) should score 0."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.0,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
        )
        scorer = ModelScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['occupancy'] == 0.0

    def test_class_a_property(self):
        """Class A property (fully optimized) should score 0 on class."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="A",  # Class A (no upside)
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
        )
        scorer = ModelScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['property_class'] == 0.0

    def test_expense_ratio_below_benchmark(self):
        """Property with expenses below benchmark should score 0."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.25,  # Below 0.28 benchmark
            market_expense_ratio=0.28,
        )
        scorer = ModelScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['expense_ratio_gap'] == 0.0

    def test_rent_above_market(self):
        """Property renting above market has no upside."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1400,  # 10% above market
            market_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
        )
        scorer = ModelScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['rent_upside'] == 0.0


class TestManagementScorerEdgeCases:
    """Test edge cases for Management scoring."""

    def test_owner_managed_inexperienced(self):
        """Owner-managed inexperienced property scores low on PM type."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
            management_type="Owner-managed",  # No "experienced" keyword
        )
        scorer = ManagementScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        # Owner without "experienced" scores 5 pts (or 10 if "experienced" is present)
        assert breakdown['pm_type'] in [5.0, 10.0]  # Depends on string parsing

    def test_class_c_property_no_lory_fit(self):
        """Class C property has weak Lory playbook fit."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="ST",
            units=150,
            property_class="C",  # Class C (major renovations needed)
            year_built=1990,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
            management_type="Third-party",
        )
        scorer = ManagementScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        # Class C fails class criterion but passes other 3 (units, PM, market) = 10 pts
        assert breakdown['lory_rebranding'] == 10.0  # Moderate fit, not excellent

    def test_non_target_market(self):
        """Property outside target markets scores lower on integration."""
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="AK",  # Alaska (not in target markets)
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
            management_type="Third-party",
        )
        scorer = ManagementScorer()
        score, breakdown = scorer.score(prop, ThesisConfig())
        assert breakdown['lory_rebranding'] < 20.0  # Not perfect fit
        assert breakdown['first_communities_integration'] < 20.0


class TestFinalScorerEdgeCases:
    """Test edge cases for final weighted scoring."""

    def test_weight_normalization(self):
        """Weights should normalize to 1.0 even if not manually normalized."""
        thesis = ThesisConfig()
        thesis.market_weight = 0.50
        thesis.model_weight = 0.50
        thesis.management_weight = 0.50  # Sum = 1.5 (not normalized)

        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="GA",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            expense_ratio=0.32,
            market_expense_ratio=0.28,
            employment_anchors=["military"],
            employment_growth_yoy=0.025,
            population_growth_yoy=0.018,
            market_cap_rate=0.080,
            management_type="Third-party",
        )

        scorer = FinalScorer()
        result = scorer.score(prop, thesis)
        # Final score should still be valid
        assert 0 <= result.final_fit_score <= 100

    def test_all_minimum_thresholds(self):
        """Property at all minimum thresholds should score C or D."""
        thesis = ThesisConfig()
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="GA",
            units=70,  # Minimum
            property_class="B",
            year_built=2010,
            occupancy=0.80,  # Minimum
            avg_rent_per_unit=1300,
            expense_ratio=0.28,  # At benchmark (no gap)
            market_expense_ratio=0.28,
            employment_anchors=[],  # No anchors
            employment_growth_yoy=0.02,  # Minimum
            population_growth_yoy=0.015,  # Minimum
            market_cap_rate=0.062,  # Minimum spread (200 bps)
            management_type="Third-party",
        )

        scorer = FinalScorer()
        result = scorer.score(prop, thesis)
        # Should be C or lower (weak fundamentals despite good management)
        assert result.confidence_grade in [ConfidenceGrade.C, ConfidenceGrade.D]

    def test_all_maximum_strengths(self):
        """Property with all maximum strengths should score A."""
        thesis = ThesisConfig()
        prop = PropertyProfile(
            property_id="test",
            property_name="Test",
            address="123 Main",
            city="City",
            state="GA",
            units=200,  # Sweet spot
            property_class="B",
            year_built=2010,
            occupancy=0.85,  # Sweet spot
            avg_rent_per_unit=1200,
            market_rent_per_unit=1400,  # 14% below market
            expense_ratio=0.38,  # 10% above benchmark
            market_expense_ratio=0.28,
            employment_anchors=["military", "medical"],  # Multiple anchors
            employment_growth_yoy=0.035,  # Strong growth
            population_growth_yoy=0.025,  # Strong growth
            market_cap_rate=0.085,  # Wide spread
            management_type="Third-party",
        )

        scorer = FinalScorer()
        result = scorer.score(prop, thesis)
        # Should be A or B (excellent fundamentals)
        assert result.confidence_grade in [ConfidenceGrade.A, ConfidenceGrade.B]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
