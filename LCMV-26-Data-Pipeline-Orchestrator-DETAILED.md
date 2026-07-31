# LCMV-26: Stage 2 — End-to-End Data Pipeline & Batch Processing Orchestrator

**Epic:** Stage 2 Data Integration Pipeline  
**Stage:** 2 — Production Pipeline  
**Status:** To Do  
**Priority:** High  
**Owner:** [Assigned Developer]  
**Dependencies:** LCMV-23, LCMV-24, LCMV-25 (must be completed first)

---

## Executive Summary

Build the **production data pipeline orchestrator** that coordinates all Stage 2 enrichment modules (BLS, Census, Zillow, Freddie Mac/Fannie Mae) into a single, repeatable batch-processing workflow. This is the **operational engine** of Lexerd's sourcing and scoring system.

**Strategic Function:**
- **Input:** Raw property CSV (city, state, units, occupancy, etc.)
- **Processing:** Enrichment pipeline (BLS → Census/Zillow → Freddie Mac/Fannie Mae → Market/Model scoring)
- **Output:** Scored properties CSV + sourcing alerts + reporting dashboards
- **Execution:** CLI tool, scheduled monthly, integrated with Streamlit UI

**Impact:**
- Enables repeatable, auditable deal sourcing (not manual)
- Powers Streamlit dashboard for real-time scoring and tuning
- Feeds downstream CRM/sourcing workflows
- Creates measurable sourcing KPIs (deal flow, close rate, IRR)

---

## Problem Statement

### Current State (Without LCMV-26)

```
Manual, one-off property scoring:
1. Download CSV of properties (manual)
2. Manually lookup BLS employment data (1–2 min per property)
3. Manually lookup Census population data (1–2 min per property)
4. Manually lookup Zillow rents/cap rates (2–3 min per property)
5. Manually run scoring script (error-prone)
6. Export results (error-prone)

Time: 10–15 minutes per property → 5–10 properties/day
Result: Non-scalable, error-prone, no audit trail
```

### Target State (With LCMV-26)

```
Automated, reproducible pipeline:
1. Upload CSV of properties (UI upload)
2. Select pipeline mode (quick=BLS only, standard=BLS+Census+Zillow, full=+Freddie Mac)
3. Click "Run Pipeline"
4. System:
   - Enriches 1000 properties in 3–5 minutes (parallel processing)
   - Scores all properties with 3M Model
   - Generates alert report (top 100 deals)
   - Exports scored CSV
   - Updates Streamlit dashboard in real-time

Time: 5 minutes for 1000 properties
Result: Scalable, auditable, reproducible, with full data lineage
```

---

## Technical Architecture

### High-Level Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Lexerd Data Pipeline (LCMV-26)                       │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT LAYER:
┌──────────────────────────────────────────────────────────────┐
│ 1. CSV Upload (Streamlit UI)                                │
│    - properties.csv (property_id, city, state, units, etc.) │
│ 2. Pipeline Configuration (UI selectors)                    │
│    - Enrichment mode: quick | standard | full               │
│    - Target market filter (optional)                        │
│    - DSCR/LTV thresholds (optional)                         │
│ 3. Data Source Selection                                    │
│    - BLS API enabled? (default: yes)                        │
│    - Census API enabled? (default: yes)                     │
│    - Zillow enabled? (default: yes)                         │
│    - Freddie Mac/Fannie Mae tapes? (default: no, on-demand) │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
ENRICHMENT LAYER (Parallel Processing):
┌──────────────────────────────────────────────────────────────┐
│ Stage 1: BLS Employment Data (LCMV-23)                       │
│ - enrich_batch(properties, bls_client)                       │
│ - 100 properties in <2s (parallel API calls + caching)       │
│ - Output: employment_growth_yoy ← PropertyProfile            │
└──────────────────────────────────────────────────────────────┘
                         │
                         ├─────────────────────────────────────┐
                         │                                     │
                         ▼                                     ▼
    ┌──────────────────────────────────┐    ┌─────────────────────────────────┐
    │ Stage 2a: Census Population       │    │ Stage 2b: Zillow Market Data    │
    │ (LCMV-24)                         │    │ (LCMV-24)                       │
    │ - enrich_market_data()            │    │ - get_market_cap_rate()         │
    │ - population_growth_yoy           │    │ - get_comparable_rents()        │
    │ - 365d cache (annual)             │    │ - derive cap rates              │
    │ - <1s per 100 props               │    │ - 30d cache (monthly)           │
    │ - Output: pop growth, market rents│    │ - <3s per 100 props             │
    └──────────────────────────────────┘    └─────────────────────────────────┘
                         │                                     │
                         └──────────────┬──────────────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 3: Freddie Mac/Fannie Mae Loan Matching (LCMV-25)     │
