"""MLPD adapter tests, using a tiny synthetic file with the real MLPD column names."""

from datetime import date

import pytest

from maturity_radar.mlpd import load_mlpd
from maturity_radar.scoring import score_loan

pytest.importorskip("pandas")

CSV = """lnno,quarter,mrtg_status,amt_upb_endg,liq_dte,dt_fund,dt_mty,rate_int,rate_dcr,cnt_rsdntl_unit,cnt_blln_term,code_st,geographical_region,Dealname
501,y23q4,Current,9000000,,01MAR2016,01NOV2026,3.60,1.30,132,120,TX,College Station TX,FHMS-K068
501,y24q4,Current,8900000,,01MAR2016,01NOV2026,3.60,1.24,132,120,TX,College Station TX,FHMS-K068
502,y24q4,Current,5800000,,01JUN2017,01MAR2027,3.89,1.20,88,120,GA,Augusta GA,FHMS-K733
503,y24q4,Paid Off,7000000,01JAN2025,01JAN2015,01JAN2026,3.40,1.10,100,120,GA,Savannah GA,FHMS-K055
504,y24q4,Current,4000000,,01JAN2019,01JAN2028,4.50,1.35,0,120,TX,Bryan TX,FHMS-K741
"""


@pytest.fixture
def mlpd_file(tmp_path):
    p = tmp_path / "MLPD.csv"
    p.write_text(CSV)
    return str(p)


def test_takes_latest_quarter_per_loan(mlpd_file):
    loans = load_mlpd(mlpd_file)
    l501 = [l for l in loans if l.loan_id == "501"][0]
    assert l501.current_balance == 8_900_000   # y24q4, not y23q4's 9.0M
    assert l501.most_recent_dscr == pytest.approx(1.24)


def test_excludes_liquidated_and_zero_unit(mlpd_file):
    ids = {l.loan_id for l in load_mlpd(mlpd_file)}
    assert "503" not in ids     # paid off / has liq_dte
    assert "504" not in ids     # zero units


def test_state_filter(mlpd_file):
    tx = load_mlpd(mlpd_file, states={"TX"})
    assert {l.loan_id for l in tx} == {"501"}


def test_rate_normalized_and_date_parsed(mlpd_file):
    l = [x for x in load_mlpd(mlpd_file) if x.loan_id == "501"][0]
    assert l.note_rate == pytest.approx(0.036)      # 3.60 -> 0.036
    assert l.maturity == date(2026, 11, 1)


def test_source_url_present(mlpd_file):
    l = load_mlpd(mlpd_file)[0]
    assert l.source_url.startswith("https://mf.freddiemac.com")
    assert l.deal


def test_implied_noi_gives_rate_shock_signal(mlpd_file):
    """projected refi DSCR should reduce to in-place DSCR x note/market rate."""
    l = [x for x in load_mlpd(mlpd_file) if x.loan_id == "501"][0]
    s = score_loan(l, as_of=date(2026, 7, 24), market_rate=0.06)
    assert s.projected_refi_dscr == pytest.approx(1.24 * 0.036 / 0.06, abs=1e-3)  # ~0.744
    assert s.pressure_score > 80
