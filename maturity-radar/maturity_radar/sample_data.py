"""A realistic sample loan universe for two Lexerd markets.

IMPORTANT — this is ILLUSTRATIVE data, not live GSE disclosure. It is modeled on the fields and
realistic ranges of Freddie Mac Multifamily loan-level disclosure (the data Sajan surveilled at
KBRA), hand-built for two of Lexerd's real markets so the pipeline can be demonstrated end to end
without depending on a live scrape. The production path replaces this module with a Freddie
disclosure adapter; see data_sources.py. Owner fields are the human-in-the-loop enrichment layer,
filled only for the higher-pressure loans — exactly as the scoped build intends.

Markets: Bryan / College Station, TX (Brazos County) and Augusta / Savannah, GA
(Richmond & Chatham Counties) — all Lexerd's stated footprint.
"""

from datetime import date

from .models import Loan

_LOANS = [
    # ── Bryan / College Station, TX (Brazos County) ──
    Loan("FHMS-K7X-0142", "Aggieland Flats", "College Station", "Brazos", "TX", 184,
         2017, 14_800_000, 13_950_000, 0.0372, date(2027, 2, 1), True,
         910_000, 1.29, 0.93,
         owner_entity="Aggieland Flats Holdings LLC",
         owner_mailing="c/o CT Corporation, 1999 Bryan St, Dallas TX",
         principal_hint="Mgr: R. Alvarez (SOS filing) — mgmt co: Asset Living"),
    Loan("FHMS-K068-0231", "Wolf Pen Crossing", "College Station", "Brazos", "TX", 132,
         2016, 9_600_000, 8_900_000, 0.0348, date(2026, 11, 1), True,
         560_000, 1.24, 0.90,
         owner_entity="WPC Multifamily LLC",
         owner_mailing="2200 Texas Ave S, College Station TX",
         principal_hint="Principal likely local sponsor — SOS shows single manager"),
    Loan("FHMS-K734-0088", "Bryan Station Apartments", "Bryan", "Brazos", "TX", 96,
         2018, 6_450_000, 6_100_000, 0.0405, date(2027, 6, 1), True,
         470_000, 1.31, 0.88,
         owner_entity="Bryan Station Partners LLC",
         owner_mailing="c/o Registered Agent, Austin TX",
         principal_hint="Unresolved — registered-agent only"),
    Loan("FHMS-K095-0455", "Northgate Lofts", "College Station", "Brazos", "TX", 220,
         2015, 21_500_000, 19_800_000, 0.0331, date(2026, 9, 1), False,
         1_180_000, 1.18, 0.86,
         owner_entity="Northgate Lofts Owner LLC",
         owner_mailing="c/o Greystar, Charleston SC",
         principal_hint="Institutional-adjacent (Greystar-managed) — lower fit"),
    Loan("FHMS-K741-0310", "Villas at Traditions", "Bryan", "Brazos", "TX", 78,
         2019, 5_900_000, 5_650_000, 0.0448, date(2028, 4, 1), True,
         430_000, 1.34, 0.91,
         owner_entity="", owner_mailing="", principal_hint=""),

    # ── Augusta, GA (Richmond County) ──
    Loan("FHMS-K070-0129", "Riverwalk Augusta", "Augusta", "Richmond", "GA", 156,
         2016, 11_200_000, 10_400_000, 0.0356, date(2026, 12, 1), True,
         640_000, 1.22, 0.89,
         owner_entity="Riverwalk Augusta LLC",
         owner_mailing="3625 Walton Way Ext, Augusta GA",
         principal_hint="Local sponsor: J. Whitfield (deed + SOS match)"),
    Loan("FHMS-K733-0201", "Summerville Court", "Augusta", "Richmond", "GA", 88,
         2017, 5_800_000, 5_500_000, 0.0389, date(2027, 3, 1), True,
         395_000, 1.20, 0.84,
         owner_entity="Summerville Court GA LLC",
         owner_mailing="c/o Registered Agent, Atlanta GA",
         principal_hint="Unresolved — Atlanta registered agent"),
    Loan("FHMS-K088-0377", "Hill District Flats", "Augusta", "Richmond", "GA", 124,
         2015, 8_900_000, 8_150_000, 0.0342, date(2026, 10, 1), False,
         470_000, 1.15, 0.82,
         owner_entity="Hill District Flats LLC",
         owner_mailing="1450 Greene St, Augusta GA",
         principal_hint="Two-member LLC; both names on deed (workable lead)"),

    # ── Savannah, GA (Chatham County) ──
    Loan("FHMS-K072-0512", "Savannah Trellis", "Savannah", "Chatham", "GA", 168,
         2018, 13_400_000, 12_700_000, 0.0398, date(2027, 8, 1), True,
         850_000, 1.33, 0.92,
         owner_entity="Savannah Trellis Holdings LLC",
         owner_mailing="c/o CT Corporation, Atlanta GA",
         principal_hint="Registered-agent only — not yet resolved"),
    Loan("FHMS-K736-0164", "Tybee Gateway", "Savannah", "Chatham", "GA", 104,
         2016, 7_700_000, 7_150_000, 0.0361, date(2026, 12, 1), True,
         430_000, 1.16, 0.85,
         owner_entity="Tybee Gateway Apartments LLC",
         owner_mailing="112 W Congress St, Savannah GA",
         principal_hint="Local: M. Okafor (deed + business license match)"),
    Loan("FHMS-K099-0620", "Forsyth Row", "Savannah", "Chatham", "GA", 142,
         2015, 10_600_000, 9_650_000, 0.0327, date(2026, 8, 1), False,
         540_000, 1.12, 0.80,
         owner_entity="Forsyth Row Owner LLC",
         owner_mailing="c/o Registered Agent, Savannah GA",
         principal_hint="High stress; principal unresolved (priority to skip-trace)"),
    Loan("FHMS-K738-0245", "Landings Edge", "Savannah", "Chatham", "GA", 72,
         2019, 5_200_000, 5_000_000, 0.0459, date(2028, 7, 1), True,
         395_000, 1.38, 0.94,
         owner_entity="", owner_mailing="", principal_hint=""),

    # A couple of clean-refi loans (should score LOW — proves the screen discriminates)
    Loan("FHMS-K102-0733", "Perimeter Bend (control)", "Augusta", "Richmond", "GA", 110,
         2021, 9_100_000, 8_800_000, 0.0585, date(2029, 5, 1), True,
         720_000, 1.40, 0.95,
         owner_entity="", owner_mailing="", principal_hint=""),
]


def sample_loans():
    """Return the illustrative loan universe (a fresh list each call).

    Fills each loan's deal + source_url from its Freddie-style loan id, so the source-link
    column behaves the same in sample mode as it does on real MLPD data.
    """
    import dataclasses
    out = []
    for l in _LOANS:
        deal = "-".join(l.loan_id.split("-")[:2]) if "-" in l.loan_id else l.loan_id
        out.append(dataclasses.replace(
            l, deal=deal,
            source_url="https://mf.freddiemac.com/investors/performance-lookup",
        ))
    return out
