# Group One RAG Testing Framework

Comprehensive testing suite for Group One Trading RAG system with Tier 1 and Tier 2 evaluation.

## Overview

This framework provides:

- **500 golden trading queries** (`golden_queries.json`) covering Greeks, hedging, market regimes, and risk management
- **Tier 1 Retrieval Evaluation**: Hybrid dense + BM25 retrieval (Precision@10, Hit@1, nDCG@10, MRR, latency)
- **Tier 2 Entity Extraction**: Trading entity identification and classification (F1, precision, recall, latency)
- **End-to-End Pipeline Tests**: Full RAG system integration
- **Regression Tracking**: Baseline performance and drift detection
- **Benchmark Validation**: Against proven targets

## Target Benchmarks

| Metric | Target | Tier |
|--------|--------|------|
| Precision@10 | ≥ 0.50 | 1 (Retrieval) |
| Hit@1 Rate | ≥ 0.30 | 1 (Retrieval) |
| nDCG@10 | ≥ 0.50 | 1 (Retrieval) |
| Entity F1 | ≥ 0.85 | 2 (Extraction) |
| Entity Precision | ≥ 0.80 | 2 (Extraction) |
| Entity Recall | ≥ 0.80 | 2 (Extraction) |
| Tier 1 Latency (p99) | ≤ 100ms | 1 (Retrieval) |
| Tier 2 Latency (p99) | ≤ 500ms | 2 (Extraction) |
| Combined Latency | ≤ 600ms | E2E |

## Project Structure

```
tests/
├── README.md                      # This file
├── pytest.ini                     # Pytest configuration
├── conftest.py                    # Fixtures and configuration
├── test_metrics.py                # Evaluation metrics and logic
├── test_retrieval.py              # Tier 1 retrieval tests
├── test_entity_extraction.py      # Tier 2 entity extraction tests
├── test_end_to_end.py             # E2E pipeline tests
├── test_runner.py                 # Custom test runner with reporting
├── golden_queries.json            # 500 golden query set
├── __init__.py                    # Package initialization
└── results/                       # Test results (generated)
    ├── pytest.log                 # Detailed test log
    ├── junit.xml                  # JUnit format results
    ├── RESULTS.md                 # Summary report
    └── *.json                     # Individual test reports
```

## Installation

```bash
# Install dependencies
pip install pytest numpy

# Optional: For advanced reporting
pip install pytest-html pytest-cov pytest-timeout
```

## Quick Start

### Run All Tests

```bash
cd /workspace/group1-rag/tests
pytest
```

### Run Specific Tiers

```bash
# Tier 1 retrieval only
pytest -m tier1

# Tier 2 entity extraction only
pytest -m tier2

# End-to-end tests only
pytest -m e2e
```

### Run with Custom Test Runner

```bash
# Run all tests with detailed reporting
python test_runner.py

# Run Tier 1 only
python test_runner.py --tier 1

# Run Tier 2 only
python test_runner.py --tier 2

# Run E2E only
python test_runner.py --e2e

# Verbose output
python test_runner.py --verbose
```

### View Results

```bash
# View test log
cat results/pytest.log

# View summary report
cat results/RESULTS.md

# View detailed JSON results
cat results/results_*.json
```

## Evaluation Metrics

### Tier 1: Retrieval Evaluation

**Precision@10**
- Definition: Fraction of top-10 retrieved documents that are relevant
- Formula: `|relevant ∩ retrieved_top_10| / 10`
- Target: ≥ 0.50
- Interpretation: For every 10 results, at least 5 should be relevant

**Hit@1**
- Definition: Whether the top-1 result is relevant
- Formula: `1 if doc_0 ∈ relevant else 0`
- Interpretation: First result quality metric

**nDCG@10 (Normalized Discounted Cumulative Gain)**
- Definition: Ranking quality metric accounting for position
- Formula: `DCG@10 / IDCG@10` where `DCG = Σ rel(i) / log₂(i+1)`
- Target: ≥ 0.50
- Interpretation: Accounts for ranking position (earlier = better)

