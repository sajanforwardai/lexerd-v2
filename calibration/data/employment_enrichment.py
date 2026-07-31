"""Employment data enrichment module (LCMV-23)."""

import logging
from copy import deepcopy
from typing import Optional

from calibration.data.bls_client import BLSClient
from calibration.models.thesis import PropertyProfile

logger = logging.getLogger(__name__)


def enrich_property_with_employment(
    prop: PropertyProfile,
    bls_client: BLSClient,
    confidence_threshold: float = 0.0,
) -> PropertyProfile:
    """
    Enrich a single property with employment growth data from BLS.

    Args:
        prop: PropertyProfile to enrich
        bls_client: BLSClient instance
        confidence_threshold: Minimum confidence level (0.0–1.0)

    Returns:
        New PropertyProfile with employment_growth_yoy populated, or original if no data
    """
    # Create a copy to avoid modifying the original
    enriched = deepcopy(prop)

    try:
        # Skip if already enriched
        if enriched.employment_growth_yoy is not None:
            return enriched

        # Skip if missing location info
        if not enriched.city or not enriched.state:
            logger.debug(f"Skipping enrichment for {enriched.property_id}: missing city/state")
            return enriched

        # Get MSA code
        msa_code = bls_client.get_msa_by_city_state(enriched.city, enriched.state)
        if not msa_code:
            logger.debug(
                f"No MSA mapping for {enriched.city}, {enriched.state} "
                f"(property: {enriched.property_id})"
            )
            return enriched

        # Fetch employment growth
        data = bls_client.fetch_employment_growth(msa_code)
        if not data:
            logger.warning(
                f"Failed to fetch BLS data for {enriched.city}, {enriched.state} "
                f"(MSA: {msa_code}, property: {enriched.property_id})"
            )
            return enriched

        # Populate employment growth
        enriched.employment_growth_yoy = data.get("employment_growth_yoy")
        cache_age = bls_client.get_cache_age(msa_code)

        logger.info(
            f"Enriched {enriched.property_id} with employment growth "
            f"{enriched.employment_growth_yoy:.4f} from {enriched.city}, {enriched.state}"
            + (f" (cache age: {cache_age}m)" if cache_age is not None else "")
        )

        return enriched

    except Exception as e:
        logger.error(f"Error enriching property {prop.property_id}: {e}")
        # Return original on error
        return prop


def enrich_batch(
    properties: list[PropertyProfile],
    bls_client: BLSClient,
    confidence_threshold: float = 0.0,
) -> list[PropertyProfile]:
    """
    Enrich a batch of properties with employment growth data.

    Args:
        properties: List of PropertyProfile objects
        bls_client: BLSClient instance
        confidence_threshold: Minimum confidence level

    Returns:
        List of enriched PropertyProfile objects
    """
    enriched = []
    for prop in properties:
        try:
            enriched_prop = enrich_property_with_employment(
                prop, bls_client, confidence_threshold
            )
            enriched.append(enriched_prop)
        except Exception as e:
            logger.error(f"Error enriching property {prop.property_id}: {e}")
            # Return original on error
            enriched.append(prop)

    logger.info(f"Enriched {len(enriched)} properties with employment data")
    return enriched


def estimate_msa_from_property(prop: PropertyProfile) -> Optional[str]:
    """
    Estimate MSA code from property location.

    Args:
        prop: PropertyProfile with city/state

    Returns:
        MSA code or None if not found
    """
    if not prop.city or not prop.state:
        return None

    # Would use more sophisticated matching in production
    # For now, relies on BLSClient.get_msa_by_city_state
    from calibration.data.bls_client import MSA_CODES

    key = (prop.city.title(), prop.state.upper())
    return MSA_CODES.get(key)