│ - Optional: match properties to securitized loans           │
│ - Extract maturity dates, DSCR, LTV, refinance risk         │
│ - Flag Tier 1 opportunities (maturity + stress)             │
│ - Output: maturity_date, dscr, ltv, risk_tier ←ProfileProf. │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
SCORING LAYER:
┌──────────────────────────────────────────────────────────────┐
│ MarketScorer (calibration/models/scorers.py)                 │
│ - Input: employment_growth_yoy, population_growth_yoy,      │
│          market_cap_rate, employment_anchors                 │
│ - Output: market_score (0–100), breakdown                    │
│                                                               │
│ ModelScorer                                                  │
│ - Input: units, occupancy, expense_ratio, market_rent,      │
│          year_built, property_class, rent_gap_pct            │
│ - Output: model_score (0–100), breakdown                     │
│                                                               │
│ ManagementScorer                                             │
│ - Input: management_type, operator_track_record,            │
│          lender_relationship, sponsor_expertise              │
│ - Output: management_score (0–100), breakdown                │
│                                                               │
│ FinalScorer (3M Model weighted combination)                  │
│ - Weighted average: (30% market) + (40% model) + (30% mgmt)  │
│ - Output: final_fit_score (0–100), confidence_grade (A–D)   │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
OUTPUT LAYER:
┌──────────────────────────────────────────────────────────────┐
│ 1. Scored Properties CSV                                     │
│    - All input fields + scores (market, model, mgmt, final)  │
│    - Breakdown details for transparency                      │
│    - Confidence grades (A, B, C, D)                          │
│                                                               │
│ 2. Alert Report (Top 100 deals)                              │
│    - Tier 1 opportunities (DSCR + maturity stress)           │
│    - Tier 2 opportunities (elevated risk)                    │
│    - Ranked by opportunity score                             │
│    - Export: HTML, PDF, CSV                                  │
│                                                               │
│ 3. Pipeline Summary Report                                   │
│    - Records processed: N                                    │
│    - Enrichment success rate: X%                             │
│    - Average scores (market, model, mgmt, final)             │
│    - Score distribution (histogram)                          │
│    - Data lineage (timestamps, source versions)              │
│                                                               │
│ 4. Streamlit Dashboard Update                                │
│    - Real-time scoring progress (progress bar)               │
│    - Score histograms                                        │
│    - Top opportunities (table)                               │
│    - Market heat map (MSA scores)                            │
└──────────────────────────────────────────────────────────────┘
```

### Module Structure

```
calibration/
├── pipeline/
│   ├── __init__.py
│   ├── pipeline.py                        # ← LCMV-26.1
│   │   ├── DataPipeline class
│   │   ├── run(config) → PipelineResult
│   │   ├── enrich_batch() → enriched_properties
│   │   ├── score_batch() → scored_properties
│   │   └── generate_reports() → (csv, html, pdf)
│   │
│   ├── config.py                          # ← LCMV-26.2
│   │   ├── PipelineConfig dataclass
│   │   ├── EnrichmentMode enum
│   │   ├── OutputFormat enum
│   │   └── load_config_from_yaml()
│   │
│   ├── cli.py                             # ← LCMV-26.3
│   │   ├── main() entry point
│   │   ├── @click.command() decorators
│   │   ├── --input-csv, --output-csv, --mode, --filter, etc.
│   │   └── progress_bar integration
│   │
│   ├── reporters.py                       # ← LCMV-26.4
│   │   ├── CSVReporter (export_scored_csv())
│   │   ├── AlertReporter (generate_alert_report())
│   │   ├── SummaryReporter (pipeline_metrics())
│   │   └── Format: CSV, HTML, PDF
│   │
│   └── validators.py                      # ← LCMV-26.5
│       ├── validate_input_csv()
│       ├── validate_pipeline_config()
│       ├── validate_enrichment_results()
│       └── validate_scoring_results()
│
├── tests/
│   └── test_pipeline.py                   # ← LCMV-26.6
│       ├── TestPipeline (8 tests)
│       ├── TestConfig (4 tests)
│       ├── TestReporters (6 tests)
│       ├── TestValidators (4 tests)
│       └── TestIntegration (4 tests)
│
└── docs/
    └── PIPELINE.md                        # ← LCMV-26.7
        ├── Architecture overview
        ├── Configuration reference
        ├── CLI usage guide
        ├── Output format reference
        └── Troubleshooting