**MRR (Mean Reciprocal Rank)**
- Definition: Average of 1/position of first relevant result
- Formula: `1/R` where R is rank of first relevant result
- Interpretation: How quickly relevant results appear

**Recall@10**
- Definition: Fraction of all relevant documents that appear in top-10
- Formula: `|relevant ∩ retrieved_top_10| / |relevant|`
- Interpretation: Coverage of relevant results

**Latency (p50, p99)**
- Definition: Response time percentiles
- Target: ≤ 100ms (p99)
- Interpretation: Retrieval speed and consistency

### Tier 2: Entity Extraction Evaluation

**F1 Score**
- Definition: Harmonic mean of precision and recall
- Formula: `2 * (precision * recall) / (precision + recall)`
- Target: ≥ 0.85
- Interpretation: Balanced measure of extraction quality

**Precision**
- Definition: Fraction of extracted entities that are correct
- Formula: `|correct| / |predicted|`
- Target: ≥ 0.80
- Interpretation: How many extracted entities are accurate

**Recall**
- Definition: Fraction of ground-truth entities that are extracted
- Formula: `|correct| / |ground_truth|`
- Target: ≥ 0.80
- Interpretation: How many entities are found

**Latency (p50, p99)**
- Definition: Response time percentiles
- Target: ≤ 500ms (p99)
- Interpretation: Extraction speed

## Golden Query Set

The `golden_queries.json` file contains 500 trading questions organized by domain:

### Domains

- **greeks_options**: Delta, gamma, vega, theta, rho (100+ queries)
- **hedging_strategies**: Covered calls, spreads, calendars (100+ queries)
- **market_regimes**: Volatility regimes, trend/mean-reversion (80+ queries)
- **risk_management**: VaR, stress testing, drawdown (100+ queries)
- **products**: Options, futures, bonds, swaps (80+ queries)
- **technical_analysis**: Moving averages, RSI, MACD (50+ queries)
- **market_scenarios**: Earnings, gaps, flash crashes (50+ queries)

### Query Structure

```json
{
  "id": 1,
  "query": "What is gamma?",
  "ground_truth_keywords": ["gamma", "delta", "second derivative", "options"],
  "expected_tier": 1,
  "category": "greeks_options",
  "difficulty": "easy"
}
```

### Query Difficulty Levels

- **easy**: Single concept, straightforward answer (e.g., "What is gamma?")
- **intermediate**: Multiple concepts, some domain knowledge (e.g., "How do I hedge vega?")
- **advanced**: Complex scenarios, synthesis needed (e.g., "What strategies work in this regime?")

## Regression Testing

### Baseline Creation

Establish a performance baseline:

```python
from test_metrics import RegressionTracker, EvaluationReport

# Create report from your evaluation
report = EvaluationReport(...)
report.compute_aggregates()

# Save as baseline
tracker = RegressionTracker()
tracker.save_baseline(report, Path("baseline.json"))
```

### Regression Detection

Compare new results against baseline:

```python
tracker = RegressionTracker(baseline_path=Path("baseline.json"))
regression_result = tracker.check_regression(new_report, threshold_percent=5.0)

if not regression_result["passed"]:
    print("Regression detected:")
    for regression in regression_result["regressions"]:
        print(f"  {regression['metric']}: {regression['change_pct']:.1f}% decline")
```

### Threshold Interpretation

- **5% threshold**: Detects small degradations (default, strict)
- **10% threshold**: Allows minor fluctuations (relaxed)
- **-X% for latency**: Negative change is improvement (latency decreases)

## Benchmark Validation

Validate against target benchmarks:

```python
from test_metrics import BenchmarkValidator

validator = BenchmarkValidator()
validation_result = validator.validate(report)

if validation_result["passed"]:
    print("✅ All benchmarks met!")
else:
    print("❌ Benchmark failures:")
    for result in validation_result["results"]:
        if not result["passed"]:
            print(f"  {result['benchmark']}: {result['message']}")
```

