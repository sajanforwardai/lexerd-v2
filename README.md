# Lexerd Deal Engine v2

Next-generation multifamily acquisition scoring and opportunity identification platform.

**Status**: Development  
**Port**: 8506 (runs alongside v1 at 8505)  
**Deployment**: https://forwardai.dev/sg-lexerdcapitalmanagement-v2

---

## 🎯 Features

### Core Scoring Engine
- **3M Model**: Market (30%) + Model (40%) + Management (30%)
- **Multifamily Focus**: Residential 5+ unit properties
- **Evidence-Based**: Data-driven, not broker-dependent

### Data Sources
- **Freddie Mac B3**: GSE multifamily loans (weekly updates, 41% market coverage)
- **SEC CMBS Filings**: Private-label securitizations (424B5 prospectuses, 10-D servicer reports)
- **Employment Data**: BLS MSA codes (20+ markets, monthly updates)
- **Census & Zillow**: Population growth, cap-rates, market comps (ready to integrate)

### Opportunity Pipeline
- **Tier 1 (Critical)**: < 6 months to maturity (immediate refinance pressure)
- **Tier 2 (High)**: 6-24 months (near-term refinance risk)
- **Tier 3 (Monitor)**: 24+ months (future pipeline)

### Dashboard Features
- **Batch Scoring**: Upload CSV, score 100+ properties in < 5 minutes
- **Opportunity Ranking**: Unified GSE + CMBS opportunity list
- **Analytics**: Score distribution, risk breakdown, geographic concentration
- **Export**: CSV/Excel reports for CRM integration

---

## 📁 Project Structure

```
lexerd2/
├── calibration/              # Core scoring engine
│   ├── models/              # Thesis config, scoring logic (FinalScorer, ThesisConfig)
│   ├── data/                # Data clients
│   │   ├── bls_client.py           # Bureau of Labor Statistics API
│   │   ├── sec_edgar_client.py     # SEC EDGAR API (CMBS filings)
│   │   ├── sec_prospectus_parser.py # Parse 424B5 prospectuses
│   │   ├── loan_deduplication.py   # Match SEC loans to B3 loans
│   │   └── alert_system.py         # Maturity alerts & ranking
│   │
│   ├── opportunities/       # Opportunity loading & ranking
│   │   ├── opportunity_loader.py   # Load from cache + deduplicate
│   │   └── cache/                  # Parquet caches (freddie_mac_loans.parquet)
│   │
│   ├── ui/                  # Streamlit dashboard
│   │   └── app.py                  # Main dashboard (Properties, Opportunities, Analytics, About)
│   │
│   ├── tests/               # Comprehensive test suite
│   │   ├── test_bls_integration.py
│   │   ├── test_sec_edgar_client.py
│   │   ├── test_sec_prospectus_parser.py
│   │   ├── test_loan_pipeline.py
│   │   └── test_opportunities.py
│   │
│   ├── docs/                # User & developer documentation
│   │   ├── BLS_INTEGRATION.md
│   │   ├── SEC_EDGAR_API.md
│   │   ├── SEC_LOAN_PIPELINE.md
│   │   └── LOAN_PIPELINE.md
│   │
│   └── .streamlit/config.toml    # Port 8506 configuration
│
├── site/                    # Static deployment files (if needed)
│
├── deploy.v2.spec.json      # v2 deployment configuration
├── CHANGELOG.v2.md          # Version history
├── MIGRATION-GUIDE.md       # v1 → v2 upgrade guide
├── DEPLOYMENT.md            # Production deployment guide
│
└── [LCMV specs]             # Feature specifications
    ├── LCMV-23-BLS-Integration-DETAILED.md
    ├── LCMV-24-Census-Zillow-Integration-DETAILED.md
    ├── LCMV-25-Loan-Maturity-Pipeline-DETAILED.md
    └── LCMV-26-Data-Pipeline-Orchestrator-DETAILED.md
```

---

## 🚀 Getting Started

### Local Development

```bash
# Clone repo
git clone <private-repo-url> /workspace/lexerd2
cd /workspace/lexerd2/calibration

# Run Streamlit (port 8506)
streamlit run ui/app.py --server.port 8506

# Visit http://localhost:8506
```

### Run Tests

```bash
cd calibration
pytest tests/ -v --cov=calibration

# Run praxis-gate (before committing)
bash /workspace/.swarm/praxis/toolkit/bin/praxis-gate.sh
```

### Score Properties

