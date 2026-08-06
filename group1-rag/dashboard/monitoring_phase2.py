#!/usr/bin/env python3
"""
Group One RAG Phase 2 Advanced Monitoring Dashboard

Extends dashboard.py with:
  1. Tier 3 Metrics: reasoning steps, branching factor, latency per step
  2. Safety Metrics: limit violations, correlation flags, circuit breaker triggers
  3. A/B Comparison: Tier 2 vs Tier 3 (Sharpe, max drawdown, p-value)
  4. Learning Feedback: lessons extracted, KB confidence scores, conflicts
  5. Failure Mode Alerts: reasoning depth, safety escalation, correlation breakdown, regime shift
  6. Live Trade Monitoring: position Greeks, correlation matrix, margin utilization
  7. Visualizations: correlation heatmaps, Sharpe convergence time series, escalation event logs

Run: streamlit run monitoring_phase2.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import json
from pathlib import Path
from scipy import stats

# Page config
st.set_page_config(
    page_title="Group One RAG Phase 2 Monitor",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---- Phase 2 Data Models ----

class Tier3Metrics:
    """Tier 3 Agentic Reasoning metrics."""
    def __init__(self):
        # Reasoning pipeline
        self.reasoning_steps_avg = 3.2  # avg steps per query
        self.reasoning_steps_max = 7
        self.branching_factor_avg = 2.1  # avg branches explored
        self.branching_factor_max = 5

        # Per-step latency (ms)
        self.step_retrieve_ms = 150  # entity retrieval
        self.step_infer_ms = 200     # inference/reasoning
        self.step_validate_ms = 80   # safety validation
        self.step_aggregate_ms = 40  # result aggregation

        # Tier 3 latency SLA
        self.tier3_latency_p50 = 520  # ms
        self.tier3_latency_p99 = 4800  # ms (within 5s SLA)
        self.tier3_precision = 0.92
        self.tier3_queries_processed = 128  # Phase 2 pilot
        self.tier3_success_rate = 0.94


class SafetyMetrics:
    """Safety & compliance metrics for Tier 3."""
    def __init__(self):
        # Limit violations (detected & prevented)
        self.margin_violations_caught = 12
        self.position_limit_violations = 5
        self.greeks_exposure_violations = 3
        self.correlation_breakdown_flags = 7

        # Safety checks
        self.circuit_breaker_triggers = 2
        self.escalations_to_human = 1
        self.safety_validation_rate = 0.99
        self.false_positive_rate = 0.02  # overly conservative alerts

        # Correlation & regime tracking
        self.correlation_matrix_updates = 47
        self.regime_shift_detections = 2
        self.crisis_mode_enabled_hours = 1.5


class ABTestPhase2:
    """Phase 2 A/B test results (Tier 2 baseline vs Tier 3 candidate)."""
    def __init__(self):
        # Phase 2 pilot A/B test (2 weeks running)
        self.queries_tier2 = 2847
        self.queries_tier3 = 128

        # Performance metrics
        self.tier2_sharpe = 1.84
        self.tier3_sharpe = 2.12
        self.sharpe_p_value = 0.034  # statistically significant

        self.tier2_max_drawdown = -0.087
        self.tier3_max_drawdown = -0.062
        self.drawdown_improvement = 0.025

        self.tier2_latency_p50 = 280
        self.tier3_latency_p50 = 520
        self.tier2_precision = 0.84
        self.tier3_precision = 0.92

        self.tier2_user_satisfaction = 0.76
        self.tier3_user_satisfaction = 0.88
        self.satisfaction_improvement = 0.12

        # Statistical power
        self.confidence_level = 0.95
        self.test_status = "Running (2w elapsed)"


class LearningFeedback:
    """Knowledge base learning & lessons learned."""
    def __init__(self):
        # Lessons extracted this week
        self.lessons_extracted = 23
        self.high_confidence_lessons = 18
        self.kb_confidence_avg = 0.76

        # Confidence score distribution
        self.confidence_scores = {
            "high (>0.8)": 18,
            "medium (0.6-0.8)": 4,
            "low (<0.6)": 1
        }

        # Conflicts & deduplication
        self.conflicts_detected = 3
        self.conflicts_resolved = 2
        self.dedup_ratio = 0.12  # 12% of new lessons are duplicates


class LiveTradeMonitoring:
    """Real-time portfolio & trade monitoring."""
    def __init__(self):
        # Position Greeks (aggregate portfolio)
        self.delta_exposure = 0.34
        self.gamma_exposure = 0.021
        self.vega_exposure = 2.4  # ($ per 1 vol point)
        self.theta_daily = -850  # ($ per day)
        self.rho_exposure = 1.2  # ($ per 1 bp rate change)

        # Margin & utilization
        self.margin_used_pct = 0.62
        self.margin_used_usd = 310_000
        self.margin_available_usd = 500_000 - 310_000

        # Correlation matrix (selected pairs)
        self.correlation_pairs = {
            "SPY-VIX": -0.72,
            "TLT-IEF": 0.95,
            "GLD-USD": -0.18,
            "DBC-USD": 0.42
        }


class FailureMode:
    """Represents a failure mode alert."""
    def __init__(self, mode_type, severity, trigger_value, threshold, timestamp=None):
        self.mode_type = mode_type  # "reasoning_depth", "safety_escalation", etc.
        self.severity = severity    # "critical", "warning", "info"
        self.trigger_value = trigger_value
        self.threshold = threshold
        self.timestamp = timestamp or datetime.now()
        self.is_active = True
        self.resolved_at = None


def generate_phase2_mock_data():
    """Generate realistic Phase 2 data with Tier 3, safety, and live trade info."""
    tier3 = Tier3Metrics()
    safety = SafetyMetrics()
    ab_test = ABTestPhase2()
    learning = LearningFeedback()
    trades = LiveTradeMonitoring()

    # Failure modes (recent incidents & escalations)
    failures = [
        FailureMode("reasoning_depth_exceeded", "warning", 7, 6,
                   datetime.now() - timedelta(minutes=45)),
        FailureMode("safety_escalation_triggered", "critical", 1, 0,
                   datetime.now() - timedelta(minutes=12)),
        FailureMode("correlation_breakdown", "warning", -0.15, -0.10,
                   datetime.now() - timedelta(minutes=8)),
        FailureMode("regime_shift_detected", "info", 2, 1,
                   datetime.now() - timedelta(hours=1))
    ]

    # Sharpe ratio convergence (last 14 days, 2-week A/B test)
    days = pd.date_range(end=datetime.now(), periods=14, freq='D')
    tier2_sharpe_ts = [1.52 + 0.05*i + np.random.normal(0, 0.03) for i in range(14)]
    tier3_sharpe_ts = [1.78 + 0.08*i + np.random.normal(0, 0.04) for i in range(14)]
    sharpe_data = pd.DataFrame({
        "Date": days,
        "Tier 2 (Baseline)": tier2_sharpe_ts,
        "Tier 3 (Candidate)": tier3_sharpe_ts
    })

    # Correlation matrix heatmap data (daily changes over 10 days)
    assets = ["SPY", "QQQ", "IWM", "VIX", "TLT"]
    corr_snapshots = []
    for day in range(10):
        np.random.seed(100 + day)
        corr_matrix = np.random.uniform(-0.8, 0.95, (5, 5))
        corr_matrix = (corr_matrix + corr_matrix.T) / 2
        np.fill_diagonal(corr_matrix, 1.0)
        corr_snapshots.append(corr_matrix)

    # Escalation event log (safety events this week)
    escalations = pd.DataFrame({
        "Timestamp": [
            datetime.now() - timedelta(minutes=12),
            datetime.now() - timedelta(hours=3),
            datetime.now() - timedelta(hours=8),
            datetime.now() - timedelta(days=1, hours=2)
        ],
        "Event Type": [
            "Safety Escalation",
            "Reasoning Depth Exceeded",
            "Correlation Breakdown",
            "Circuit Breaker Trigger"
        ],
        "Severity": ["Critical", "Warning", "Warning", "Info"],
        "Resolution": ["Human Review", "Fallback to Tier 2", "KG Refresh", "Auto-Reset"]
    })

    return tier3, safety, ab_test, learning, trades, failures, sharpe_data, corr_snapshots, escalations


# ---- Styling ----

def apply_phase2_theme():
    """Apply Phase 2 dashboard theme with dark mode support."""
    theme_css = """
    <style>
    :root {
        --primary: #0066cc;
        --primary-light: #3b82f6;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --critical: #dc2626;
        --text-primary: #1f2937;
        --text-secondary: #6b7280;
        --bg-card: #ffffff;
        --bg-alt: #f9fafb;
        --border: #e5e7eb;
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --text-primary: #f3f4f6;
            --text-secondary: #d1d5db;
            --bg-card: #1f2937;
            --bg-alt: #111827;
            --border: #374151;
        }
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    h1 { color: var(--text-primary); font-size: 2rem; font-weight: 700; }
    h2 { color: var(--text-primary); font-size: 1.5rem; font-weight: 600; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
    h3 { color: var(--text-primary); font-size: 1.125rem; font-weight: 600; }

    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    .alert-critical {
        background: rgba(220, 38, 38, 0.1);
        border-left: 4px solid #dc2626;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }

    .alert-danger {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }

    .alert-warning {
        background: rgba(245, 158, 11, 0.1);
        border-left: 4px solid #f59e0b;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }

    .alert-success {
        background: rgba(16, 185, 129, 0.1);
        border-left: 4px solid #10b981;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }
    </style>
    """
    st.markdown(theme_css, unsafe_allow_html=True)


# ---- Dashboard Components ----

def render_phase2_header():
    """Render Phase 2 dashboard header."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🚀 Group One RAG Phase 2 Monitor")
        st.markdown("_Real-time monitoring for Tier 3 agentic reasoning + safety + live trades_")
    with col2:
        st.metric("Status", "Phase 2 LIVE", delta="A/B Test Running")
        st.metric("Last Sync", datetime.now().strftime("%H:%M:%S"))


def render_tier3_metrics(tier3):
    """Render Tier 3 agentic reasoning metrics."""
    st.markdown("## Tier 3: Agentic Reasoning Metrics (≤5s SLA)")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            "Latency P50",
            f"{tier3.tier3_latency_p50}ms",
            delta="-20ms",
            delta_color="inverse"
        )
    with col2:
        st.metric(
            "Latency P99",
            f"{tier3.tier3_latency_p99}ms",
            delta="+100ms"
        )
    with col3:
        st.metric(
            "Precision",
            f"{tier3.tier3_precision:.3f}",
            delta="+0.08"
        )
    with col4:
        st.metric(
            "Success Rate",
            f"{tier3.tier3_success_rate:.1%}",
            delta="-1%"
        )
    with col5:
        st.metric(
            "Queries (Pilot)",
            f"{tier3.tier3_queries_processed:,}",
            delta="+32 today"
        )

    # Reasoning pipeline breakdown
    st.subheader("Reasoning Pipeline Breakdown (Per-Step Latency)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Retrieve", f"{tier3.step_retrieve_ms}ms", delta="-5ms", delta_color="inverse")
    with col2:
        st.metric("Infer", f"{tier3.step_infer_ms}ms", delta="+10ms")
    with col3:
        st.metric("Validate", f"{tier3.step_validate_ms}ms", delta="-2ms", delta_color="inverse")
    with col4:
        st.metric("Aggregate", f"{tier3.step_aggregate_ms}ms", delta="+1ms")

    # Reasoning complexity
    st.subheader("Reasoning Complexity Distribution")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Avg Steps/Query", f"{tier3.reasoning_steps_avg:.1f}", delta="+0.1")
        st.caption(f"Max: {tier3.reasoning_steps_max} steps")
    with col2:
        st.metric("Avg Branching Factor", f"{tier3.branching_factor_avg:.1f}", delta="-0.1", delta_color="inverse")
        st.caption(f"Max: {tier3.branching_factor_max} branches")

    # Reasoning complexity histogram
    steps_dist = np.random.normal(tier3.reasoning_steps_avg, 1.2, 500)
    steps_dist = np.clip(steps_dist, 1, 10).astype(int)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(steps_dist, bins=range(1, 11), alpha=0.7, color='#3b82f6', edgecolor='black')
    ax.set_xlabel("Reasoning Steps per Query")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Reasoning Steps (Phase 2 Pilot)")
    ax.grid(axis='y', alpha=0.3)
    st.pyplot(fig, use_container_width=True)


def render_safety_metrics(safety):
    """Render safety & compliance metrics."""
    st.markdown("## Safety & Compliance Metrics")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Violations Caught",
            f"{safety.margin_violations_caught + safety.position_limit_violations + safety.greeks_exposure_violations}",
            delta="+3 today",
            delta_color="off"
        )
    with col2:
        st.metric(
            "Circuit Breaks",
            f"{safety.circuit_breaker_triggers}",
            delta="This week"
        )
    with col3:
        st.metric(
            "Escalations",
            f"{safety.escalations_to_human}",
            delta="Pending review"
        )
    with col4:
        st.metric(
            "Safety Check Rate",
            f"{safety.safety_validation_rate:.1%}",
            delta="+0.5pp"
        )

    # Violation breakdown
    st.subheader("Limit Violations Detected (Prevention System)")
    violation_data = pd.DataFrame({
        "Violation Type": [
            "Margin Violations",
            "Position Limits",
            "Greeks Exposure",
            "Correlation Flags"
        ],
        "Count": [
            safety.margin_violations_caught,
            safety.position_limit_violations,
            safety.greeks_exposure_violations,
            safety.correlation_breakdown_flags
        ]
    })

    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.barh(violation_data["Violation Type"], violation_data["Count"], color=['#ef4444', '#f59e0b', '#f59e0b', '#06b6d4'])
    ax.set_xlabel("Count")
    ax.set_title("Limit Violations Detected This Week (All Prevented)")
    ax.grid(axis='x', alpha=0.3)
    for i, (bar, count) in enumerate(zip(bars, violation_data["Count"])):
        ax.text(count + 0.2, bar.get_y() + bar.get_height()/2, str(count), va='center')
    st.pyplot(fig, use_container_width=True)

    st.markdown("**Key:** All violations detected in real-time and prevented before trade execution. "
                "False positive rate: 2% (overly conservative).")


def render_ab_comparison(ab_test):
    """Render detailed A/B test comparison (Tier 2 vs Tier 3)."""
    st.markdown("## A/B Test: Tier 2 vs Tier 3 (Phase 2 Running)")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Tier 2 (Baseline)")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.metric("Queries", f"{ab_test.queries_tier2:,}")
            st.metric("Sharpe Ratio", f"{ab_test.tier2_sharpe:.2f}")
            st.metric("Max Drawdown", f"{ab_test.tier2_max_drawdown:.1%}")
        with col_a2:
            st.metric("Latency P50", f"{ab_test.tier2_latency_p50}ms")
            st.metric("Precision", f"{ab_test.tier2_precision:.3f}")
            st.metric("Satisfaction", f"{ab_test.tier2_user_satisfaction:.0%}")

    with col2:
        st.subheader("🚀 Tier 3 (Candidate)")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.metric("Queries", f"{ab_test.queries_tier3:,}")
            st.metric("Sharpe Ratio", f"{ab_test.tier3_sharpe:.2f}", delta=f"+{ab_test.tier3_sharpe - ab_test.tier2_sharpe:.2f}")
            st.metric("Max Drawdown", f"{ab_test.tier3_max_drawdown:.1%}", delta=f"{ab_test.tier3_max_drawdown - ab_test.tier2_max_drawdown:.1%}", delta_color="inverse")
        with col_b2:
            st.metric("Latency P50", f"{ab_test.tier3_latency_p50}ms", delta=f"+{ab_test.tier3_latency_p50 - ab_test.tier2_latency_p50}ms")
            st.metric("Precision", f"{ab_test.tier3_precision:.3f}", delta=f"+{ab_test.tier3_precision - ab_test.tier2_precision:.3f}")
            st.metric("Satisfaction", f"{ab_test.tier3_user_satisfaction:.0%}", delta=f"+{ab_test.tier3_user_satisfaction - ab_test.tier2_user_satisfaction:.0%}")

    # Statistical significance
    st.subheader("Statistical Significance (Sharpe Ratio)")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("P-Value", f"{ab_test.sharpe_p_value:.4f}")
        st.caption(f"Confidence: {ab_test.confidence_level:.0%}")
    with col2:
        if ab_test.sharpe_p_value < 0.05:
            st.markdown('<div class="alert-success">✓ Statistically significant (p < 0.05)</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-warning">⚠ Not significant yet (p ≥ 0.05)</div>', unsafe_allow_html=True)

    st.info(f"**Test Status:** {ab_test.test_status} | "
            f"**Satisfaction Improvement:** +{ab_test.satisfaction_improvement:.0%} | "
            f"**Drawdown Improvement:** +{ab_test.drawdown_improvement:.1%}")


def render_sharpe_convergence(sharpe_data):
    """Render Sharpe ratio convergence over time (A/B test duration)."""
    st.markdown("## Sharpe Ratio Convergence (14-Day A/B Test)")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(sharpe_data["Date"], sharpe_data["Tier 2 (Baseline)"], marker='o', label='Tier 2 (Baseline)', linewidth=2)
    ax.plot(sharpe_data["Date"], sharpe_data["Tier 3 (Candidate)"], marker='s', label='Tier 3 (Candidate)', linewidth=2)
    ax.fill_between(sharpe_data["Date"], sharpe_data["Tier 2 (Baseline)"], sharpe_data["Tier 3 (Candidate)"], alpha=0.2)
    ax.set_xlabel("Date")
    ax.set_ylabel("Sharpe Ratio")
    ax.set_title("Sharpe Ratio Convergence: Tier 2 Baseline vs Tier 3 Candidate")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig, use_container_width=True)

    st.caption("Tier 3 consistently outperforms baseline with statistical significance reached on Day 12.")


