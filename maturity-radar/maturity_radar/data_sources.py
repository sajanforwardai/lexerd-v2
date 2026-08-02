"""Where the loan universe comes from — the production path, documented.

The prototype runs on sample_data.py (illustrative, Freddie-shaped). This module records the
real sources so the path from prototype to production is explicit, and provides the adapter
seam where a live loader plugs in.

Per the council's data-plumbing correction:
  - USE  Freddie Mac Multifamily disclosure (K-Deal / SBL), direct from the GSE — property-level,
         includes note rate, maturity, current balance, most-recent NOI/DSCR, occupancy. This is
         the data Sajan surveilled at KBRA and the most defensible source.
  - DROP FHFA PUDB — it is census-tract aggregated, has no property addresses or loan IDs, and
         therefore can never produce an enrichable lead.
  - DEEMPHASIZE SEC ABS-EE / EX-102 — conduit-CMBS-centric and thin on agency multifamily; much
         CMBS is 144A / CRE-CLO that never files ABS-EE.

Owner enrichment (county assessor -> LLC -> principal) is deliberately human-in-the-loop for the
top of the list, not an automated scrape of hundreds of counties.
"""

# Reference endpoints for the production loader (documented, not called by the prototype).
FREDDIE_MF_DISCLOSURE = "https://mf.freddiemac.com/investors/data"   # K-Deal / SBL loan-level files
SEC_EDGAR_UA_REQUIRED = True   # EDGAR returns 403 without a declared User-Agent header


import os

# Where the adapter looks for a downloaded MLPD file (env override or these defaults).
MLPD_PATHS = [
    os.environ.get("MLPD_PATH", ""),
    os.path.join(os.path.dirname(__file__), "..", "data", "MLPD.csv"),
    "/workspace/Lexerd Capital Management/maturity-radar/data/MLPD.csv",
]


SEC_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "sec_loans.json")
FREDDIE_MAC_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "freddie_mac_loans.json")
FANNIE_MAE_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "fannie_mae_loans.json")

# Target states for Lexerd Capital Management outreach (multifamily focus)
TARGET_STATES = {"AL", "FL", "GA", "KS", "KY", "LA", "NC", "TX"}

# Fannie Mae Data Dynamics — public loan-level performance data
# Register free at: https://capitalmarkets.fanniemae.com/
# Download latest multifamily performance data (CSV format)
FANNIE_MAE_DYNAMICS = "https://capitalmarkets.fanniemae.com/"


def mlpd_file():
    """Return the path to a present MLPD file, or None if none is downloaded yet."""
    for p in MLPD_PATHS:
        if p and os.path.isfile(p):
            return p
    return None


def save_sec_cache(loans, path=SEC_CACHE):
    """Write fetched SEC loans to a JSON cache so the app doesn't re-fetch each run."""
    import dataclasses
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    for l in loans:
        d = dataclasses.asdict(l)
        d["maturity"] = l.maturity.isoformat()
        rows.append(d)
    with open(path, "w") as f:
        json.dump(rows, f, indent=1)
    return path


def _load_sec_cache(path):
    import json
    from datetime import date
    from .models import Loan
    with open(path) as f:
        rows = json.load(f)
    out = []
    for r in rows:
        r = dict(r)
        r["maturity"] = date.fromisoformat(r["maturity"])
        r.setdefault("program", "Conduit")  # the SEC cache is conduit CMBS
        out.append(Loan(**r))
    return out


def save_freddie_mac_cache(loans, path=FREDDIE_MAC_CACHE):
    """Write fetched Freddie Mac loans to a JSON cache for the app."""
    import dataclasses
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    for l in loans:
        d = dataclasses.asdict(l)
        d["maturity"] = l.maturity.isoformat()
        rows.append(d)
    with open(path, "w") as f:
        json.dump(rows, f, indent=1)
    return path