```python
from calibration.models import FinalScorer, ThesisConfig, PropertyProfile
from calibration.data.bls_client import BLSClient

# Initialize scorer
thesis = ThesisConfig(market_weight=0.30, model_weight=0.40, management_weight=0.30)
scorer = FinalScorer()

# Create a property
prop = PropertyProfile(
    property_id="prop-1",
    property_name="Oak Ridge Apartments",
    city="Jacksonville",
    state="FL",
    units=180,
    property_class="B",
    year_built=2010,
    occupancy=0.85,
    avg_rent_per_unit=1600,
    expense_ratio=0.30,
    market_expense_ratio=0.28,
)

# Score it
result = scorer.score(prop, thesis)
print(f"Final Score: {result.final_fit_score:.0f}")
print(f"Grade: {result.confidence_grade.value}")
```

### Load Opportunities

```python
from calibration.opportunities import load_opportunities, get_tier_breakdown

# Load top 100 opportunities by risk tier
opportunities = load_opportunities(top_n=100)

# Get tier breakdown
tiers = get_tier_breakdown()
print(f"Tier 1 (Critical): {tiers[1]}")
print(f"Tier 2 (High): {tiers[2]}")
print(f"Tier 3 (Monitor): {tiers[3]}")
```

---

## 📊 Data Freshness

| Source | Update Frequency | Lag | Coverage |
|--------|------------------|-----|----------|
| Freddie Mac B3 | Weekly | 1-2 weeks | 41% of multifamily market |
| SEC CMBS Filings | Weekly (new deals) | Varies | 40-50% of multifamily market |
| BLS Employment | Monthly | 6 days after month-end | 20+ MSAs |
| Census | Annual | Real-time (cached 365d) | 350+ MSAs |
| Zillow | Real-time API | Real-time | 350+ MSAs |

---

## 🔧 Development Workflow

v2 follows **ForwardAI praxis build doctrine**:

### 1. Spec-Gate
Write a feature spec in `/workspace/.swarm/briefs/` and use the spec-agent template.

### 2. TDD Worktree-Swarm
```bash
# Create feature branch
git checkout -b feature/your-feature

# Write failing test first
pytest tests/test_your_feature.py -v

# Implement to make test pass
# Commit with test-first discipline
```

### 3. Two-Reviewer Gate
```bash
# Run praxis-gate before merge (lint, type-check, test, coverage, security)
bash /workspace/.swarm/praxis/toolkit/bin/praxis-gate.sh
```

### 4. Interactive Deploy
```bash
# Merge to master
git push origin feature/your-feature
# Create PR → review → merge

# Auto-deploys to port 8506 → nginx → https://forwardai.dev/sg-lexerdcapitalmanagement-v2
```

---

## 🧪 Testing

```bash
# Unit tests (TDD)
pytest tests/ -v

# Full praxis-gate (before commit)
bash /workspace/.swarm/praxis/toolkit/bin/praxis-gate.sh

# Coverage report
pytest --cov=calibration --cov-report=html
open htmlcov/index.html
```

---

## 📚 Documentation

- **DEPLOYMENT.md** — Production setup & troubleshooting
- **MIGRATION-GUIDE.md** — Upgrading from v1
- **CHANGELOG.v2.md** — Version history
- **calibration/docs/** — Feature documentation
  - BLS_INTEGRATION.md
  - SEC_EDGAR_API.md
  - SEC_LOAN_PIPELINE.md
  - LOAN_PIPELINE.md

---

## 🏗️ Architecture

### Scoring Flow
```
Property → Market Score (BLS, Census, Zillow, cap-rates)
        → Model Score (DSCR, LTV, rent positioning, occupancy)
        → Management Score (sponsor track record, ops efficiency)
        → 3M Weighted Score (30-40-30)
        → Grade (A/B/C/D) + Confidence
        → Investment Decision
```

### Opportunity Pipeline
```
Freddie Mac B3 Tapes (weekly)
        ↓
Parse → Extract → Deduplicate
        ↓
SEC CMBS Filings (weekly)
        ↓
Score → Rank by Tier (1/2/3) → Maturity → Opportunity Pipeline
        ↓
Dashboard → Analytics → Export (CSV/Excel)
```

---

## 🔐 Security & Compliance

- **No hardcoded credentials**: API keys via environment variables
- **Praxis security gate**: Secrets scanning, SBOM, CVE checks
- **Test coverage >90%**: Comprehensive test suite
- **Code review**: Two-reviewer gate before merge
- **Audit trail**: Git history + test logs

---

## 🚢 Production Deployment

Deployed at: **https://forwardai.dev/sg-lexerdcapitalmanagement-v2**

- Streamlit on port 8506
- Nginx reverse proxy
- Cloudflare CDN
- See DEPLOYMENT.md for setup

---

## 📞 Support & Feedback

- **Issues**: [GitHub repo]/issues
- **Docs**: See calibration/docs/
- **Questions**: Ask in pull request comments
- **Feedback**: Create a discussion or issue

---

**Built with ForwardAI praxis build doctrine**  
*Spec-gate → TDD worktree-swarm → two-reviewer gate → interactive deploy*

---

*Last updated: 2026-07-31*
