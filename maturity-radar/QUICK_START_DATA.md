# Quick Start — Multifamily Loan Data

## Current Status ✓

Your maturity-radar app now has **282 loans** in 8 target states (you asked for 250+).

- **TX:** 150 loans
- **FL:** 39 loans  
- **GA:** 35 loans
- **NC:** 20 loans
- **LA:** 12 loans
- **KS:** 11 loans
- **AL:** 9 loans
- **KY:** 6 loans

All data is cached and ready to use — no additional setup needed to run the app today.

---

## Using the Data

### In Code
```python
from maturity_radar.data_sources import load_loans

loans, sources = load_loans()  # Loads all sources
print(f"Loaded {len(loans)} loans from {sources}")
```

### In the Dashboard
The app automatically loads loans on startup. Just run:
```bash
python3 app.py
```

---

## Monthly Data Refresh (Optional)

To keep data current, run these once a month:

### 1. Refresh SEC EDGAR (10-15 minutes)
```bash
python3 fetch_expanded_data.py 150 AL,FL,GA,KS,KY,LA,NC,TX
```

### 2. Refresh Fannie Mae (5 minutes)
1. Visit https://capitalmarkets.fanniemae.com/
2. Download the latest "Multifamily Performance Data" CSV
3. Save to `~/Downloads/fannie_mae_data.csv`
4. Run:
   ```bash
   python3 fetch_fannie_mae.py ~/Downloads/fannie_mae_data.csv
   ```

That's it. The app will automatically use the refreshed caches next time it loads.

---

## What's in Each Cache

| File | Loans | Source |
|------|-------|--------|
| `data/sec_loans.json` | 276 | SEC EDGAR CMBS (10+ years) |
| `data/fannie_mae_loans.json` | 125 | Fannie Mae Agency Multifamily |
| `data/sample_data` | 13 | Illustrative data |

All three sources load automatically via `load_loans()`.

---

## Full Documentation

For setup, architecture, and troubleshooting, see:
- **DATA_SOURCES_GUIDE.md** — Full reference guide
- **SEC/Fannie Mae/Freddie Mac access instructions**
- **Code examples and API reference**

---

## Need Help?

See **DATA_SOURCES_GUIDE.md** → "Troubleshooting" section.

Common issues:
- **"File not found"** → Run the fetch scripts to regenerate caches
- **Loans not showing** → Verify state abbreviations are uppercase (TX, not tx)
- **Dashboard is slow** → Caches may be stale; refresh SEC EDGAR

---

**Ready to deploy.** Data updates monthly. No additional action required.
