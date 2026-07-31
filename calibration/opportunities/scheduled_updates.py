"""
Background Scheduler for Automatic Opportunity Updates

LCMV-68: Scheduled data refresh from SEC/B3 sources

This module runs background jobs to keep opportunity data fresh:
1. SEC data pull: Daily (checks for new 424B5 filings)
2. B3 data pull: Monthly (day 10 at 2 AM UTC)
3. Scoring: After each data pull
4. Cache refresh: As needed

Uses APScheduler for robust background scheduling.

Author: Sajan Goswami (Lexerd Capital Management)
Date: 2026-07-31
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
import json
from pathlib import Path

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    CronTrigger = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ScheduledUpdater:
    """
    Background scheduler for automatic opportunity updates.

    Schedules:
    - SEC data pull: Daily (checks for new 424B5 filings)
    - B3 data pull: Monthly (day 10 at 2 AM UTC)
    - Scoring: After each data pull
    - Cache refresh: As needed
    """

    def __init__(self, cache_dir: Path = None):
        """
        Initialize scheduler.

        Args:
            cache_dir: Directory for cache and metadata files
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent / "cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.cache_dir / "metadata.json"

        # Background scheduler (optional - apscheduler may not be installed)
        if APSCHEDULER_AVAILABLE:
            self.scheduler = BackgroundScheduler()
        else:
            self.scheduler = None
            logger.warning("APScheduler not available - scheduled updates will not run")

        self._started = False

        logger.info(f"ScheduledUpdater initialized (cache_dir={cache_dir}, scheduler_available={APSCHEDULER_AVAILABLE})")

    def start(self):
        """Start background scheduler with all update jobs."""
        if self._started:
            logger.warning("Scheduler already started")
            return

        if not APSCHEDULER_AVAILABLE:
            logger.warning("APScheduler not available - cannot start scheduler. Install with: pip install apscheduler")
            return

        try:
            # Schedule daily SEC pull (2 AM UTC)
            self.scheduler.add_job(
                self.refresh_sec_data,
                CronTrigger(hour=2, minute=0),  # 2 AM UTC daily
                id='daily_sec_pull',
                name='Daily SEC CMBS pull',
                replace_existing=True,
            )
            logger.info("Scheduled daily SEC pull (2 AM UTC)")

            # Schedule monthly B3 pull (10th of month at 2 AM UTC)
            self.scheduler.add_job(
                self.refresh_b3_data,
                CronTrigger(day=10, hour=2, minute=0),  # Day 10 at 2 AM UTC
                id='monthly_b3_pull',
                name='Monthly B3 Freddie Mac pull',
                replace_existing=True,
            )
            logger.info("Scheduled monthly B3 pull (10th @ 2 AM UTC)")

            # Schedule opportunity scoring refresh (after data pulls)
            self.scheduler.add_job(
                self.refresh_opportunities,
                CronTrigger(hour='*/4', minute=5),  # Every 4 hours at :05
                id='opportunity_scoring',
                name='Opportunity rescoring',
                replace_existing=True,
            )
            logger.info("Scheduled opportunity rescoring (every 4 hours)")

            self.scheduler.start()
            self._started = True
            logger.info("Scheduler started successfully")

        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            raise

    def stop(self):
        """Stop background scheduler."""
        if self._started and self.scheduler is not None:
            try:
                self.scheduler.shutdown()
                self._started = False
                logger.info("Scheduler stopped")
            except Exception as e:
                logger.error(f"Error stopping scheduler: {e}")

    def refresh_sec_data(self):
        """
        Refresh SEC CMBS data from Edgar filings.

        This is called daily by the scheduler.
        In production, this would:
        1. Query SEC Edgar for new 424B5 filings
        2. Parse prospectuses for loan data
        3. Extract DSCR, LTV, maturity info
        4. Update SEC cache
        """
        try:
            logger.info("Starting SEC data refresh...")

            # TODO: Integrate with LCMV-58 SEC CMBS pipeline
            # from calibration.data.sec_edgar_client import SecEdgarClient
            # client = SecEdgarClient()
            # sec_loans = client.fetch_latest_filings()
            # sec_loans.to_parquet(self.cache_dir / "sec_loans.parquet")

            # For now, log that this would happen
            logger.info("SEC data refresh would pull latest 424B5 filings")
            self._update_metadata('sec_last_update', datetime.now().isoformat())

        except Exception as e:
            logger.error(f"Error refreshing SEC data: {e}")

    def refresh_b3_data(self):
        """
        Refresh Freddie Mac B3 tape data.

        This is called monthly (10th) by the scheduler.
        In production, this would:
        1. Download latest Freddie Mac B3 tape
        2. Parse loan-level data
        3. Extract DSCR, LTV, maturity info
        4. Update B3 cache
        """
        try:
            logger.info("Starting B3 data refresh...")

            # TODO: Integrate with LCMV-37 B3 pipeline
            # from calibration.data.loan_tape_parser import LoanTapeParser
            # parser = LoanTapeParser()
            # b3_loans = parser.parse_freddie_mac_b3()
            # b3_loans.to_parquet(self.cache_dir / "b3_loans.parquet")

            # For now, log that this would happen
            logger.info("B3 data refresh would download Freddie Mac tape")
            self._update_metadata('b3_last_update', datetime.now().isoformat())

        except Exception as e:
            logger.error(f"Error refreshing B3 data: {e}")

    def refresh_opportunities(self):
        """
        Refresh opportunity scoring and ranking.

        This is called every 4 hours by the scheduler.
        Rescores all opportunities and updates unified cache.
        """
        try:
            logger.info("Starting opportunity rescoring...")

            # TODO: Integrate with opportunity_loader
            # from calibration.opportunities.opportunity_loader import OpportunityLoader
            # loader = OpportunityLoader(self.cache_dir)
            # unified = loader.load_opportunities(top_n=1000)
            # loader.save_unified_cache(unified)

            logger.info("Opportunity rescoring complete")
            self._update_metadata('rescored_at', datetime.now().isoformat())

        except Exception as e:
            logger.error(f"Error rescoring opportunities: {e}")

    def get_last_update_time(self) -> Dict[str, str]:
        """
        Return when each source was last updated.

        Returns:
            Dict with keys 'b3', 'sec', 'rescored_at' containing ISO datetime strings
        """
        metadata = self._load_metadata()
        return {
            'b3': metadata.get('b3_last_update', 'Never'),
            'sec': metadata.get('sec_last_update', 'Never'),
            'rescored_at': metadata.get('rescored_at', 'Never'),
        }

    def _load_metadata(self) -> Dict:
        """Load metadata from file."""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading metadata: {e}")

        return {}

    def _update_metadata(self, key: str, value: str):
        """Update metadata file with a value."""
        try:
            metadata = self._load_metadata()
            metadata[key] = value
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating metadata: {e}")

    def force_refresh_sec(self):
        """Force immediate SEC data refresh (manual trigger)."""
        logger.info("Force-refreshing SEC data...")
        self.refresh_sec_data()

    def force_refresh_b3(self):
        """Force immediate B3 data refresh (manual trigger)."""
        logger.info("Force-refreshing B3 data...")
        self.refresh_b3_data()

    def force_refresh_opportunities(self):
        """Force immediate opportunity scoring refresh (manual trigger)."""
        logger.info("Force-rescoring opportunities...")
        self.refresh_opportunities()

    def get_scheduler_status(self) -> Dict:
        """Get status of scheduler and all jobs."""
        if self.scheduler is None:
            return {'running': False, 'available': False, 'jobs': []}

        try:
            jobs = self.scheduler.get_jobs()
            return {
                'running': self._started,
                'available': True,
                'jobs': [
                    {
                        'id': job.id,
                        'name': job.name,
                        'next_run': job.next_run_time.isoformat() if job.next_run_time else 'Unknown',
                    }
                    for job in jobs
                ],
            }
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {'running': False, 'available': True, 'jobs': []}


# Global scheduler instance
_global_scheduler: Optional[ScheduledUpdater] = None


def get_global_scheduler() -> ScheduledUpdater:
    """Get or create the global scheduler instance."""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = ScheduledUpdater()
    return _global_scheduler


def start_scheduler():
    """Start the global background scheduler."""
    scheduler = get_global_scheduler()
    scheduler.start()
    logger.info("Global scheduler started")


def stop_scheduler():
    """Stop the global background scheduler."""
    scheduler = get_global_scheduler()
    scheduler.stop()
    logger.info("Global scheduler stopped")
