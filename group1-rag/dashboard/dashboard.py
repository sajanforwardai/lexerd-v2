#!/usr/bin/env python3
"""
Group One RAG Monitoring Dashboard

Real-time monitoring for Group One Trading RAG system with three retrieval tiers:
  - Tier 1: Retrieval only (≤100ms)
  - Tier 2: Entity extraction (≤500ms)
  - Tier 3: Agentic reasoning (≤5s, Phase 2)

Displays: real-time metrics, query volume, error rates, recent queries, A/B tests,
corpus stats, and SLA alerts. Supports light/dark theme.

Run: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

# Page config
st.set_page_config(
    page_title="Group One RAG Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---- Data Models & Mock Data ----

class MetricsSnapshot:
    """Current metrics snapshot across all tiers."""
    def __init__(self):
        # Tier 1: Retrieval Only (≤100ms)
        self.tier1_latency_p50 = 45  # ms
        self.tier1_latency_p99 = 98  # ms
        self.tier1_precision_at10 = 0.68

        # Tier 2: Entity Extraction (≤500ms)
        self.tier2_latency_p50 = 280  # ms
        self.tier2_latency_p99 = 450  # ms
        self.tier2_entity_f1 = 0.84

        # Tier 3: Agentic Reasoning (≤5s, Phase 2)
        self.tier3_latency_p50 = None  # Not yet deployed
        self.tier3_latency_p99 = None

        # Query routing
        self.total_queries_1h = 1247
        self.tier1_queries = 742  # 59.5%
        self.tier2_queries = 505  # 40.5%
        self.tier3_queries = 0    # 0%

        # Errors & fallbacks
        self.error_rate = 0.032  # 3.2%
        self.fallback_rate = 0.18  # 18% (T1→T2, T2→T3 fallback)
        self.tier1_fallback_to_tier2 = 0.15
        self.tier2_fallback_to_tier3 = 0.03

        # Corpus stats
        self.documents_ingested = 18_450
        self.entities_in_kg = 847
        self.relationships_in_kg = 2_134
        self.vector_db_size_gb = 3.8

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


class QueryRecord:
    """Individual query record for recent queries table."""
    def __init__(self, qid, query, tier, latency_ms, precision, error=None, feedback=None):
        self.id = qid
        self.query = query
        self.tier = tier
        self.latency_ms = latency_ms
        self.precision = precision
        self.error = error
        self.feedback = feedback or "pending"
        self.timestamp = datetime.now() - timedelta(seconds=np.random.randint(1, 600))

    def to_dict(self):
        return {
            "ID": self.id,
            "Query": self.query,
            "Tier": self.tier,
            "Latency (ms)": self.latency_ms,
            "Precision@10": f"{self.precision:.3f}" if self.precision else "—",
            "Error": self.error or "—",
            "Feedback": self.feedback,
            "Timestamp": self.timestamp.strftime("%H:%M:%S")
        }


def generate_mock_data():
    """Generate realistic mock data for demonstration."""
    metrics = MetricsSnapshot()

    # Recent queries
    queries = [
        QueryRecord("q_001", "straddle vs strangle differences", "Tier 1", 42, 0.87),
        QueryRecord("q_002", "gamma neutralization strategies", "Tier 2", 310, 0.91),
        QueryRecord("q_003", "volatility smile in index options", "Tier 1", 56, 0.73),
        QueryRecord("q_004", "Greeks exposure analysis for portfolio", "Tier 2", 285, 0.88),
        QueryRecord("q_005", "theta decay in short premium", "Tier 1", 38, 0.79),
        QueryRecord("q_006", "vega risk across strikes", "Tier 2", 405, 0.92, feedback="useful"),
        QueryRecord("q_007", "delta hedging rebalance frequency", "Tier 1", 51, 0.81),
        QueryRecord("q_008", "market regime identification", "Tier 2", 440, 0.86, feedback="needs_refinement"),
        QueryRecord("q_009", "correlation breakdown in crisis", "Tier 2", 520, None, error="timeout"),
        QueryRecord("q_010", "basis risk in index futures", "Tier 1", 44, 0.74),
    ]

    # Hourly query volume (last 24 hours)
    hours = [(datetime.now() - timedelta(hours=i)).strftime("%H:00") for i in range(24, 0, -1)]
    tier1_volume = [50 + np.random.randint(-10, 30) for _ in range(24)]
    tier2_volume = [30 + np.random.randint(-8, 25) for _ in range(24)]

    volume_data = pd.DataFrame({
        "Hour": hours,
        "Tier 1": tier1_volume,
        "Tier 2": tier2_volume,
    })

    # A/B test results (Phase 2 preview - Tier 3 vs Tier 2)
    ab_test = {
        "variant": ["Tier 2 (Baseline)", "Tier 3 (Candidate)"],
        "queries_processed": [245, 0],  # Tier 3 not deployed yet
        "latency_p50_ms": [280, None],
        "latency_p99_ms": [450, None],
        "precision_at10": [0.84, None],
        "user_satisfaction": [0.76, None],
        "status": ["Active", "Pending Phase 2 Launch"]
    }

    # Latency time series (last 100 minutes)
    minutes = list(range(100, 0, -1))
    tier1_latencies = 45 + np.random.normal(0, 8, len(minutes))
    tier1_latencies = np.clip(tier1_latencies, 20, 120)
    tier2_latencies = 280 + np.random.normal(0, 50, len(minutes))
    tier2_latencies = np.clip(tier2_latencies, 150, 600)

    latency_data = pd.DataFrame({
        "Minutes Ago": minutes,
        "Tier 1 (ms)": tier1_latencies,
        "Tier 2 (ms)": tier2_latencies,
    }).sort_values("Minutes Ago")

    return metrics, queries, volume_data, pd.DataFrame(ab_test), latency_data


# ---- Styling & Theme ----

def apply_theme():
    """Apply light/dark theme CSS."""
    theme_css = """
    <style>
    :root {
        --primary-color: #0066cc;
        --primary-light: #3b82f6;
        --secondary-light: #f8fafc;
        --secondary-gray: #e2e8f0;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --danger-color: #ef4444;
        --text-primary: #1f2937;
        --text-secondary: #6b7280;
        --border-light: #e5e7eb;
        --bg-card: #ffffff;
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --text-primary: #f3f4f6;
            --text-secondary: #d1d5db;
            --border-light: #374151;
            --bg-card: #1f2937;
            --secondary-light: #111827;
            --secondary-gray: #374151;
        }
    }

    * {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .main {
        padding: 1.5rem 2rem;
    }

    h1 {
        color: var(--text-primary);
        font-size: 2.25rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.5px;
    }

    h2 {
        color: var(--text-primary);
        font-size: 1.5rem;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-light);
        padding-bottom: 0.75rem;
    }

    h3 {
        color: var(--text-primary);
        font-size: 1.125rem;
        font-weight: 600;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: 8px;
        padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: all 0.2s ease;
    }

    [data-testid="metric-container"]:hover {
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-color: var(--primary-light);
    }

    /* Alert boxes */
    .alert-danger {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }

    .alert-warning {
        background: rgba(245, 158, 11, 0.1);
        border-left: 4px solid #f59e0b;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }

    .alert-success {
        background: rgba(16, 185, 129, 0.1);
        border-left: 4px solid #10b981;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }

    /* Table styling */
    table {
        border-collapse: collapse;
        width: 100%;
        font-size: 0.875rem;
    }

    th {
        background: var(--secondary-light);
        color: var(--text-primary);
        font-weight: 600;
        padding: 0.75rem;
        text-align: left;
        border-bottom: 2px solid var(--border-light);
    }

    td {
        padding: 0.75rem;
        border-bottom: 1px solid var(--border-light);
        color: var(--text-primary);
    }

    tr:hover {
        background: var(--secondary-light);
    }
    </style>
    """
    st.markdown(theme_css, unsafe_allow_html=True)


# ---- Dashboard Components ----

def render_header():
    """Render dashboard header with timestamp."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("📊 Group One RAG Monitor")
        st.markdown(f"_Real-time monitoring for Group One Trading RAG system_")
    with col2:
        st.metric("Last Updated", datetime.now().strftime("%H:%M:%S"))


def render_metrics_section(metrics):
    """Render real-time metrics (Tier 1, Tier 2, Tier 3)."""
    st.markdown("## Real-Time Metrics")

    # Tier 1 Metrics
    st.subheader("🚀 Tier 1: Retrieval Only (≤100ms)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Latency P50",
            f"{metrics.tier1_latency_p50}ms",
            delta="-2ms",
            delta_color="inverse"
        )
    with col2:
        st.metric(
            "Latency P99",
            f"{metrics.tier1_latency_p99}ms",
            delta="+1ms"
        )
    with col3:
        st.metric(
            "Precision@10",
            f"{metrics.tier1_precision_at10:.3f}",
            delta="+0.02"
        )

    # Tier 2 Metrics
    st.subheader("⚙️ Tier 2: Entity Extraction (≤500ms)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Latency P50",
            f"{metrics.tier2_latency_p50}ms",
            delta="+5ms"
        )
    with col2:
        st.metric(
            "Latency P99",
            f"{metrics.tier2_latency_p99}ms",
            delta="-8ms",
            delta_color="inverse"
        )
    with col3:
        st.metric(
            "Entity F1 Score",
            f"{metrics.tier2_entity_f1:.3f}",
            delta="+0.01"
        )

    # Tier 3 Status (Phase 2)
    st.subheader("🧠 Tier 3: Agentic Reasoning (≤5s, Phase 2)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Status", "Pending Launch", delta="Phase 2")
    with col2:
        st.info("Tier 3 deployment begins in Phase 2. A/B test setup complete.")


def render_query_volume(volume_data):
    """Render query volume by tier (1h)."""
    st.markdown("## Query Volume (Last 24 Hours)")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.line_chart(volume_data.set_index("Hour"), height=300)
    with col2:
        st.metric("Queries in Last Hour", "1,247")
        st.metric("Avg Tier 1", "742 q/h", delta="59.5%", delta_color="off")
        st.metric("Avg Tier 2", "505 q/h", delta="40.5%", delta_color="off")


def render_latency_timeseries(latency_data):
    """Render latency over time (last 100 minutes)."""
    st.markdown("## Latency Trend (Last 100 Minutes)")
    st.line_chart(latency_data.set_index("Minutes Ago"), height=300)


def render_error_section(metrics):
    """Render error rate and fallback frequency."""
    st.markdown("## Error Handling & Fallbacks")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Overall Error Rate",
            f"{metrics.error_rate * 100:.1f}%",
            delta="-0.3%",
            delta_color="inverse"
        )
    with col2:
        st.metric(
            "T1→T2 Fallback",
            f"{metrics.tier1_fallback_to_tier2 * 100:.1f}%"
        )
    with col3:
        st.metric(
            "T2→T3 Fallback",
            f"{metrics.tier2_fallback_to_tier3 * 100:.1f}%"
        )

    st.markdown("### Fallback Mechanism")
    st.info(
        "**Tier 1** falls back to **Tier 2** when: latency SLA miss, retrieval precision < 0.5, "
        "or critical entity not found.\n\n"
        "**Tier 2** falls back to **Tier 3** (Phase 2) when: entity extraction F1 < 0.70 or "
        "knowledge graph lookup returns empty."
    )


def render_recent_queries(queries):
    """Render recent queries with feedback."""
    st.markdown("## Recent Queries (Last 10)")

    query_rows = [q.to_dict() for q in queries[:10]]
    df = pd.DataFrame(query_rows)

    # Color-code feedback
    def highlight_feedback(val):
        if val == "useful":
            return "background-color: rgba(16, 185, 129, 0.2)"
        elif val == "needs_refinement":
            return "background-color: rgba(245, 158, 11, 0.2)"
        elif val == "pending":
            return "background-color: rgba(226, 232, 240, 0.5)"
        return ""

    styled_df = df.style.applymap(
        lambda x: highlight_feedback(x) if isinstance(x, str) else "",
        subset=["Feedback"]
    )
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    st.markdown("**Feedback legend:** 🟢 useful · 🟡 needs_refinement · ⚪ pending")


def render_ab_test(ab_data):
    """Render A/B test results (Phase 2 Tier 3 vs Tier 2)."""
    st.markdown("## A/B Test: Tier 3 vs Tier 2 (Phase 2 Preview)")

    if ab_data["queries_processed"][1] == 0:
        st.warning(
            "**Tier 3 Agentic Reasoning** deployment launches Phase 2. "
            "A/B test infrastructure is ready; results will populate upon deployment."
        )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Tier 2 (Baseline)")
        st.metric("Queries Processed", ab_data["queries_processed"][0])
        st.metric("Latency P50", f"{ab_data['latency_p50_ms'][0]}ms")
        st.metric("Latency P99", f"{ab_data['latency_p99_ms'][0]}ms")
        st.metric("Precision@10", f"{ab_data['precision_at10'][0]:.3f}")
        st.metric("User Satisfaction", f"{ab_data['user_satisfaction'][0]:.0%}")

    with col2:
        st.subheader("Tier 3 (Candidate)")
        st.metric("Queries Processed", ab_data["queries_processed"][1] or "—")
        st.metric("Latency P50", ab_data["latency_p50_ms"][1] or "—")
        st.metric("Latency P99", ab_data["latency_p99_ms"][1] or "—")
        st.metric("Precision@10", ab_data["precision_at10"][1] or "—")
        st.metric("User Satisfaction", ab_data["user_satisfaction"][1] or "—")

    st.info(
        "**Tier 3 vs Tier 2 Comparison:** Once Tier 3 launches, we'll measure reasoning quality "
        "(multi-hop entity paths), user satisfaction, and latency tradeoff. Target: "
        "90%+ user satisfaction vs 76% for Tier 2."
    )


def render_corpus_stats(metrics):
    """Render corpus & knowledge graph statistics."""
    st.markdown("## Corpus & Knowledge Graph Stats")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Documents Ingested", f"{metrics.documents_ingested:,}")
    with col2:
        st.metric("Entities in KG", f"{metrics.entities_in_kg:,}")
    with col3:
        st.metric("Relationships", f"{metrics.relationships_in_kg:,}")
    with col4:
        st.metric("Vector DB Size", f"{metrics.vector_db_size_gb}GB")

    st.markdown("### Knowledge Graph Entities")
    entities = [
        ("Trading Regime", 87),
        ("Option Strategy", 156),
        ("Greeks Exposure", 201),
        ("Market Microstructure", 142),
        ("Volatility Patterns", 95),
        ("Instrument", 104),
        ("Counterparty", 63),
    ]
    entity_df = pd.DataFrame(entities, columns=["Entity Type", "Count"])
    st.bar_chart(entity_df.set_index("Entity Type"))

    st.markdown("### Corpus Ingestion Pipeline")
    st.info(
        "**Layer 1 (Write):** corpus-open/close snapshots capture research insights.\n\n"
        "**Layer 2 (Ingest):** Nightly cron extracts entities, validates against KG, updates vector DB.\n\n"
        "**Layer 3 (Eval):** Auto-Council flags low-confidence extractions for manual review."
    )


def render_alerts(metrics):
    """Render SLA alerts and critical events."""
    st.markdown("## Alerts & SLA Status")

    alerts = []

    # Check SLA violations
    if metrics.tier1_latency_p99 > 100:
        alerts.append(("danger", "🔴 Tier 1 P99 latency SLA miss", f"{metrics.tier1_latency_p99}ms > 100ms"))
    elif metrics.tier1_latency_p99 > 85:
        alerts.append(("warning", "🟡 Tier 1 P99 latency trending high", f"{metrics.tier1_latency_p99}ms (threshold: 100ms)"))
    else:
        alerts.append(("success", "🟢 Tier 1 latency nominal", f"P99: {metrics.tier1_latency_p99}ms"))

    if metrics.tier2_latency_p99 > 500:
        alerts.append(("danger", "🔴 Tier 2 P99 latency SLA miss", f"{metrics.tier2_latency_p99}ms > 500ms"))
    elif metrics.tier2_latency_p99 > 400:
        alerts.append(("warning", "🟡 Tier 2 P99 latency trending high", f"{metrics.tier2_latency_p99}ms (threshold: 500ms)"))
    else:
        alerts.append(("success", "🟢 Tier 2 latency nominal", f"P99: {metrics.tier2_latency_p99}ms"))

    if metrics.tier1_precision_at10 < 0.50:
        alerts.append(("danger", "🔴 Tier 1 precision below target", f"{metrics.tier1_precision_at10:.3f} < 0.50"))
    else:
        alerts.append(("success", "🟢 Tier 1 precision target met", f"{metrics.tier1_precision_at10:.3f}"))

    if metrics.tier2_entity_f1 < 0.70:
        alerts.append(("danger", "🔴 Tier 2 entity F1 below threshold", f"{metrics.tier2_entity_f1:.3f} < 0.70"))
    else:
        alerts.append(("success", "🟢 Tier 2 entity extraction nominal", f"F1: {metrics.tier2_entity_f1:.3f}"))

    if metrics.error_rate > 0.05:
        alerts.append(("danger", "🔴 Error rate elevated", f"{metrics.error_rate * 100:.1f}% > 5%"))
    else:
        alerts.append(("success", "🟢 Error rate nominal", f"{metrics.error_rate * 100:.1f}%"))

    # Render alerts
    for level, title, desc in alerts:
        if level == "danger":
            st.markdown(f'<div class="alert-danger"><strong>{title}</strong><br>{desc}</div>',
                       unsafe_allow_html=True)
        elif level == "warning":
            st.markdown(f'<div class="alert-warning"><strong>{title}</strong><br>{desc}</div>',
                       unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-success"><strong>{title}</strong><br>{desc}</div>',
                       unsafe_allow_html=True)


def render_footer():
    """Render dashboard footer with documentation links."""
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Documentation**")
        st.markdown(
            "- [Architecture](https://forwardai.dev/sajan/group1-rag-architecture)\n"
            "- [Tier Specs](https://forwardai.dev/sajan/group1-rag-tiers)\n"
            "- [Corpus Pipeline](https://forwardai.dev/sajan/group1-rag-corpus)"
        )
    with col2:
        st.markdown("**Status Pages**")
        st.markdown(
            "- [Retrieval Engine Logs](/group1-rag-logs)\n"
            "- [Vector DB Health](/group1-rag-vectors)\n"
            "- [KG Audit](/group1-rag-kg-audit)"
        )
    with col3:
        st.markdown("**Development**")
        st.markdown(
            "- [Phase 2 Roadmap](/group1-rag-phase2)\n"
            "- [Test Coverage](/group1-rag-tests)\n"
            "- [Incident Log](/group1-rag-incidents)"
        )


# ---- Main ----

def main():
    """Main dashboard entry point."""
    apply_theme()

    # Sidebar controls
    with st.sidebar:
        st.markdown("### Dashboard Controls")
        refresh_interval = st.selectbox(
            "Auto-refresh interval",
            ["Off", "5s", "15s", "30s", "60s"],
            index=0
        )

        tier_filter = st.multiselect(
            "Show tiers",
            ["Tier 1", "Tier 2", "Tier 3"],
            default=["Tier 1", "Tier 2"]
        )

        view_mode = st.radio(
            "View mode",
            ["Overview", "Tier 1 Deep Dive", "Tier 2 Deep Dive", "A/B Test", "Corpus"],
            index=0
        )

        st.markdown("---")
        st.markdown(
            "**Last sync:** " + datetime.now().strftime("%H:%M:%S") +
            "\n\n**Status:** All systems nominal ✓"
        )

    # Load data
    metrics, queries, volume_data, ab_data, latency_data = generate_mock_data()

    # Render based on view mode
    render_header()

    if view_mode == "Overview":
        render_metrics_section(metrics)
        st.divider()
        render_query_volume(volume_data)
        render_latency_timeseries(latency_data)
        st.divider()
        render_error_section(metrics)
        st.divider()
        render_recent_queries(queries)
        st.divider()
        render_ab_test(ab_data)
        st.divider()
        render_corpus_stats(metrics)
        st.divider()
        render_alerts(metrics)

    elif view_mode == "Tier 1 Deep Dive":
        st.markdown("## Tier 1: Retrieval Only (≤100ms)")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("P50 Latency", f"{metrics.tier1_latency_p50}ms", delta="-2ms", delta_color="inverse")
        with col2:
            st.metric("P99 Latency", f"{metrics.tier1_latency_p99}ms", delta="+1ms")
        with col3:
            st.metric("Precision@10", f"{metrics.tier1_precision_at10:.3f}", delta="+0.02")

        st.subheader("Tier 1 Queries")
        tier1_queries = [q for q in queries if q.tier == "Tier 1"]
        st.dataframe(
            pd.DataFrame([q.to_dict() for q in tier1_queries]),
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Performance Distribution")
        latency_dist = np.random.normal(metrics.tier1_latency_p50, 8, 1000)
        st.histogram(latency_dist, bins=30, title="Latency Distribution (ms)")

    elif view_mode == "Tier 2 Deep Dive":
        st.markdown("## Tier 2: Entity Extraction (≤500ms)")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("P50 Latency", f"{metrics.tier2_latency_p50}ms", delta="+5ms")
        with col2:
            st.metric("P99 Latency", f"{metrics.tier2_latency_p99}ms", delta="-8ms", delta_color="inverse")
        with col3:
            st.metric("Entity F1", f"{metrics.tier2_entity_f1:.3f}", delta="+0.01")

        st.subheader("Tier 2 Queries")
        tier2_queries = [q for q in queries if q.tier == "Tier 2"]
        st.dataframe(
            pd.DataFrame([q.to_dict() for q in tier2_queries]),
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Entity Extraction Breakdown")
        entities = ["Regime", "Strategy", "Greeks", "Instrument", "Counterparty"]
        scores = [0.88, 0.85, 0.84, 0.82, 0.79]
        entity_df = pd.DataFrame({"Entity Type": entities, "F1 Score": scores})
        st.bar_chart(entity_df.set_index("Entity Type"))

    elif view_mode == "A/B Test":
        render_ab_test(ab_data)
        st.subheader("Test Infrastructure Status")
        st.info(
            "**Tier 3 A/B Test Harness:** Ready for Phase 2 launch.\n\n"
            "- Hypothesis: Tier 3 agentic reasoning achieves 90%+ user satisfaction\n"
            "- Allocation: 50/50 split Tier 2 baseline vs Tier 3 candidate\n"
            "- Duration: 2 weeks minimum, until 95% confidence\n"
            "- Success metric: Satisfaction improvement > 10 points"
        )

    elif view_mode == "Corpus":
        render_corpus_stats(metrics)

    # Footer
    render_footer()


if __name__ == "__main__":
    main()