```

---

## Sub-Tickets (Comprehensive Breakdown)

### LCMV-26.1: Data Pipeline Core Orchestrator
**Type:** Task  
**Acceptance Criteria:**
- [ ] `pipeline.py` implements DataPipeline class
- [ ] Orchestrates LCMV-23 (BLS) → LCMV-24 (Census/Zillow) → LCMV-25 (Freddie Mac) → Scoring
- [ ] Supports enrichment modes: quick (BLS only), standard (BLS+Census+Zillow), full (+Freddie Mac)
- [ ] Parallel processing: 1000 properties in 3–5 minutes
- [ ] Handles partial enrichment (one source fails, continue)
- [ ] Tracks data lineage (timestamps, source versions, API call counts)
- [ ] Generates PipelineResult with all metrics

**PipelineConfig Structure:**

```python
@dataclass
class EnrichmentMode(Enum):
    QUICK = "quick"             # BLS only (fastest)
    STANDARD = "standard"       # BLS + Census + Zillow
    FULL = "full"               # BLS + Census + Zillow + Freddie Mac

@dataclass
class PipelineConfig:
    # Input/output
    input_csv: str              # Path to input properties CSV
    output_dir: str             # Directory for outputs
    
    # Enrichment
    enrichment_mode: EnrichmentMode = EnrichmentMode.STANDARD
    bls_enabled: bool = True
    census_enabled: bool = True
    zillow_enabled: bool = True
    freddie_mac_enabled: bool = False
    
    # Filtering (optional)
    target_states: Optional[List[str]] = None  # ['GA', 'FL', ...]
    min_units: int = 70
    max_units: int = 300
    min_dscr: Optional[float] = None
    max_ltv: Optional[float] = None
    
    # Performance
    batch_size: int = 100       # Properties per batch
    max_workers: int = 4        # Parallel workers
    cache_enabled: bool = True
    
    # Output
    export_csv: bool = True
    export_alerts: bool = True
    export_summary: bool = True
    export_formats: List[str] = ["csv", "html"]  # csv, html, pdf
    
    # Thesis tuning
    market_weight: float = 0.30
    model_weight: float = 0.40
    management_weight: float = 0.30
    target_irr: float = 0.12

@dataclass
class PipelineResult:
    # Processing stats
    total_processed: int
    enriched_count: int
    enrichment_success_rate: float  # 0.0–1.0
    
    # Scoring stats
    avg_market_score: float
    avg_model_score: float
    avg_management_score: float
    avg_final_score: float
    
    # Scores distribution
    score_distribution: Dict[str, int]  # {"A": 45, "B": 120, "C": 200, "D": 135}
    
    # Alerts
    tier1_opportunities: int  # Critical deals
    tier2_opportunities: int  # High deals
    
    # Data lineage
    enrichment_sources: Dict[str, dict]  # {"bls": {...}, "census": {...}}
    timestamps: Dict[str, float]  # Start, end, durations
    errors: List[str]  # Any non-fatal errors logged
