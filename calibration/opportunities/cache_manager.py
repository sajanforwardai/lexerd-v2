"""
Cache Management for Opportunity Data

LCMV-68: Cache management for auto-populated opportunities

Manages caching of B3 and SEC loan data with:
- Parquet/SQLite storage
- TTL (time-to-live) tracking
- Manual clear/refresh
- Cache hit/miss statistics

Author: Sajan Goswami (Lexerd Capital Management)
Date: 2026-07-31
"""

import logging
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CacheManager:
    """
    Manages caching of opportunity data.

    Supports:
    - Parquet format (efficient columnar storage)
    - SQLite for structured queries
    - Metadata tracking (age, hit/miss stats)
    - TTL management (auto-invalidation)
    - Manual clear/refresh
    """

    # Default cache TTL: 24 hours for B3, 12 hours for SEC
    DEFAULT_B3_TTL_HOURS = 24
    DEFAULT_SEC_TTL_HOURS = 12

    def __init__(self, cache_dir: Path = None):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory for cache files.
                      Defaults to calibration/opportunities/cache/
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent / "cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache file paths
        self.b3_cache_file = self.cache_dir / "b3_loans.parquet"
        self.sec_cache_file = self.cache_dir / "sec_loans.parquet"
        self.unified_cache_file = self.cache_dir / "unified_opportunities.parquet"
        self.stats_file = self.cache_dir / "cache_stats.json"
        self.metadata_file = self.cache_dir / "metadata.json"

        logger.info(f"CacheManager initialized (cache_dir={cache_dir})")

    def load_b3_cache(self) -> Tuple[Optional[pd.DataFrame], int]:
        """
        Load B3 loans from cache.

        Returns:
            Tuple of (DataFrame, age_in_minutes)
            Returns (None, -1) if cache missing or expired
        """
        try:
            if not self.b3_cache_file.exists():
                self._record_cache_miss('b3')
                return None, -1

            df = pd.read_parquet(self.b3_cache_file)
            age_minutes = self._get_cache_age_minutes(self.b3_cache_file)

            # Check if expired
            if age_minutes > (self.DEFAULT_B3_TTL_HOURS * 60):
                logger.warning(f"B3 cache expired ({age_minutes} minutes old)")
                self._record_cache_miss('b3')
                return None, age_minutes

            self._record_cache_hit('b3')
            logger.info(f"Loaded {len(df)} B3 loans from cache ({age_minutes} min old)")
            return df, age_minutes

        except Exception as e:
            logger.error(f"Error loading B3 cache: {e}")
            return None, -1

    def load_sec_cache(self) -> Tuple[Optional[pd.DataFrame], int]:
        """
        Load SEC loans from cache.

        Returns:
            Tuple of (DataFrame, age_in_minutes)
            Returns (None, -1) if cache missing or expired
        """
        try:
            if not self.sec_cache_file.exists():
                self._record_cache_miss('sec')
                return None, -1

            df = pd.read_parquet(self.sec_cache_file)
            age_minutes = self._get_cache_age_minutes(self.sec_cache_file)

            # Check if expired
            if age_minutes > (self.DEFAULT_SEC_TTL_HOURS * 60):
                logger.warning(f"SEC cache expired ({age_minutes} minutes old)")
                self._record_cache_miss('sec')
                return None, age_minutes

            self._record_cache_hit('sec')
            logger.info(f"Loaded {len(df)} SEC loans from cache ({age_minutes} min old)")
            return df, age_minutes

        except Exception as e:
            logger.error(f"Error loading SEC cache: {e}")
            return None, -1

    def load_unified_cache(self) -> Tuple[Optional[pd.DataFrame], int]:
        """
        Load unified opportunities from cache.

        Returns:
            Tuple of (DataFrame, age_in_minutes)
            Returns (None, -1) if cache missing
        """
        try:
            if not self.unified_cache_file.exists():
                return None, -1

            df = pd.read_parquet(self.unified_cache_file)
            age_minutes = self._get_cache_age_minutes(self.unified_cache_file)

            logger.info(f"Loaded {len(df)} unified opportunities from cache ({age_minutes} min old)")
            return df, age_minutes

        except Exception as e:
            logger.error(f"Error loading unified cache: {e}")
            return None, -1

    def save_b3_cache(self, df: pd.DataFrame):
        """Save B3 loans to cache."""
        try:
            df.to_parquet(self.b3_cache_file)
            self._update_metadata('b3_last_update', datetime.now().isoformat())
            logger.info(f"Saved {len(df)} B3 loans to cache")
        except Exception as e:
            logger.error(f"Error saving B3 cache: {e}")

    def save_sec_cache(self, df: pd.DataFrame):
        """Save SEC loans to cache."""
        try:
            df.to_parquet(self.sec_cache_file)
            self._update_metadata('sec_last_update', datetime.now().isoformat())
            logger.info(f"Saved {len(df)} SEC loans to cache")
        except Exception as e:
            logger.error(f"Error saving SEC cache: {e}")

    def save_unified_cache(self, df: pd.DataFrame):
        """Save unified opportunities to cache."""
        try:
            df.to_parquet(self.unified_cache_file)
            logger.info(f"Saved {len(df)} unified opportunities to cache")
        except Exception as e:
            logger.error(f"Error saving unified cache: {e}")

    def clear_cache(self, source: str = 'all'):
        """
        Clear cache (manual refresh trigger).

        Args:
            source: 'b3', 'sec', 'unified', or 'all'
        """
        try:
            if source in ('b3', 'all'):
                if self.b3_cache_file.exists():
                    self.b3_cache_file.unlink()
                    logger.info("Cleared B3 cache")

            if source in ('sec', 'all'):
                if self.sec_cache_file.exists():
                    self.sec_cache_file.unlink()
                    logger.info("Cleared SEC cache")

            if source in ('unified', 'all'):
                if self.unified_cache_file.exists():
                    self.unified_cache_file.unlink()
                    logger.info("Cleared unified cache")

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def get_cache_age(self) -> Dict[str, int]:
        """
        Return cache age in minutes for each source.

        Returns:
            Dict with 'b3', 'sec', 'unified' keys (minutes, or -1 if missing)
        """
        return {
            'b3': self._get_cache_age_minutes(self.b3_cache_file),
            'sec': self._get_cache_age_minutes(self.sec_cache_file),
            'unified': self._get_cache_age_minutes(self.unified_cache_file),
        }

    def get_cache_stats(self) -> Dict:
        """Get cache hit/miss statistics."""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading cache stats: {e}")

        return {
            'b3_hits': 0,
            'b3_misses': 0,
            'sec_hits': 0,
            'sec_misses': 0,
        }

    def is_cache_fresh(self, source: str = 'all') -> bool:
        """
        Check if cache is fresh (not expired).

        Args:
            source: 'b3', 'sec', or 'all'

        Returns:
            True if cache is fresh, False otherwise
        """
        if source in ('b3', 'all'):
            age = self._get_cache_age_minutes(self.b3_cache_file)
            if age < 0 or age > (self.DEFAULT_B3_TTL_HOURS * 60):
                return False

        if source in ('sec', 'all'):
            age = self._get_cache_age_minutes(self.sec_cache_file)
            if age < 0 or age > (self.DEFAULT_SEC_TTL_HOURS * 60):
                return False

        return True

    def _get_cache_age_minutes(self, cache_file: Path) -> int:
        """Get age of cache file in minutes. Returns -1 if file missing."""
        try:
            if not cache_file.exists():
                return -1

            mtime = cache_file.stat().st_mtime
            age_seconds = (datetime.now() - datetime.fromtimestamp(mtime)).total_seconds()
            return int(age_seconds / 60)

        except Exception as e:
            logger.warning(f"Error getting cache age for {cache_file}: {e}")
            return -1

    def _record_cache_hit(self, source: str):
        """Record cache hit for statistics."""
        try:
            stats = self.get_cache_stats()
            stats[f'{source}_hits'] = stats.get(f'{source}_hits', 0) + 1
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f)
        except Exception as e:
            logger.warning(f"Error recording cache hit: {e}")

    def _record_cache_miss(self, source: str):
        """Record cache miss for statistics."""
        try:
            stats = self.get_cache_stats()
            stats[f'{source}_misses'] = stats.get(f'{source}_misses', 0) + 1
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f)
        except Exception as e:
            logger.warning(f"Error recording cache miss: {e}")

    def _update_metadata(self, key: str, value: str):
        """Update metadata file."""
        try:
            metadata = {}
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    metadata = json.load(f)

            metadata[key] = value
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"Error updating metadata: {e}")

    def get_metadata(self) -> Dict:
        """Load all metadata."""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading metadata: {e}")

        return {}
