# Quick Start Guide - Group One RAG Testing Framework

## 5-Minute Setup

### Step 1: Install Dependencies
```bash
cd /workspace/group1-rag/tests
pip install -r requirements.txt
```

### Step 2: Run Tests
```bash
# Run all tests
pytest

# Or with the test runner
python test_runner.py
```

### Step 3: View Results
```bash
# Summary report
cat results/RESULTS.md

# Detailed log
cat results/pytest.log
```

## Common Commands

```bash
# Run Tier 1 (retrieval) only
pytest -m tier1 -v

# Run Tier 2 (entity extraction) only  
pytest -m tier2 -v

# Run end-to-end tests
pytest -m e2e -v

# Run specific test file
pytest test_retrieval.py -v

# Run specific test
pytest test_retrieval.py::TestTier1Retrieval::test_retrieval_precision_at_10_sample -v

# Generate coverage report
pytest --cov=. --cov-report=html

# Run in parallel (faster)
pytest -n auto

# Stop on first failure
pytest -x

# Show print statements
pytest -s
```

## What Gets Tested

### ✅ Tier 1: Retrieval
- **Precision@10**: At least 5 out of 10 results are relevant
- **Hit@1**: Top result is relevant
- **nDCG@10**: Ranking quality (position matters)
- **MRR**: How quickly relevant results appear
- **Latency**: Response time ≤ 100ms (p99)

### ✅ Tier 2: Entity Extraction
- **F1 Score**: Balanced precision/recall ≥ 0.85
- **Precision**: Accuracy of extracted entities ≥ 0.80
- **Recall**: Coverage of ground-truth entities ≥ 0.80
- **Latency**: Response time ≤ 500ms (p99)

### ✅ End-to-End
- Full retrieval → entity extraction pipeline
- Combined latency ≤ 600ms
- Benchmark validation
- Regression detection

## Understanding the Results

### Success Indicators ✅
- `PASSED` - Test passed
- `P99 latency < 100ms` - Performance target met
- `Precision@10 > 0.50` - Retrieval quality good
- `Entity F1 > 0.85` - Extraction quality excellent

### Warnings ⚠️
- `FAILED` - Test assertions didn't pass
- `P99 latency > 100ms` - Retrieval slow
- `P99 latency > 500ms` - Extraction slow
- `Regression detected` - Performance declined

## Key Files

| File | Purpose |
|------|---------|
| `test_metrics.py` | Evaluation metrics (Precision@k, nDCG, F1, etc.) |
| `test_retrieval.py` | Tier 1 retrieval tests |
| `test_entity_extraction.py` | Tier 2 entity extraction tests |
| `test_end_to_end.py` | Full pipeline tests |
| `conftest.py` | Test fixtures (mock retriever, extractor, etc.) |
| `golden_queries.json` | 500 golden trading questions |
| `pytest.ini` | Pytest configuration |
| `test_runner.py` | Custom test runner with reporting |

## Interpreting Metrics

### Precision@10
- **0.50**: 5 out of 10 results are relevant (minimum target)
- **0.70**: 7 out of 10 results are relevant (good)
- **0.90**: 9 out of 10 results are relevant (excellent)

### nDCG@10
- **0.50**: Reasonable ranking quality (minimum target)
- **0.70**: Good ranking considering position
- **0.90**: Excellent ranking with relevant results first

### Entity F1
- **0.50**: Moderate entity extraction
- **0.85**: Target - balanced precision and recall
- **0.95**: Excellent extraction

### Latency (p99)
- **50ms**: Very fast (excellent)
- **100ms**: Tier 1 target
- **200ms**: Acceptable (slower)
- **500ms**: Tier 2 target
- **1000ms+**: Slow (investigate)

## Typical Test Run Output

```
===== test session starts =====
collected 45 items

test_retrieval.py::TestTier1Retrieval::test_retrieval_precision_at_10_sample PASSED      [ 2%]
test_retrieval.py::TestTier1Retrieval::test_retrieval_hit_at_1_sample PASSED             [ 4%]
test_entity_extraction.py::TestTier2EntityExtraction::test_entity_f1_score_sample PASSED [ 20%]
test_end_to_end.py::TestEndToEndPipeline::test_e2e_retrieval_and_extraction PASSED       [ 40%]

===== 45 passed in 2.34s =====

Test Summary:
- Total: 45
- Passed: 45 ✅
- Failed: 0 ❌
- Pass Rate: 100%

Benchmark Status:
- Tier 1 Precision@10: 0.65 (target: ≥0.50) ✅
- Tier 2 Entity F1: 0.92 (target: ≥0.85) ✅
- Tier 1 Latency p99: 45ms (target: ≤100ms) ✅
- Tier 2 Latency p99: 150ms (target: ≤500ms) ✅
```

## Troubleshooting

### Tests fail immediately
```bash
# Check if pytest is installed correctly
pytest --version

# Install dependencies
pip install -r requirements.txt

# Run with verbose output
pytest -v -s
```

### Low precision scores
- Check query-document relevance in mock retriever
- Verify sample corpus has relevant documents
- Review ground_truth_keywords in test

### Latency too high
- Check system load
- Run with fewer parallel processes: `pytest -n 1`
- Profile with: `pytest --profile`

### Import errors
- Make sure you're in tests directory: `cd /workspace/group1-rag/tests`
- Add to PYTHONPATH: `export PYTHONPATH=/workspace/group1-rag:$PYTHONPATH`

## Next Steps

1. **Integrate with real retriever**: Replace `MockRetriever` with actual `HybridRetriever`
2. **Integrate with real extractor**: Replace `MockEntityExtractor` with actual system
3. **Benchmark on full dataset**: Use all 500 golden queries
4. **Establish baseline**: `python test_runner.py --save-baseline baseline.json`
5. **Track regression**: `python test_runner.py --compare baseline.json`

## Resources

- **Full documentation**: See `README.md`
- **Metrics explanation**: See `README.md` → "Evaluation Metrics"
- **Golden queries**: See `golden_queries.json`
- **Test framework**: See `test_metrics.py`

---

**Need help?** Check `results/pytest.log` for detailed error messages.
