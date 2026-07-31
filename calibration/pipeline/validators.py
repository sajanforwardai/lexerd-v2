"""Input/output validation for pipeline execution."""

import logging
from typing import List, Dict, Any, Tuple

from calibration.models.thesis import PropertyProfile, ScoreResult, ThesisConfig

logger = logging.getLogger(__name__)


class InputValidator:
    """Validates pipeline input data."""

    @staticmethod
    def validate_property(prop: PropertyProfile) -> Tuple[bool, List[str]]:
        """
        Validate a single property.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Required fields
        if not prop.property_id:
            errors.append("property_id is required")
        if not prop.property_name:
            errors.append("property_name is required")
        if not prop.city:
            errors.append("city is required")
        if not prop.state:
            errors.append("state is required")

        # Numeric constraints
        if prop.units <= 0:
            errors.append(f"units must be positive (got {prop.units})")
        if prop.units > 10000:
            errors.append(f"units seems unreasonably high ({prop.units})")

        # Occupancy validation (0.0–1.0)
        if prop.occupancy < 0.0 or prop.occupancy > 1.0:
            errors.append(f"occupancy must be 0.0–1.0 (got {prop.occupancy})")
        if prop.occupancy == 0.0:
            errors.append("occupancy is 0% (suspicious)")
        if prop.occupancy == 1.0:
            errors.append("occupancy is 100% (may be unrealistic)")

        # Expense ratio validation (0.0–1.0)
        if prop.expense_ratio < 0.0 or prop.expense_ratio > 1.0:
            errors.append(f"expense_ratio must be 0.0–1.0 (got {prop.expense_ratio})")
        if prop.market_expense_ratio < 0.0 or prop.market_expense_ratio > 1.0:
            errors.append(f"market_expense_ratio must be 0.0–1.0 (got {prop.market_expense_ratio})")

        # Year built validation
        if prop.year_built < 1900 or prop.year_built > 2025:
            errors.append(f"year_built seems invalid ({prop.year_built})")

        # Rent validation
        if prop.avg_rent_per_unit < 0:
            errors.append(f"avg_rent_per_unit must be non-negative (got {prop.avg_rent_per_unit})")
        if prop.market_rent_per_unit is not None and prop.market_rent_per_unit < 0:
            errors.append(f"market_rent_per_unit must be non-negative (got {prop.market_rent_per_unit})")

        # Optional enriched fields validation
        if prop.employment_growth_yoy is not None:
            if prop.employment_growth_yoy < -0.5 or prop.employment_growth_yoy > 0.5:
                errors.append(f"employment_growth_yoy seems extreme ({prop.employment_growth_yoy})")

        if prop.population_growth_yoy is not None:
            if prop.population_growth_yoy < -0.2 or prop.population_growth_yoy > 0.2:
                errors.append(f"population_growth_yoy seems extreme ({prop.population_growth_yoy})")

        if prop.market_cap_rate is not None:
            if prop.market_cap_rate < 0.01 or prop.market_cap_rate > 0.20:
                errors.append(f"market_cap_rate seems extreme ({prop.market_cap_rate:.2%})")

        return len(errors) == 0, errors

    @staticmethod
    def validate_properties(properties: List[PropertyProfile]) -> Dict[str, Any]:
        """
        Validate a batch of properties.

        Returns:
            {
                'valid_count': int,
                'invalid_count': int,
                'total_count': int,
                'details': {property_id: {'valid': bool, 'errors': [str]}},
                'critical_errors': [str],
            }
        """
        if not properties:
            return {
                'valid_count': 0,
                'invalid_count': 0,
                'total_count': 0,
                'details': {},
                'critical_errors': ['No properties provided'],
            }

        details = {}
        valid_count = 0
        critical_errors = []

        for prop in properties:
            is_valid, errors = InputValidator.validate_property(prop)
            details[prop.property_id] = {'valid': is_valid, 'errors': errors}
            if is_valid:
                valid_count += 1

        invalid_count = len(properties) - valid_count

        # Check for critical issues
        if valid_count == 0:
            critical_errors.append("No valid properties in batch")
        if invalid_count > len(properties) * 0.5:
            critical_errors.append(f"More than 50% of properties are invalid ({invalid_count}/{len(properties)})")

        return {
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'total_count': len(properties),
            'details': details,
            'critical_errors': critical_errors,
        }


class OutputValidator:
    """Validates pipeline output data."""

    @staticmethod
    def validate_score_result(score: ScoreResult) -> Tuple[bool, List[str]]:
        """
        Validate a scored property result.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Score ranges (0–100)
        if not 0 <= score.market_score <= 100:
            errors.append(f"market_score out of range: {score.market_score}")
        if not 0 <= score.model_score <= 100:
            errors.append(f"model_score out of range: {score.model_score}")
        if not 0 <= score.management_score <= 100:
            errors.append(f"management_score out of range: {score.management_score}")
        if not 0 <= score.final_fit_score <= 100:
            errors.append(f"final_fit_score out of range: {score.final_fit_score}")

        # Confidence grade must be A, B, C, or D
        if score.confidence_grade not in ['A', 'B', 'C', 'D']:
            errors.append(f"confidence_grade invalid: {score.confidence_grade}")

        # Required text fields
        if not score.fit_rationale:
            errors.append("fit_rationale is empty")
        if score.key_strengths is None:
            errors.append("key_strengths is None")
        if score.key_weaknesses is None:
            errors.append("key_weaknesses is None")

        # Breakdowns must be dictionaries
        if not isinstance(score.market_breakdown, dict):
            errors.append("market_breakdown is not a dict")
        if not isinstance(score.model_breakdown, dict):
            errors.append("model_breakdown is not a dict")
        if not isinstance(score.management_breakdown, dict):
            errors.append("management_breakdown is not a dict")

        # Breakdown scores should sum approximately to main score
        market_total = sum(score.market_breakdown.values())
        if market_total > 105:  # Allow 5 point tolerance for rounding
            errors.append(f"market_breakdown sum ({market_total}) exceeds 100")

        model_total = sum(score.model_breakdown.values())
        if model_total > 105:
            errors.append(f"model_breakdown sum ({model_total}) exceeds 100")

        management_total = sum(score.management_breakdown.values())
        if management_total > 105:
            errors.append(f"management_breakdown sum ({management_total}) exceeds 100")

        return len(errors) == 0, errors

    @staticmethod
    def validate_scored_results(results: List[ScoreResult]) -> Dict[str, Any]:
        """
        Validate a batch of scored results.

        Returns validation summary.
        """
        if not results:
            return {
                'valid_count': 0,
                'invalid_count': 0,
                'total_count': 0,
                'details': {},
            }

        details = {}
        valid_count = 0

        for result in results:
            is_valid, errors = OutputValidator.validate_score_result(result)
            details[result.property_id] = {'valid': is_valid, 'errors': errors}
            if is_valid:
                valid_count += 1

        return {
            'valid_count': valid_count,
            'invalid_count': len(results) - valid_count,
            'total_count': len(results),
            'details': details,
        }


