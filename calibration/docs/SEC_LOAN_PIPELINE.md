# SEC CMBS Loan Maturity Pipeline (LCMV-58)

Securitized SEC Loan Maturity Pipeline documentation.

## Overview

LCMV-58 extends the loan maturity pipeline (LCMV-37) to include private-label securitized multifamily loans via SEC filings. This closes the coverage gap from 41% (GSE-only) to 80-90% of the multifamily loan market.

### Strategic Value

- **Market gap**: Freddie Mac/Fannie Mae cover GSE channel (41% of originations); SEC captures private-label CMBS (40-50%)
- **2026 CMBS maturity wall**: $76.6B-$146.2B; ~$57.7B with default risk
- **First-mover advantage**: SEC filings flag deals 1-3 years before maturity
- **Competitive moat**: Data is public, but integration quality + early detection = defensible

### SEC Data Sources

Three primary SEC filing types:

1. **Form 424B5** (Initial Prospectus)
   - Filed when CMBS deal closes
   - Contains loan-level tape (20-30 fields per loan)
   - Clean, structured data (origination snapshot)
   - Best source for loan characteristics (DSCR, LTV, property, etc.)

2. **Form 10-D** (Servicer Report)
   - Filed monthly/quarterly by servicers
   - Tracks loan performance over time (updated regularly)
   - Shows delinquencies, occupancy, loan modifications
   - Best source for ongoing monitoring and distress detection

3. **Form 8-K** (Material Events) [Optional]
   - Filed for material events (optional in MVP)
   - Signals defaults, extensions, payoffs
   - Best source for early warning

## Installation

### Dependencies

```bash
pip install pandas requests pdfplumber PyPDF2 openpyxl
```

Optional (for HTML parsing):
```bash
pip install beautifulsoup4
```

### Setup

1. Clone or navigate to calibration directory:
```bash
cd /workspace/Lexerd\ Capital\ Management/calibration
```

2. Import modules:
```python
from data.sec_edgar_client import SecEdgarClient
from data.prospectus_parser import ProspectusParser
from data.servicer_report_parser import ServicerReportParser
from data.loan_deduplication import LoanDeduplicator
from data.unified_loan_scorer import UnifiedLoanScorer
from data.sec_alert_system import SecAlertSystem
```

## Usage Guide

### Step 1: Query SEC EDGAR for CMBS Deals

```python
from data.sec_edgar_client import SecEdgarClient

# Initialize client
client = SecEdgarClient(cache_enabled=True)

# Query CMBS deals
deals = client.query_cmbs_deals(
    keywords=["multifamily", "apartment"],
    years=[2024, 2023, 2022],
    form_types=["424B5", "10-D"]
)

print(f"Found {len(deals)} CMBS deals")
for deal in deals[:5]:
    print(f"  - {deal['deal_name']} ({deal['filing_date']})")
```

### Step 2: Download and Parse Prospectuses

```python
from data.prospectus_parser import ProspectusParser

# Initialize parser
parser = ProspectusParser()

# Download prospectus
prospectus_pdf = client.download_prospectus(deal['filing_url'])

# Save to disk (optional)
with open('prospectus.pdf', 'wb') as f:
    f.write(prospectus_pdf)

# Parse loan schedule
loans = parser.parse_prospectus_pdf('prospectus.pdf')
print(f"Extracted {len(loans)} loans from prospectus")
print(loans[['property_address', 'dscr', 'ltv', 'maturity_date']].head())
```

### Step 3: Download and Parse Servicer Reports

```python
from data.servicer_report_parser import ServicerReportParser

# Initialize parser
parser = ServicerReportParser()

# Download servicer report (10-D)
report = client.download_servicer_report(servicer_report_url)

# Parse performance data
performance = parser.parse_servicer_report(report)
print(f"Extracted performance for {len(performance)} loans")
print(performance[['loan_id', 'delinquency_status', 'occupancy']].head())
```

### Step 4: Deduplicate SEC Loans Against B3

```python
from data.loan_deduplication import LoanDeduplicator

# Load B3 loans (from LCMV-37 pipeline)
b3_loans = pd.read_csv('b3_loans.csv')

# Deduplicate
dedup = LoanDeduplicator()
unified = dedup.match_sec_to_b3_loans(sec_loans, b3_loans)

print(unified['loan_source'].value_counts())
# Output:
#   GSE-only      1234
#   SEC-only      567
#   dual-channel  45
```

### Step 5: Score SEC Loans

```python
from data.unified_loan_scorer import UnifiedLoanScorer

# Score using LCMV-37 logic
scorer = UnifiedLoanScorer()
scored_loans = scorer.score_sec_loans(unified_loans)

print(scored_loans[['loan_id', 'maturity_tier', 'refinance_risk', 'opportunity_rank']].head())
```

