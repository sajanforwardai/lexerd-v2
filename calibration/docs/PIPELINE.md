# Lexerd Data Pipeline & Batch Processing Orchestrator (LCMV-45)

This is the **HEART of Lexerd Deal Engine** — orchestrating all enrichment modules into a unified production pipeline that identifies top investment opportunities.

## Overview

The pipeline ties together three prior modules into a seamless workflow:

- **LCMV-30: BLS Employment Enrichment** — Labor market fundamentals
- **LCMV-37: Census + Zillow Market Enrichment** — Population, valuation, rent comparables
- **LCMV-58: SEC + B3 Loan Matching** — Loan maturity signals, refinance opportunities

**Output:** Ranked deal opportunities (top 100) scored by the 3M Model, plus alerts for maturity and refinance signals.

## Architecture

```
┌─────────────────────┐
│   Input CSV         │  ← Properties or market opportunities
└──────────┬──────────┘
           │
           ├─→ [Load] → CSV parsing, basic validation
           │
           ├─→ [Validate] → Required fields, data quality checks
           │
           ├─→ [Enrich] → BLS | SEC | Census | Zillow | B3
           │     ├─ BLS: employment_growth_yoy
           │     ├─ SEC: loan_maturity_years, loan_balance
           │     ├─ Census: population_growth_yoy, anchors
           │     ├─ Zillow: market_cap_rate, market_rent
           │     └─ B3: secondary market availability
           │
           ├─→ [Score] → 3M Model (Market/Model/Management)
           │     ├─ Market Score (30%) ← employment, population, cap rates
           │     ├─ Model Score (40%) ← units, occupancy, expense gaps
           │     └─ Management Score (30%) ← PM type, integration fit
           │
           ├─→ [Rank] → Sort by final_fit_score, select top 100
           │
           ├─→ [Alert] → Identify maturity/refinance signals
           │
           └─→ [Export] → CSV, HTML, PDF reports
               └─ scored_properties.csv
               └─ ranked_opportunities.csv
               └─ alerts.csv
               └─ dashboard.html
               └─ summary.json
```

## CLI Usage

### Installation

```bash
pip install -e .  # Install package in development mode
```

### Run Pipeline

```bash
# Standard enrichment (BLS + SEC)
lexerd-pipeline run properties.csv --mode standard --output-dir ./results

# Quick mode (BLS only)
lexerd-pipeline run properties.csv --mode quick --output-dir ./results

# Full enrichment (all sources)
lexerd-pipeline run properties.csv --mode full --output-dir ./results

# With configuration file
lexerd-pipeline run properties.csv --config pipeline_config.yaml

# Dry run (no output files)
lexerd-pipeline run properties.csv --dry-run

# Verbose logging
lexerd-pipeline run properties.csv -v
```

### Validate Configuration

```bash
# Create default config
lexerd-pipeline init-config pipeline_config.yaml

# Validate existing config
lexerd-pipeline validate-config pipeline_config.yaml

# Validate input CSV
lexerd-pipeline validate-input properties.csv
```

## Configuration

### YAML Configuration File

