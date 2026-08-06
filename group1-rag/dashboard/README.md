# Group One RAG Monitoring Dashboard

Real-time monitoring dashboard for Group One Trading RAG system with three retrieval tiers:
- **Tier 1:** Retrieval only (≤100ms)
- **Tier 2:** Entity extraction (≤500ms)
- **Tier 3:** Agentic reasoning (≤5s, Phase 2)

## Features

### 1. Real-Time Metrics
- **Tier 1:** Latency (P50, P99), Precision@10
- **Tier 2:** Latency (P50, P99), Entity F1 score
- **Tier 3:** Status and Phase 2 readiness (pending deployment)

### 2. Query Volume
- Hourly query breakdown by tier (last 24 hours)
- Distribution across Tier 1 (59.5%) and Tier 2 (40.5%)
- Queries per hour tracking

### 3. Error Handling & Fallbacks
- Overall error rate tracking
- Tier 1 → Tier 2 fallback frequency (15%)
- Tier 2 → Tier 3 fallback frequency (3%)
- Fallback trigger conditions documented

### 4. Recent Queries
- Last 10 queries with latency and precision
- User feedback (useful, needs_refinement, pending)
- Error tracking and timestamps
- Color-coded feedback status

### 5. A/B Test Results (Phase 2)
- Tier 2 (baseline) vs Tier 3 (candidate) comparison
- Ready for launch; results populate on deployment
- Hypothesis: Tier 3 achieves 90%+ user satisfaction
- Test infrastructure documented

### 6. Corpus & Knowledge Graph Stats
- Documents ingested: 18,450
- Entities in KG: 847
- Relationships: 2,134
- Vector DB size: 3.8GB
- Entity type breakdown chart
- Corpus ingestion pipeline documentation (Layer 1–3)

### 7. SLA Alerts
- Latency SLA breach detection
- Accuracy drop alerts
- Error rate monitoring
- Color-coded severity (danger, warning, success)
- Real-time status propagation

### 8. Theme Support
- Light/dark theme detection via CSS media query
- Automatic theme following system preference
- Professional color scheme with Lexerd design pattern

## File Structure

```
/workspace/group1-rag/dashboard/
├── dashboard.py              # Main Streamlit application
├── requirements.txt          # Python dependencies
├── .streamlit/config.toml    # Streamlit configuration
└── README.md                 # This file
```

## Configuration

### Streamlit Config (`config.toml`)
```toml
[server]
port = 8506
address = "0.0.0.0"
headless = true
baseUrlPath = "group1-rag-dashboard"  # Deployed to forwardai.dev/sajan/group1-rag-dashboard
```

## Running Locally

### Setup
```bash
cd /workspace/group1-rag/dashboard
pip install -r requirements.txt
```

### Run Dashboard
```bash
streamlit run dashboard.py
```

Dashboard opens at: `http://localhost:8506`

### Run with Production Config
```bash
streamlit run dashboard.py --config .streamlit/config.toml
```

## Deploying to forwardai.dev

1. Ensure `/workspace/group1-rag/dashboard/` exists with all files
2. Run sajan-deploy (or ask host to deploy):
   ```bash
   sajan-deploy
   ```
3. Access at: `forwardai.dev/sajan/group1-rag-dashboard`

**Key requirement:** `baseUrlPath = "group1-rag-dashboard"` in config.toml enables correct routing.

## Customizing with Real Data

### Current State
The dashboard uses `generate_mock_data()` for demonstration. To integrate real data:

### 1. Metrics Data Source
Replace `MetricsSnapshot` class initialization with real queries:

```python
class MetricsSnapshot:
    def __init__(self, db_connection=None):
        # Query real database or metrics store
        if db_connection:
            self.tier1_latency_p50 = db_connection.query("SELECT p50 FROM tier1_latency")
            # ... etc
```

### 2. Query Records Source
Replace `generate_mock_data()` queries section:

```python
def get_recent_queries(db_connection, limit=10):
    results = db_connection.query(
        "SELECT id, query, tier, latency_ms, precision, error, feedback FROM queries "
        "ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    return [QueryRecord(*row) for row in results]
```

### 3. Corpus Stats Source
Connect to real knowledge graph or vector DB:

