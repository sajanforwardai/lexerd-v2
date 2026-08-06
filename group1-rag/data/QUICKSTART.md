# Data Ingestion Pipeline — Quick Start

Load 12 months of historical options data for backtesting in <30 minutes.

## Setup (5 minutes)

```bash
cd /workspace/group1-rag/data

# Install dependencies
pip install -r requirements.txt

# Set environment (optional; defaults to localhost)
export DB_HOST=localhost
export DB_NAME=group1_trading
export DB_USER=postgres
export DB_PASSWORD=password
```

## Option 1: Without Database (In-Memory, Fastest)

Loads data into memory for immediate backtesting. No database setup needed.

```bash
# Quick test: load SPY last 30 days
python3 -c "
from data_ingestion import DataIngestionPipeline
from datetime import datetime, timedelta

pipeline = DataIngestionPipeline()
end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
stats = pipeline.run(['SPY'], start_date, end_date)
print('Loaded:', stats)
"

# Full year: load SPY + QQQ + IWM
python3 data_ingestion.py
```

**Time:** ~2 minutes for 12 months (yfinance is fast)  
**Output:** Prints summary stats, data in memory for backtesting

## Option 2: With PostgreSQL Database (Persistent, Recommended)

Stores data persistently for repeated backtests and analysis.

### Setup Database

```bash
# Create Postgres database (one-time)
createdb group1_trading

# Load schema
psql -d group1_trading -f schema.sql

# Verify tables created
psql -d group1_trading -c "\dt"
```

### Run Pipeline

```bash
# Load historical data
python3 data_ingestion.py

# Or programmatically:
python3 -c "
from data_ingestion import DataIngestionPipeline
from datetime import datetime, timedelta

pipeline = DataIngestionPipeline(
    db_host='localhost',
    db_name='group1_trading',
    db_user='postgres',
    db_password='password'
)

end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
stats = pipeline.run(['SPY', 'QQQ', 'IWM'], start_date, end_date)
print(stats)
"
```

**Time:** ~5-10 minutes for 12 months (includes DB inserts)  
**Output:** Data in PostgreSQL tables, ready for queries

## Verify Data Loaded

```sql
-- Connect to database
psql -d group1_trading

-- Check underlyings
SELECT * FROM underlyings LIMIT 5;

-- Check OHLCV records
SELECT COUNT(*) FROM daily_ohlcv;

-- Check options
SELECT COUNT(*) FROM daily_options;

-- View daily snapshot (SPY)
SELECT * FROM vw_daily_snapshot WHERE symbol = 'SPY' ORDER BY date DESC LIMIT 5;
```

## Use Data for Backtesting

### In Python (In-Memory)

```python
from data_sources import DEFAULT_SOURCE
from datetime import datetime, timedelta

# Fetch OHLCV
source = DEFAULT_SOURCE
ohlcv = source.fetch_ohlcv('SPY', '2024-01-01', '2024-12-31')
print(f"Loaded {len(ohlcv)} daily prices")

# Fetch options
options = source.fetch_options('SPY', '2024-03-15', '2024-01-01', '2024-12-31')
print(f"Loaded {len(options)} option prices")

# Calculate Greeks
from greek_calculator import calc
greeks = calc.calculate_greeks(spot=450, strike=450, vol=0.20, time_to_exp=0.1)
print(f"Call delta: {greeks.delta}, gamma: {greeks.gamma}")
```

### From PostgreSQL (Persistent)

```python
import psycopg2
import pandas as pd

conn = psycopg2.connect("dbname=group1_trading user=postgres")

# Fetch SPY data
df = pd.read_sql("SELECT * FROM vw_daily_snapshot WHERE symbol = 'SPY' ORDER BY date", conn)
print(f"SPY prices: {len(df)} days")

# Fetch IV surface
df_iv = pd.read_sql("""
    SELECT strike, expiration_date, implied_vol 
    FROM vw_iv_by_strike 
    WHERE symbol = 'SPY' AND date = '2024-03-15'
    ORDER BY expiration_date, strike
""", conn)
print(f"IV surface: {len(df_iv)} strikes x expirations")
```

## Architecture

### Data Sources (Priority Order)

1. **yfinance** (OHLCV): Free, unlimited, fast. ~50ms/symbol for 12 months
2. **MockOptionsSource** (Options): Synthetic but realistic. Good for testing
3. **QuantConnect** (Options): Free tier available, 6-month rolling window. Requires SDK setup
4. **Intrinio** (Options): Free tier limited. Requires API key

### ETL Flow

```
Download → Transform → Enrich → Load → Verify
   ↓           ↓          ↓       ↓       ↓
yfinance   Greeks        Regimes  DB    Quality checks
           calculation   Events
```

### Performance

| Component | Time | Scale |
|-----------|------|-------|
| yfinance (12mo) | ~2 min | 3 symbols |
| Greek calc (30k options) | ~1 min | 768dim GPU, <100ms CPU |
| Regime calc (12mo) | ~30 sec | 250 trading days |
| DB inserts | ~2 min | Postgres on localhost |
| **Total** | **~5 min** | Full 12-month dataset |

## Troubleshooting

### "yfinance download failed"
→ Check internet connection, try different symbol

### "psycopg2.OperationalError: could not connect"
→ PostgreSQL not running. Start it: `brew services start postgresql` (Mac) or `pg_ctl -D /usr/local/var/postgres start`

### "Connection refused"
→ Check credentials in environment variables or code

### "Table does not exist"
→ Run schema.sql: `psql -d group1_trading -f schema.sql`

## Next Steps

1. **Load full 12 months:** `python3 data_ingestion.py`
2. **Backtest scenarios:** See `example_backtest.py` (coming next)
3. **Calculate metrics:** Use PostgreSQL views (`vw_daily_snapshot`, `vw_iv_by_strike`)

## Data Quality Notes

- **OHLCV:** Complete for all trading days. No weekends/holidays.
- **Options:** Synthetic (MockSource) or limited history (free tiers). Production use QuantConnect or Intrinio with paid tier.
- **Greeks:** Calculated from Black-Scholes. Assumes European options (daily data, not intraday).
- **Regimes:** Simplified classification (real system uses eigenvalue decomposition + correlation analysis)
- **Events:** Sample only. Add your own via `load_market_events()`

---

**Status:** Ready for backtesting. Load data now, backtest tomorrow.
