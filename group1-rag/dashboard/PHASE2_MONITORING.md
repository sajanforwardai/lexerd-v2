# Phase 2 Monitoring Dashboard — Group One RAG System

## Overview

The Phase 2 monitoring dashboard extends the existing Group One RAG dashboard with comprehensive tracking for **Tier 3 agentic reasoning**, **safety compliance**, **A/B testing**, **learning feedback**, **live trading metrics**, and **failure mode detection**.

**Dashboard Entry Point:** `monitoring_phase2.py` (run alongside or replace `dashboard.py`)

## Architecture

### New Components (Phase 2)

1. **Tier 3 Metrics** — Reasoning depth, branching factor, per-step latency
2. **Safety Metrics** — Limit violations caught, circuit breaker triggers, correlation flags
3. **A/B Test Analysis** — Tier 2 baseline vs Tier 3 candidate (Sharpe, drawdown, p-value)
4. **Learning Feedback** — Lessons extracted, KB confidence scores, conflict detection
5. **Live Trading Monitoring** — Position Greeks, correlation matrix, margin utilization
6. **Failure Mode Alerts** — Escalations, reasoning depth exceeded, regime shifts
7. **Visualizations** — Heatmaps, time series (Sharpe convergence), event logs

### Data Models

```python
class Tier3Metrics
  - reasoning_steps_avg, max
  - branching_factor_avg, max
  - step_retrieve_ms, step_infer_ms, step_validate_ms, step_aggregate_ms
  - tier3_latency_p50/p99
  - tier3_precision, success_rate

class SafetyMetrics
  - margin_violations_caught, position_limit_violations, greeks_exposure_violations
  - circuit_breaker_triggers
  - escalations_to_human
  - correlation_breakdown_flags

class ABTestPhase2
  - queries_tier2, queries_tier3
  - tier2/tier3_sharpe, max_drawdown, latency_p50, precision
  - tier2/tier3_user_satisfaction
  - sharpe_p_value (statistical significance)

class LearningFeedback
  - lessons_extracted, high_confidence_lessons
  - kb_confidence_avg, confidence_scores distribution
  - conflicts_detected, conflicts_resolved

class LiveTradeMonitoring
  - delta, gamma, vega, theta, rho exposure
  - margin_used_pct, margin_available_usd
  - correlation_pairs (SPY-VIX, TLT-IEF, etc.)

class FailureMode
  - mode_type (reasoning_depth, safety_escalation, correlation_breakdown, regime_shift)
  - severity (critical, warning, info)
  - trigger_value, threshold
```

## Dashboard Views

### 1. Overview (Default)
- Tier 3 real-time metrics (latency, precision, queries)
- Safety metrics (violations caught, circuit breaks)
- A/B test comparison (Tier 2 vs Tier 3)
- Sharpe ratio convergence (14-day trend)
- Correlation matrix snapshot
- Active failure mode alerts

### 2. Tier 3 Deep Dive
- Per-step latency breakdown (Retrieve → Infer → Validate → Aggregate)
- Reasoning steps distribution (histogram)
- Branching factor evolution
- Query complexity analysis

### 3. Safety & Compliance
- Limit violation breakdown (margin, position, Greeks, correlation)
- Circuit breaker trigger history
- Escalation event log (with resolution)
- Active failure modes (reasoning depth, safety escalation, regime shift)

### 4. A/B Test Analysis
- Sharpe ratio comparison (time series over 14 days)
- Max drawdown improvement
- Latency & precision tradeoff
- User satisfaction metrics
- Statistical significance (p-value)

### 5. Learning Feedback
- Lessons extracted (distribution by confidence)
- KB confidence score histogram
- Conflict detection & resolution
- Deduplication ratio

### 6. Live Trading
- Portfolio Greeks exposure (Delta, Gamma, Vega, Theta, Rho)
- Margin utilization (% used, pie chart)
- Key asset pair correlations (SPY-VIX, TLT-IEF, GLD-USD, DBC-USD)
- Correlation matrix heatmap (5x5 assets)

### 7. Failure Modes
- Active failure mode alerts (reasoning depth, safety escalation, regime shift)
- Escalation event log with severity coloring
- Time since trigger + resolution status

## Alert Configuration (`alerts_config.yaml`)

### Tier 3 Metrics Thresholds

```yaml
tier3_metrics:
  latency:
    p99_target_ms: 4500
    p99_critical_ms: 5000  # SLA hard limit

  reasoning:
    max_steps_warning: 7
    max_steps_critical: 8
    branching_factor_warning: 2.5

  quality:
    precision_target: 0.90
    success_rate_target: 0.95
```

### Safety Metrics Thresholds

```yaml
safety_metrics:
  violations:
    margin_limit_critical: 10
    position_limit_critical: 5
    correlation_breakdown_critical: 10

  circuit_breaker:
    triggers_per_day_critical: 5
    reset_interval_minutes: 30
```

### A/B Test Configuration

```yaml
ab_test:
  sharpe_ratio:
    statistical_significance_p_value: 0.05
    tier3_improvement_target: 0.25  # 25 bps Sharpe improvement

  satisfaction:
    tier3_target: 0.88  # 12-13% above Tier 2
    minimum_improvement: 0.10

  test_duration_days: 14
```

### Failure Mode Detection

```yaml
failure_modes:
  reasoning_depth_exceeded:
    threshold_steps: 6
    escalation_action: "fallback_to_tier2"

  safety_escalation_triggered:
    escalation_action: "human_review"
    escalation_sla_minutes: 15

  correlation_breakdown:
    threshold_correlation_drop: -0.20
    escalation_action: "kg_refresh"

  regime_shift_detected:
    volatility_spike_pct: 30
    escalation_action: "knowledge_update"
```

### Escalation Policies

