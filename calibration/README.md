# Stage 1: Calibrate & Encode — Thesis & 3M Model Calibration

Encode Lexerd's exact investment box and 3M Model (Market/Model/Management) into a transparent, calibrated scoring framework.

## What This Does

**Input:** Lexerd's investment parameters (geographic markets, financial constraints, property specs, management requirements)

**Process:** 3M Model scoring engine (Market 30%, Model 40%, Management 30%)

**Output:** Transparent fit-scoring rubric + configurable dashboard for parameter tuning + instant re-scoring

## Architecture

```
config/lexerd_thesis.json
         ↓
models/thesis.py (ThesisConfig, PropertyProfile, ScoreResult)
         ↓
models/scorers.py (MarketScorer, ModelScorer, ManagementScorer, FinalScorer)
         ↓
config.py (load/save configuration)
         ↓
ui/ (Streamlit dashboard — coming Phase 3)
```

## Core Models

### ThesisConfig
Lexerd's tunable parameters:
- **Geographic:** target_markets, population thresholds
- **Employment:** min growth 2% YoY, anchor types (military, medical, university, manufacturing)
- **Valuation:** min cap-rate spread 200bps
- **Financial:** $2M–$20M equity, $10M–$100M capital, <$50M acq price
- **Property:** 70–300 units, Class B/B-, 10–30 years old
- **Operations:** 80–95% occupancy, >28% expense ratio above benchmark
- **Management:** third-party preferred, First Communities integration, Lory playbook
- **Weights:** Market 30%, Model 40%, Management 30%

### PropertyProfile
Input property data:
```python
PropertyProfile(
    property_id="prop_123",
    property_name="San Marco Village",
    address="...",
    city="Jacksonville",
    state="FL",
    units=200,
    property_class="B",
    year_built=2005,
    occupancy=0.85,  # 85% occupied = upside signal
    avg_rent_per_unit=1250,
    expense_ratio=0.32,  # 32% = above-benchmark opportunity
    market_expense_ratio=0.28,
    employment_anchors=["military"],
    population_growth_yoy=0.018,
    employment_growth_yoy=0.025,
)
```

### ScoreResult
Output: transparent fit scoring with breakdown
```python
ScoreResult(
    property_id="prop_123",
    market_score=78.5,          # 0–100
    model_score=85.0,
    management_score=72.0,
    final_fit_score=81.2,       # Weighted: (78.5 × 0.30) + (85.0 × 0.40) + (72.0 × 0.30)
    confidence_grade="B",       # 75–89: Good fit
    market_breakdown={...},     # How points broken down
    model_breakdown={...},
    management_breakdown={...},
    fit_rationale="...",        # Human-readable explanation
    key_strengths=["..."],      # What it does well
    key_weaknesses=["..."],     # What it lacks
)
```

## 3M Model Scoring

### Market Score (30% weight)
- Employment growth (25 pts)
- Population growth (15 pts)
- Cap-rate spread (30 pts)
- Employment anchor strength (30 pts)

**Example:** Property in Fargo, ND (military base, 3% emp growth, 250bps cap spread) scores 85/100 on Market.

### Model Score (40% weight)
- Unit count 70–300 (20 pts)
- Property class B/B- (20 pts)
- Occupancy 80–95% (20 pts)
- Expense ratio gap (20 pts)
- Rent upside (20 pts)

**Example:** 180-unit Class B, 85% occupied, 32% expense ratio (4% above 28% benchmark) scores 90/100 on Model.

### Management Score (30% weight)
- PM type: third-party (20 pts)
- First Communities integration (20 pts)
- Lory rebranding fit (20 pts)
- Operator track record (20 pts)

**Example:** Third-party-managed, good Lory fit scores 78/100 on Management.

### Final Fit Score
```
Final = (Market × 0.30) + (Model × 0.40) + (Management × 0.30)
Final = (85 × 0.30) + (90 × 0.40) + (78 × 0.30)
Final = 25.5 + 36 + 23.4 = 84.9 → Confidence Grade B (Good fit)
```

## Quick Start

