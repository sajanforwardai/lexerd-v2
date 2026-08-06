# Deployment Guide: Group One RAG Monitoring Dashboard

## Quick Start

### Local Testing
```bash
cd /workspace/group1-rag/dashboard
pip install -r requirements.txt
streamlit run dashboard.py
```

Access at: `http://localhost:8506`

### Production Deployment (forwardai.dev/sajan)

The dashboard is configured to deploy to: **`forwardai.dev/sajan/group1-rag-dashboard`**

#### Configuration
- **Port:** 8506 (unique, no conflicts with other dashboards)
- **Base URL Path:** `group1-rag-dashboard` (set in `.streamlit/config.toml`)
- **Address:** `0.0.0.0` (listens on all interfaces)
- **CORS:** Disabled (production-safe)
- **XSRF Protection:** Enabled

#### Deployment Steps

1. **Verify files are in place:**
   ```bash
   ls -la /workspace/group1-rag/dashboard/
   # Should show: dashboard.py, requirements.txt, README.md, .streamlit/config.toml
   ```

2. **Deploy via sajan-deploy:**
   ```bash
   cd /workspace
   sajan-deploy
   ```
   This copies files to staging and production deployments.

3. **Access the dashboard:**
   - **URL:** `https://forwardai.dev/sajan/group1-rag-dashboard`
   - **Status:** Monitor at `forwardai.dev` dashboard
   - **Logs:** Check host at `/srv/projects/refiner/forwardai-site/...`

#### Monitoring Deployment
The dashboard runs on port 8506 and is proxied through traefik-edge. To verify:

```bash
# On host
curl http://localhost:8506

# From container (if needed)
curl http://172.17.0.1:8506
```

#### Restart Service (if needed)
Contact the host to restart the dashboard service:
```bash
# On host (not in container)
systemctl restart streamlit-sajan@group1-rag
# OR manually
cd /workspace/group1-rag/dashboard && streamlit run dashboard.py --config .streamlit/config.toml &
```

## Customization Before Deployment

### Theme Colors
Edit `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#0066cc"      # Primary brand color
backgroundColor = "#ffffff"   # Page background
secondaryBackgroundColor = "#f8fafc"  # Card backgrounds
textColor = "#1f2937"        # Text color
```

### Port Number
If port 8506 conflicts, update `.streamlit/config.toml`:
```toml
[server]
port = 8507  # Change to unused port
```

Then update deployment configuration accordingly.

### Base URL Path
The dashboard URL is determined by `baseUrlPath`. Current config:
```toml
baseUrlPath = "group1-rag-dashboard"
# → https://forwardai.dev/sajan/group1-rag-dashboard
```

To change, update `.streamlit/config.toml` and redeploy.

## Connecting Real Data

Before production, replace mock data sources in `dashboard.py`:

### 1. Database Connection
```python
# Add to dashboard.py
import psycopg2
from typing import Optional

db_conn = None

@st.cache_resource
def get_db_connection():
    global db_conn
    if db_conn is None:
        db_conn = psycopg2.connect(
            host="localhost",
            database="group1_rag_metrics",
            user="rag_monitor",
            password=st.secrets["db_password"]
        )
    return db_conn
```

### 2. Replace generate_mock_data()
```python
def get_live_data():
    db = get_db_connection()
    
    # Metrics
    metrics = MetricsSnapshot()
    metrics.tier1_latency_p50 = db.query("SELECT p50 FROM tier1_latency WHERE timestamp > NOW() - '1h'::interval")[0][0]
    # ... populate all metrics
    
    # Queries
    queries = get_recent_queries(db)
    
    # Volume
    volume_data = pd.read_sql("SELECT * FROM query_volume_hourly", db)
    
    # Latency timeseries
    latency_data = pd.read_sql("SELECT * FROM latency_telemetry WHERE timestamp > NOW() - '100m'::interval", db)
    
    return metrics, queries, volume_data, ab_data, latency_data
```

### 3. Use Live Data in Main
```python
def main():
    apply_theme()
    render_header()
    
    # Load live data instead of mock
    if st.sidebar.checkbox("Use live data"):
        metrics, queries, volume_data, ab_data, latency_data = get_live_data()
    else:
        metrics, queries, volume_data, ab_data, latency_data = generate_mock_data()
    
    # ... rest of dashboard
```