def render_correlation_heatmap(corr_snapshots):
    """Render correlation matrix heatmap (latest snapshot)."""
    st.markdown("## Correlation Matrix Snapshot (Latest)")

    assets = ["SPY", "QQQ", "IWM", "VIX", "TLT"]
    latest_corr = corr_snapshots[-1]  # Most recent

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(latest_corr, annot=True, fmt='.2f', cmap='coolwarm', center=0,
                xticklabels=assets, yticklabels=assets, cbar_kws={'label': 'Correlation'},
                vmin=-1, vmax=1, ax=ax)
    ax.set_title("Asset Correlation Matrix (Latest Snapshot)")
    st.pyplot(fig, use_container_width=True)

    # Correlation change summary
    st.subheader("Correlation Changes (24h)")
    prev_corr = corr_snapshots[-2] if len(corr_snapshots) > 1 else corr_snapshots[-1]
    changes = latest_corr - prev_corr

    change_data = []
    for i in range(len(assets)):
        for j in range(i+1, len(assets)):
            change_data.append({
                "Pair": f"{assets[i]}-{assets[j]}",
                "Previous": f"{prev_corr[i,j]:.3f}",
                "Current": f"{latest_corr[i,j]:.3f}",
                "Change": f"{changes[i,j]:+.3f}"
            })

    change_df = pd.DataFrame(change_data)
    st.dataframe(change_df, use_container_width=True, hide_index=True)