### Load & Score
```python
from models.scorers import FinalScorer
from models.thesis import PropertyProfile
from config import get_default_config

# Get Lexerd's baseline thesis
thesis = get_default_config()

# Score a property
scorer = FinalScorer()
prop = PropertyProfile(
    property_id="test_1",
    property_name="Test Property",
    address="123 Main St",
    city="Atlanta",
    state="GA",
    units=150,
    property_class="B",
    year_built=2010,
    occupancy=0.85,
    avg_rent_per_unit=1300,
    expense_ratio=0.32,
    market_expense_ratio=0.28,
    employment_anchors=["medical"],
    employment_growth_yoy=0.025,
    population_growth_yoy=0.018,
)

result = scorer.score(prop, thesis)
print(f"Final Fit Score: {result.final_fit_score:.1f}/100 ({result.confidence_grade.value})")
print(f"Rationale: {result.fit_rationale}")
```

### Tune Parameters & Re-Score
```python
# Expand to new markets
thesis.target_markets.append('LA')

# Increase capital range
thesis.max_capital = 150_000_000

# Adjust weights (emphasize Model more)
thesis.model_weight = 0.50
thesis.market_weight = 0.25
thesis.management_weight = 0.25

# Re-score instantly
result = scorer.score(prop, thesis)
# Property may now rank higher if Model score is strong
```

## Tickets

- **LCMV-19:** Thesis Calibration & 3M Rubric Design
- **LCMV-20:** Scoring Engine Implementation & Unit Tests
- **LCMV-21:** Configurable Calibration Dashboard & UI
- **LCMV-22:** Testing, Documentation & Interview Demo

## Interview Narrative

Stage 1 demonstrates:
1. **Deep investment thesis understanding** — encoded Lexerd's 3M Model into transparent scoring
2. **Configurable systems thinking** — parameters tunable, model re-scores instantly
3. **Full-stack capability** — from Python backend (Pydantic, scoring logic) to Streamlit UI
4. **Data-driven rigor** — weights documented, breakdowns transparent, confidence grades justified

**Demo flow:**
1. Show baseline thesis + scoring rubric
2. Score a sample property (San Marco Village, Lory of Braden River)
3. Tune parameters: "Expand to KS market" → property scores change
4. Export scored universe as CSV

## Files

```
calibration/
├── models/
│   ├── __init__.py
│   ├── thesis.py           # ThesisConfig, PropertyProfile, ScoreResult
│   └── scorers.py          # Market/Model/Management scorers
├── config/
│   └── lexerd_thesis.json  # Default parameters
├── config.py               # Load/save configuration
├── tests/
│   ├── __init__.py
│   └── test_scorers.py     # Unit tests (Market/Model/Management/Final)
├── ui/
│   └── __init__.py         # Streamlit dashboard (Phase 3)
├── docs/
│   ├── LEXERD_THESIS.md    # Complete investment thesis (6-part structure)
│   └── FIT_SCORING_RUBRIC.md # Detailed 3M Model rubric with examples
└── README.md
```

## Documentation

### LEXERD_THESIS.md
Comprehensive investment thesis encoding Lexerd's 3M Model:
- Part 1: Market Thesis (employment anchors, growth criteria, valuations)
- Part 2: Model Thesis (property specs, value-add signals)
- Part 3: Management Thesis (PM strategy, First Communities, Lory playbook)
- Part 4: Financial Constraints (equity, capital, returns)
- Part 5: 3M Model Scoring Rubric (detailed point allocations)
- Part 6: Interview Narrative (2-minute pitch)

### FIT_SCORING_RUBRIC.md
Operational rubric for deal screening and evaluation:
- Quick reference table (A/B/C/D confidence grades)
- Detailed scoring for each 3M dimension with examples
- Decision-making framework (screening → diligence → post-close)
- Calibration notes (tunable parameters)

## Dashboard

**Stage 1 is now interactive!** Run the Streamlit dashboard for thesis tuning and deal scoring:

```bash
cd calibration
streamlit run ui/app.py
```

**Features:**
- Thesis parameter tuning (weights, thresholds, financial constraints)
- Sample property scoring (San Marco Village, Lory of Braden River)
- Batch CSV upload & scoring (score 100+ deals at once)
- Results visualization (scores, breakdowns, confidence grades)
- Export scored universe as CSV

See `/calibration/ui/README.md` for detailed usage guide.

## Next Phases

Phase 4 integrates real data pipelines (Zillow, securitized maturity signals).  
Phase 5 completes interview demo and deal sourcing workflows.
