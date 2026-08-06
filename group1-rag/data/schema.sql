-- Group One Trading RAG: Historical Data Schema
-- Supports backtesting with OHLCV, Greeks, regimes, events

-- Underlyings (stocks)
CREATE TABLE underlyings (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255),
    sector VARCHAR(50),
    exchange VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily OHLCV data for underlyings
CREATE TABLE daily_ohlcv (
    id SERIAL PRIMARY KEY,
    underlying_id INT REFERENCES underlyings(id),
    date DATE NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    volume BIGINT,
    adjusted_close DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(underlying_id, date)
);

-- Options chains (strikes, expirations)
CREATE TABLE options_chains (
    id SERIAL PRIMARY KEY,
    underlying_id INT REFERENCES underlyings(id),
    expiration_date DATE NOT NULL,
    strike DECIMAL(10, 2) NOT NULL,
    option_type VARCHAR(4) CHECK (option_type IN ('CALL', 'PUT')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(underlying_id, expiration_date, strike, option_type)
);

-- Daily options data (IV, Greeks, bid-ask)
CREATE TABLE daily_options (
    id SERIAL PRIMARY KEY,
    chain_id INT REFERENCES options_chains(id),
    date DATE NOT NULL,
    bid DECIMAL(10, 4),
    ask DECIMAL(10, 4),
    mid DECIMAL(10, 4),
    implied_vol DECIMAL(6, 4),
    delta DECIMAL(6, 4),
    gamma DECIMAL(6, 4),
    vega DECIMAL(6, 4),
    theta DECIMAL(6, 4),
    rho DECIMAL(6, 4),
    open_interest INT,
    volume INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chain_id, date)
);

-- Market regimes (calculated daily)
CREATE TABLE market_regimes (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    regime VARCHAR(50),
    vol_level VARCHAR(20),
    vix_close DECIMAL(6, 2),
    vol_30day DECIMAL(6, 4),
    vol_10day DECIMAL(6, 4),
    skew DECIMAL(6, 4),
    term_structure VARCHAR(20),
    correlation DECIMAL(4, 2),
    confidence DECIMAL(4, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Market events (earnings, Fed, etc.)
CREATE TABLE market_events (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    event_type VARCHAR(50),
    description TEXT,
    impact_level VARCHAR(20),
    related_symbols VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data quality log
CREATE TABLE data_quality_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100),
    date_range VARCHAR(100),
    record_count INT,
    missing_count INT,
    gap_count INT,
    status VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Backtest results (store for analysis)
CREATE TABLE backtest_results (
    id SERIAL PRIMARY KEY,
    scenario_name VARCHAR(255),
    start_date DATE,
    end_date DATE,
    strategy_name VARCHAR(255),
    initial_capital DECIMAL(12, 2),
    final_capital DECIMAL(12, 2),
    total_return DECIMAL(8, 4),
    sharpe_ratio DECIMAL(6, 4),
    max_drawdown DECIMAL(8, 4),
    trades_count INT,
    win_rate DECIMAL(6, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast queries
CREATE INDEX idx_daily_ohlcv_date ON daily_ohlcv(date);
CREATE INDEX idx_daily_ohlcv_symbol ON daily_ohlcv USING (underlying_id, date);
CREATE INDEX idx_daily_options_date ON daily_options(date);
CREATE INDEX idx_daily_options_chain ON daily_options(chain_id, date);
CREATE INDEX idx_market_regimes_date ON market_regimes(date);
CREATE INDEX idx_market_events_date ON market_events(date);

-- Views for common queries
CREATE VIEW vw_daily_snapshot AS
SELECT
    u.symbol,
    d.date,
    d.close as spot_price,
    mr.vol_30day,
    mr.regime,
    mr.skew,
    COUNT(DISTINCT do.id) as active_chains
FROM underlyings u
JOIN daily_ohlcv d ON u.id = d.underlying_id
LEFT JOIN market_regimes mr ON d.date = mr.date
LEFT JOIN options_chains oc ON u.id = oc.underlying_id
LEFT JOIN daily_options do ON oc.id = do.chain_id AND d.date = do.date
GROUP BY u.symbol, d.date, d.close, mr.vol_30day, mr.regime, mr.skew;

CREATE VIEW vw_iv_by_strike AS
SELECT
    u.symbol,
    oc.expiration_date,
    oc.strike,
    oc.option_type,
    do.date,
    do.implied_vol,
    do.delta,
    do.bid,
    do.ask,
    do.mid
FROM underlyings u
JOIN options_chains oc ON u.id = oc.underlying_id
JOIN daily_options do ON oc.id = do.chain_id
ORDER BY u.symbol, oc.expiration_date, oc.strike;