def render_learning_feedback(learning):
    """Render knowledge base learning & KB confidence scores."""
    st.markdown("## Learning Feedback (This Week)")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Lessons Extracted",
            f"{learning.lessons_extracted}",
            delta=f"+{learning.high_confidence_lessons} high-conf"
        )
    with col2:
        st.metric(
            "KB Confidence (Avg)",
            f"{learning.kb_confidence_avg:.2f}",
            delta="+0.04"
        )
    with col3:
        st.metric(
            "Conflicts Detected",
            f"{learning.conflicts_detected}",
            delta=f"-{learning.conflicts_detected - learning.conflicts_resolved} resolved"
        )

    # Confidence score distribution
    st.subheader("KB Confidence Score Distribution")
    conf_data = pd.DataFrame({
        "Confidence Level": list(learning.confidence_scores.keys()),
        "Count": list(learning.confidence_scores.values())
    })

    fig, ax = plt.subplots(figsize=(10, 4))
    colors = ['#10b981', '#3b82f6', '#f59e0b']
    bars = ax.bar(conf_data["Confidence Level"], conf_data["Count"], color=colors, edgecolor='black')
    ax.set_ylabel("Number of Lessons")
    ax.set_title("Knowledge Base Confidence Score Distribution")
    ax.grid(axis='y', alpha=0.3)
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontweight='bold')
    st.pyplot(fig, use_container_width=True)

    # Conflict resolution
    st.subheader("Conflict Resolution")
    conflict_rate = (learning.conflicts_detected - learning.conflicts_resolved) / learning.conflicts_detected if learning.conflicts_detected > 0 else 0
    st.info(f"**{learning.conflicts_resolved}/{learning.conflicts_detected}** conflicts resolved | "
            f"**Dedup Ratio:** {learning.dedup_ratio:.0%} of new lessons are duplicates (healthy)")


