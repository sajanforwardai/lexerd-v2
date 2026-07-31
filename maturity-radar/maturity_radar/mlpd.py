"""Adapter for the Freddie Mac Multifamily Loan Performance Database (MLPD).

The MLPD is a loan-quarter panel covering a subset of Freddie's multifamily book (K-deal, SBL,
and whole loans) through 2025Q3. It is DE-IDENTIFIED: it carries property state and metro but no
street address, city, or property name — so it powers the refinance-pressure scoring, and owner
enrichment stays a separate human-in-the-loop step.

Access requires registering at infofreddiemac.com (LP=755); this adapter parses the file you
download from there. It reads the real MLPD column names below.

    from maturity_radar.mlpd import load_mlpd
    loans = load_mlpd("MLPD_public.csv", states={"TX", "GA"})

Field names (from the MLPD data dictionary):
    lnno            Loan ID                     amt_upb_endg   Ending unpaid balance
    quarter         Calendar quarter (y12q4)    rate_int       Note rate
    mrtg_status     Loan status                 rate_dcr       Original DSCR (DCR)
    dt_mty          Maturity date (DDMMMYYYY)   cnt_rsdntl_unit  Residential units
    code_st         Property state (2-char)     Dealname       K/SBL deal name
    geographical_region  Property metro
"""

from datetime import datetime

from .models import Loan

# MLPD status values that mean the loan is gone (paid off / liquidated / REO). Kept loose;
# the presence of a liquidation date is the firmer signal, handled below.
_DEAD_STATUS = {"PAIDOFF", "PAID OFF", "LIQUIDAT", "REO", "MATURED", "REPURCH"}

SECURITIES_LOOKUP = "https://mf.freddiemac.com/investors/performance-lookup"


def _num(v, default=0.0):
    try:
        s = str(v).strip().replace(",", "")
        return float(s) if s not in ("", "nan", "None", ".") else default
    except (ValueError, TypeError):
        return default


def _norm_rate(r):
    """MLPD note rate may be a percent (3.6) or a decimal (0.036); normalize to decimal."""
    r = _num(r)
    return r / 100.0 if r > 1 else r


def _parse_date(v):
    """MLPD dates are DDMMMYYYY (e.g. 01MAR2027). Return a date or None."""
    s = str(v).strip().upper()
    for fmt in ("%d%b%Y", "%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _quarter_key(q):
    """Turn 'y12q4' / '2012Q4' into a sortable integer so we can pick the latest observation."""
    s = str(q).lower().replace("y", "").replace("-", "")
    try:
        yr, qtr = s.split("q")
        yr = int(yr)
        yr += 2000 if yr < 100 else 0
        return yr * 10 + int(qtr)
    except (ValueError, IndexError):
        return 0


def _source_url(dealname):
    # The lookup is a search UI, not a deep link — point at the real page; the deal name
    # is carried separately as the thing to search there.
    return SECURITIES_LOOKUP


def load_mlpd(path, states=None):
    """Parse an MLPD file into Loan objects: latest active observation per loan.

    Requires pandas. Filters to loans that (a) have a maturity date and residential units,
    (b) are not liquidated, and (c) are in ``states`` if given. NOI is not in the MLPD, so an
    in-place NOI is implied from the reported DSCR: NOI = DSCR x (balance x note rate), which
    makes the projected-refi DSCR reduce to DSCR x (note_rate / market_rate) — a transparent
    rate-shock proxy.
    """
    import pandas as pd

    df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    # Keep the actual most-recent-quarter ROW per loan. NOTE: groupby().last() must NOT be used
    # here — it returns the last non-null value of each column independently, which back-fills
    # blank cells in the newest quarter from older quarters and produces incoherent records.
    df["_qk"] = df["quarter"].map(_quarter_key)
    df = df.sort_values("_qk").drop_duplicates("lnno", keep="last").reset_index(drop=True)

    keep_states = set(states) if states else None
    loans = []
    for _, r in df.iterrows():
        state = str(r.get("code_st", "")).strip().upper()
        if keep_states and state not in keep_states:
            continue
        status = str(r.get("mrtg_status", "")).strip().upper()
        if any(d in status for d in _DEAD_STATUS) or str(r.get("liq_dte", "")).strip() not in ("", "nan", "None"):
            continue
        maturity = _parse_date(r.get("dt_mty"))
        units = int(_num(r.get("cnt_rsdntl_unit")))
        if maturity is None or units <= 0:
            continue

        balance = _num(r.get("amt_upb_endg"))
        note_rate = _norm_rate(r.get("rate_int"))
        dscr = _num(r.get("rate_dcr"), default=0.0)
        if balance <= 0 or note_rate <= 0 or dscr <= 0:
            continue
        implied_noi = dscr * balance * note_rate  # see docstring

        deal = str(r.get("Dealname", "")).strip()
        metro = str(r.get("geographical_region", "")).strip() or state
        loans.append(Loan(
            loan_id=str(r.get("lnno", "")).strip(),
            property_name=f"Loan {str(r.get('lnno','')).strip()}",  # de-identified: no name
            city=metro, county="", state=state, units=units,
            origination_year=(_parse_date(r.get("dt_fund")).year if _parse_date(r.get("dt_fund")) else 0),
            original_balance=balance, current_balance=balance,
            note_rate=note_rate, maturity=maturity,
            interest_only=(int(_num(r.get("cnt_blln_term"))) > 0),
            most_recent_noi=implied_noi, most_recent_dscr=dscr,
            occupancy=0.0,
            program="Agency", deal=deal, source_url=_source_url(deal),
        ))
    return loans