```yaml
# Pipeline mode: quick | standard (default) | full
enrichment_mode: standard

# API keys and cache settings
bls_api_key: ${BLS_API_KEY}  # Environment variable
sec_cache_dir: ./data/sec_cache
loan_tape_path: ./data/loan_tapes/current.csv

# Skip processing steps
skip_enrichment: false
skip_validation: false
dry_run: false

# Output settings
output_settings:
  output_dir: ./results
  export_csv: true
  export_html: true
  export_pdf: false

# Thesis parameters (scoring configuration)
thesis:
  # Geographic scope
  target_markets: [GA, FL, AL, SC, NC, TX, KS]
  min_population: null
  max_population: 1000000

  # Employment growth (Market score)
  min_employment_growth_yoy: 0.02
  employment_anchor_types: [military, medical, university, manufacturing]

  # Population (Market score)
  min_population_growth_yoy: 0.015

  # Cap rate spread (Market score)
  min_cap_rate_spread_bps: 200  # >200 bps above national average

  # Unit count (Model score)
  min_units: 70
  max_units: 300

  # Property class (Model score)
  property_classes: [A, A-, B, B+, B-, C]

  # Property age (Model score)
  min_property_age_years: 10
  max_property_age_years: 30

  # Occupancy (Model score)
  min_occupancy: 0.80
  max_occupancy: 0.95

  # Expense ratio (Model score)
  min_expense_ratio_above_benchmark: 0.05  # 5% above market

  # Management (Management score)
  require_third_party_management: true
  support_first_communities_integration: true

  # Loan maturity (Refinance score)
  min_maturity_years: 1.0
  max_maturity_years: 3.0

  # Financial constraints
  min_equity: 2000000
  max_equity: 20000000
  min_capital: 10000000
  max_capital: 100000000
  max_acq_price: 50000000

  # Scoring weights (must sum to 1.0)
  market_weight: 0.30
  model_weight: 0.40
  management_weight: 0.30

  # Target return
  target_irr_pct: 12.0

# Performance settings
batch_size: 100
max_workers: 4
timeout_seconds: 300
```

### JSON Configuration Alternative

```json
{
  "enrichment_mode": "standard",
  "bls_api_key": "...",
  "output_settings": {
    "output_dir": "./results",
    "export_csv": true
  },
  "thesis": { ... }
}
```

## Input Format

### CSV Columns

Required:
- `property_id` — Unique identifier
- `property_name` — Property name
- `address` — Street address
- `city` — City
- `state` — State (2-letter code)
- `units` — Number of units (>0)
- `property_class` — A, A-, B, B+, B-, C
- `year_built` — Year built (1900–2025)
- `occupancy` — Occupancy rate (0.0–1.0)
- `avg_rent_per_unit` — Average rent per unit ($)
- `expense_ratio` — Operating expense ratio (0.0–1.0)
- `market_expense_ratio` — Market benchmark ratio (0.0–1.0)

Optional (enriched data):
- `employment_growth_yoy` — YoY employment growth (2.5% = 0.025)
- `population_growth_yoy` — YoY population growth (1.8% = 0.018)
- `market_cap_rate` — Market cap rate (7.5% = 0.075)
- `employment_anchors` — Comma-separated list (e.g., "military,medical")
- `market_rent_per_unit` — Market rent per unit ($)
- `loan_maturity_years` — Years to loan maturity (1.5)
- `dscr` — Debt service coverage ratio (1.25)
- `purchase_price` — Acquisition price ($)

### Example CSV

```csv
property_id,property_name,address,city,state,units,property_class,year_built,occupancy,avg_rent_per_unit,expense_ratio,market_expense_ratio,employment_growth_yoy
PROP001,Riverside Apartments,123 Main St,Jacksonville,FL,150,B,2010,0.85,1200,0.30,0.28,0.025
PROP002,Downtown Lofts,456 Oak Ave,Jacksonville,FL,200,B+,2015,0.90,1500,0.28,0.28,0.025
PROP003,Suburban Commons,789 Pine Rd,Gainesville,FL,180,B,2008,0.78,950,0.32,0.28,0.018
```

## Output Format

### scored_properties.csv

All properties with their scores and breakdowns.

| Column | Description |
|--------|-------------|
| property_id | Unique identifier |
| market_score | Market score (0–100) |
| model_score | Model/opportunity score (0–100) |
| management_score | Management fit score (0–100) |
| final_fit_score | Weighted final score (0–100) |
| confidence_grade | A, B, C, or D |
| fit_rationale | Explanation of score |
| key_strengths | Bulleted strengths |
| key_weaknesses | Bulleted weaknesses |
| market_breakdown | JSON: {employment: 25, population: 15, ...} |
| model_breakdown | JSON: {units: 20, occupancy: 20, ...} |
| management_breakdown | JSON: {pm_type: 40, integration: 60, ...} |

### ranked_opportunities.csv

Top 100 opportunities sorted by final_fit_score (descending).

Same columns as scored_properties.csv.

### alerts.csv

Maturity signals and refinance opportunities.