def render_live_trade_monitoring(trades):
    """Render live portfolio Greeks and margin utilization."""
    st.markdown("## Live Trade Monitoring")

    # Greeks exposure
    st.subheader("Portfolio Greeks Exposure (Aggregate)")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Delta", f"{trades.delta_exposure:+.2f}", delta="+0.05")
    with col2:
        st.metric("Gamma", f"{trades.gamma_exposure:+.3f}", delta="-0.001", delta_color="inverse")
    with col3:
        st.metric("Vega", f"${trades.vega_exposure:+.1f}", delta="-0.2")
    with col4:
        st.metric("Theta (Daily)", f"${trades.theta_daily:+,.0f}", delta="-$50", delta_color="inverse")
    with col5:
        st.metric("Rho", f"${trades.rho_exposure:+.1f}", delta="+0.1")

    # Margin utilization
    st.subheader("Margin Utilization")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Margin Used",
            f"{trades.margin_used_pct:.0%}",
            delta="+2pp"
        )
        st.caption(f"${trades.margin_used_usd:,} / ${trades.margin_used_usd + trades.margin_available_usd:,}")
    with col2:
        fig, ax = plt.subplots(figsize=(6, 4))
        sizes = [trades.margin_used_usd, trades.margin_available_usd]
        labels = [f"Used\n${trades.margin_used_usd:,.0f}", f"Available\n${trades.margin_available_usd:,.0f}"]
        colors = ['#ef4444', '#10b981']
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%',
                                           startangle=90, textprops={'fontsize': 10})
        ax.set_title("Margin Utilization")
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        st.pyplot(fig, use_container_width=True)

    # Correlation matrix (selected pairs)
    st.subheader("Key Asset Pair Correlations")
    corr_data = pd.DataFrame({
        "Pair": list(trades.correlation_pairs.keys()),
        "Correlation": list(trades.correlation_pairs.values())
    })

    fig, ax = plt.subplots(figsize=(10, 4))
    colors_corr = ['#ef4444' if x < 0 else '#10b981' for x in corr_data["Correlation"]]
    bars = ax.barh(corr_data["Pair"], corr_data["Correlation"], color=colors_corr, edgecolor='black')
    ax.axvline(0, color='black', linewidth=0.8)
    ax.set_xlabel("Correlation Coefficient")
    ax.set_title("Key Asset Pair Correlations")
    ax.set_xlim([-1, 1])
    ax.grid(axis='x', alpha=0.3)
    for bar, corr in zip(bars, corr_data["Correlation"]):
        ax.text(corr + 0.05 if corr > 0 else corr - 0.05, bar.get_y() + bar.get_height()/2,
                f'{corr:.2f}', va='center', ha='left' if corr > 0 else 'right', fontweight='bold')
    st.pyplot(fig, use_container_width=True)


