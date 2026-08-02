"""Maturity Radar — Streamlit dashboard for the refinance-pressure watchlist.

All figures come from the tested `maturity_radar` scoring engine. This file only filters and
presents; no financial logic lives here. Every data-sourced string is HTML-escaped before it
reaches the page.
"""

import html
from datetime import date

import pandas as pd  # noqa: F401  (kept for future export use)
import streamlit as st

from maturity_radar import DEFAULT_MARKET_RATE, DEFAULT_REFI_DSCR_FLOOR
from maturity_radar.data_sources import load_loans
from maturity_radar.rates import load_rate
from maturity_radar.watchlist import build_watchlist

st.set_page_config(page_title="Maturity Radar", page_icon="📡", layout="wide")


def esc(x):
    """Normalize and HTML-escape any value before it goes into the page markup.

    Unescape-then-escape so both already-encoded SEC XML text (`&amp;`) and plain strings render
    correctly and can never break the table or inject markup.
    """
    return html.escape(html.unescape(str(x)), quote=True)


# ── Design system ────────────────────────────────────────────────────────────
st.markdown("""
<style>
  :root{
    --navy:#1b3a5b; --navy2:#2f5680; --ink:#1a1d21; --soft:#5b6470; --faint:#949ba6;
    --line:#e9ecef; --line2:#f0f2f4; --paper:#f7f8fa; --panel:#ffffff;
    --hi:#c2412d; --hi-bg:#fbe9e6; --mid:#b07813; --mid-bg:#f7edd7; --lo:#1c7a5e; --lo-bg:#e4f1ec;
  }
  .stApp{background:var(--paper);}
  .block-container{padding-top:1.5rem; padding-bottom:3rem; max-width:1220px;}
  footer, header[data-testid="stHeader"]{visibility:hidden;}
  html, body, [class*="css"]{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,sans-serif; color:var(--ink);}

  /* top bar */
  .topbar{display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:4px;}
  .brand{display:flex; align-items:center; gap:11px;}
  .brand .mark{width:34px; height:34px; border-radius:9px; background:linear-gradient(135deg,var(--navy),var(--navy2));
    display:flex; align-items:center; justify-content:center; color:#fff; font-size:18px;}
  .brand .nm{font-size:20px; font-weight:750; color:var(--navy); letter-spacing:-.01em; line-height:1;}
  .brand .sb{font-size:11.5px; color:var(--faint); margin-top:2px;}
  .status{font-weight:700; padding:4px 12px; border-radius:100px; font-size:11.5px; white-space:nowrap;}
  .status.live{color:var(--lo); background:var(--lo-bg);}
  .status.samp{color:var(--mid); background:var(--mid-bg);}

  /* rate strip */
  .strip{display:flex; align-items:baseline; gap:9px; flex-wrap:wrap; background:var(--panel);
    border:1px solid var(--line); border-radius:11px; padding:12px 16px; margin:16px 0 4px;}
  .strip .big{font-size:22px; font-weight:800; color:var(--navy); font-variant-numeric:tabular-nums;}
  .strip .lab{font-size:13px; color:var(--ink); font-weight:600;}
  .strip .src{font-size:12px; color:var(--faint); margin-left:auto;}

  /* KPI cards */
  .kpis{display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:16px 0 6px;}
  .kpi{background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 17px;
    box-shadow:0 1px 3px rgba(20,25,35,.05);}
  .kpi .n{font-size:28px; font-weight:800; color:var(--ink); line-height:1; font-variant-numeric:tabular-nums;}
  .kpi .l{font-size:12px; color:var(--soft); margin-top:7px; line-height:1.35;}
  .kpi.hi{border-top:3px solid var(--hi);} .kpi.mid{border-top:3px solid var(--mid);}

  .insight{font-size:14px; color:var(--soft); margin:18px 0 6px; line-height:1.5;}
  .insight b{color:var(--ink);}
  .sect{display:flex; justify-content:space-between; align-items:center; margin:22px 0 10px;
    padding-bottom:8px; border-bottom:1px solid var(--line);}
  .sect .t{font-size:12px; letter-spacing:.13em; text-transform:uppercase; color:var(--faint); font-weight:700;}
  .legend{display:flex; gap:14px; font-size:11.5px; color:var(--soft);}
  .legend .dot{display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; vertical-align:middle;}

  /* watchlist table */
  .scrollx{overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--panel);}
  table.wl{width:100%; border-collapse:collapse; font-size:13.5px; min-width:920px;}
  table.wl thead th{text-align:left; font-size:10.5px; letter-spacing:.08em; text-transform:uppercase;
    color:var(--faint); font-weight:700; padding:12px 12px; background:var(--line2); border-bottom:1px solid var(--line);}
  table.wl thead th.r, table.wl td.r{text-align:right; font-variant-numeric:tabular-nums;}
  table.wl tbody td{padding:11px 12px; border-bottom:1px solid var(--line2); color:var(--ink); vertical-align:middle;}
  table.wl tbody tr:last-child td{border-bottom:none;}
  table.wl tbody tr:hover{background:#fafbfc;}
  .prop{font-weight:650;} .mkt{color:var(--soft); font-size:12.5px;}
  .scorewrap{display:flex; align-items:center; gap:10px;}
  .track{flex:1; height:7px; border-radius:4px; background:var(--line); min-width:60px; overflow:hidden;}
  .fill{height:100%; border-radius:4px; background:linear-gradient(90deg,var(--navy2),var(--navy));}
  .scoreval{font-weight:750; font-variant-numeric:tabular-nums; min-width:26px; text-align:right;}
  .pill{display:inline-block; font-size:11px; font-weight:700; padding:3px 10px; border-radius:100px; white-space:nowrap;}
  .pill.hi{color:var(--hi); background:var(--hi-bg);} .pill.mid{color:var(--mid); background:var(--mid-bg);}
  .pill.lo{color:var(--lo); background:var(--lo-bg);}
  .ptype{font-size:11px; font-weight:650; color:var(--soft); background:var(--line2); padding:3px 9px; border-radius:100px;}
  .src a{color:var(--navy2); font-size:12px; text-decoration:none; font-weight:600;}
  .src a:hover{text-decoration:underline;}

  .foot{color:var(--faint); font-size:11.5px; margin-top:20px; padding-top:14px; border-top:1px solid var(--line); line-height:1.6;}
  .prepared{font-size:11.5px; color:var(--faint);}

  /* about */
  .about h3{font-size:13px; letter-spacing:.1em; text-transform:uppercase; color:var(--navy); margin:24px 0 8px; font-weight:750;}
  .about p{font-size:14.5px; color:var(--ink); line-height:1.7; max-width:78ch; margin:0 0 13px;}
  .about b{color:var(--ink); font-weight:700;}
  .about code{background:var(--line2); padding:2px 7px; border-radius:5px; font-size:13px; color:var(--navy2);}
  .about .lead{font-size:16px; color:var(--soft);}

  section[data-testid="stSidebar"]{background:var(--panel); border-right:1px solid var(--line);}
  section[data-testid="stSidebar"] .block-container{padding-top:1.7rem;}
  div[data-baseweb="tab-list"]{gap:6px; border-bottom:1px solid var(--line);}
  button[data-baseweb="tab"]{font-weight:650; font-size:14px;}
  @media(max-width:820px){.kpis{grid-template-columns:repeat(2,1fr);}}
</style>
""", unsafe_allow_html=True)