def _load_freddie_mac_cache(path):
    """Load cached Freddie Mac loans from JSON."""
    import json
    from datetime import date
    from .models import Loan
    with open(path) as f:
        rows = json.load(f)
    out = []
    for r in rows:
        r = dict(r)
        r["maturity"] = date.fromisoformat(r["maturity"])
        r.setdefault("program", "Agency")  # Freddie Mac loans are Agency multifamily
        out.append(Loan(**r))
    return out


def save_fannie_mae_cache(loans, path=FANNIE_MAE_CACHE):
    """Write fetched Fannie Mae loans to a JSON cache for the app."""
    import dataclasses
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    for l in loans:
        d = dataclasses.asdict(l)
        d["maturity"] = l.maturity.isoformat()
        rows.append(d)
    with open(path, "w") as f:
        json.dump(rows, f, indent=1)
    return path


def _load_fannie_mae_cache(path):
    """Load cached Fannie Mae loans from JSON."""
    import json
    from datetime import date
    from .models import Loan
    with open(path) as f:
        rows = json.load(f)
    out = []
    for r in rows:
        r = dict(r)
        r["maturity"] = date.fromisoformat(r["maturity"])
        r.setdefault("program", "Agency")  # Fannie Mae loans are Agency multifamily
        out.append(Loan(**r))
    return out


def _num(v, default=0.0):
    """Parse a numeric value, handling strings with commas, currency symbols, and whitespace."""
    try:
        s = str(v).strip().replace(",", "").replace("$", "").replace('"', "")
        return float(s) if s not in ("", "nan", "None", ".") else default
    except (ValueError, TypeError):
        return default


def _rate(v):
    """Parse interest rate, normalizing percent to decimal form."""
    s = str(v).strip().replace("%", "")
    r = _num(s)
    return r / 100.0 if r > 1 else r


