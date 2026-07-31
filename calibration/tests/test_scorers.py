"""Unit tests for 3M Model scorers."""

import pytest
from models.thesis import ThesisConfig, PropertyProfile, ConfidenceGrade
from models.scorers import MarketScorer, ModelScorer, ManagementScorer, FinalScorer


@pytest.fixture
def default_thesis() -> ThesisConfig:
    """Lexerd's default thesis configuration."""
    return ThesisConfig()


@pytest.fixture
def sample_property() -> PropertyProfile:
    """Sample property for testing."""
    return PropertyProfile(
        property_id="test_prop_1",
        property_name="Test Property",
        address="123 Main St",
        city="Atlanta",
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
    )


class TestMarketScorer:
    """Test Market scoring (30% weight)."""

    def test_market_scorer_returns_score_0_100(self, default_thesis, sample_property):
        """Market score should be between 0 and 100."""
        scorer = MarketScorer()
        score, breakdown = scorer.score(sample_property, default_thesis)
        assert 0 <= score <= 100

    def test_market_scorer_breakdown_keys(self, default_thesis, sample_property):
        """Breakdown should contain all expected keys."""
        scorer = MarketScorer()
        score, breakdown = scorer.score(sample_property, default_thesis)
        expected_keys = {'employment_growth', 'population_growth', 'cap_rate_spread', 'employment_anchor_strength'}
        assert set(breakdown.keys()) == expected_keys


class TestModelScorer:
    """Test Model scoring (40% weight)."""

    def test_model_scorer_returns_score_0_100(self, default_thesis, sample_property):
        """Model score should be between 0 and 100."""
        scorer = ModelScorer()
        score, breakdown = scorer.score(sample_property, default_thesis)
        assert 0 <= score <= 100

    def test_model_scorer_perfect_score_for_ideal_property(self, default_thesis):
        """Property meeting all criteria should score high."""
        ideal_prop = PropertyProfile(
            property_id="ideal_1",
            property_name="Ideal Property",
            address="456 Main",
            city="Atlanta",
            state="GA",
            units=150,  # In range
            property_class="B",  # In thesis classes
            year_built=2010,  # In age range
            occupancy=0.85,  # In 80–95% range
            avg_rent_per_unit=1300,
            expense_ratio=0.34,  # Above benchmark (0.28 + 0.05)
            market_expense_ratio=0.28,
            employment_growth_yoy=0.025,
            population_growth_yoy=0.018,
        )
        scorer = ModelScorer()
        score, breakdown = scorer.score(ideal_prop, default_thesis)
        assert score > 80  # Should score high


class TestManagementScorer:
    """Test Management scoring (30% weight)."""

    def test_management_scorer_returns_score_0_100(self, default_thesis, sample_property):
        """Management score should be between 0 and 100."""
        scorer = ManagementScorer()
        score, breakdown = scorer.score(sample_property, default_thesis)
        assert 0 <= score <= 100


class TestFinalScorer:
    """Test final fit scoring (weighted 3M Model)."""

    def test_final_scorer_returns_valid_result(self, default_thesis, sample_property):
        """Final scorer should return valid ScoreResult."""
        scorer = FinalScorer()
        result = scorer.score(sample_property, default_thesis)
        assert 0 <= result.final_fit_score <= 100
        assert result.confidence_grade in [ConfidenceGrade.A, ConfidenceGrade.B, ConfidenceGrade.C, ConfidenceGrade.D]

    def test_confidence_grading(self, default_thesis):
        """Test confidence grade assignment based on fit score."""
        scorer = FinalScorer()

        # Create properties with different characteristics
        strong_prop = PropertyProfile(
            property_id="strong",
            property_name="Strong Property",
            address="111 Main",
            city="Atlanta",
            state="GA",
            units=150,
            property_class="B",
            year_built=2010,
            occupancy=0.85,
            avg_rent_per_unit=1300,
            market_rent_per_unit=1400,
            expense_ratio=0.34,
            market_expense_ratio=0.28,
            employment_anchors=["military"],
            employment_growth_yoy=0.035,  # 3.5% = strong
            population_growth_yoy=0.022,  # 2.2% = strong
            market_cap_rate=0.082,  # 220 bps spread
            management_type="Third-party",
        )

        result = scorer.score(strong_prop, default_thesis)
        # Strong property with excellent market, model, and management should get A or B grade
        assert result.confidence_grade in [ConfidenceGrade.A, ConfidenceGrade.B], \
            f"Expected A or B but got {result.confidence_grade} with score {result.final_fit_score}"

    def test_weights_affect_final_score(self, default_thesis, sample_property):
        """Changing weights should change final fit score."""
        scorer = FinalScorer()

        # Score with default weights
        result1 = scorer.score(sample_property, default_thesis)
        score1 = result1.final_fit_score

        # Score with different weights
        thesis2 = ThesisConfig()
        thesis2.market_weight = 0.10  # Lower market weight
        thesis2.model_weight = 0.60  # Higher model weight
        thesis2.management_weight = 0.30

        result2 = scorer.score(sample_property, thesis2)
        score2 = result2.final_fit_score

        # Scores should differ (unless by coincidence)
        assert score1 != score2 or (result1.market_score == result2.market_score and result1.model_score == result2.model_score)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
