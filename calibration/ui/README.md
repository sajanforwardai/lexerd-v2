# Calibration Dashboard — Streamlit UI (Phase 3)

**Status:** COMPLETE  
**Ticket:** LCMV-21: Configurable Calibration Dashboard & UI

Interactive dashboard for thesis parameter tuning and deal scoring.

---

## Quick Start

### Run the Dashboard

```bash
cd /workspace/Lexerd\ Capital\ Management/calibration

# Install dependencies (first time only)
pip install -r requirements.txt

# Run the Streamlit app
streamlit run ui/app.py
```

**URL:** `http://localhost:8501`

---

## Features

### 1. **Thesis Configuration (Sidebar)**

Tune Lexerd's investment parameters and watch scores update in real-time:

- **3M Model Weights:** Adjust Market (30%), Model (40%), Management (30%) weights
- **Market Thresholds:** Employment growth minimum, population growth minimum
- **Property Specs:** Unit count range, occupancy range
- **Financial Constraints:** Minimum/maximum equity

**Normalized weights automatically update** to sum to 100%.

### 2. **Sample Scoring**

One-click scoring of known properties:

- **San Marco Village** — Jacksonville FL, 180 units, Class B
- **Lory of Braden River** — Bradenton FL, 250 units, Class B−

**Output:**
- Market/Model/Management scores (0–100)
- Final fit score + confidence grade (A/B/C/D)
- Detailed breakdown by dimension
- Key strengths & weaknesses

### 3. **Batch Upload & Scoring**

Score multiple properties at once:

1. **Upload CSV** with property data
2. **Click "Score All Properties"** to score the universe
3. **Results sorted by fit score** (highest first)
4. **Download CSV** with all scores

#### CSV Format

```
property_id,property_name,city,state,units,property_class,year_built,occupancy,avg_rent_per_unit,market_rent_per_unit,expense_ratio,market_expense_ratio,employment_anchors,employment_growth_yoy,population_growth_yoy,market_cap_rate,management_type
san_marco_001,San Marco Village,Jacksonville,FL,180,B,2005,0.85,1200,1300,0.32,0.27,"military",0.025,0.018,0.080,Third-party
```

**Required columns:**
- `property_id`, `property_name`, `city`, `state`
- `units`, `property_class`, `year_built`
- `occupancy`, `avg_rent_per_unit`, `market_rent_per_unit`
- `expense_ratio`, `market_expense_ratio`
- `employment_anchors` (comma-separated), `employment_growth_yoy`, `population_growth_yoy`
- `market_cap_rate`, `management_type`

**Sample data:** `/calibration/sample_data.csv` (10 test properties)

### 4. **Thesis Documentation**

Quick reference for the 3M Model framework:

- Market scoring (4 dimensions)
- Model scoring (5 dimensions)
- Management scoring (4 dimensions)
- Confidence grading rules (A/B/C/D)
- Links to thesis & rubric documents

---

## Usage Examples

### Example 1: Score San Marco Village

1. Run dashboard
2. Click "Score San Marco Village"
3. View results:
   - Market: 56.9/100 (Jacksonville fundamentals)
   - Model: 90.0/100 (excellent value-add setup)
   - Management: 75.0/100 (good execution capability)
   - Final: 75.6/100 → **Grade B** (good fit, full diligence recommended)

### Example 2: Tune Weights & Re-Score

1. Run dashboard
2. In sidebar, increase Model weight to 50% (from 40%)
3. Decrease Market weight to 25% (from 30%)
4. Click "Score San Marco Village" again
5. **Result:** Final score increases (since Model score is strong)

### Example 3: Batch Score Deal Flow

1. Run dashboard
2. Go to "Batch Upload" tab
3. Upload CSV with 100+ deal prospects
4. Click "Score All Properties"
5. Review results sorted by fit score
6. Download CSV for spreadsheet analysis

---

## Architecture

```
ui/
├── app.py                    # Streamlit dashboard (Main)
├── README.md                 # This file
└── __init__.py

models/
├── thesis.py                 # Pydantic models
└── scorers.py                # 3M Model scoring engines
```

### Data Flow

```
CSV Upload / Sample Property
         ↓
PropertyProfile (input)
         ↓
FinalScorer (score using tuned thesis)
         ↓
ScoreResult (Market/Model/Management scores + rationale)
         ↓
Display in UI (metrics, breakdown, CSV export)
```

---

## Configuration

### Default Thesis

Lexerd's baseline parameters are set in `models/thesis.py` (`ThesisConfig`):

```python
target_markets = ['GA', 'FL', 'AL', 'SC', 'NC', 'TX', 'KS']
min_employment_growth_yoy = 0.02  # 2%
min_population_growth_yoy = 0.015  # 1.5%
min_units = 70
max_units = 300
min_equity = 2_000_000  # $2M
max_equity = 20_000_000  # $20M
market_weight = 0.30
model_weight = 0.40
management_weight = 0.30
```

### Tuning in the Dashboard

All parameters can be adjusted via the sidebar sliders/inputs. Changes take effect immediately on re-scoring.

---

## Testing

### Local Testing

```bash
# From calibration directory
streamlit run ui/app.py

# In browser: http://localhost:8501
# 1. Try "Score San Marco Village"
# 2. Adjust weights in sidebar
# 3. Try "Score Lory of Braden River"
# 4. Upload sample_data.csv for batch scoring
```

### Sample Data

`/calibration/sample_data.csv` contains 10 test properties for quick testing:

- San Marco Village (Jacksonville, Grade B expected)
- Lory of Braden River (Bradenton, Grade B expected)
- Fargo Residential (Fargo, Grade B+ expected)
- Atlanta Metro Garden (Atlanta, Grade C expected)
- Austin Tech Hub (Austin, Grade A expected)
- Houston Energy Park (Houston, Grade D expected)
- Raleigh University Edge (Raleigh, Grade B expected)
- Charleston Harbor Court (Charleston, Grade B expected)
- Miami Luxury Towers (Miami, Grade D expected — too expensive)
- Tulsa Central Plaza (Tulsa, Grade D expected — weak market)

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'models'"

**Solution:** Run from the `calibration` directory, not `ui` directory.

```bash
cd /workspace/Lexerd\ Capital\ Management/calibration
streamlit run ui/app.py
```

### "streamlit: command not found"

**Solution:** Install streamlit via requirements.txt

```bash
pip install -r requirements.txt
```

### CSV upload fails

**Solution:** Ensure CSV has all required columns (see "CSV Format" section above). Use `sample_data.csv` as a template.

---

## Next Steps

- **Phase 4:** Real data integration (Zillow, securitized maturity signals)
- **Phase 5:** Portfolio analysis + sourcing pipeline + interview demo
- **Enhancements:**
  - Property-level drill-down (view all scoring components)
  - Comparison view (score properties side-by-side)
  - Market comparison (how does Jacksonville compare to Fargo?)
  - Scenario analysis (what-if weight changes)
  - Export templates (for LP presentations, deal memo)

---

*Last updated: July 31, 2026*  
*LCMV-21 Status: COMPLETE ✓*
