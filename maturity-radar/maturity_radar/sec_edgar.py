"""Adapter for SEC EDGAR CMBS loan-level data (Reg AB II, Form ABS-EE, Exhibit 102).

Public and fetchable — no login. Conduit CMBS deals disclose every loan's terms and property
data; we keep only the multifamily properties (propertyTypeCode == "MF"), which gives real,
multifamily-only loans with balance, note rate, maturity, DSCR, NOI, occupancy, and location —
each traceable to its SEC filing.

Note: this is CONDUIT CMBS, not agency (Freddie K-deals are not filed as ABS-EE). It is real
loan-level multifamily data; it is not the whole agency universe. Every loan carries a source_url
to the exact SEC filing it came from.
"""

import json
import re
import time
import urllib.request
from datetime import date, datetime

from .models import Loan

UA = "Sajan Goswami research sanjugos66@gmail.com"
EFTS = "https://efts.sec.gov/LATEST/search-index?q=%22commercial%20mortgage%22&forms=ABS-EE&from={}"
DIRLIST = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"


def _get(url, timeout=60):
    # Advertise only gzip (the one encoding we decompress) so the body is never returned in a
    # format we can't read.
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        import gzip
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "ignore")


def _f(tag, s):
    m = re.search(r"<" + tag + r">([^<]*)</" + tag + r">", s)
    return m.group(1).strip() if m else ""


def _num(v):
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return 0.0


def _rate(v):
    r = _num(v)
    return r / 100.0 if r > 1 else r        # EX-102 rates are already decimals (.03486)


def _date(v):
    for fmt in ("%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d", "%d%b%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def find_recent_deals(max_deals=25, max_pages=25):
    """Page EDGAR full-text search for ABS-EE filings and keep the NEWEST filing per trust.

    The full-text feed is relevance-ordered, not date-ordered, so we can't trust arrival order.
    Accession numbers are ``{filerCIK}-{YY}-{sequence}`` (fixed width), so for a given trust the
    lexicographically largest accession is its most recent filing — we keep that.
    Returns [(cik, accession, deal_name)].
    """
    best = {}  # cik -> (accession, name)
    for page in range(max_pages):
        try:
            data = json.loads(_get(EFTS.format(page * 10), timeout=30))
        except Exception:
            continue
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break
        for h in hits:
            src = h.get("_source", {})
            ciks = src.get("ciks") or []
            if not ciks:
                continue
            cik = str(int(ciks[0]))
            acc = h["_id"].split(":")[0].replace("-", "")
            name = (src.get("display_names") or ["?"])[0]
            if cik not in best or acc > best[cik][0]:
                best[cik] = (acc, name)
        time.sleep(0.15)
    deals = [(cik, acc, name) for cik, (acc, name) in best.items()]
    return deals[:max_deals]


def parse_ex102(xml, deal, source_url, states=None, min_maturity=date(2026, 1, 1)):
    """Extract multifamily loans (one per asset, located at its first MF property in a target
    state) from an EX-102 document. Loans maturing before ``min_maturity`` (already resolved or
    outside the maturity-wall window) are skipped."""
    keep = set(states) if states else None
    loans = []
    for chunk in xml.split("<assetNumber>")[1:]:
        asset_no = chunk[:chunk.find("<")].strip() if "<" in chunk else ""
        props = re.findall(r"<property>(.*?)</property>", chunk, re.S)
        mf = None
        for p in props:
            if _f("propertyTypeCode", p) == "MF":
                st = _f("propertyState", p).upper()
                if keep is None or st in keep:
                    mf = p
                    break
        if mf is None:
            continue

        balance = _num(_f("reportPeriodEndScheduledLoanBalanceAmount", chunk)) or \
            _num(_f("originalLoanAmount", chunk))
        rate = _rate(_f("interestRateSecuritizationPercentage", chunk) or
                     _f("originalInterestRatePercentage", chunk))
        maturity = _date(_f("maturityDate", chunk))
        # DSCR is the reliable, standardized field. The raw NOI amount in EX-102 is often a
        # partial-period figure that doesn't reconcile with it, so we derive NOI from DSCR for
        # internal consistency (projected refi DSCR then reduces to DSCR x note_rate / market_rate).
        dscr = _num(_f("mostRecentDebtServiceCoverageNetOperatingIncomePercentage", chunk) or
                    _f("debtServiceCoverageNetOperatingIncomeSecuritizationPercentage", chunk))
        units = int(_num(_f("unitsBedsRoomsNumber", mf)))
        occ = _num(_f("mostRecentPhysicalOccupancyPercentage", chunk))

        if balance <= 0 or rate <= 0 or maturity is None or dscr <= 0:
            continue
        if maturity < min_maturity:
            continue
        noi = dscr * balance * rate

        name = _f("propertyName", mf) or f"Asset {asset_no}"
        city = _f("propertyCity", mf) or _f("propertyCounty", mf) or "(multiple)"
        loans.append(Loan(
            loan_id=f"{deal}-{asset_no}",
            property_name=name,
            city=city, county=_f("propertyCounty", mf),
            state=_f("propertyState", mf).upper(), units=max(units, 0),
            origination_year=0, original_balance=balance, current_balance=balance,
            note_rate=rate, maturity=maturity, interest_only=False,
            most_recent_noi=noi, most_recent_dscr=dscr, occupancy=occ,
            program="Conduit", deal=deal, source_url=source_url,
        ))
    return loans


def _ex102_url(cik, acc):
    """Resolve the asset-data (Exhibit 102) file for a filing — its name varies by filer."""
    try:
        idx = _get(DIRLIST.format(cik=cik, acc=acc), timeout=30)
    except Exception:
        return None
    xmls = re.findall(r'href="([^"]*\.xml)"', idx, re.I)
    names = [x.split("/")[-1] for x in xmls]
    for n in names:
        if "ex102" in n.lower() or "ex-102" in n.lower() or "102" in n.lower():
            return DIRLIST.format(cik=cik, acc=acc) + n
    return None


def fetch_universe(states=None, max_deals=25, log=print):
    """Fetch recent conduit CMBS deals and aggregate their multifamily loans in ``states``."""
    deals = find_recent_deals(max_deals=max_deals)
    log(f"found {len(deals)} deals; parsing multifamily loans...")
    out = []
    for cik, acc, name in deals:
        ex_url = _ex102_url(cik, acc)
        if not ex_url:
            log(f"  skip {name.split('(')[0].strip()}: no EX-102 file")
            continue
        try:
            xml = _get(ex_url)
        except Exception as e:
            log(f"  skip {name.split('(')[0].strip()}: {e}")
            continue
        # Link each loan to the human-browsable SEC filing page, not the raw XML.
        filing_url = DIRLIST.format(cik=cik, acc=acc)
        got = parse_ex102(xml, deal=name.split("(")[0].strip(), source_url=filing_url, states=states)
        if got:
            log(f"  {name.split('(')[0].strip()}: +{len(got)} MF loan(s)")
        out.extend(got)
        time.sleep(0.15)
    log(f"total: {len(out)} multifamily loans in {sorted(states) if states else 'all states'}")
    return out