```

**Pipeline Execution Flow:**

```python
def run(config: PipelineConfig) -> PipelineResult:
    """
    Execute full pipeline: load → enrich → score → report
    
    Flow:
    1. Load and validate input CSV
    2. Initialize clients (BLS, Census, Zillow, Freddie Mac)
    3. Apply filters (states, units, etc.) if specified
    4. Batch processing:
       a. Enrich batch with BLS/Census/Zillow/Freddie Mac
       b. Score batch with 3M Model
       c. Track results + metrics
    5. Generate reports (CSV, HTML, alerts)
    6. Return PipelineResult with all metrics
    """
```

---

### LCMV-26.2: Configuration Management
**Type:** Task  
**Acceptance Criteria:**
- [ ] `config.py` implements PipelineConfig dataclass
- [ ] Supports YAML config files (load_config_from_yaml)
- [ ] Supports CLI argument overrides
- [ ] Validates all config parameters
- [ ] Provides sensible defaults
- [ ] Generates example config YAML

**Example Config YAML:**

```yaml
# pipeline_config.yaml
pipeline:
  enrichment_mode: standard          # quick | standard | full
  
enrichment:
  bls_enabled: true
  census_enabled: true
  zillow_enabled: true
  freddie_mac_enabled: false
  freddie_mac_tape_path: null
  
filters:
  target_states: [GA, FL, AL, SC, NC, TX, KS]
  min_units: 70
  max_units: 300
  min_dscr: null
  max_ltv: null
  
performance:
  batch_size: 100
  max_workers: 4
  cache_enabled: true
  
output:
  export_csv: true
  export_alerts: true
  export_summary: true
  formats: [csv, html]
  
scoring:
  market_weight: 0.30
  model_weight: 0.40
  management_weight: 0.30
  target_irr: 0.12
```

---

### LCMV-26.3: CLI Tool (Command-Line Interface)
**Type:** Task  
**Acceptance Criteria:**
- [ ] `cli.py` implements Click-based command-line interface
- [ ] Command: `lexerd-pipeline run --input-csv properties.csv --mode standard --output-dir ./results`
- [ ] Progress bar showing enrichment/scoring progress
- [ ] Colorized output (✓ success, ✗ error, ⚠ warning)
- [ ] Logging to file + console
- [ ] Config file support: `lexerd-pipeline run --config pipeline_config.yaml`
- [ ] Help text for all options: `lexerd-pipeline run --help`

**CLI Usage Examples:**

```bash
# Quick mode (BLS only)
lexerd-pipeline run \
  --input-csv properties.csv \
  --output-dir ./results \
  --mode quick

# Standard mode (BLS + Census + Zillow)
lexerd-pipeline run \
  --input-csv properties.csv \
  --output-dir ./results \
  --mode standard \
  --target-states GA FL \
  --min-units 70 \
  --max-units 300

# Full mode (all sources)
lexerd-pipeline run \
  --input-csv properties.csv \
  --output-dir ./results \
  --mode full \
  --freddie-mac-tape ./data/freddie_mac_2024_08.txt

# From config file
lexerd-pipeline run --config pipeline_config.yaml
```

**CLI Output Example:**

```
Lexerd Data Pipeline v1.0
═══════════════════════════════════════════

Loading input: properties.csv
  ✓ 1000 properties loaded

Initializing clients:
  ✓ BLS client ready
  ✓ Census client ready
  ✓ Zillow client ready
  ✗ Freddie Mac: disabled

Enrichment (Standard Mode):
  ├─ Stage 1 (BLS Employment):
  │  ├─ Batch 1: 100/100 properties → 98 enriched (98%)
  │  ├─ Batch 2: 100/100 properties → 97 enriched (97%)
  │  ├─ Batch 3: 100/100 properties → 99 enriched (99%)
  │  ├─ ...
  │  └─ Total: 980/1000 enriched (98%)
  │
  ├─ Stage 2a (Census Population):
  │  └─ Total: 945/1000 enriched (94.5%)
  │
  └─ Stage 2b (Zillow Market Data):
     └─ Total: 920/1000 enriched (92%)

