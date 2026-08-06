"""Address Discovery Orchestrator - Coordinates Tier 1 sources"""

import sys
from pathlib import Path
import json
import logging
from typing import Optional, List
from datetime import datetime

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "maturity-radar"))

from .sources.county_assessor import CountyAssessorManager
from .sources.real_estate_apis import RealEstateAPIManager
from .validators.address_validator import AddressValidator, ConfidenceScorer
from .config import (
    COUNTY_ASSESSOR_CONFIG, REAL_ESTATE_APIS, VALIDATION_CONFIG,
    OUTPUT_CONFIG, LOGGING_CONFIG
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG["log_level"]),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGGING_CONFIG["log_file"])
    ]
)
logger = logging.getLogger(__name__)


class AddressDiscoveryOrchestrator:
    """Main orchestrator for Tier 1 address discovery"""

    def __init__(self):
        """Initialize all Tier 1 sources"""
        logger.info("Initializing Address Discovery Orchestrator (Tier 1)")

        self.county_manager = CountyAssessorManager(COUNTY_ASSESSOR_CONFIG)
        self.api_manager = RealEstateAPIManager(REAL_ESTATE_APIS)

        self.results = []
        self.cache = {}

    def discover_addresses(self, loans: List[dict], output_file: Optional[str] = None) -> dict:
        """Discover addresses for all loans using Tier 1 sources

        Args:
            loans: List of loan objects with {property_name, city, state, units, county}
            output_file: Optional output file for results

        Returns:
            {total: N, found: N, not_found: N, confidence_scores: {...}, results: [...]}
        """
        logger.info(f"Starting address discovery for {len(loans)} loans")

        found_count = 0
        not_found = []
        results = []

        for i, loan in enumerate(loans, 1):
            pct = (i / len(loans)) * 100
            property_name = loan.get("property_name", "")
            city = loan.get("city", "")
            state = loan.get("state", "")
            county = loan.get("county", "")
            units = loan.get("units")

            print(f"[{i:3d}/{len(loans)}] {pct:5.1f}% | {property_name:40s} | {city:15s}, {state}", end=" | ", flush=True)

            # Try to find address
            result = self._search_property(property_name, city, state, county, units)

            if result and result.get("found"):
                found_count += 1
                print("✓ FOUND")
                results.append(result)
            else:
                not_found.append({
                    "property_name": property_name,
                    "city": city,
                    "state": state,
                })
                print("✗ NOT FOUND")

            # Progress summary every 50
            if i % 50 == 0:
                print(f"  Progress: {found_count}/{i} found ({found_count/i*100:.1f}%)\n")

        # Summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total": len(loans),
            "found": found_count,
            "not_found": len(not_found),
            "coverage": f"{found_count/len(loans)*100:.1f}%",
            "results": results,
            "not_found_list": not_found,
        }

        if output_file:
            self._save_results(summary, output_file)

        return summary

    def _search_property(self, property_name: str, city: str, state: str,
                        county: str, units: Optional[int] = None) -> Optional[dict]:
        """Search for single property using Tier 1 sources

        Args:
            property_name: Property name
            city: City
            state: State code
            county: County name
            units: Unit count (for validation)

        Returns:
            {found: bool, address, city, state, phone, sources, confidence_score} or None
        """
        candidates = []

        # Source 1: County Assessor
        if county and state:
            county_result = self.county_manager.search(county, state, property_name, city)
            if county_result:
                candidates.append(county_result)

        # Source 2: Real Estate APIs
        api_results = self.api_manager.search(property_name, city, state, units)
        candidates.extend(api_results)

        if not candidates:
            return None

        # Validate and score all candidates
        validator = AddressValidator({
            "property_name": property_name,
            "city": city,
            "state": state,
            "units": units,
            "county": county,
        })

        scored_results = []
        for candidate in candidates:
            validation = validator.validate_address(
                address=candidate.get("address", ""),
                city=candidate.get("city", city),
                state=candidate.get("state", state),
                units=candidate.get("units"),
                source=candidate.get("source", "unknown")
            )

            scored_results.append({
                **candidate,
                "confidence_score": validation.confidence_score,
                "is_valid": validation.is_valid,
                "validation_issues": validation.issues,
            })

        # Select best result
        best = ConfidenceScorer.select_best(scored_results, min_confidence=VALIDATION_CONFIG["min_confidence_score"])

        if best:
            return {
                "found": True,
                "property_name": property_name,
                "address": best.get("address"),
                "city": best.get("city"),
                "state": best.get("state"),
                "phone": best.get("phone"),
                "confidence_score": best.get("confidence_score"),
                "source": best.get("source"),
                "sources_tried": [c.get("source") for c in scored_results],
            }

        return None

    def _save_results(self, summary: dict, output_file: str):
        """Save results to JSON file

        Args:
            summary: Summary dictionary
            output_file: Output file path
        """
        try:
            with open(output_file, "w") as f:
                json.dump(summary, f, indent=2, default=str)
            logger.info(f"Results saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")

    def update_cache(self, results: List[dict], cache_file: Optional[str] = None):
        """Update address verification cache with found addresses

        Args:
            results: List of found addresses
            cache_file: Cache file path (defaults to config)
        """
        if not cache_file:
            cache_file = OUTPUT_CONFIG["cache_file"]

        logger.info(f"Updating cache at {cache_file}")

        # Load existing cache
        cache = {}
        cache_path = Path(cache_file)
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    cache = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load existing cache: {e}")

        # Add new results
        for result in results:
            if result.get("found"):
                key = f"{result.get('property_name')}|{result.get('city')}|{result.get('state')}".lower()
                cache[key] = {
                    "address": result.get("address"),
                    "city": result.get("city"),
                    "state": result.get("state"),
                    "phone": result.get("phone"),
                    "confidence_score": result.get("confidence_score"),
                    "source": result.get("source"),
                    "property_name": result.get("property_name"),
                    "verified_at": datetime.now().isoformat(),
                }

        # Save updated cache
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(cache, f, indent=2, default=str)
            logger.info(f"Cache updated with {len(results)} new entries")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