def render_failure_mode_alerts(failures):
    """Render failure mode alerts and escalations."""
    st.markdown("## Failure Mode Alerts (This Week)")

    for failure in failures:
        severity_emoji = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "ℹ️"
        }

        alert_class = {
            "critical": "alert-critical",
            "warning": "alert-warning",
            "info": "alert-success"
        }

        time_ago = datetime.now() - failure.timestamp
        if time_ago.total_seconds() < 60:
            time_str = f"{int(time_ago.total_seconds())}s ago"
        elif time_ago.total_seconds() < 3600:
            time_str = f"{int(time_ago.total_seconds() / 60)}m ago"
        else:
            time_str = f"{int(time_ago.total_seconds() / 3600)}h ago"

        alert_html = f"""
        <div class="{alert_class[failure.severity]}">
            <strong>{severity_emoji[failure.severity]} {failure.mode_type.replace('_', ' ').title()}</strong><br>
            Triggered {time_str} | Value: {failure.trigger_value} (Threshold: {failure.threshold}) | Status: {"Active" if failure.is_active else "Resolved"}
        </div>
        """
        st.markdown(alert_html, unsafe_allow_html=True)


def render_escalation_event_log(escalations):
    """Render safety escalation event log."""
    st.markdown("## Escalation Event Log (This Week)")

    def color_severity(severity):
        if severity == "Critical":
            return "background-color: rgba(220, 38, 38, 0.2)"
        elif severity == "Warning":
            return "background-color: rgba(245, 158, 11, 0.2)"
        else:
            return "background-color: rgba(16, 185, 129, 0.2)"

    # Format timestamps
    escalations_display = escalations.copy()
    escalations_display["Timestamp"] = escalations_display["Timestamp"].apply(lambda x: x.strftime("%H:%M:%S"))
    escalations_display["Timestamp"] = escalations_display["Timestamp"].apply(lambda x: f"{x} ({(datetime.now() - datetime.strptime(x, '%H:%M:%S')).seconds // 60}m ago)")

    styled_df = escalations_display.style.applymap(
        lambda x: color_severity(x) if isinstance(x, str) else "",
        subset=["Severity"]
    )

    st.dataframe(styled_df, use_container_width=True, hide_index=True)


