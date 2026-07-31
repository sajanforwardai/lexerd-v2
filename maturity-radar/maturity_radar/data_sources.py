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


def load_loans(source: str = "auto", states=None):
    """Return (loans, source_label).

    source="auto": prefer the real SEC EDGAR cache, then a downloaded MLPD file, then sample.
    source_label is one of "sec", "mlpd", "sample".
    """
    if source in ("auto", "sec"):
        if os.path.isfile(SEC_CACHE):
            try:
                loans = _load_sec_cache(SEC_CACHE)
            except (ValueError, OSError, KeyError, TypeError):
                # Corrupt / truncated / half-written cache — fall through to MLPD or sample
                # rather than taking the whole dashboard down.
                loans = None
            if loans:
                if states:
                    loans = [l for l in loans if l.state in set(states)]
                return loans, "sec"
        if source == "sec":
            raise FileNotFoundError("No usable SEC cache. Run: python3 fetch_data.py")

    if source in ("auto", "mlpd"):
        path = mlpd_file()
        if path:
            from .mlpd import load_mlpd
            return load_mlpd(path, states=states), "mlpd"
        if source == "mlpd":
            raise FileNotFoundError(
                "No MLPD file found. Register at infofreddiemac.com (LP=755), download the "
                "dataset, and place it at data/MLPD.csv (or set MLPD_PATH)."
            )

    from .sample_data import sample_loans
    loans = sample_loans()
    if states:
        loans = [l for l in loans if l.state in set(states)]
    return loans, "sample"
