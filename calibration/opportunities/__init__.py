"""
Opportunities auto-population module.

LCMV-68: Auto-Populate Opportunities from SEC/B3 Data

This package provides:
- OpportunityLoader: Unified loader for B3 and SEC opportunities
- ScheduledUpdater: Background scheduler for automatic data refresh
- CacheManager: Cache management for opportunity data
"""

from .opportunity_loader import (
    OpportunityLoader,
    load_opportunities,
    get_data_freshness,
    get_tier_breakdown,
)

from .cache_manager import CacheManager

from .scheduled_updates import (
    ScheduledUpdater,
    get_global_scheduler,
    start_scheduler,
    stop_scheduler,
)

__all__ = [
    'OpportunityLoader',
    'load_opportunities',
    'get_data_freshness',
    'get_tier_breakdown',
    'CacheManager',
    'ScheduledUpdater',
    'get_global_scheduler',
    'start_scheduler',
    'stop_scheduler',
]
