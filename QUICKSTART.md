# Lexerd v2 Quick Start

## 1. Clone & Setup

```bash
cd /workspace/lexerd2
git log --oneline  # Verify commits are there
```

## 2. Run Locally

```bash
cd calibration
streamlit run ui/app.py --server.port 8506
```

Visit: http://localhost:8506

## 3. Upload Properties & Score

1. Go to **Properties** tab
2. Upload `sample_data.csv` (or your own CSV)
3. Click "Score Properties"
4. View results in **Analytics** tab

## 4. View Opportunities

1. Go to **Opportunities** tab
2. See 161 real SEC CMBS deals ranked by maturity
3. 24 Tier 1 (Critical) with immediate refinance pressure
4. Click "View Filing" to see SEC documents

## 5. Run Tests

```bash
pytest tests/ -v --cov=calibration
bash /workspace/.swarm/praxis/toolkit/bin/praxis-gate.sh
```

## 6. Development Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Implement + test (TDD first)
pytest tests/test_my_feature.py

# Run gate before commit
bash /workspace/.swarm/praxis/toolkit/bin/praxis-gate.sh

# Commit with descriptive message
git add -A
git commit -m "Feature: add my feature

- What it does
- Why it matters
- How to test it

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# Push & create PR
git push origin feature/my-feature
```

## 7. Key Files to Know

- `calibration/ui/app.py` — Streamlit dashboard
- `calibration/models/thesis.py` — ThesisConfig (weights, rules)
- `calibration/models/scorers.py` — FinalScorer (3M model)
- `calibration/data/bls_client.py` — Employment data
- `calibration/data/sec_edgar_client.py` — CMBS filings
- `calibration/opportunities/opportunity_loader.py` — Load deals
- `calibration/tests/` — Comprehensive test suite

## 8. Available Data

### Properties
- Upload CSV with property details
- Auto-enriched with BLS employment, Census data
- Scored on Market / Model / Management

### Opportunities
- 161 real multifamily CMBS deals
- Ranked by maturity (Tier 1/2/3)
- Real DSCR, LTV, maturity dates
- Clickable SEC filing links

### Markets
- 20+ BLS MSA codes (Jacksonville, Austin, Denver, etc.)
- Employment growth data (monthly, 24h cache)
- Ready for Census/Zillow integration

## 9. Port Configuration

- **v1**: Port 8505 (production) → /sg-lexerdcapitalmanagement
- **v2**: Port 8506 (development) → /sg-lexerdcapitalmanagement-v2

Run both simultaneously for A/B testing or feature validation.

## 10. Deployment

When ready to deploy v2 to production:

```bash
# v2 runs on port 8506
# Nginx proxy routes /sg-lexerdcapitalmanagement-v2 → localhost:8506
# See DEPLOYMENT.md for full setup

# Start app (background)
cd /workspace/lexerd2/calibration
python3 -m streamlit run ui/app.py --server.port 8506 &
```

---

See README.md for full documentation.
