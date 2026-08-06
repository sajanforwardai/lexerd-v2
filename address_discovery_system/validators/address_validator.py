"""Address Validation and Confidence Scoring"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    """Result of address validation"""
    is_valid: bool
    confidence_score: float
    issues: list = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class AddressValidator:
    """Validate and score addresses for property matching"""

    def __init__(self, property_data: dict):
        """Initialize validator with property loan data

        Args:
            property_data: {name, city, state, units, county}
        """
        self.property_name = property_data.get("property_name")
        self.city = property_data.get("city")
        self.state = property_data.get("state")
        self.units = property_data.get("units")
        self.county = property_data.get("county")

    def validate_address(self, address: str, city: str, state: str,
                        units: Optional[int] = None, source: str = "unknown") -> ValidationResult:
        """Validate and score an address result

        Args:
            address: Street address
            city: City from result
            state: State from result
            units: Unit count from result (optional)
            source: Source of address (county_api, zillow, etc.)

        Returns:
            ValidationResult with confidence score
        """
        issues = []
        confidence = 1.0

        # 1. Format validation
        if not self._is_valid_address_format(address):
            issues.append("Invalid address format")
            confidence -= 0.15

        # 2. City matching
        if not self._city_matches(city):
            issues.append(f"City mismatch: expected {self.city}, got {city}")
            confidence -= 0.20

        # 3. State matching
        if state.upper() != self.state.upper():
            issues.append(f"State mismatch: expected {self.state}, got {state}")
            confidence -= 0.25

        # 4. Unit count matching (if available)
        if units and self.units:
            if not self._units_match(units):
                issues.append(f"Unit count mismatch: expected {self.units}, got {units}")
                confidence -= 0.15  # Lower penalty, might be different property with same name
            else:
                confidence += 0.05  # Bonus for unit count match

        # 5. Source confidence
        source_confidence = {
            "county_assessor": 0.95,
            "zillow": 0.85,
            "apartments_list": 0.80,
            "google_maps": 0.85,
            "cmbs_pdf": 0.75,
            "loan_id": 0.90,
        }
        source_conf = source_confidence.get(source, 0.70)
        confidence *= source_conf

        # Clamp confidence to 0-1
        confidence = max(0.0, min(1.0, confidence))

        is_valid = confidence >= 0.70 and len([i for i in issues if "mismatch" in i]) <= 1

        return ValidationResult(
            is_valid=is_valid,
            confidence_score=confidence,
            issues=issues
        )

    def _is_valid_address_format(self, address: str) -> bool:
        """Check if address has valid format (number + street name)"""
        # Pattern: number + street name (must have at least number and street)
        pattern = r'^\d+\s+[\w\s]+(St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Lane|Ln|Way|Court|Ct|Circle|Cir|Place|Pl|Square|Sq|Trail|Tr|Row)'
        return bool(re.search(pattern, address, re.IGNORECASE))

    def _city_matches(self, result_city: str) -> bool:
        """Check if cities match (exact or close match)"""
        if not result_city:
            return False

        # Exact match
        if result_city.lower() == self.city.lower():
            return True

        # Close match (within 2 character edits)
        if self._edit_distance(result_city.lower(), self.city.lower()) <= 2:
            return True

        return False

    def _units_match(self, result_units: int, tolerance: float = 0.05) -> bool:
        """Check if unit counts match (within 5% tolerance)"""
        if not self.units or not result_units:
            return False

        diff = abs(result_units - self.units)
        tolerance_amount = self.units * tolerance

        return diff <= tolerance_amount

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein edit distance between two strings"""
        if len(s1) < len(s2):
            return AddressValidator._edit_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]


class ConfidenceScorer:
    """Score and rank multiple address results"""

    @staticmethod
    def rank_results(results: list) -> list:
        """Rank results by confidence score

        Args:
            results: List of {address, city, state, confidence_score, source}

        Returns:
            Sorted list by confidence score (highest first)
        """
        return sorted(results, key=lambda r: r["confidence_score"], reverse=True)

    @staticmethod
    def select_best(results: list, min_confidence: float = 0.70) -> Optional[dict]:
        """Select best result if above minimum confidence

        Args:
            results: List of validation results
            min_confidence: Minimum confidence threshold

        Returns:
            Best result or None
        """
        if not results:
            return None

        ranked = ConfidenceScorer.rank_results(results)
        best = ranked[0]

        if best["confidence_score"] >= min_confidence:
            return best

        return None