```python
def get_corpus_stats(kg_connection):
    entities = kg_connection.query("MATCH (e) RETURN COUNT(e) as count")
    relationships = kg_connection.query("MATCH ()-[r]->() RETURN COUNT(r) as count")
    # ... populate MetricsSnapshot
```

### 4. Time Series Data
Replace `generate_mock_data()` latency/volume sections with real telemetry:

```python
def get_latency_timeseries(metrics_db, window_minutes=100):
    results = metrics_db.query(
        "SELECT minutes_ago, tier1_latency, tier2_latency FROM latency_telemetry "
        "WHERE timestamp > NOW() - INTERVAL ? MINUTE", (window_minutes,)
    )
    return pd.DataFrame(results)
```

## Architecture Reference

See `/workspace/corpus/financial-services/group1-trading-rag-architecture.md` for:
- Full system architecture
- Tier SLAs and use cases
- Retrieval engine specs (hybrid dense+BM25)
- Knowledge graph schema (9 entities, 12 relationships)
- Vector DB models (FinBERT for SEC, text-embedding-3-large for news)

## Performance Targets

| Tier | Latency (P99) | Precision/F1 | Fallback Rate |
|------|---------------|--------------|---------------|
| Tier 1 | ≤100ms | Precision@10 ≥0.50 | 15% → Tier 2 |
| Tier 2 | ≤500ms | Entity F1 ≥0.70 | 3% → Tier 3 |
| Tier 3 | ≤5s | User satisfaction ≥90% | — |

## Alert Thresholds

- **P99 Latency SLA miss:** Tier 1 >100ms, Tier 2 >500ms
- **Precision/F1 drop:** Tier 1 <0.50, Tier 2 <0.70
- **Error rate elevated:** >5%
- **Fallback surge:** >20%

## Dashboard Navigation

### Sidebar Controls
- **Auto-refresh:** Off, 5s, 15s, 30s, 60s
- **Tier filter:** Show/hide tiers dynamically
- **View mode:**
  - Overview (all metrics, queries, alerts)
  - Tier 1 Deep Dive (latency distribution, queries)
  - Tier 2 Deep Dive (entity F1 by type, fallbacks)
  - A/B Test (Phase 2 comparison)
  - Corpus (KG stats, ingestion pipeline)

### Key Sections
1. **Real-Time Metrics** — Live P50/P99 latency, precision scores
2. **Query Volume** — 24h trend by tier
3. **Latency Trend** — 100-minute timeseries
4. **Error Handling** — Fallback rates and triggers
5. **Recent Queries** — Last 10 with user feedback
6. **A/B Test** — Tier 2 vs Tier 3 (ready for Phase 2)
7. **Corpus Stats** — KG entities, relationships, ingestion pipeline
8. **Alerts** — SLA status, critical events

## Development

### Adding New Metrics
1. Add field to `MetricsSnapshot` class
2. Render in `render_metrics_section()` with `st.metric()`
3. Add to `generate_mock_data()` or real data source

### Adding Alerts
1. Define threshold in `render_alerts()`
2. Append to `alerts` list with (level, title, description)
3. CSS classes handle styling: `.alert-danger`, `.alert-warning`, `.alert-success`

### Styling
All CSS is inline in `apply_theme()` and uses CSS variables for light/dark theme support:
- `--primary-color`, `--text-primary`, `--border-light`, etc.
- Media query `@media (prefers-color-scheme: dark)` for auto theme switching

## Known Limitations

1. **Mock data only:** Currently uses `generate_mock_data()` for demonstration
2. **Tier 3 placeholder:** A/B test shows Phase 2 readiness but no real Tier 3 data yet
3. **No persistence:** Dashboard state resets on refresh (no session management)
4. **Static documentation links:** Links in footer are placeholders for future pages

## Next Steps

1. Connect to real metrics database (PostgreSQL, ClickHouse, etc.)
2. Integrate knowledge graph queries (Neo4j)
3. Wire up real query logs from retrieval engine
4. Add WebSocket support for true real-time updates
5. Implement user feedback collection form
6. Phase 2: Deploy Tier 3 and populate A/B test section

## Support

For issues or feature requests:
- Check `/workspace/group1-rag/retrieval/retrieval_engine.py` for engine specs
- Review corpus files in `/workspace/corpus/financial-services/`
- Contact Sajan for deployment and configuration questions