Scoring (3M Model):
  ├─ Market scores: avg=62.4, min=12, max=98
  ├─ Model scores: avg=71.2, min=15, max=99
  ├─ Management scores: avg=58.3, min=0, max=95
  └─ Final scores: avg=67.8, min=10, max=97

Score Distribution:
  A (90–100): 45 properties (4.5%)
  B (75–89):  240 properties (24%)
  C (60–74):  415 properties (41.5%)
  D (<60):    300 properties (30%)

Generating reports:
  ✓ scored_properties.csv (1000 records)
  ✓ top_100_opportunities.html (100 deals)
  ✓ pipeline_summary.txt (metrics + lineage)

═══════════════════════════════════════════
Pipeline completed successfully
Total time: 4m 32s
Results: ./results/
```

---

### LCMV-26.4: Report Generators
**Type:** Task  
**Acceptance Criteria:**
- [ ] `reporters.py` implements multiple report formats
- [ ] CSVReporter: exports scored_properties.csv with all scores + breakdowns
- [ ] AlertReporter: generates top 100 opportunities (HTML + PDF)
- [ ] SummaryReporter: generates pipeline metrics + data lineage
- [ ] All reports include data freshness info (timestamps, source versions)
- [ ] HTML reports: styled, sortable tables, charts

**Report Outputs:**

```
results/
├── scored_properties.csv
│   Columns: property_id, city, state, units, class, occupancy, ...
│   + employment_growth_yoy, population_growth_yoy, market_cap_rate
│   + market_score, market_breakdown_*, model_score, model_breakdown_*
│   + management_score, management_breakdown_*
│   + final_score, confidence_grade
│   Rows: 1000 (or filtered count)
│
├── top_100_opportunities.html
│   - Tier 1 (Critical) opportunities ranked
│   - Tier 2 (High) opportunities ranked
│   - Tier 3 (Monitor) opportunities
│   - Interactive tables (sort, filter)
│   - Charts: score distribution, MSA heat map
│
├── top_100_opportunities.pdf
│   - Print-friendly version of HTML
│
├── pipeline_summary.txt
│   Processing Statistics:
│   - Start time, end time, duration
│   - Records processed: 1000
│   - Enrichment success rates (BLS 98%, Census 94.5%, Zillow 92%)
│   - Average scores (market 62.4, model 71.2, mgmt 58.3, final 67.8)
│   - Score distribution (A/B/C/D counts)
│   
│   Data Lineage:
│   - BLS: 120 API calls, 850 cache hits (97% hit rate), 2 failures
│   - Census: 45 API calls, 955 cache hits, 0 failures
│   - Zillow: 35 API calls, 965 cache hits, 0 failures
│   
│   Configuration:
│   - Enrichment mode: standard
│   - Scoring weights: market 30%, model 40%, mgmt 30%
│   - Filters applied: states [GA, FL, ...], units [70–300]
│
└── pipeline_config_used.yaml
    (Copy of config for reproducibility)
```

---

### LCMV-26.5: Data Validation & Error Handling
**Type:** Task  
**Acceptance Criteria:**
- [ ] `validators.py` validates input CSV structure
- [ ] Validates pipeline config completeness
- [ ] Validates enrichment results (no NaN scores, etc.)
- [ ] Validates scoring results (scores 0–100, grades A–D)
- [ ] Provides clear error messages
- [ ] Non-fatal errors logged, processing continues
- [ ] Fatal errors halt pipeline with clear messages

**Validation Rules:**

```python
# Input CSV validation
- Required columns: property_id, city, state, units, occupancy
- Optional but recommended: property_class, year_built, expense_ratio
- Data types: units (int), occupancy (0.0–1.0 float), etc.
- No duplicate property_ids
- All cities/states valid (2-letter state codes)