# ── Data + live rate ─────────────────────────────────────────────────────────
_all, SRC = load_loans("auto")
_rate = load_rate()
market_rate = float(_rate["rate"]) if _rate else DEFAULT_MARKET_RATE

# Map full state names to state codes for the 8-state filter
_state_map = {
    "Alabama": "AL",
    "Florida": "FL",
    "Georgia": "GA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "North Carolina": "NC",
    "Texas": "TX",
}
_all_states = sorted(_state_map.keys())

# ── Controls ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("### Filters")
selected_state_names = st.sidebar.multiselect("Markets (state)", _all_states, default=_all_states)
states = [_state_map[name] for name in selected_state_names]
angles = st.sidebar.multiselect("Refinance pressure", ["Severe", "Moderate", "Borderline"],
                                default=["Severe", "Moderate", "Borderline"])
min_score = st.sidebar.slider("Minimum pressure score", 0, 100, 0, 5)

floor = DEFAULT_REFI_DSCR_FLOOR   # fixed 1.25x lender DSCR requirement (used for banding + scoring)


def band(s):
    if s.projected_refi_dscr < 1.0:
        return "hi", "Severe"
    if s.projected_refi_dscr < floor - 0.10:
        return "mid", "Moderate"
    return "lo", "Borderline"   # within 0.10x of the floor — genuinely marginal


def market_label(s):
    city = esc(s.loan.city) if s.loan.city and s.loan.city != "(multiple)" else "Multiple properties"
    return f"{city}, {esc(s.loan.state)}" if s.loan.state else city