class DataQualityValidator:
    """Validates data quality metrics across pipeline."""

    @staticmethod
    def check_coverage(properties: List[PropertyProfile]) -> Dict[str, float]:
        """
        Calculate data coverage by field.

        Returns dict of field_name -> coverage_pct (0–100)
        """
        if not properties:
            return {}

        total = len(properties)
        coverage = {}

        # Check enrichment fields
        coverage['employment_growth'] = (
            sum(1 for p in properties if p.employment_growth_yoy is not None) / total * 100
        )
        coverage['population_growth'] = (
            sum(1 for p in properties if p.population_growth_yoy is not None) / total * 100
        )
        coverage['market_cap_rate'] = (
            sum(1 for p in properties if p.market_cap_rate is not None) / total * 100
        )
        coverage['employment_anchors'] = (
            sum(1 for p in properties if p.employment_anchors) / total * 100
        )
        coverage['market_rent'] = (
            sum(1 for p in properties if p.market_rent_per_unit is not None) / total * 100
        )
        coverage['dscr'] = (
            sum(1 for p in properties if p.dscr is not None) / total * 100
        )

        return coverage

    @staticmethod
    def check_score_distribution(results: List[ScoreResult]) -> Dict[str, Any]:
        """
        Analyze score distribution.

        Returns statistics on score distribution for quality assessment.
        """
        if not results:
            return {'error': 'No results to analyze'}

        final_scores = [r.final_fit_score for r in results]
        grade_counts = {}
        for grade in ['A', 'B', 'C', 'D']:
            grade_counts[grade] = sum(1 for r in results if r.confidence_grade == grade)

        return {
            'score_min': min(final_scores),
            'score_max': max(final_scores),
            'score_mean': sum(final_scores) / len(final_scores),
            'grade_distribution': grade_counts,
            'grade_a_pct': grade_counts['A'] / len(results) * 100,
            'grade_b_pct': grade_counts['B'] / len(results) * 100,
            'grade_c_pct': grade_counts['C'] / len(results) * 100,
            'grade_d_pct': grade_counts['D'] / len(results) * 100,
        }

    @staticmethod
    def check_thesis_alignment(
        properties: List[PropertyProfile],
        results: List[ScoreResult],
        thesis: ThesisConfig,
    ) -> Dict[str, Any]:
        """
        Check if scoring aligns with thesis constraints.

        Returns issues that may indicate scoring problems.
        """
        issues = []

        # Check if any A-graded properties violate hard constraints
        a_grades = [r for r in results if r.confidence_grade == 'A']
        for grade_result in a_grades:
            # Find corresponding property
            prop = next((p for p in properties if p.property_id == grade_result.property_id), None)
            if not prop:
                continue

            # Check thesis constraints
            if prop.units < thesis.min_units or prop.units > thesis.max_units:
                issues.append(f"{prop.property_id}: A-grade but units ({prop.units}) outside thesis range")

            if prop.occupancy < thesis.min_occupancy or prop.occupancy > thesis.max_occupancy:
                issues.append(f"{prop.property_id}: A-grade but occupancy ({prop.occupancy:.1%}) outside thesis range")

        return {
            'alignment_issues': issues,
            'issue_count': len(issues),
        }


