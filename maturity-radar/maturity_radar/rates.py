"""Current refinance-rate benchmark, fetched live.

The refinance rate an owner faces today isn't published as one number, so we derive it the way
the market does: the current 10-year Treasury (FRED, series DGS10) plus a typical agency
multifamily spread. Fetched at data-refresh time and cached, so the dashboard shows a real,
dated number instead of a hard-coded assumption.
"""

import json
import os
import urllib.request

FRED_DGS10 = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
AGENCY_MF_SPREAD = 0.0175  # ~175 bps over the 10-yr UST for agency multifamily
RATE_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "rate.json")
UA = "Sajan Goswami research sanjugos66@gmail.com"


def fetch_current_rate():
    """Return {ten_year, spread, rate, as_of, source}, or None on failure."""
    try:
        req = urllib.request.Request(FRED_DGS10, headers={"User-Agent": UA})
        txt = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return None
    last, as_of = None, None
    for line in txt.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) == 2 and parts[1].strip() not in ("", "."):
            try:
                last = float(parts[1]); as_of = parts[0]
            except ValueError:
                continue
    if last is None:
        return None
    ten = last / 100.0
    return {
        "ten_year": round(ten, 4),
        "spread": AGENCY_MF_SPREAD,
        "rate": round(ten + AGENCY_MF_SPREAD, 4),
        "as_of": as_of,
        "source": "10-yr UST (FRED DGS10) + agency spread",
    }


def save_rate(r, path=RATE_CACHE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(r, f, indent=1)
    return path


def load_rate(path=RATE_CACHE):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None