# An empty selection means "show nothing" (respect the user's clear), not "show everything".
_sel = set(states)
_angles = set(angles)
wl = []
if states and angles:
    wl = build_watchlist(_all, states=_sel, market_rate=market_rate, floor=floor, min_score=min_score)
    wl = [s for s in wl if band(s)[1] in _angles]

# ── Top bar ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="topbar">
  <div class="brand">
    <div class="mark">📡</div>
    <div class="nm">Maturity Radar</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Live refinance-rate strip ────────────────────────────────────────────────
_asof = date.today().strftime("%b %d, %Y")
if _rate:
    _src = (f'{_rate["ten_year"]*100:.2f}% 10-yr UST + {int(_rate["spread"]*10000)} bps agency spread '
            f'· FRED {esc(_rate["as_of"])} · analysis as of {esc(_asof)}')
else:
    _src = f"benchmark assumption · analysis as of {esc(_asof)}"
st.markdown(f"""
<div class="strip">
  <span class="big">{market_rate*100:.2f}%</span>
  <span class="lab">today's multifamily refinance rate</span>
  <span class="src">{_src}</span>
</div>
""", unsafe_allow_html=True)

tab_watch, tab_about = st.tabs(["Watchlist", "About"])

# ── WATCHLIST TAB ────────────────────────────────────────────────────────────
with tab_watch:
    if not states or not angles:
        st.info("Select at least one market and one pressure band in the sidebar to see loans.")
    elif not wl:
        st.info("No loans match the current filters. Widen the markets, pressure bands, or lower "
                "the minimum score in the sidebar.")
    else:
        severe = [s for s in wl if s.projected_refi_dscr < 1.0]
        near = [s for s in wl if s.months_to_maturity <= 24]
        upb = sum(s.loan.current_balance for s in wl)
        n_states = len({s.loan.state for s in wl})

        st.markdown(f"""
<div class="kpis">
  <div class="kpi"><div class="n">{len(wl)}</div><div class="l">Loans on watch · {n_states} state{'s' if n_states != 1 else ''}</div></div>
  <div class="kpi hi"><div class="n">{len(severe)}</div><div class="l">Severe — can't cover new debt at {market_rate*100:.2f}%</div></div>
  <div class="kpi mid"><div class="n">{len(near)}</div><div class="l">Maturing within 24 months</div></div>
  <div class="kpi"><div class="n">${upb/1e6:,.0f}M</div><div class="l">Total loan balance on watch</div></div>
</div>
""", unsafe_allow_html=True)

        st.markdown(
            f'<div class="insight"><b>{len(wl)}</b> multifamily loans across <b>{n_states}</b> '
            f'state{"s" if n_states != 1 else ""}, ranked by refinance pressure at today\'s '
            f'<b>{market_rate*100:.2f}%</b> rate — the highest-pressure, earliest conversations first.</div>',
            unsafe_allow_html=True)

        st.markdown("""
<div class="sect">
  <span class="t">Watchlist · ranked by refinance pressure</span>
  <span class="legend">
    <span><span class="dot" style="background:#c2412d"></span>Severe</span>
    <span><span class="dot" style="background:#b07813"></span>Moderate</span>
    <span><span class="dot" style="background:#1c7a5e"></span>Borderline</span>
  </span>
</div>
""", unsafe_allow_html=True)

        # Build filterable DataFrame
        data = []
        for s in wl:
            l = s.loan
            cls, label = band(s)
            data.append({
                'Pressure': s.pressure_score,
                'Property': l.property_name,
                'Market': market_label(s),
                'State': l.state,
                'Type': l.program or '—',
                'Units': l.units or 0,
                'Maturity': l.maturity.strftime("%b %Y"),
                'Note Rate': f"{l.note_rate*100:.1f}%",
                'Refi DSCR': f"{s.projected_refi_dscr:.2f}×",
                'Band': label,
                'Source': l.deal or 'SEC filing',
                'URL': l.source_url,
            })
        df = pd.DataFrame(data)

        # Filter controls
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            min_pressure = st.slider("Min Pressure", 0, 100, value=0, step=5)
        with col2:
            selected_states = st.multiselect("State", sorted(df['State'].unique()), default=sorted(df['State'].unique()))
        with col3:
            selected_bands = st.multiselect("Band", ['Severe', 'Moderate', 'Borderline'], default=['Severe', 'Moderate', 'Borderline'])
        with col4:
            prop_search = st.text_input("Property search", "")

        # Apply filters
        df_filtered = df[
            (df['Pressure'] >= min_pressure) &
            (df['State'].isin(selected_states)) &
            (df['Band'].isin(selected_bands))
        ]
        if prop_search:
            df_filtered = df_filtered[df_filtered['Property'].str.contains(prop_search, case=False, na=False)]

        # Display sortable/filterable table
        st.dataframe(
            df_filtered[['Pressure', 'Property', 'Market', 'Type', 'Units', 'Maturity', 'Note Rate', 'Refi DSCR', 'Band', 'Source']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'Pressure': st.column_config.NumberColumn(format='%d'),
                'Units': st.column_config.NumberColumn(format='%d'),
            }
        )

        # Show expandable details for top 20 pressure loans
        st.markdown("### Loan Details", help="Click to expand individual loan details")
        top_loans = sorted(wl, key=lambda s: s.pressure_score, reverse=True)[:20]
        for i, s in enumerate(top_loans):
            with st.expander(f"🔍 {esc(s.loan.property_name)} — {esc(s.loan.city)}, {s.loan.state} | Score: {s.pressure_score}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Property:** {esc(s.loan.property_name)}")
                    st.write(f"**Location:** {esc(s.loan.city)}, {s.loan.state}")
                    st.write(f"**Units:** {s.loan.units:,}")
                    st.write(f"**Type:** {esc(s.loan.program or 'Agency')}")
                    st.write(f"**Note Rate:** {s.loan.note_rate:.2%}")
                with col2:
                    st.write(f"**Maturity:** {s.loan.maturity}")
                    st.write(f"**Current Balance:** ${s.loan.current_balance:,.0f}")
                    st.write(f"**Original Balance:** ${s.loan.original_balance:,.0f}")
                    st.write(f"**Projected Refi DSCR:** {s.projected_refi_dscr:.2f}×")
                    st.write(f"**Pressure Score:** {s.pressure_score:.0f}")
                st.write("---")
                st.write(f"**Source:** {esc(s.loan.deal or 'SEC filing')}")
                if s.loan.source_url:
                    st.write(f"[View SEC Filing]({s.loan.source_url})")

        st.markdown("""
<div class="foot">
Refinance DSCR is the projected coverage if the loan were refinanced today at its current balance
and the rate above. Pressure score (0–100) weights maturity proximity, rate shock, and that DSCR
stress. Figures from the tested scoring engine; coverage is securitized conduit CMBS, multifamily
only. <span class="prepared">Prepared for Lexerd Capital Management.</span>
</div>
""", unsafe_allow_html=True)