### Step 6: Generate Alerts

```python
from data.sec_alert_system import SecAlertSystem

# Generate opportunities
alert_system = SecAlertSystem()
opportunities = alert_system.generate_sec_opportunities(scored_loans)

print(f"Generated {len(opportunities)} opportunities for outreach")

# Export to CSV for sourcing team
csv = alert_system.generate_outreach_list(opportunities, format="csv")
with open('sec_opportunities.csv', 'w') as f:
    f.write(csv)
```

### Complete Pipeline Example

```python
from data.sec_edgar_client import SecEdgarClient
from data.prospectus_parser import ProspectusParser
from data.servicer_report_parser import ServicerReportParser
from data.loan_deduplication import LoanDeduplicator
from data.unified_loan_scorer import UnifiedLoanScorer
from data.sec_alert_system import SecAlertSystem
import pandas as pd

# Step 1: Query SEC
client = SecEdgarClient()
deals = client.query_cmbs_deals(years=[2024])

# Step 2-3: Parse prospectuses and reports
all_loans = []
for deal in deals[:10]:  # Process first 10 deals
    try:
        prospectus_pdf = client.download_prospectus(deal['filing_url'])
        parser = ProspectusParser()
        loans = parser.parse_prospectus_pdf(prospectus_pdf)
        all_loans.append(loans)
    except Exception as e:
        print(f"Error processing {deal['deal_name']}: {e}")

sec_loans = pd.concat(all_loans, ignore_index=True)

# Step 4: Deduplicate
dedup = LoanDeduplicator()
b3_loans = pd.read_csv('b3_loans.csv')
unified_loans = dedup.match_sec_to_b3_loans(sec_loans, b3_loans)

# Step 5: Score
scorer = UnifiedLoanScorer()
scored_loans = scorer.score_sec_loans(unified_loans)

# Step 6: Generate alerts
alert_system = SecAlertSystem()
opportunities = alert_system.generate_sec_opportunities(scored_loans)

print(f"Pipeline complete: {len(opportunities)} opportunities identified")
```

## Data Sources

### SEC EDGAR API

- **Endpoint**: https://data.sec.gov/submissions
- **Rate limit**: No official limit, self-throttled to 1 req/sec
- **Authentication**: None required (public data)
- **Data access**: 100% free, permanent archive

### CIK Lookup

Find CIK (issuer identifier) via:
- SEC EDGAR Company Search: https://www.sec.gov/cgi-bin/browse-edgar
- By company name or ticker

### Example CIKs (Multifamily CMBS)

- JP Morgan Chase: 0000047809
- Deutsche Bank: 0000315627
- Goldman Sachs: 0000886947

## Parsing Strategy

### PDF Parsing (424B5 Prospectuses)

Tools: `pdfplumber` (preferred) or `PyPDF2`

Steps:
1. Open PDF with pdfplumber
2. Iterate pages, find loan schedule tables
3. Extract table → DataFrame
4. Validate field ranges (DSCR, LTV, occupancy)
5. Standardize column names to B3 format

Common challenges:
- Pre-2010 prospectuses: Scanned images with OCR errors
- Multi-page tables: Continuation pages, header rows
- Column name variations: "DSCR" vs "Debt Service Coverage Ratio"
- Missing optional fields: Occupancy, rent not always disclosed

### HTML Parsing (10-D Servicer Reports)

Tools: `BeautifulSoup` (preferred) or `pandas.read_html()`

Steps:
1. Extract tables from HTML using BeautifulSoup
2. Identify performance table (has payment status, loan ID, balance)
3. Convert to DataFrame
4. Classify delinquency status (Performing, 30+, 60+, 90+, Default)
5. Extract modifications (extensions, payoffs)

Common challenges:
- Variable table structures (different servicers)
- Nested headers (multi-level column names)
- Mixed data types (text, currency, percentages)
- Missing occupancy disclosure (optional)

## Data Quality Notes

### What's Included

- Loan origination date (from prospectus filing date)
- Property address, type, units
- DSCR, LTV, occupancy at origination
- Current balance (from servicer reports)
- Payment status (current, 30+, 60+, 90+, default)
- Loan modifications (extensions, rate adjustments)

### What's Missing or Limited

- Rent roll detail (only summary occupancy)
- Tenant concentration (not disclosed in most servicer reports)
- Capital expenditure plans (not disclosed)
- Environmental/phase 1 reports (not in SEC filings)
- Full property financials (confidential, not disclosed)

### Data Quality Issues

1. **Pre-2010 deals**: Scanned prospectuses with OCR errors
   - Solution: Manual validation, fuzzy matching on addresses
2. **Servicer report inconsistency**: Format varies by servicer
   - Solution: Flexible HTML parsing, fallback to text extraction