def _parse_date(v):
    """Parse a date string in multiple formats common in GSE disclosures."""
    from datetime import datetime
    s = str(v).strip().upper()
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%d%b%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def load_fannie_mae(path, states=None, log=print):
    """Parse a Fannie Mae multifamily performance CSV file into Loan objects.

    Fannie Mae provides loan-level performance data via Data Dynamics platform (free registration at
    https://capitalmarkets.fanniemae.com/). Files contain multifamily loans with current balance,
    note rate, maturity, DSCR, occupancy, and property detail.

    Expected CSV columns (Fannie Mae standard format, may vary by dataset):
      - Loan Identifier (or Loan ID, loanid) — unique identifier
      - Property State (or state, State)
      - Number of Units (or units, Units)
      - Interest Rate (or Note Rate, interest_rate) — typically in percent
      - Maturity Date (or dt_mty, maturity_date)
      - Current Balance (or Unpaid Balance, current_balance)
      - Original Balance (or original_balance)
      - Debt Service Coverage Ratio (or DSCR, dscr)
      - Physical Occupancy (or occupancy, Occupancy Rate)
      - Property Name — optional
      - City — optional
      - County — optional

    Args:
        path: Path to the CSV file
        states: Set of state abbreviations to filter by (e.g., {"TX", "GA"}). If None, no filter.
        log: Logging function (default: print)

    Returns:
        List of Loan objects matching the schema.
    """
    import csv
    from datetime import date
    from .models import Loan

    loans = []
    target = set(states) if states else None

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                if log:
                    log(f"Warning: empty or malformed CSV at {path}")
                return loans

            # Normalize column names (strip whitespace, case-insensitive matching)
            headers = {k.strip().lower(): k for k in reader.fieldnames or []}

            # Map expected field names to their actual CSV column (case-insensitive)
            def get_col(names):
                """Return the actual column name, or None if not found."""
                for n in names:
                    if n.lower() in headers:
                        return headers[n.lower()]
                return None

            col_loan_id = get_col(["Loan Identifier", "Loan ID", "loanid", "loan_id", "LoanID"])
            col_state = get_col(["Property State", "State", "state", "code_st"])
            col_units = get_col(["Number of Units", "Units", "units", "cnt_rsdntl_unit"])
            col_rate = get_col(["Interest Rate", "Note Rate", "interest_rate", "rate_int"])
            col_maturity = get_col(["Maturity Date", "maturity_date", "dt_mty"])
            col_current_balance = get_col(["Current Balance", "Unpaid Balance", "current_balance", "amt_upb_endg"])
            col_orig_balance = get_col(["Original Balance", "original_balance"])
            col_dscr = get_col(["Debt Service Coverage Ratio", "DSCR", "dscr", "rate_dcr"])
            col_occupancy = get_col(["Physical Occupancy", "Occupancy", "occupancy", "Occupancy Rate"])
            col_noi = get_col(["Net Operating Income", "NOI", "noi"])
            col_property_name = get_col(["Property Name", "property_name", "PropertyName"])
            col_city = get_col(["City", "city", "PropertyCity"])
            col_county = get_col(["County", "county", "PropertyCounty"])
            col_source_url = get_col(["Source URL", "source_url"])

            row_count = 0
            for row in reader:
                row_count += 1

                # Extract and validate required fields
                loan_id = (row.get(col_loan_id) or "").strip()
                state = (row.get(col_state) or "").strip().upper()

                if not loan_id or not state:
                    continue

                if target and state not in target:
                    continue

                # Parse numeric and date fields
                units = int(_num(row.get(col_units), 0))
                note_rate = _rate(row.get(col_rate))
                maturity = _parse_date(row.get(col_maturity))
                current_balance = _num(row.get(col_current_balance))
                orig_balance = _num(row.get(col_orig_balance), current_balance)
                dscr = _num(row.get(col_dscr))
                occupancy = _num(row.get(col_occupancy)) / 100.0 if _num(row.get(col_occupancy)) > 1 else _num(row.get(col_occupancy))

                # Validation: all core fields required
                if maturity is None or units <= 0 or note_rate <= 0 or current_balance <= 0 or dscr <= 0:
                    continue

                # NOI: use provided value or derive from DSCR
                noi_val = _num(row.get(col_noi))
                if noi_val <= 0:
                    noi_val = dscr * current_balance * note_rate

                # Optional fields (safe to leave empty/default)
                property_name = (row.get(col_property_name) or "").strip() or f"Loan {loan_id}"
                city = (row.get(col_city) or "").strip() or state
                county = (row.get(col_county) or "").strip()
                source_url = (row.get(col_source_url) or "").strip() or FANNIE_MAE_DYNAMICS

                # Parse origination year if possible
                origination_year = 0

                loans.append(Loan(
                    loan_id=loan_id,
                    property_name=property_name,
                    city=city,
                    county=county,
                    state=state,
                    units=units,
                    origination_year=origination_year,
                    original_balance=orig_balance,
                    current_balance=current_balance,
                    note_rate=note_rate,
                    maturity=maturity,
                    interest_only=False,
                    most_recent_noi=noi_val,
                    most_recent_dscr=dscr,
                    occupancy=occupancy,
                    program="Agency",
                    source_url=source_url,
                ))

        if log:
            log(f"Parsed {len(loans)} valid loans from {row_count} rows in {path}")

    except FileNotFoundError:
        if log:
            log(f"File not found: {path}")
    except Exception as e:
        if log:
            log(f"Error parsing {path}: {e}")

    return loans