class ThesisValidator:
    """Validates thesis configuration."""

    @staticmethod
    def validate_thesis(thesis: ThesisConfig) -> Tuple[bool, List[str]]:
        """
        Validate thesis configuration consistency.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Market parameters
        if thesis.min_employment_growth_yoy < 0 or thesis.min_employment_growth_yoy > 0.2:
            errors.append(f"min_employment_growth_yoy seems extreme: {thesis.min_employment_growth_yoy}")

        if thesis.min_population_growth_yoy < 0 or thesis.min_population_growth_yoy > 0.2:
            errors.append(f"min_population_growth_yoy seems extreme: {thesis.min_population_growth_yoy}")

        if thesis.min_cap_rate_spread_bps < 0 or thesis.min_cap_rate_spread_bps > 500:
            errors.append(f"min_cap_rate_spread_bps seems extreme: {thesis.min_cap_rate_spread_bps}")

        # Model parameters
        if thesis.min_units > thesis.max_units:
            errors.append(f"min_units ({thesis.min_units}) > max_units ({thesis.max_units})")

        if thesis.min_property_age_years > thesis.max_property_age_years:
            errors.append(f"min_property_age_years > max_property_age_years")

        # Occupancy
        if thesis.min_occupancy > thesis.max_occupancy:
            errors.append(f"min_occupancy ({thesis.min_occupancy}) > max_occupancy ({thesis.max_occupancy})")

        if thesis.min_occupancy < 0.5 or thesis.max_occupancy > 1.0:
            errors.append(f"Occupancy range {thesis.min_occupancy}–{thesis.max_occupancy} seems invalid")

        # Financial constraints
        if thesis.min_equity > thesis.max_equity:
            errors.append(f"min_equity > max_equity")

        if thesis.min_capital > thesis.max_capital:
            errors.append(f"min_capital > max_capital")

        # Weights must sum to 1.0 (allow 0.01 tolerance for floating point)
        weight_sum = thesis.market_weight + thesis.model_weight + thesis.management_weight
        if abs(weight_sum - 1.0) > 0.01:
            errors.append(f"Scoring weights sum to {weight_sum} (expected 1.0)")

        # Target markets
        if not thesis.target_markets:
            errors.append("target_markets is empty")

        return len(errors) == 0, errors