# Enrichment validation
- employment_growth_yoy: None or 0.0–0.10 (realistic range)
- population_growth_yoy: None or 0.0–0.10
- market_cap_rate: None or 0.03–0.15 (realistic yield)

# Scoring validation
- market_score: 0–100
- model_score: 0–100
- management_score: 0–100
- final_score: 0–100
- confidence_grade: A, B, C, or D
- final_score weighted average of components (within tolerance)
```

---

### LCMV-26.6: Comprehensive Unit Tests
**Type:** Task  
**Acceptance Criteria:**
- [ ] 26+ test cases covering all modules
- [ ] Test coverage >90% on pipeline.py, config.py, reporters.py, validators.py
- [ ] End-to-end integration test: CSV → pipeline → reports
- [ ] Performance test: 1000 properties in <5 minutes
- [ ] Mock all external clients (BLS, Census, Zillow, Freddie Mac)

**Test Structure:**

```python
class TestPipeline:
    # 8 tests
    def test_run_quick_mode(self): pass  # BLS only
    def test_run_standard_mode(self): pass  # BLS + Census + Zillow
    def test_run_full_mode(self): pass  # All sources
    def test_partial_enrichment_handling(self): pass  # One source fails
    def test_batch_processing_parallelism(self): pass  # 4 workers
    def test_data_lineage_tracking(self): pass  # Timestamps, API counts
    def test_performance_1000_properties_under_5m(self): pass
    def test_error_handling_graceful_degradation(self): pass

class TestConfig:
    # 4 tests
    def test_load_config_from_yaml(self): pass
    def test_validate_config_completeness(self): pass
    def test_cli_argument_overrides_yaml(self): pass
    def test_default_values_applied(self): pass

class TestReporters:
    # 6 tests
    def test_export_scored_csv(self): pass
    def test_export_alert_html(self): pass
    def test_export_summary_txt(self): pass
    def test_report_includes_data_lineage(self): pass
    def test_pdf_export(self): pass
    def test_chart_generation(self): pass

class TestValidators:
    # 4 tests
    def test_validate_input_csv_structure(self): pass
    def test_validate_enrichment_results(self): pass
    def test_validate_scoring_results(self): pass
    def test_error_messages_actionable(self): pass

class TestIntegration:
    # 4 tests
    def test_end_to_end_csv_to_scored_results(self): pass
    def test_streaming_scorecard_for_streamlit(self): pass
    def test_reproducibility_same_config_same_results(self): pass
    def test_concurrent_pipeline_runs_isolation(self): pass