def load_freddie_mac(path, states=None, log=print):
    """Parse a Freddie Mac K-Deal or SBL CSV disclosure file into Loan objects.

    K-Deal and SBL files contain loan-level disclosures with property detail, current balance,
    note rate, maturity, most-recent DSCR, occupancy, and NOI. These are real, de-identified
    multifamily agency loans — the data Sajan surveilled at KBRA.

    Expected CSV columns (Freddie Mac standard K-Deal format):
      - Loan Sequence Number (or LoanSequenceNumber, Loan ID) — unique identifier
      - Property State
      - Units (or Number of Units)
      - Note Rate (or Interest Rate) — in percent or decimal
      - Maturity Date
      - Current Balance (or Current UPB, Unpaid Balance)
      - Original Balance (or Original UPB)
      - Most Recent DSCR (or Debt Service Coverage Ratio)
      - Most Recent Occupancy (or Occupancy Rate)
      - Most Recent NOI (or Net Operating Income) — optional; derived from DSCR if missing
      - Property Name — optional
      - City — optional
      - County — optional
      - Deal Name — optional

    Args:
        path: Path to the CSV file
        states: Set of state abbreviations to filter by (e.g., {"TX", "GA"}). If None, no filter.
        log: Logging function (default: print)

    Returns:
        List of Loan objects matching the schema.
    """
    import csv
    from datetime import date
    from .models import Loan

    loans = []
    target = set(states) if states else None

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                log(f"Warning: empty or malformed CSV at {path}")
                return loans

            # Normalize column names (strip whitespace, case-insensitive matching)
            headers = {k.strip().lower(): k for k in reader.fieldnames or []}

            # Map expected field names to their actual CSV column (case-insensitive)
            def get_col(names):
                """Return the actual column name, or None if not found."""
                for n in names:
                    if n.lower() in headers:
                        return headers[n.lower()]
                return None

            col_loan_id = get_col(["Loan Sequence Number", "LoanSequenceNumber", "Loan ID", "loan id", "lnno"])
            col_state = get_col(["Property State", "State", "code_st"])
            col_units = get_col(["Units", "Number of Units", "cnt_rsdntl_unit"])
            col_rate = get_col(["Note Rate", "Interest Rate", "rate_int"])
            col_maturity = get_col(["Maturity Date", "dt_mty"])
            col_current_balance = get_col(["Current Balance", "Current UPB", "Unpaid Balance", "amt_upb_endg"])
            col_orig_balance = get_col(["Original Balance", "Original UPB", "original amount"])
            col_dscr = get_col(["Most Recent DSCR", "Debt Service Coverage Ratio", "rate_dcr"])
            col_occupancy = get_col(["Most Recent Occupancy", "Occupancy Rate"])
            col_noi = get_col(["Most Recent NOI", "Net Operating Income", "noi"])
            col_property_name = get_col(["Property Name", "property_name"])
            col_city = get_col(["City", "city"])
            col_county = get_col(["County", "county"])
            col_deal = get_col(["Deal Name", "deal_name", "Dealname"])
            col_source_url = get_col(["Source URL", "source_url"])

            row_count = 0
            for row in reader:
                row_count += 1

                # Extract and validate required fields
                loan_id = (row.get(col_loan_id) or "").strip()
                state = (row.get(col_state) or "").strip().upper()

                if not loan_id or not state:
                    continue

                if target and state not in target:
                    continue

                # Parse numeric and date fields
                units = int(_num(row.get(col_units), 0))
                note_rate = _rate(row.get(col_rate))
                maturity = _parse_date(row.get(col_maturity))
                current_balance = _num(row.get(col_current_balance))
                orig_balance = _num(row.get(col_orig_balance), current_balance)
                dscr = _num(row.get(col_dscr))
                occupancy = _num(row.get(col_occupancy)) / 100.0 if _num(row.get(col_occupancy)) > 1 else _num(row.get(col_occupancy))

                # Validation: all core fields required
                if maturity is None or units <= 0 or note_rate <= 0 or current_balance <= 0 or dscr <= 0:
                    continue

                # NOI: use provided value or derive from DSCR
                noi_val = _num(row.get(col_noi))
                if noi_val <= 0:
                    noi_val = dscr * current_balance * note_rate

                # Optional fields (safe to leave empty/default)
                property_name = (row.get(col_property_name) or "").strip() or f"Loan {loan_id}"
                city = (row.get(col_city) or "").strip() or state
                county = (row.get(col_county) or "").strip()
                deal = (row.get(col_deal) or "").strip()
                source_url = (row.get(col_source_url) or "").strip() or FREDDIE_MF_DISCLOSURE

                # Parse origination year from maturity or deal name if possible
                origination_year = 0
                if deal and len(deal) >= 4:
                    try:
                        # Try to extract year from deal name (e.g., "K7X-2019" or "SBL 2018")
                        import re
                        year_match = re.search(r'\b(19|20)\d{2}\b', deal)
                        if year_match:
                            yr = int(year_match.group(0))
                            origination_year = yr
                    except:
                        pass

                loans.append(Loan(
                    loan_id=loan_id,
                    property_name=property_name,
                    city=city,
                    county=county,
                    state=state,
                    units=units,
                    origination_year=origination_year,
                    original_balance=orig_balance,
                    current_balance=current_balance,
                    note_rate=note_rate,
                    maturity=maturity,
                    interest_only=False,  # K-Deal/SBL don't typically disclose IO status in standard files
                    most_recent_noi=noi_val,
                    most_recent_dscr=dscr,
                    occupancy=occupancy,
                    program="Agency",
                    deal=deal,
                    source_url=source_url,
                ))

        if log:
            log(f"Parsed {len(loans)} valid loans from {row_count} rows in {path}")

    except FileNotFoundError:
        if log:
            log(f"File not found: {path}")
    except Exception as e:
        if log:
            log(f"Error parsing {path}: {e}")

    return loans


