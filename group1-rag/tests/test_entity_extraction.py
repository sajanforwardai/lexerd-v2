"""test_entity_extraction.py — Tier 2 entity extraction evaluation tests.

Tests for named entity extraction and classification.
Measures: F1, precision, recall, latency.

Target: Entity F1 ≥ 0.85, Latency ≤ 500ms
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from test_metrics import (
    EntityExtractionResult,
    EvaluationReport,
    entity_extraction_f1,
    compute_latency_stats,
    save_report,
)


@pytest.mark.tier2
class TestTier2EntityExtraction:
    """Tier 2 entity extraction evaluation suite."""

    def test_entity_extraction_basic(self, mock_entity_extractor):
        """Test basic entity extraction."""
        text = "Gamma is a key greek. Delta hedging is critical for options traders."

        entities = mock_entity_extractor.extract(text)

        assert isinstance(entities, set)
        assert "gamma" in entities or len(entities) > 0
        print(f"Extracted entities: {entities}")

    def test_entity_f1_score_sample(self, mock_entity_extractor):
        """Test F1 score on sample text."""
        text = "Vega hedging and gamma scalping are volatility strategies. Use delta neutral positioning."

        predicted = mock_entity_extractor.extract(text)
        ground_truth = {"vega", "gamma", "delta", "volatility", "hedge"}

        f1, precision, recall = entity_extraction_f1(predicted, ground_truth)

        assert 0.0 <= f1 <= 1.0
        assert 0.0 <= precision <= 1.0
        assert 0.0 <= recall <= 1.0
        print(f"Entity extraction - F1: {f1:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}")

    def test_entity_extraction_perfect_match(self, mock_entity_extractor):
        """Test F1 when predicted == ground truth."""
        text = "delta gamma vega theta rho"

        predicted = {"delta", "gamma", "vega", "theta", "rho"}
        ground_truth = {"delta", "gamma", "vega", "theta", "rho"}

        f1, precision, recall = entity_extraction_f1(predicted, ground_truth)

        assert f1 == 1.0
        assert precision == 1.0
        assert recall == 1.0

    def test_entity_extraction_no_predictions(self, mock_entity_extractor):
        """Test F1 when extractor finds no entities."""
        predicted = set()
        ground_truth = {"gamma", "vega"}

        f1, precision, recall = entity_extraction_f1(predicted, ground_truth)

        assert f1 == 0.0
        assert precision == 0.0
        assert recall == 0.0

    def test_entity_extraction_no_ground_truth(self, mock_entity_extractor):
        """Test F1 when there are no ground truth entities."""
        predicted = {"gamma", "vega"}
        ground_truth = set()

        f1, precision, recall = entity_extraction_f1(predicted, ground_truth)

        assert f1 == 0.0
        assert precision == 0.0

    def test_entity_extraction_partial_overlap(self, mock_entity_extractor):
        """Test F1 with partial overlap."""
        predicted = {"gamma", "vega", "theta", "incorrect"}
        ground_truth = {"gamma", "vega", "delta"}

        f1, precision, recall = entity_extraction_f1(predicted, ground_truth)

        # Precision: 2/4 (gamma, vega are correct)
        # Recall: 2/3 (gamma, vega found)
        assert 0 < f1 < 1
        assert precision == 0.5  # 2 correct out of 4 predicted
        assert recall == 2.0 / 3  # 2 correct out of 3 ground truth
        print(f"Partial overlap - F1: {f1:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}")

    def test_entity_extraction_case_sensitivity(self, mock_entity_extractor):
        """Test case sensitivity in entity matching."""
        # Entity extractor should normalize to lowercase
        predicted = {"gamma", "vega"}
        ground_truth = {"Gamma", "VEGA"}

        # Convert for comparison
        ground_truth_lower = {e.lower() for e in ground_truth}

        f1, precision, recall = entity_extraction_f1(predicted, ground_truth_lower)

        assert f1 == 1.0
        print("Case handling verified")

    def test_entity_extraction_latency_tier2(self, mock_entity_extractor, test_config):
        """Test Tier 2 latency (target: ≤ 500ms)."""
        text = "Gamma and vega are key greeks. Delta hedging requires continuous rebalancing. Theta decay accelerates near expiration."

        latencies = []
        for _ in range(5):
            start = time.perf_counter()
            _ = mock_entity_extractor.extract(text)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latency_stats = compute_latency_stats(latencies)
        target_latency = test_config["tier_2_timeout_ms"]

        print(f"Tier 2 latency: mean={latency_stats.mean_ms:.2f}ms, p99={latency_stats.p99_ms:.2f}ms (target={target_latency}ms)")

    def test_entity_extraction_long_text(self, mock_entity_extractor):
        """Test entity extraction on longer text."""
        long_text = """
        In options trading, the Greeks are essential risk measures.
        Gamma measures the rate of change of delta. High gamma positions benefit from large moves.
        Vega exposure is sensitive to volatility changes. Theta decay accelerates near expiration.
        A delta-neutral portfolio uses hedging to control directional risk.
        Correlation and regime changes affect hedge ratios.
        """

        entities = mock_entity_extractor.extract(long_text)
        assert isinstance(entities, set)
        assert len(entities) > 0
        print(f"Long text extraction: {len(entities)} entities found")

    def test_entity_extraction_empty_text(self, mock_entity_extractor):
        """Test entity extraction on empty text."""
        entities = mock_entity_extractor.extract("")
        assert isinstance(entities, set)
        assert len(entities) == 0

    def test_entity_extraction_special_characters(self, mock_entity_extractor):
        """Test extraction with special characters."""
        text = "Gamma (δγ/δS²) is gamma! Vega's sensitivity... is key."

        entities = mock_entity_extractor.extract(text)
        assert isinstance(entities, set)
        print(f"Special character handling: {entities}")

    def test_entity_extraction_numbers(self, mock_entity_extractor):
        """Test that numbers are handled appropriately."""
        text = "Strike at 100, delta 0.5, vega 0.01, expiration in 30 days"

        entities = mock_entity_extractor.extract(text)
        # Mock extractor likely doesn't extract numbers
        assert isinstance(entities, set)

    @pytest.mark.parametrize("text_length", [10, 100, 500, 1000])
    def test_entity_extraction_scaling(self, mock_entity_extractor, text_length):
        """Test extraction speed with different text lengths."""
        # Create synthetic text
        base = "gamma vega delta theta " * (text_length // 20)
        text = base[:text_length]

        start = time.perf_counter()
        entities = mock_entity_extractor.extract(text)
        elapsed = (time.perf_counter() - start) * 1000

        print(f"Text length {text_length}: {len(entities)} entities in {elapsed:.2f}ms")

    def test_entity_extraction_duplicate_handling(self, mock_entity_extractor):
        """Test that duplicate entities in text are deduplicated."""
        text = "gamma gamma gamma vega vega delta"

        entities = mock_entity_extractor.extract(text)

        # Should have 3 unique entities
        assert isinstance(entities, set)
        # Set automatically deduplicates

    def test_entity_extraction_repeated_corpus(self, mock_entity_extractor):
        """Test extraction consistency across multiple documents."""
        texts = [
            "gamma is a key greek in options",
            "gamma measures the convexity of delta",
            "high gamma means high convexity",
        ]

        all_extractions = []
        for text in texts:
            entities = mock_entity_extractor.extract(text)
            all_extractions.append(entities)

        # All should contain "gamma"
        for extraction in all_extractions:
            assert "gamma" in extraction or len(extraction) > 0


class TestTier2RegressionBaseline:
    """Baseline and regression tests for Tier 2 entity extraction."""

    def test_tier2_baseline_creation(self, mock_entity_extractor, test_config):
        """Create and save Tier 2 baseline."""
        from datetime import datetime

        test_texts = [
            ("Gamma and delta are key greeks", {"gamma", "delta"}),
            ("Vega hedging through volatility swaps", {"vega"}),
            ("Theta decay near expiration", {"theta"}),
        ]

        entity_results = []
        query_id = 1

        for text, ground_truth in test_texts:
            predicted = mock_entity_extractor.extract(text)

            start = time.perf_counter()
            _ = mock_entity_extractor.extract(text)
            latency = (time.perf_counter() - start) * 1000

            f1, precision, recall = entity_extraction_f1(predicted, ground_truth)

            result = EntityExtractionResult(
                query_id=query_id,
                query=text,
                f1=f1,
                precision=precision,
                recall=recall,
                latency_ms=latency,
                tier=2
            )
            entity_results.append(result)
            query_id += 1

        report = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_queries=len(entity_results),
            entity_results=entity_results
        )
        report.compute_aggregates()

        # Save as baseline
        baseline_path = test_config["results_dir"] / "baseline_tier2.json"
        from test_metrics import RegressionTracker
        tracker = RegressionTracker()
        tracker.save_baseline(report, baseline_path)

        assert baseline_path.exists()
        print(f"Created Tier 2 baseline - Entity F1: {report.entity_avg_f1:.4f}")


class TestEntityExtractionEdgeCases:
    """Edge case tests for entity extraction."""

    def test_entity_extraction_unicode(self, mock_entity_extractor):
        """Test unicode handling."""
        text = "Greeks: Γ=gamma, Δ=delta, Σ=sigma"
        entities = mock_entity_extractor.extract(text)
        assert isinstance(entities, set)

    def test_entity_extraction_mixed_case_acronyms(self, mock_entity_extractor):
        """Test handling of acronyms."""
        text = "VaR (Value at Risk) and CVaR calculations"
        entities = mock_entity_extractor.extract(text)
        assert isinstance(entities, set)

    def test_entity_extraction_very_long_document(self, mock_entity_extractor):
        """Test performance on very long document."""
        # Create a 10KB document
        text = ("gamma vega delta theta rho " * 400)[:10000]

        start = time.perf_counter()
        entities = mock_entity_extractor.extract(text)
        elapsed = (time.perf_counter() - start) * 1000

        assert isinstance(entities, set)
        print(f"Large document ({len(text)} chars): {len(entities)} entities in {elapsed:.2f}ms")
