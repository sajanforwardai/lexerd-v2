-- Database initialization for Group One Trading RAG Enterprise
-- Creates tables for audit logging, queries, and system state

-- ============================================================================
-- AUDIT LOGGING TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    details JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    status TEXT DEFAULT 'success',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_org_id ON audit_logs(org_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);

-- ============================================================================
-- USER MANAGEMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    org_id TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_users_status ON users(status);

-- ============================================================================
-- ORGANIZATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_organizations_status ON organizations(status);

-- ============================================================================
-- QUERY EXECUTION HISTORY
-- ============================================================================

CREATE TABLE IF NOT EXISTS query_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    parameters JSONB,
    result JSONB,
    latency_ms DECIMAL(10, 2),
    cached BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_query_history_user_id ON query_history(user_id);
CREATE INDEX idx_query_history_org_id ON query_history(org_id);
CREATE INDEX idx_query_history_created_at ON query_history(created_at DESC);
CREATE INDEX idx_query_history_status ON query_history(status);

-- ============================================================================
-- TRADE EXECUTION LOGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    pnl DECIMAL(20, 8),
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_trades_user_id ON trades(user_id);
CREATE INDEX idx_trades_org_id ON trades(org_id);
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_created_at ON trades(created_at DESC);

-- ============================================================================
-- PERFORMANCE METRICS
-- ============================================================================

CREATE TABLE IF NOT EXISTS metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value DECIMAL(20, 8) NOT NULL,
    tags JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_name ON metrics(metric_name);
CREATE INDEX idx_metrics_timestamp ON metrics(timestamp DESC);

-- ============================================================================
-- SYSTEM CONFIGURATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO config (key, value, description) VALUES
    ('api.version', '4.0.0', 'API version'),
    ('db.version', '1', 'Database schema version'),
    ('backup.last_timestamp', '2024-01-01T00:00:00Z', 'Last backup timestamp'),
    ('maintenance.mode', 'false', 'Maintenance mode enabled')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- BACKUP METADATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS backups (
    id TEXT PRIMARY KEY,
    s3_key TEXT NOT NULL,
    file_size_bytes BIGINT,
    file_hash_sha256 TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'success',
    retention_until TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_backups_created_at ON backups(created_at DESC);
CREATE INDEX idx_backups_status ON backups(status);

-- ============================================================================
-- RATE LIMIT TRACKING (optional - can use Redis instead)
-- ============================================================================

CREATE TABLE IF NOT EXISTS rate_limits (
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    request_count INT DEFAULT 0,
    PRIMARY KEY (user_id, org_id, window_start)
);

CREATE INDEX idx_rate_limits_user_id ON rate_limits(user_id);

-- ============================================================================
-- ALERTS & INCIDENTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    alert_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT DEFAULT 'firing',
    description TEXT,
    fired_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_fired_at ON alerts(fired_at DESC);

-- ============================================================================
-- SESSIONS (for rate limiting and access control)
-- ============================================================================

CREATE TABLE IF NOT EXISTS sessions (
    token_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Recent queries per organization
CREATE OR REPLACE VIEW v_recent_queries AS
SELECT
    org_id,
    user_id,
    COUNT(*) as query_count,
    AVG(latency_ms) as avg_latency,
    MAX(created_at) as last_query
FROM query_history
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
GROUP BY org_id, user_id;

-- Audit summary
CREATE OR REPLACE VIEW v_audit_summary AS
SELECT
    org_id,
    action,
    COUNT(*) as count,
    DATE_TRUNC('hour', timestamp) as hour
FROM audit_logs
GROUP BY org_id, action, DATE_TRUNC('hour', timestamp);

-- ============================================================================
-- GRANTS (adjust for your security model)
-- ============================================================================

-- Grant permissions to application user (if not using default postgres user)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_user;