def load_kdeal_supplemental(path, states=None, log=print):
    """Parse Freddie Mac K-Deal Supplemental MSIA CSV file into Loan objects.

    K-Deal Supplemental files contain detailed loan-level data on multifamily mortgages
    with supplemental financing, including property names, maturity dates, note rates,
    current balances, and original balances. State information is enriched via K-Deal
    number lookup from data/kdeal_states.json (extracted from performance reports).

    Args:
        path: Path to the CSV file
        states: Set of state abbreviations to filter by (optional; loans enriched with state)
        log: Logging function (default: print)

    Returns:
        List of Loan objects matching the schema.
    """
    from datetime import date
    import csv
    import json
    from .models import Loan

    loans = []
    row_count = 0
    target = set(states) if states else None

    # Load K-Deal to state mapping
    kdeal_states_path = os.path.join(os.path.dirname(__file__), "..", "data", "kdeal_states.json")
    kdeal_states = {}
    try:
        if os.path.isfile(kdeal_states_path):
            with open(kdeal_states_path) as f:
                kdeal_states = json.load(f)
            if log:
                log(f"Loaded {len(kdeal_states)} deal-to-state mappings")
    except (OSError, json.JSONDecodeError):
        if log:
            log(f"Could not load K-Deal state mappings from {kdeal_states_path}")

    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            # Read all lines, skip first line (metadata), use second line as header
            all_lines = f.readlines()

            if len(all_lines) < 3:
                if log:
                    log(f"File too short: {path}")
                return loans

            # Line 1 is header (skip line 0 which is "Report as of...")
            header_line = all_lines[1].strip()
            reader = csv.reader([header_line])
            headers = next(reader)

            # Build column map
            col_map = {}
            for i, h in enumerate(headers):
                h_stripped = h.strip()
                if "K-Deal #" in h_stripped:
                    col_map['deal_id'] = i
                elif "Property Name" in h_stripped:
                    col_map['property_name'] = i
                elif "K-Deal loan" in h_stripped and "Maturity" in h_stripped:
                    col_map['maturity'] = i
                elif "K-Deal loan" in h_stripped and "Note Rate" in h_stripped:
                    col_map['note_rate'] = i
                elif "K-Deal loan" in h_stripped and "Current UPB" in h_stripped:
                    col_map['current_balance'] = i
                elif "K-Deal loan" in h_stripped and "Original UPB" in h_stripped:
                    col_map['orig_balance'] = i
                elif "KDeal loan" in h_stripped and "Loan Status" in h_stripped:
                    col_map['loan_status'] = i

            # Validate required columns
            required = ['deal_id', 'property_name', 'maturity', 'note_rate', 'current_balance', 'orig_balance']
            if not all(k in col_map for k in required):
                if log:
                    log(f"Missing required columns in {path}. Found: {col_map}")
                return loans

            # Parse data rows (starting from line 2)
            for line_idx in range(2, len(all_lines)):
                line = all_lines[line_idx].strip()
                if not line:
                    continue

                row_count += 1
                try:
                    reader = csv.reader([line])
                    values = next(reader)

                    if len(values) < max(col_map.values()) + 1:
                        continue

                    # Extract and clean values
                    deal_id = values[col_map['deal_id']].strip()
                    property_name = values[col_map['property_name']].strip()

                    if not deal_id or not property_name:
                        continue

                    loan_id = f"KDEAL-{deal_id}"

                    # Parse numeric fields
                    note_rate_str = values[col_map['note_rate']].strip()
                    note_rate = _rate(note_rate_str)

                    current_balance_str = values[col_map['current_balance']].strip()
                    current_balance = _num(current_balance_str)

                    orig_balance_str = values[col_map['orig_balance']].strip()
                    orig_balance = _num(orig_balance_str, current_balance)

                    maturity_str = values[col_map['maturity']].strip()
                    maturity = _parse_date(maturity_str)

                    loan_status = values[col_map.get('loan_status', len(values))].strip() if col_map.get('loan_status', len(values)) < len(values) else "Active"

                    # Validation: require minimum fields
                    if maturity is None or note_rate <= 0 or current_balance <= 0:
                        continue

                    # Skip defeased/closed loans
                    if "Defeased" in loan_status or "Closed" in loan_status:
                        continue

                    # Enrich state via K-Deal number lookup
                    state = kdeal_states.get(deal_id, "")

                    # If state filtering is requested, skip loans not in target states
                    if target and state and state not in target:
                        continue

                    loans.append(Loan(
                        loan_id=loan_id,
                        property_name=property_name,
                        city="",
                        county="",
                        state=state,  # Enriched via K-Deal to state mapping
                        units=0,
                        origination_year=0,
                        original_balance=orig_balance,
                        current_balance=current_balance,
                        note_rate=note_rate,
                        maturity=maturity,
                        interest_only=False,
                        most_recent_noi=0.0,
                        most_recent_dscr=1.0,
                        occupancy=0.0,
                        program="Agency",
                        source_url="https://mf.freddiemac.com/investors/data",
                    ))

                except Exception as e:
                    continue

        if log:
            log(f"Parsed {len(loans)} valid loans from {row_count} data rows in {path}")

    except FileNotFoundError:
        if log:
            log(f"File not found: {path}")
    except Exception as e:
        if log:
            log(f"Error parsing {path}: {e}")

    return loans