## Fixtures and Mocks

The framework provides mock implementations for testing without real retrieval/extraction systems:

### MockEncoder
- Deterministic embeddings based on text hash
- Caching for reproducibility

### MockRetriever
- Simulates hybrid retrieval
- Supports custom relevance functions
- Uses sample corpus of trading documents

### MockEntityExtractor
- Extracts trading-domain entities
- Pattern-based (simple mock)

### Example Usage

```python
def test_my_query(mock_retriever, sample_corpus):
    query = "What is gamma?"
    results = mock_retriever.search(query, k=10)
    # Assert results...
```

## Test Markers

Run tests by category:

```bash
pytest -m tier1              # Tier 1 retrieval tests
pytest -m tier2              # Tier 2 entity extraction tests
pytest -m e2e                # End-to-end pipeline tests
pytest -m regression         # Regression and benchmark tests
pytest -m "not slow"         # Skip slow tests
```

## Interpreting Results

### Pass/Fail Criteria

A test passes if:
1. Expected functionality is present (mock retriever returns results, extractor finds entities)
2. Metrics are computed correctly
3. No exceptions are raised
4. Latency is reasonable

### Report Analysis

View `results/RESULTS.md` for:
- Test execution summary (total, passed, failed, skipped)
- Test breakdown by category (Tier 1, Tier 2, E2E)
- Pass rates per category
- Benchmark target status

View `results/pytest.log` for:
- Detailed test output
- Assertion failures and stack traces
- Performance measurements

View `results/*.json` for:
- Granular metric data
- Per-query results
- Latency distributions

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Group One RAG Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install pytest numpy
      - run: cd tests && pytest --junit-xml=results.xml
      - uses: EnricoMi/publish-unit-test-result-action@v1
        if: always()
        with:
          files: tests/results.xml
```

## Troubleshooting

### No Results Returned

**Issue**: Mock retriever returns empty results
- Check query string (should contain trading terms)
- Verify sample corpus has relevant documents
- Increase k value

### Low F1 Scores

**Issue**: Entity extraction F1 < 0.85
- Check ground truth keywords are complete
- Verify extraction covers all domain entities
- Review text preprocessing

### Latency Exceeds Target

**Issue**: Latency p99 > 100ms (Tier 1) or > 500ms (Tier 2)
- Profile bottlenecks in retrieval/extraction
- Check corpus size scaling
- Verify no redundant operations

### Regression Detected

**Issue**: New results regress from baseline
- Compare metrics in detail
- Check if query set changed
- Verify reproducibility (same seed)

## Performance Profiling

For profiling test performance:

```bash
# With pytest-profiling
pip install pytest-profiling
pytest --profile

# With cProfile
python -m cProfile -s cumulative test_runner.py
```

## Contributing

To add new tests:

1. Create test in appropriate file (`test_retrieval.py`, `test_entity_extraction.py`, etc.)
2. Use appropriate markers (`@pytest.mark.tier1`, `@pytest.mark.tier2`, etc.)
3. Use fixtures from `conftest.py`
4. Add to golden_queries.json if needed
5. Run full suite: `pytest`

## References

### Metrics Literature

- **nDCG**: Järvelin & Kekäläinen (2002) - "Cumulated gain-based evaluation of IR techniques"
- **MRR**: Voorhees (1999) - "The TREC-8 Question Answering Track Report"
- **F1 Score**: van Rijsbergen (1979) - "Information Retrieval"

### Trading Domain

- Greeks: Hull (2018) - "Options, Futures, and Other Derivatives"
- Risk Management: Jorion (2006) - "Value at Risk"
- Hedging: Bodie et al. (2013) - "Investments"

## Support

- **Test failures**: Check `results/pytest.log` for detailed errors
- **Metric interpretation**: See "Evaluation Metrics" section above
- **Query coverage**: Review `golden_queries.json` structure
- **Performance tuning**: Use profiling tools (see "Performance Profiling")

---

**Last Updated**: 2026-08-06
**Framework Version**: 1.0.0