### 4. Add Secrets Configuration
Create `~/.streamlit/secrets.toml`:
```toml
db_host = "localhost"
db_name = "group1_rag_metrics"
db_user = "rag_monitor"
db_password = "xxx"
kg_connection = "neo4j://localhost:7687"
kg_password = "xxx"
```

Access in code:
```python
db_password = st.secrets["db_password"]
```

## Monitoring & Troubleshooting

### Check Dashboard Health
```bash
# Verify port is listening
lsof -i :8506

# Check Streamlit logs
ps aux | grep streamlit

# Monitor resource usage
top -p <pid>
```

### Common Issues

#### 1. "Address already in use"
Port 8506 is occupied. Change port in config.toml or kill process:
```bash
fuser -k 8506/tcp
```

#### 2. "Cannot connect to database"
- Verify database is running and accessible
- Check credentials in secrets.toml
- Verify network connectivity

#### 3. "Metrics not updating"
- Check if real data queries are working
- Verify database has recent data
- Add logging: `st.write(db.query(...))`

#### 4. "Theme not applying"
- Clear browser cache (Ctrl+Shift+Delete)
- Force hard refresh (Ctrl+F5)
- Check CSS in browser DevTools

## Performance Considerations

### Caching
The dashboard uses `@st.cache_resource` and `@st.cache_data` for expensive operations:
- Database connections cached with `@st.cache_resource`
- Metrics queries cached for 5 minutes (default)
- Dataframes cached between reruns

Add custom caching:
```python
@st.cache_data(ttl=300)
def get_latency_data():
    return pd.read_sql("SELECT * FROM latency_telemetry WHERE timestamp > NOW() - '1h'", db)
```

### Query Optimization
For large tables, use:
- **Aggregation:** Pre-compute hourly/daily summaries
- **Pagination:** Show top 10 queries, allow "Load more"
- **Indexing:** Ensure database indexes on frequently queried columns

### Auto-Refresh
Sidebar control allows user-selected refresh intervals. To implement:
```python
if st.sidebar.button("Refresh now"):
    st.rerun()

# Auto-refresh not recommended (wastes resources)
# Use st.session_state for manual refresh instead
```

## Security Checklist

- [x] XSRF protection enabled in config.toml
- [x] CORS disabled (production-safe)
- [x] Error details hidden from users (showErrorDetails = false)
- [ ] Database credentials in secrets.toml, not hardcoded
- [ ] HTTPS enabled for production (handled by traefik-edge)
- [ ] API keys/tokens in st.secrets, not in code
- [ ] No sensitive data logged or displayed

## Support & Escalation

### Dashboard Issues
1. Check local logs: `tail -f ~/.streamlit/logs/`
2. Verify config: `cat .streamlit/config.toml`
3. Test with mock data: Remove live data connection, run `dashboard.py`
4. Review this guide and README.md

### Data Issues
1. Check database connectivity
2. Verify query syntax: Run SQL directly
3. Confirm data freshness: Check latest timestamps
4. Review data pipeline logs

### Production Deployment
1. Test locally first
2. Stage deployment (contact host)
3. Monitor metrics during rollout
4. Keep rollback plan ready (host has snapshots)

## Rollback Procedure

If deployment fails, host keeps 5 snapshots:
```bash
# On host (not in container)
ls -la /srv/projects/forwardai/.backup-sajan-*

# Restore from snapshot
rsync -av /srv/projects/forwardai/.backup-sajan-1/ /srv/projects/refiner/forwardai-site/sajan/
```

## Next Steps

1. **Connect Real Data** → Replace mock data with live database queries
2. **Set Up Alerts** → Integrate with incident management (Slack, PagerDuty)
3. **Add Drill-Down** → Click metrics to see detailed breakdowns
4. **Enable Exports** → CSV/JSON export for analysis
5. **Phase 2 Launch** → Populate A/B test section with Tier 3 data

---

**Deployment managed by:** Sajan / ForwardAI  
**Last updated:** 2026-08-06  
**Dashboard version:** 1.0