def load_loans(source: str = "auto", states=None):
    """Return (loans, sources_used).

    Loads loans from multiple sources in priority order:
      1. SEC EDGAR cache (conduit CMBS, broadest)
      2. Fannie Mae cache (agency, 72K+ loans available)
      3. Freddie Mac cache (agency, K-Deal/SBL)
      4. MLPD file (agency, requires registration)
      5. Sample data (illustrative fallback)

    If source="auto" (the default), tries all sources and merges results, deduplicating by loan_id
    (SEC wins in case of conflict, then Fannie Mae, then Freddie Mac). source_label reflects which
    sources were combined ("sec+freddie+fannie", "sec", etc.).

    Args:
        source: "auto" (combine all), "sec", "freddie", "fannie", "mlpd", or "sample" (use only that one).
        states: Set or list of state abbreviations to filter by (default: no filter).

    Returns:
        Tuple of (loans, source_label_string)
    """
    sources_used = []
    all_loans = {}  # loan_id -> Loan (for deduping, with priority: sec > fannie > freddie > mlpd > sample)

    if source in ("auto", "sec"):
        if os.path.isfile(SEC_CACHE):
            try:
                loans = _load_sec_cache(SEC_CACHE)
                if loans:
                    for l in loans:
                        if not states or l.state in set(states):
                            all_loans[l.loan_id] = l
                    sources_used.append("sec")
            except (ValueError, OSError, KeyError, TypeError):
                pass
        if source == "sec" and not sources_used:
            raise FileNotFoundError("No usable SEC cache. Run: python3 fetch_data.py")

    if source in ("auto", "fannie"):
        if os.path.isfile(FANNIE_MAE_CACHE):
            try:
                loans = _load_fannie_mae_cache(FANNIE_MAE_CACHE)
                if loans:
                    for l in loans:
                        if not states or l.state in set(states):
                            # Fannie Mae loans only fill gaps (don't override SEC)
                            if l.loan_id not in all_loans:
                                all_loans[l.loan_id] = l
                    sources_used.append("fannie")
            except (ValueError, OSError, KeyError, TypeError):
                pass
        if source == "fannie" and not sources_used:
            raise FileNotFoundError(
                "No Fannie Mae cache. Register at https://capitalmarkets.fanniemae.com/, "
                "download multifamily performance data CSV, and run: "
                "python3 -c 'from maturity_radar.data_sources import load_fannie_mae, save_fannie_mae_cache; "
                "loans = load_fannie_mae(\"path/to/fannie_mae.csv\"); save_fannie_mae_cache(loans)'"
            )

    if source in ("auto", "freddie"):
        if os.path.isfile(FREDDIE_MAC_CACHE):
            try:
                loans = _load_freddie_mac_cache(FREDDIE_MAC_CACHE)
                if loans:
                    for l in loans:
                        if not states or l.state in set(states):
                            # Freddie loans only fill gaps (don't override SEC/Fannie)
                            if l.loan_id not in all_loans:
                                all_loans[l.loan_id] = l
                    sources_used.append("freddie")
            except (ValueError, OSError, KeyError, TypeError):
                pass
        if source == "freddie" and not sources_used:
            raise FileNotFoundError(
                "No Freddie Mac cache. Run: python3 fetch_freddie_data.py (requires K-Deal/SBL CSV files)"
            )

    # K-Deal Supplemental MSIA files (Freddie Mac agency multifamily supplemental loans)
    kdeal_paths = [
        "/workspace/kdeal-data/supplemental-june2026/Kdeal_Supplemental_Mortgage_Loans_June_2026 (1)-KDeal Supp MSIA.csv",
    ]

    if source in ("auto", "kdeal"):
        for kdeal_file in kdeal_paths:
            if os.path.isfile(kdeal_file):
                try:
                    loans = load_kdeal_supplemental(kdeal_file)
                    if loans:
                        for l in loans:
                            # K-Deal loans have no state; skip state filtering
                            # Loans are accepted as-is but flagged with empty state
                            if l.loan_id not in all_loans:
                                all_loans[l.loan_id] = l
                        if "kdeal" not in sources_used:
                            sources_used.append("kdeal")
                except (ValueError, OSError, KeyError, TypeError):
                    pass
        if source == "kdeal" and not sources_used:
            raise FileNotFoundError(
                "No K-Deal Supplemental MSIA CSV found. Download from Freddie Mac investor portal "
                "(https://mf.freddiemac.com/investors/data) and place at: "
                "/workspace/kdeal-data/supplemental-june2026/Kdeal_Supplemental_Mortgage_Loans_June_2026-KDeal Supp MSIA.csv"
            )

    if source in ("auto", "mlpd"):
        path = mlpd_file()
        if path:
            from .mlpd import load_mlpd
            loans = load_mlpd(path, states=states)
            if loans:
                for l in loans:
                    if l.loan_id not in all_loans:
                        all_loans[l.loan_id] = l
                sources_used.append("mlpd")
        if source == "mlpd" and not sources_used:
            raise FileNotFoundError(
                "No MLPD file found. Register at infofreddiemac.com (LP=755), download the "
                "dataset, and place it at data/MLPD.csv (or set MLPD_PATH)."
            )

    if source in ("auto", "sample"):
        from .sample_data import sample_loans
        loans = sample_loans()
        if loans:
            for l in loans:
                if not states or l.state in set(states):
                    if l.loan_id not in all_loans:
                        all_loans[l.loan_id] = l
            sources_used.append("sample")
        if source == "sample" and not sources_used:
            raise FileNotFoundError("No sample data available.")

    if not all_loans:
        raise FileNotFoundError("No loans available from any source.")

    loans = list(all_loans.values())
    source_label = "+".join(sources_used) if sources_used else "none"
    return loans, source_label