```

---

### LCMV-26.7: Documentation & Integration Guide
**Type:** Task  
**Deliverable:** `PIPELINE.md`
**Sections:**
- Architecture overview (data flow diagrams)
- Configuration reference (all YAML options)
- CLI usage guide (command examples)
- Output format reference (CSV/HTML structure)
- Integration with Streamlit UI
- Performance benchmarks
- Troubleshooting (common errors)
- Running scheduled monthly pipelines

---

## Acceptance Criteria (LCMV-26 Overall)

### Functionality
- [ ] Orchestrates LCMV-23 → LCMV-24 → LCMV-25 → Scoring pipeline
- [ ] Supports 3 enrichment modes (quick, standard, full)
- [ ] Processes 1000 properties in <5 minutes
- [ ] Parallel processing with configurable worker count
- [ ] Handles partial enrichment (one source fails, continues)
- [ ] Generates scored CSV + alert report + summary
- [ ] Tracks full data lineage (API calls, cache hits, timestamps)

### Code Quality
- [ ] All modules documented (docstrings, type hints)
- [ ] CLI tool with progress bar and colored output
- [ ] Configuration via YAML + CLI arguments
- [ ] Follows Lexerd code style (PEP 8)
- [ ] Comprehensive logging

### Testing
- [ ] 26+ unit tests with >90% coverage
- [ ] End-to-end integration test
- [ ] Performance benchmarks
- [ ] All mocked (no real API calls in tests)

### Documentation
- [ ] PIPELINE.md complete
- [ ] CLI help text (--help)
- [ ] Example config.yaml
- [ ] Integration guide for Streamlit

---

## Integration Points

### Upstream Dependencies
- LCMV-23: BLS client (calibration/data/bls_client.py)
- LCMV-24: Census/Zillow clients (calibration/data/census_client.py, zillow_client.py)
- LCMV-25: Freddie Mac/Fannie Mae parser (calibration/data/loan_tape_parser.py)
- Scoring: MarketScorer, ModelScorer, ManagementScorer, FinalScorer

### Downstream Consumers
- **Streamlit UI** (calibration/ui/app.py) — Calls pipeline.run() on CSV upload
- **Scheduled tasks** — Monthly Freddie Mac/Fannie Mae refresh
- **CRM workflow** — Ingests opportunity pipeline CSV
- **Reporting dashboards** — Uses summary metrics
- **Backtesting** — Historical pipeline results for validation

---

## Performance Targets

| Scenario | Target | Notes |
|----------|--------|-------|
| Quick mode (BLS only) | 100 props in <1m | Cached BLS data |
| Standard mode (BLS+Census+Zillow) | 100 props in <2m | Mix of cached/API |
| Full mode (+Freddie Mac) | 100 props in <3m | File I/O for tapes |
| Large batch (1000 props) | <5 minutes | Parallel processing |
| Cache hit rate | 95%+ | BLS/Census/Zillow caching |
| API call reduction | 10x | Batch caching strategy |

---

## Success Metrics

| Metric | Target | Verification |
|--------|--------|---|
| Enrichment coverage | 90%+ | Enrichment success rate per source |
| Scoring accuracy | Consistent with Stage 1 tests | Regression testing vs. known properties |
| Pipeline reliability | 99%+ uptime | Error logs, graceful degradation |
| Processing speed | <5m for 1000 props | Benchmark test |
| Data lineage completeness | 100% | All API calls, timestamps logged |
| Code coverage | >90% | pytest --cov report |

---

## Deployment & Scheduling

**Development:**
- CLI tool: `python -m calibration.pipeline.cli run --config config.yaml`

**Production (Scheduled):**
```cron
# Monthly Freddie Mac/Fannie Mae refresh (1st of month, 2 AM)
0 2 1 * * /usr/local/bin/lexerd-pipeline run --mode full --freddie-mac-tape ./data/tapes/latest.txt --output-dir ./results/monthly

# Weekly standard pipeline (Tuesday, 6 AM)
0 6 * * TUE /usr/local/bin/lexerd-pipeline run --mode standard --output-dir ./results/weekly
```

**Streamlit Integration:**
```python
# In calibration/ui/app.py
if st.button("Run Pipeline"):
    with st.spinner("Processing..."):
        config = PipelineConfig(
            input_csv=uploaded_file,
            enrichment_mode=EnrichmentMode.STANDARD,
            output_dir="./streamlit_results"
        )
        result = DataPipeline().run(config)
        st.success(f"Processed {result.total_processed} properties")
        st.download_button(
            label="Download Scored CSV",
            data=open("./streamlit_results/scored_properties.csv").read(),
            file_name="scored_properties.csv"
        )
```

---

## Definition of Done

- ✅ All 7 sub-tickets completed
- ✅ pytest calibration/tests/test_pipeline.py → all green
- ✅ Coverage >90% on all pipeline modules
- ✅ PIPELINE.md complete
- ✅ CLI tool functional (run --help works)
- ✅ End-to-end test: sample CSV → scored results
- ✅ Streamlit integration verified
- ✅ Code review approved

---

## References

- Calibration models: `calibration/models/`
- BLS integration: `LCMV-23-BLS-Integration-DETAILED.md`
- Census/Zillow: `LCMV-24-Census-Zillow-Integration-DETAILED.md`
- Loan pipeline: `LCMV-25-Loan-Maturity-Pipeline-DETAILED.md`
- Lexerd Thesis: `LEXERD_THESIS.md`

---

*Created: 2026-07-31 | Owner: [TBD]*
