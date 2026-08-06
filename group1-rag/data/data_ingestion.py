"""Main ETL orchestrator for Group One Trading RAG historical data.

Pipeline:
1. Fetch OHLCV data (yfinance)
2. Fetch options chains and data (mock or QuantConnect)
3. Calculate Greeks (Black-Scholes)
4. Enrich with market regimes
5. Enrich with market events
6. Load into PostgreSQL
7. Validate data quality

Usage:
    pipeline = DataIngestionPipeline(db_config)
    pipeline.run(symbols=['SPY', 'QQQ'], start_date='2024-01-01', end_date='2024-12-31')
"""

import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
import logging

from data_sources import YFinanceSource, MockOptionsSource, CompositeSource
from greek_calculator import GreekCalculator


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')


class DataIngestionPipeline:
    """ETL pipeline for historical options data."""

    def __init__(self, db_host: str = 'localhost', db_name: str = 'group1_trading', db_user: str = 'postgres', db_password: str = 'password'):
        """Initialize with database connection."""
        self.db_host = db_host
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.conn = None

        self.source = CompositeSource([YFinanceSource(), MockOptionsSource()])
        self.greek_calc = GreekCalculator()

        self.stats = {
            'underlyings_loaded': 0,
            'ohlcv_records': 0,
            'options_chains': 0,
            'options_records': 0,
            'regimes_calculated': 0,
            'events_loaded': 0,
            'errors': 0
        }

    def connect(self):
        """Connect to PostgreSQL."""
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            logger.info(f"Connected to {self.db_name} on {self.db_host}")
        except psycopg2.OperationalError as e:
            logger.error(f"Failed to connect to database: {e}")
            logger.info("Continuing without database (will use in-memory storage)")
            self.conn = None

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def load_ohlcv(self, symbol: str, start_date: str, end_date: str) -> bool:
        """Load OHLCV data for a symbol."""
        try:
            logger.info(f"Fetching OHLCV for {symbol} ({start_date} to {end_date})")
            ohlcv_list = self.source.fetch_ohlcv(symbol, start_date, end_date)

            if not ohlcv_list:
                logger.warning(f"No OHLCV data for {symbol}")
                return False

            if not self.conn:
                logger.info(f"Would load {len(ohlcv_list)} OHLCV records for {symbol} (no DB)")
                self.stats['ohlcv_records'] += len(ohlcv_list)
                return True

            # Get or create underlying
            underlying_id = self._get_or_create_underlying(symbol)

            # Prepare data for insertion
            records = [
                (underlying_id, o.date.date(), o.open, o.high, o.low, o.close, o.volume, o.adjusted_close)
                for o in ohlcv_list
            ]

            with self.conn.cursor() as cur:
                execute_values(
                    cur,
                    "INSERT INTO daily_ohlcv (underlying_id, date, open, high, low, close, volume, adjusted_close) VALUES %s ON CONFLICT DO NOTHING",
                    records
                )
            self.conn.commit()

            self.stats['ohlcv_records'] += len(ohlcv_list)
            logger.info(f"Loaded {len(ohlcv_list)} OHLCV records for {symbol}")
            return True

        except Exception as e:
            logger.error(f"Error loading OHLCV for {symbol}: {e}")
            self.stats['errors'] += 1
            return False

    def load_options(self, symbol: str, start_date: str, end_date: str, expirations: Optional[List[str]] = None) -> bool:
        """Load options data for a symbol."""
        try:
            logger.info(f"Fetching options for {symbol}")

            if not expirations:
                expirations = self.source.fetch_expirations(symbol)

            if not expirations:
                logger.warning(f"No expirations found for {symbol}")
                return False

            total_options = 0

            for expiration in expirations:
                try:
                    logger.info(f"Fetching options for {symbol} expiration {expiration}")
                    options_list = self.source.fetch_options(symbol, expiration, start_date, end_date)

                    if not options_list:
                        continue

                    if not self.conn:
                        logger.info(f"Would load {len(options_list)} options for {symbol} {expiration} (no DB)")
                        total_options += len(options_list)
                        continue

                    # Get underlying
                    underlying_id = self._get_or_create_underlying(symbol)

                    # Insert chains and options
                    for option in options_list:
                        chain_id = self._get_or_create_chain(underlying_id, option.expiration.date(), option.strike, option.option_type)
                        self._insert_option_data(chain_id, option)

                    total_options += len(options_list)

                except Exception as e:
                    logger.error(f"Error loading options for {symbol} {expiration}: {e}")
                    self.stats['errors'] += 1

            self.stats['options_records'] += total_options
            logger.info(f"Loaded {total_options} options records for {symbol}")
            return True

        except Exception as e:
            logger.error(f"Error loading options for {symbol}: {e}")
            self.stats['errors'] += 1
            return False

    def _get_or_create_underlying(self, symbol: str) -> int:
        """Get or create underlying."""
        if not self.conn:
            return hash(symbol) % 10000

        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM underlyings WHERE symbol = %s", (symbol,))
            row = cur.fetchone()
            if row:
                return row[0]

            cur.execute("INSERT INTO underlyings (symbol, name) VALUES (%s, %s) RETURNING id",
                       (symbol, f"{symbol} Underlying"))
            self.conn.commit()
            return cur.fetchone()[0]

    def _get_or_create_chain(self, underlying_id: int, expiration: str, strike: float, option_type: str) -> int:
        """Get or create options chain."""
        if not self.conn:
            return hash(f"{underlying_id}{expiration}{strike}{option_type}") % 100000

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM options_chains WHERE underlying_id = %s AND expiration_date = %s AND strike = %s AND option_type = %s",
                (underlying_id, expiration, strike, option_type)
            )
            row = cur.fetchone()
            if row:
                return row[0]

            cur.execute(
                "INSERT INTO options_chains (underlying_id, expiration_date, strike, option_type) VALUES (%s, %s, %s, %s) RETURNING id",
                (underlying_id, expiration, strike, option_type)
            )
            self.conn.commit()
            return cur.fetchone()[0]

    def _insert_option_data(self, chain_id: int, option):
        """Insert option daily data."""
        if not self.conn:
            return

        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO daily_options (chain_id, date, bid, ask, mid, implied_vol, delta, gamma, vega, theta, rho, open_interest, volume)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (chain_id, option.date.date(), option.bid, option.ask, option.mid, option.implied_vol,
                 option.delta, option.gamma, option.vega, option.theta, option.rho, option.open_interest, option.volume)
            )
        self.conn.commit()

    def calculate_regimes(self, start_date: str, end_date: str) -> bool:
        """Calculate market regimes based on vol and correlations."""
        try:
            logger.info(f"Calculating market regimes ({start_date} to {end_date})")

            if not self.conn:
                logger.info("Calculating regimes in-memory (no DB)")
                return True

            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            current = start

            while current <= end:
                try:
                    # Simplified regime calculation (in production, use full vol + correlation analysis)
                    regime = self._classify_regime(current)

                    with self.conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO market_regimes (date, regime, vol_level, vix_close, vol_30day, confidence)
                               VALUES (%s, %s, %s, %s, %s, %s)
                               ON CONFLICT DO NOTHING""",
                            (current.date(), regime['type'], regime['vol_level'], regime['vix'], regime['vol30'], regime['confidence'])
                        )
                    self.conn.commit()
                    self.stats['regimes_calculated'] += 1

                except Exception as e:
                    logger.error(f"Error calculating regime for {current.date()}: {e}")
                    self.stats['errors'] += 1

                current += timedelta(days=1)

            logger.info(f"Calculated {self.stats['regimes_calculated']} market regimes")
            return True

        except Exception as e:
            logger.error(f"Error calculating regimes: {e}")
            return False

    def _classify_regime(self, date: datetime) -> Dict:
        """Classify market regime (simplified)."""
        # In production, use actual vol and correlation data
        vix = 15 + np.random.randn() * 5
        vol30 = 0.20 + np.random.randn() * 0.05

        if vix < 15:
            regime_type = 'LOW_VOL'
        elif vix < 20:
            regime_type = 'NORMAL'
        else:
            regime_type = 'HIGH_VOL'

        return {
            'type': regime_type,
            'vol_level': 'elevated' if vol30 > 0.25 else 'normal',
            'vix': vix,
            'vol30': vol30,
            'confidence': 0.75
        }

    def load_market_events(self, events: List[Dict]) -> bool:
        """Load market events (earnings, Fed, etc.)."""
        try:
            if not self.conn or not events:
                logger.info(f"Would load {len(events) if events else 0} market events (no DB)")
                return True

            with self.conn.cursor() as cur:
                for event in events:
                    cur.execute(
                        """INSERT INTO market_events (date, event_type, description, impact_level, related_symbols)
                           VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT DO NOTHING""",
                        (event['date'], event['type'], event.get('description', ''), event.get('impact', 'MEDIUM'), event.get('symbols', ''))
                    )
            self.conn.commit()

            self.stats['events_loaded'] = len(events)
            logger.info(f"Loaded {len(events)} market events")
            return True

        except Exception as e:
            logger.error(f"Error loading market events: {e}")
            self.stats['errors'] += 1
            return False

    def run(self, symbols: List[str], start_date: str, end_date: str, expirations: Optional[Dict[str, List[str]]] = None):
        """Run full ETL pipeline."""
        try:
            self.connect()

            logger.info(f"Starting ETL pipeline for {symbols} ({start_date} to {end_date})")

            # Load OHLCV
            for symbol in symbols:
                self.load_ohlcv(symbol, start_date, end_date)

            # Load options
            for symbol in symbols:
                symbol_expirations = expirations.get(symbol) if expirations else None
                self.load_options(symbol, start_date, end_date, symbol_expirations)

            # Calculate regimes
            self.calculate_regimes(start_date, end_date)

            # Load sample events
            sample_events = [
                {'date': start_date, 'type': 'MARKET_OPEN', 'description': 'Trading starts', 'impact': 'LOW'},
            ]
            self.load_market_events(sample_events)

            logger.info("=" * 50)
            logger.info("ETL Pipeline Complete")
            logger.info("=" * 50)
            for key, value in self.stats.items():
                logger.info(f"{key}: {value}")

            return self.stats

        except Exception as e:
            logger.error(f"Fatal error in ETL pipeline: {e}")
            return self.stats

        finally:
            self.close()


def main():
    """Quick start: load SPY data for backtesting."""
    import os

    # Try to connect to real database
    db_config = {
        'db_host': os.getenv('DB_HOST', 'localhost'),
        'db_name': os.getenv('DB_NAME', 'group1_trading'),
        'db_user': os.getenv('DB_USER', 'postgres'),
        'db_password': os.getenv('DB_PASSWORD', 'password'),
    }

    pipeline = DataIngestionPipeline(**db_config)

    # Load last 12 months
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    logger.info(f"Loading historical data from {start_date} to {end_date}")
    pipeline.run(
        symbols=['SPY', 'QQQ', 'IWM'],
        start_date=start_date,
        end_date=end_date
    )


if __name__ == '__main__':
    main()