3. **Missing fields**: Occupancy, rent not always disclosed
   - Solution: Use defaults (e.g., 95% occupancy), flag missing data
4. **Address variations**: "123 Main St" vs "123 Main Street"
   - Solution: Fuzzy matching with >85% similarity threshold

## Integration with LCMV-37

SEC pipeline reuses LCMV-37 scoring logic:

1. **Maturity Scorer**: Classify Tier 1/2/3 by refinance risk
2. **Secondary Market Filter**: Filter to Lexerd criteria (min $1M, max 80% LTV, etc.)
3. **Stress Analysis**: Model rate stress scenarios (+100bps, +200bps, +300bps)
4. **Alert System**: Rank by opportunity, generate outreach list

Key insight: Same scoring logic for SEC loans as B3 loans → unified ranking.

## Monthly Refresh Process

Recommended monthly update schedule:

```bash
# 1. Query new prospectuses (monthly CMBS issuance)
# 2. Parse and extract loan data
# 3. Deduplicate against B3 loans
# 4. Score and rank
# 5. Generate alerts for sourcing team
# 6. Archive previous month's data

# Typical volume:
# - 30-50 new CMBS deals per month
# - 100-500 loans per deal
# - ~5,000-25,000 new loans per month to track
```

## Troubleshooting

### Issue: No SEC deals found

**Cause**: Query parameters too restrictive (e.g., form_type typo)

**Solution**:
```python
# Debug: check available form types
client = SecEdgarClient()
# Try broader query
deals = client.query_cmbs_deals(keywords=["multifamily"])
```

### Issue: PDF parsing fails with OCR errors

**Cause**: Pre-2010 scanned prospectuses

**Solution**:
```python
# Use lenient validation
parser = ProspectusParser(strict_validation=False)
# Manually review flagged records
```

### Issue: Servicer report has no performance tables

**Cause**: Servicer uses non-standard HTML format

**Solution**:
1. Check if BeautifulSoup installed (`pip install beautifulsoup4`)
2. Try fallback text parsing (less accurate)
3. Check servicer name in table metadata (some servicers format differently)

### Issue: Deduplication missing matches

**Cause**: Address variations not caught by fuzzy matching

**Solution**:
```python
# Increase fuzzy match threshold
dedup = LoanDeduplicator(address_fuzzy_threshold=0.80)
# Or manually review borderline matches (score 0.6-0.75)
```

## Performance

- **Query SEC EDGAR**: 1-5 sec per query (1 req/sec throttle)
- **Parse prospectus PDF**: ~3-10 sec per deal (100-500 loans)
- **Parse servicer report**: ~1-3 sec per report
- **Deduplicate 100K loans**: ~10-30 sec (fuzzy matching)
- **Score 100K loans**: ~5-10 sec (parallel scoring possible)
- **End-to-end pipeline (1 month CMBS)**: ~5-10 minutes

Target: Process entire monthly CMBS universe in <30 minutes.

## Security & Compliance

- **No authentication required**: SEC data is public
- **No credentials in code**: All config via environment variables or config files
- **Rate limiting**: Self-imposed 1 req/sec (respect SEC infrastructure)
- **Data retention**: Archive historical data (immutable, no PII)
- **HIPAA/PCI**: Not applicable (commercial real estate data only)

## Future Enhancements

1. **8-K Event Classification** (currently optional)
   - Flag distress events (defaults, forbearances, extensions)
   - Early warning for Tier 1 loans

2. **Occupancy Forecasting**
   - Trend occupancy across servicer reports
   - Predict distress based on declining occupancy

3. **Rent Growth Analysis**
   - Extract rent data from servicer reports
   - Model refinance risk based on rent trends

4. **Lender-Servicer Network Graph**
   - Map lenders, servicers, deal relationships
   - Identify concentration risk (e.g., 1 lender = 20% of portfolio)

5. **Real-time 10-D Monitoring**
   - Automate servicer report downloads
   - Alert on delinquency changes >5% month-over-month

## References

- SEC EDGAR: https://www.sec.gov/cgi-bin/browse-edgar
- CMBS Data Hub: https://www.data-cmbs.com (commercial alternative)
- LCMV-37 Documentation: See calibration/docs/LOAN_MATURITY_PIPELINE.md
- Servicer Report Standards: SEC Form 10-D Instructions

## Support

For issues, questions, or enhancements:
- Email: sajan@forwardai.dev
- Jira: https://sajanforwardai.atlassian.net/projects/LCMV/issues
- Internal Wiki: https://wiki.forwardai.dev/lcmv-58

---

**Last Updated**: 2026-07-31  
**Version**: 1.0 (MVP)  
**Status**: In Review (LCMV-58)