| Column | Description |
|--------|-------------|
| property_id | Property ID |
| property_name | Property name |
| signal_type | "maturity" or "refinance" |
| alert_level | "high", "medium", or "low" |
| maturity_years | Years to maturity (for maturity signals) |
| dscr | DSCR (for refinance signals) |

### dashboard.html

Interactive HTML dashboard with:
- Top 100 opportunities (table)
- Maturity signals (highlighted rows)
- Refinance opportunities (highlighted rows)
- Summary statistics

### summary.json

Execution metrics and data lineage.

```json
{
  "status": "success",
  "timestamp": "2026-07-31T12:34:56",
  "execution_time_seconds": 42.5,
  "input_count": 500,
  "output_counts": {
    "scored_properties": 500,
    "ranked_opportunities": 100,
    "maturity_signals": 23,
    "refinance_opportunities": 17
  },
  "coverage_stats": {
    "bls_coverage": 95.2,
    "sec_coverage": 42.1,
    "census_coverage": 0.0,
    "zillow_coverage": 0.0
  },
  "error_summary": {
    "validation_errors": 0,
    "enrichment_errors": 12
  }
}
```

## Scoring Model (3M Model)

### Market Score (30% weight)

Evaluates geographic and economic fundamentals.

**Components:**
1. **Employment Growth (25 points)** — YoY employment growth
   - <2.0%: 0 points
   - 2.0%: 10 points
   - 3.0%: 17 points
   - 4.0%+: 25 points

2. **Population Growth (15 points)** — YoY population growth
   - <1.5%: 0 points
   - 1.5%: 6 points
   - 2.0%: 10 points
   - 2.5%+: 15 points

3. **Cap-Rate Spread (30 points)** — vs. 6% national average
   - <100 bps: 0 points
   - 200 bps: 20 points
   - 300+ bps: 30 points

4. **Employment Anchors (30 points)** — Military, medical, university, manufacturing
   - 0 anchors: 0 points
   - 1 anchor: 15 points
   - 2+ anchors: 30 points

**Market Score** = min(100, sum of components)

### Model Score (40% weight)

Evaluates value-add opportunity.

**Components:**
1. **Unit Count (20 points)** — 70–300 units optimal
   - In range: 20 points
   - 50–70 or 300–400: 10 points
   - Outside: 0 points

2. **Property Class (20 points)** — B, B+, B- preferred
   - B class: 20 points
   - Other: 0 points

3. **Occupancy (20 points)** — 80–95% optimal (below market = upside)
   - In range: 20 points
   - 75–80% or 95–99%: 10 points
   - Outside: 0 points

4. **Expense Ratio Gap (20 points)** — Above market benchmark
   - >5% above: 20 points
   - 3–5% above: 10 points
   - 0–2% above: 5 points
   - Below benchmark: 0 points

5. **Rent Upside (20 points)** — Below market rents
   - >15% below market: 20 points
   - 10–15% below: 10 points
   - 5–10% below: 5 points
   - At or above market: 0 points

**Model Score** = min(100, sum of components)

### Management Score (30% weight)

Evaluates operational fit.

**Components:**
1. **PM Type (40 points)** — Third-party preferred
   - Third-party: 40 points
   - Owner-managed: 20 points (if allowed)

2. **Integration Fit (60 points)** — Fit with existing portfolio
   - Good fit: 60 points
   - Moderate fit: 30 points
   - Poor fit: 0 points

**Management Score** = sum of components

### Final Score Calculation

```
Final Score = (Market Score × 0.30) + (Model Score × 0.40) + (Management Score × 0.30)
```

### Confidence Grade

| Range | Grade | Interpretation |
|-------|-------|-----------------|
| 90–100 | A | Strong fit — high conviction |
| 75–89 | B | Good fit — investable |
| 60–74 | C | Moderate fit — watch list |
| <60 | D | Weak fit — pass |

## API

### Python Usage