# ---- Main ----

def main():
    """Main Phase 2 monitoring dashboard."""
    apply_phase2_theme()

    # Sidebar controls
    with st.sidebar:
        st.markdown("### Phase 2 Monitor Controls")

        view_mode = st.radio(
            "View Mode",
            [
                "Overview",
                "Tier 3 Deep Dive",
                "Safety & Compliance",
                "A/B Test Analysis",
                "Learning Feedback",
                "Live Trading",
                "Failure Modes"
            ],
            index=0
        )

        refresh_interval = st.selectbox(
            "Auto-refresh",
            ["Off", "5s", "15s", "30s"],
            index=0
        )

        st.markdown("---")
        st.markdown(f"**Last sync:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                   f"**Phase 2 Status:** LIVE (A/B Test Running)")

    # Load Phase 2 data
    tier3, safety, ab_test, learning, trades, failures, sharpe_data, corr_snapshots, escalations = generate_phase2_mock_data()

    # Render header
    render_phase2_header()
    st.divider()

    # Render based on view mode
    if view_mode == "Overview":
        render_tier3_metrics(tier3)
        st.divider()
        render_safety_metrics(safety)
        st.divider()
        render_ab_comparison(ab_test)
        st.divider()
        render_sharpe_convergence(sharpe_data)
        st.divider()
        render_correlation_heatmap(corr_snapshots)
        st.divider()
        render_failure_mode_alerts(failures)

    elif view_mode == "Tier 3 Deep Dive":
        render_tier3_metrics(tier3)
        st.subheader("Tier 3 Pipeline Latency Breakdown")
        latency_components = pd.DataFrame({
            "Stage": ["Retrieve", "Infer", "Validate", "Aggregate"],
            "Latency (ms)": [tier3.step_retrieve_ms, tier3.step_infer_ms, tier3.step_validate_ms, tier3.step_aggregate_ms]
        })
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(latency_components["Stage"], latency_components["Latency (ms)"], color=['#3b82f6', '#0066cc', '#06b6d4', '#10b981'], edgecolor='black')
        ax.set_ylabel("Latency (ms)")
        ax.set_title("Tier 3 Pipeline Stage Latency Breakdown")
        ax.grid(axis='y', alpha=0.3)
        for i, (stage, latency) in enumerate(zip(latency_components["Stage"], latency_components["Latency (ms)"])):
            ax.text(i, latency + 5, str(latency), ha='center', va='bottom', fontweight='bold')
        st.pyplot(fig, use_container_width=True)

    elif view_mode == "Safety & Compliance":
        render_safety_metrics(safety)
        st.divider()
        render_escalation_event_log(escalations)
        st.divider()
        render_failure_mode_alerts(failures)

    elif view_mode == "A/B Test Analysis":
        render_ab_comparison(ab_test)
        st.divider()
        render_sharpe_convergence(sharpe_data)

    elif view_mode == "Learning Feedback":
        render_learning_feedback(learning)

    elif view_mode == "Live Trading":
        render_live_trade_monitoring(trades)
        st.divider()
        render_correlation_heatmap(corr_snapshots)

    elif view_mode == "Failure Modes":
        render_failure_mode_alerts(failures)
        st.divider()
        render_escalation_event_log(escalations)

    # Footer
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Documentation**")
        st.markdown("- [Tier 3 Architecture](https://forwardai.dev/sajan/group1-rag-tier3)\n"
                   "- [Safety Framework](https://forwardai.dev/sajan/group1-rag-safety)\n"
                   "- [Phase 2 Roadmap](https://forwardai.dev/sajan/group1-rag-phase2)")
    with col2:
        st.markdown("**Monitoring**")
        st.markdown("- [Escalation Log](/group1-rag-escalations)\n"
                   "- [A/B Test Results](/group1-rag-ab-results)\n"
                   "- [KB Health](/group1-rag-kb-health)")
    with col3:
        st.markdown("**Support**")
        st.markdown("- [Incident Response](/group1-rag-incidents)\n"
                   "- [Test Coverage](/group1-rag-tests)\n"
                   "- [Performance Tuning](/group1-rag-tuning)")


if __name__ == "__main__":
    main()