# ── ABOUT TAB ────────────────────────────────────────────────────────────────
with tab_about:
    st.markdown(f"""
<div class="about">
<p class="lead"><b>Maturity Radar</b> surfaces the multifamily owners worth a conversation before
their loan matures — ranked by how hard that loan will be to refinance at today's rate.</p>

<h3>What it does</h3>
<p>It scans securitized multifamily loans across the US and scores each by <b>refinance pressure</b>
against the 2026–28 debt-maturity wall. The output is a cultivation and negotiating-leverage queue:
who to build a relationship with, when, and the credit reason why — <b>not</b> a motivated-seller
list. In today's market the usual outcome is extend / modify / recap, so the value is timing the
conversation 12+ months ahead of a forcing event, where the entry may be a purchase or rescue equity.</p>

<h3>The signal</h3>
<p>The core metric is the <b>projected refinance DSCR</b> — <code>NOI ÷ (loan balance × today's
rate)</code>. A loan covering comfortably at 3.5% can be un-refinanceable at {market_rate*100:.2f}%;
the equity paydown needed to clear a lender's DSCR floor is what times the outreach. Each loan gets a
0–100 pressure score from three drivers: maturity proximity, rate shock, and that DSCR stress.</p>

<h3>The data</h3>
<p>Wired to real <b>SEC EDGAR CMBS loan-level disclosure</b> (Reg AB II, Form ABS-EE, Exhibit 102),
filtered to multifamily properties nationwide — every loan links to its exact SEC filing. Today's
refinance rate is live: the current 10-year Treasury (FRED) plus an agency multifamily spread.
Coverage is <b>conduit CMBS</b> for now; <b>agency</b> (Freddie/Fannie) is the next data source to add.</p>

<h3>Honest limits</h3>
<p>Coverage is securitized loans only — community-bank paper is invisible. Refinance pressure is
neither a willing seller nor value-add upside (it can be <i>anti-correlated</i> with a value-add buy
box). And the owner last mile — LLC to a reachable principal — is a separate, human-in-the-loop step.
Naming what the tool can and can't see is the point: it's a prioritized, credit-justified queue, not
a black box.</p>
</div>
""", unsafe_allow_html=True)