```python
from calibration.pipeline import DataPipeline, PipelineConfig, EnrichmentMode
from pathlib import Path

# Create configuration
config = PipelineConfig(
    enrichment_mode=EnrichmentMode.STANDARD,
    bls_api_key='your-api-key',
    output_dir=Path('./results'),
)

# Run pipeline
pipeline = DataPipeline(config)
result = pipeline.run(Path('properties.csv'))

# Access results
print(f"Status: {result.status}")
print(f"Scored properties: {len(result.scored_properties)}")
print(f"Top opportunities: {len(result.ranked_opportunities)}")
print(f"Execution time: {result.execution_time_seconds:.2f}s")

# Export to various formats
from calibration.pipeline.reporters import CSVReporter, HTMLReporter

CSVReporter.export_scored_properties(
    result.scored_properties,
    Path('./results/scores.csv')
)

HTMLReporter.export_opportunities_dashboard(
    result.ranked_opportunities,
    result.maturity_signals,
    result.refinance_opportunities,
    Path('./results/dashboard.html')
)
```

## Enrichment Modes

### Quick (BLS only)
- Loads employment growth from BLS
- Fast (< 1 min for 1000 properties)
- Limited market context
- **Use for:** Quick screening, preliminary analysis

### Standard (BLS + SEC)
- Employment growth + loan matching
- Moderate speed (1–5 min for 1000 properties)
- Good coverage for refinance signals
- **Use for:** Production pipeline (default)

### Full (All sources)
- BLS + Census + Zillow + SEC + B3
- Slowest (5–15 min for 1000 properties)
- Comprehensive market data
- **Use for:** Deep analysis, underwriting

## Validation

The pipeline includes multi-stage validation:

### Input Validation
- Required fields present
- Data types correct
- Numeric ranges reasonable
- City/state format valid

### Enrichment Validation
- API responses parsed correctly
- Data coverage tracked
- Missing data handled gracefully

### Output Validation
- Scores in 0–100 range
- Confidence grades A–D only
- Breakdowns sum to score
- No NaN values in final output

### Data Quality Metrics
```python
from calibration.pipeline.validators import DataQualityValidator

coverage = DataQualityValidator.check_coverage(properties)
# Returns: {'employment_growth': 95.2, 'population_growth': 42.1, ...}

stats = DataQualityValidator.check_score_distribution(scored)
# Returns: {'score_min': 34.2, 'score_max': 98.5, 'score_mean': 72.1, ...}

issues = DataQualityValidator.check_thesis_alignment(properties, scored, thesis)
# Returns: {'alignment_issues': [...], 'issue_count': 2}
```

## Performance Benchmarks

| Metric | Quick | Standard | Full |
|--------|-------|----------|------|
| 100 properties | 10s | 30s | 120s |
| 500 properties | 35s | 120s | 480s |
| 1000 properties | 60s | 240s | 900s |

*Times are approximate and depend on API latency, network conditions, and cache hits.*

## Troubleshooting

### Pipeline runs slowly
- Check API rate limits (BLS: 120 req/min)
- Use quick mode instead of full
- Increase batch_size or max_workers

### Low enrichment coverage
- Verify API keys are valid
- Check network connectivity
- Review error_summary in output

### Scores seem wrong
- Validate thesis configuration
- Check that input data is clean (no NaN values)
- Review score breakdowns for individual properties

### Missing output files
- Check output_dir permissions
- Verify export_csv/export_html/export_pdf settings
- Review error summary for export errors

## Development

### Running Tests

```bash
pytest calibration/tests/test_pipeline.py -v
pytest calibration/tests/test_pipeline.py::TestPipeline -v  # Specific test class
pytest calibration/tests/test_pipeline.py::TestPipeline::test_pipeline_run_end_to_end -v  # Specific test
```

### Test Coverage

```bash
pytest calibration/tests/test_pipeline.py --cov=calibration.pipeline --cov-report=html
open htmlcov/index.html
```

### Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- [ ] Parallel processing of large batches
- [ ] Support for incremental updates
- [ ] Real-time dashboard with streaming results
- [ ] Hypothesis testing on scoring assumptions
- [ ] Integration with deal management system
- [ ] PDF report generation with charts
- [ ] Export to Excel with formatting