```yaml
escalations:
  critical: ["pagerduty", "slack#trading-alerts", "email"]
  warning: ["slack#trading-alerts"]
  info: ["slack#trading-info"]

  escalation_sla:
    critical: 15 minutes
    warning: 60 minutes
    info: 240 minutes
```

## Key Metrics & KPIs

### Tier 3 Performance
- **Latency P50:** Target 500ms, warning 600ms, critical 800ms
- **Latency P99:** Target 4500ms, critical 5000ms (SLA hard limit)
- **Precision:** Target 0.90, warning 0.85, critical 0.80
- **Success Rate:** Target 95%, warning 92%, critical 90%

### Safety
- **Margin Violations Caught:** Cumulative prevention score
- **Circuit Breaker Triggers:** <3/day nominal, >5/day critical
- **Safety Check Rate:** Target 99%
- **False Positive Rate:** Target 1%, acceptable 3%, critical 5%

### A/B Test (Phase 2 Pilot)
- **Sharpe Ratio:** Tier 3 target 2.12 (+0.28 vs Tier 2's 1.84)
- **Significance:** p-value <0.05 (statistically significant on Day 12)
- **Max Drawdown:** Tier 3 target -6.2% vs Tier 2's -8.7% (+2.5% improvement)
- **User Satisfaction:** Tier 3 target 88% vs Tier 2's 76% (+12% improvement)

### Learning Feedback
- **Lessons Extracted:** Target 20/week
- **KB Confidence:** Target 78%, warning 72%, critical 65%
- **Conflicts Resolved:** SLA 24 hours

### Live Trading
- **Margin Utilization:** Nominal <70%, warning 70%, critical 85%
- **Portfolio Delta:** Normalized to [-1, +1] range
- **Correlation Regime:** Alert on ±20% correlation shift

## Usage

### Running the Dashboard

```bash
# Phase 2 Advanced Monitoring
streamlit run monitoring_phase2.py

# Original dashboard (Tier 1 & 2)
streamlit run dashboard.py
```

### Configuration

1. **Edit `alerts_config.yaml`** to customize thresholds
2. **Update integrations** (Slack, PagerDuty, email) in the config
3. **Set refresh intervals** via sidebar (5s, 15s, 30s, Off)

### Interpretation Guide

#### Green (✓)
- Metrics within target range
- All checks passing
- No escalations

#### Yellow (⚠)
- Metric trending toward threshold
- Warning-level alert
- Action recommended within 1 hour

#### Red (🔴)
- SLA violation or critical threshold exceeded
- Escalation triggered
- Immediate action required

## Integration Points

### External Systems
- **Slack:** Real-time alerts to `#group1-rag-alerts`
- **PagerDuty:** Critical escalations with SLA tracking
- **Email:** Daily summary reports

### Data Sources
- Real-time: Tier 3 reasoning pipeline metrics
- Streaming: Safety validation events, trade Greeks
- Batch: Daily A/B test aggregations, KB confidence recalc

### Feedback Loop
1. Failure mode detected → Alert generated
2. Alert escalated (Slack/PagerDuty) → Human review
3. Root cause analysis → KB update (LearningFeedback)
4. Lesson extracted + confidence score → Future query improvement

## Phase 2 Roadmap

### Week 1-2 (Current)
- Tier 3 A/B test with 50/50 split (Baseline vs Candidate)
- Safety framework validation under pilot load
- KB confidence scoring + conflict detection
- Live correlation monitoring

### Week 3-4
- Expand Tier 3 allocation if Sharpe p-value <0.05 (statistical significance)
- Escalation SLA tracking + root cause analysis
- Learning feedback automation (lessons → KG updates)

### Month 2+
- Full Tier 3 rollout (if A/B test passes gate)
- Advanced failure mode recovery (auto-fallback strategies)
- Dynamic alert tuning (ML-based threshold optimization)

## Troubleshooting

### Tier 3 Latency Exceeds SLA
- Check "Reasoning Steps" histogram — if max > 8, review query complexity
- Check "Circuit Breaker Triggers" — if >3/day, system may be under stress
- Escalation: Fallback to Tier 2, notify engineering

### Safety Escalation Triggered
- Review "Escalation Event Log" for the specific violation
- Typical reasons: Margin limit exceeded, correlation breakdown
- Action: Manual review (15-min SLA), then KG/model update

### A/B Test Not Reaching Significance
- Monitor sample size: Tier 3 needs ≥100 queries for power
- Allow 14-day minimum duration (currently running)
- If p-value remains >0.05 after 21 days, investigate quality regression

### KB Confidence Degradation
- Check "Confidence Score Distribution" histogram
- If >30% of lessons are low-confidence (<0.6), trigger manual review
- Escalate to data team for entity extraction validation

## Files

### Dashboard
- **`monitoring_phase2.py`** — Phase 2 monitoring dashboard (extends `dashboard.py`)
- **`dashboard.py`** — Original Tier 1/2 dashboard (unchanged)

### Configuration
- **`alerts_config.yaml`** — Alert thresholds, escalation policies, SLA targets

### Dependencies
- **`requirements.txt`** — Updated with matplotlib, seaborn, scipy, pyyaml

### Documentation
- **`PHASE2_MONITORING.md`** — This file
- **`README.md`** — Original dashboard documentation
- **`DEPLOYMENT.md`** — Deployment & infra guide

## Support

For questions about Phase 2 monitoring:
1. Check this documentation
2. Review `alerts_config.yaml` for your specific metric
3. Contact the engineering team via Slack `#group1-rag-alerts`
4. File an incident if SLA is at risk

---

**Last Updated:** 2026-08-06  
**Phase 2 Status:** LIVE (A/B Test Running)  
**Next Review:** 2026-08-20 (after A/B test concludes)
