"""
Lexerd Deal Engine - Streamlit Dashboard

Unified scoring & opportunity identification for multifamily acquisitions.

Features:
- Properties: Upload & score from CSV
- Opportunities: Top deals ranked by risk tier (SEC + B3 integration)
- Analytics: Score distribution, risk breakdown
- Settings: API configuration (no tunable weights - fixed thesis)
"""

import streamlit as st
import pandas as pd
from io import StringIO, BytesIO
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

# Add workspace to path so calibration package is importable
workspace_dir = str(Path(__file__).parent.parent.parent)
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from calibration.models import FinalScorer, ThesisConfig, PropertyProfile
from calibration.data.loan_deduplication import match_sec_to_b3_loans
from calibration.data.sec_alert_system import SecAlertSystem
from calibration.data.alert_system import AlertSystem

# ============================================================================
# SESSION STATE & CONFIG
# ============================================================================

def init_session_state():
    """Initialize session state with default values."""
    if 'thesis' not in st.session_state:
        # Hardcoded thesis with fixed weights (not tunable)
        st.session_state.thesis = ThesisConfig(
            market_weight=0.30,
            model_weight=0.40,
            management_weight=0.30,
        )
    if 'scored_results' not in st.session_state:
        st.session_state.scored_results = None
    if 'last_update' not in st.session_state:
        st.session_state.last_update = datetime.now().isoformat()


def apply_custom_css():
    """Apply professional SaaS styling to the dashboard."""
    st.markdown("""
    <style>
    /* Root and overall styling - Modern SaaS Palette */
    :root {
        --primary-color: #0066cc;
        --primary-light: #3b82f6;
        --secondary-light: #f8fafc;
        --secondary-gray: #e2e8f0;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --danger-color: #ef4444;
        --text-primary: #1f2937;
        --text-secondary: #6b7280;
        --border-light: #e5e7eb;
    }

    /* Main container */
    .main {
        padding: 1rem 2rem 2rem 2rem;
        background-color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    /* Header styling - Clean, minimal hierarchy */
    h1 {
        color: var(--text-primary);
        font-size: 2.25rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.5px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    h2 {
        color: var(--text-primary);
        font-size: 1.5rem;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-light);
        padding-bottom: 0.75rem;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    h3 {
        color: var(--text-primary);
        font-size: 1.125rem;
        font-weight: 600;
        margin-top: 1.25rem;
        margin-bottom: 0.5rem;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* Metric cards - Subtle, professional */
    [data-testid="metric-container"] {
        background: #ffffff;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid var(--border-light);
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    }

    [data-testid="metric-container"]:hover {
        box-shadow: 0 4px 6px rgba(0,0,0,0.07);
        border-color: var(--primary-light);
    }

    /* Opportunity card styling - Tier-based borders */
    .opp-card {
        background: white;
        border: 2px solid var(--border-light);
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.06);
        transition: all 0.2s ease;
    }

    .opp-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }

    .opp-card.tier-1 {
        border-top: 5px solid #ef4444;
        border-color: #ef4444;
    }

    .opp-card.tier-2 {
        border-top: 5px solid #f59e0b;
        border-color: #f59e0b;
    }

    .opp-card.tier-3 {
        border-top: 5px solid #eab308;
        border-color: #eab308;
    }

    /* Scrollable container for opportunities */
    .scroll-container {
        max-height: 100%;
        overflow-y: auto;
        padding-right: 0.5rem;
    }

    .scroll-container::-webkit-scrollbar {
        width: 8px;
    }

    .scroll-container::-webkit-scrollbar-track {
        background: #f3f4f6;
        border-radius: 10px;
    }

    .scroll-container::-webkit-scrollbar-thumb {
        background: #d1d5db;
        border-radius: 10px;
    }

    .scroll-container::-webkit-scrollbar-thumb:hover {
        background: #9ca3af;
    }

    /* Tier coloring - Refined */
    .tier-1 { color: var(--danger-color); font-weight: 700; }
    .tier-2 { color: var(--warning-color); font-weight: 700; }
    .tier-3 { color: var(--success-color); font-weight: 700; }

    /* Grade badges - Professional colors */
    .grade-a { background-color: var(--success-color); color: white; padding: 0.5rem 0.875rem; border-radius: 6px; font-weight: 600; font-size: 0.95rem; }
    .grade-b { background-color: var(--warning-color); color: white; padding: 0.5rem 0.875rem; border-radius: 6px; font-weight: 600; font-size: 0.95rem; }
    .grade-c { background-color: #f97316; color: white; padding: 0.5rem 0.875rem; border-radius: 6px; font-weight: 600; font-size: 0.95rem; }
    .grade-d { background-color: var(--danger-color); color: white; padding: 0.5rem 0.875rem; border-radius: 6px; font-weight: 600; font-size: 0.95rem; }

    /* Data freshness - Subtle accent */
    .data-freshness {
        background: #f0fdf4;
        padding: 1rem;
        border-radius: 8px;
        font-size: 0.9rem;
        color: var(--text-primary);
        border-left: 4px solid var(--success-color);
    }

    /* Info box styling - Clean */
    .stInfo {
        background-color: #eff6ff;
        border-left: 4px solid var(--primary-light);
        border-radius: 6px;
    }

    .stWarning {
        background-color: #fefce8;
        border-left: 4px solid var(--warning-color);
        border-radius: 6px;
    }

    .stSuccess {
        background-color: #f0fdf4;
        border-left: 4px solid var(--success-color);
        border-radius: 6px;
    }

    .stError {
        background-color: #fef2f2;
        border-left: 4px solid var(--danger-color);
        border-radius: 6px;
    }

    /* Tab styling - Modern, subtle */
    [data-baseweb="tab-list"] button {
        font-weight: 500;
        color: var(--text-secondary);
        font-size: 0.95rem;
        border-bottom: 2px solid transparent;
        transition: all 0.2s ease;
    }

    [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: var(--primary-color);
        border-bottom: 2px solid var(--primary-color);
    }

    /* Button styling - Modern, minimal */
    .stButton > button {
        background-color: var(--primary-color);
        color: white;
        font-weight: 500;
        font-size: 0.95rem;
        border-radius: 6px;
        padding: 0.5rem 1.25rem;
        border: none;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background-color: #0052a3;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Download button */
    .stDownloadButton > button {
        background-color: var(--success-color);
        color: white;
        font-weight: 500;
        font-size: 0.95rem;
        border-radius: 6px;
        padding: 0.5rem 1.25rem;
        border: none;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    }

    .stDownloadButton > button:hover {
        background-color: #059669;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Dataframe styling - Clean, professional */
    [data-testid="stDataFrame"] {
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid var(--border-light);
    }

    /* Footer styling - Minimal */
    .footer {
        color: var(--text-secondary);
        font-size: 0.875rem;
        border-top: 1px solid var(--border-light);
        padding-top: 1.5rem;
        margin-top: 3rem;
    }

    /* Text styling - Professional hierarchy */
    p, span {
        color: var(--text-secondary);
        line-height: 1.6;
        font-size: 0.95rem;
    }

    strong {
        color: var(--text-primary);
        font-weight: 600;
    }

    /* Divider - Subtle */
    hr {
        border: none;
        border-top: 1px solid var(--border-light);
        margin: 1.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)


# ============================================================================
# DATA LOADING & INTEGRATION
# ============================================================================



def load_uploaded_csv(uploaded_file) -> Optional[pd.DataFrame]:
    """Load and validate CSV upload."""
    try:
        df = pd.read_csv(uploaded_file)
        required_cols = ['property_id', 'property_name', 'city', 'state', 'units',
                        'property_class', 'year_built', 'occupancy',
                        'avg_rent_per_unit', 'market_rent_per_unit',
                        'expense_ratio', 'market_expense_ratio']

        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            st.error(f"Missing columns: {', '.join(missing_cols)}")
            return None

        return df
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return None


def unify_loan_data(b3_df: pd.DataFrame, sec_df: pd.DataFrame) -> pd.DataFrame:
    """Unify B3 and SEC loan data with deduplication."""
    try:
        # Match and dedupe
        unified = match_sec_to_b3_loans(sec_df, b3_df)

        # Add source column for display
        if 'loan_source' not in unified.columns:
            unified['loan_source'] = 'Unknown'

        logger.info(f"Unified {len(unified)} loans from B3 + SEC")
        return unified
    except Exception as e:
        logger.error(f"Error unifying loan data: {e}")
        return pd.concat([b3_df, sec_df], ignore_index=True)


# ============================================================================
# SCORING & RANKING
# ============================================================================

def score_property_profile(prop: PropertyProfile, thesis: ThesisConfig):
    """Score a single property and return result."""
    try:
        scorer = FinalScorer()
        result = scorer.score(prop, thesis)
        return result
    except Exception as e:
        logger.error(f"Error scoring property {prop.property_id}: {e}")
        return None


def score_batch_properties(df: pd.DataFrame, thesis: ThesisConfig) -> pd.DataFrame:
    """Score multiple properties from CSV."""
    scorer = FinalScorer()
    results = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, row in df.iterrows():
        status_text.text(f"Scoring {idx + 1}/{len(df)}...")

        # Parse employment anchors
        anchors = []
        if 'employment_anchors' in row and pd.notna(row['employment_anchors']):
            anchors = [a.strip() for a in str(row['employment_anchors']).split(',')]

        try:
            prop = PropertyProfile(
                property_id=str(row['property_id']),
                property_name=str(row['property_name']),
                address=row.get('address', ''),
                city=str(row['city']),
                state=str(row['state']),
                units=int(row['units']),
                property_class=str(row['property_class']),
                year_built=int(row['year_built']),
                occupancy=float(row['occupancy']),
                avg_rent_per_unit=float(row['avg_rent_per_unit']),
                market_rent_per_unit=float(row.get('market_rent_per_unit', row['avg_rent_per_unit'])),
                expense_ratio=float(row['expense_ratio']),
                market_expense_ratio=float(row['market_expense_ratio']),
                employment_anchors=anchors,
                employment_growth_yoy=float(row.get('employment_growth_yoy', 0)),
                population_growth_yoy=float(row.get('population_growth_yoy', 0)),
                market_cap_rate=float(row.get('market_cap_rate', 0.08)),
                management_type=row.get('management_type', 'Third-party'),
            )

            result = scorer.score(prop, thesis)
            results.append({
                'Property ID': prop.property_id,
                'Property Name': prop.property_name,
                'City': prop.city,
                'Units': prop.units,
                'Class': prop.property_class,
                'Market Score': f"{result.market_score:.0f}",
                'Model Score': f"{result.model_score:.0f}",
                'Management Score': f"{result.management_score:.0f}",
                'Final Fit Score': f"{result.final_fit_score:.0f}",
                'Grade': result.confidence_grade.value,
                'Rationale': result.fit_rationale[:100] + '...' if len(result.fit_rationale) > 100 else result.fit_rationale,
            })
        except Exception as e:
            logger.error(f"Error scoring row {idx}: {e}")
            continue

        progress_bar.progress((idx + 1) / len(df))

    status_text.empty()

    if results:
        results_df = pd.DataFrame(results)
        # Sort by fit score (numeric)
        results_df['Final Fit Score (numeric)'] = results_df['Final Fit Score'].astype(float)
        results_df = results_df.sort_values('Final Fit Score (numeric)', ascending=False)
        results_df = results_df.drop('Final Fit Score (numeric)', axis=1)
        return results_df

    return pd.DataFrame()


def rank_opportunities(unified_loans: pd.DataFrame, top_n: int = 100) -> pd.DataFrame:
    """Rank loans by opportunity tier."""
    try:
        alert_system = AlertSystem()
        loans_list = unified_loans.to_dict('records')
        ranked = alert_system.rank_by_opportunity(loans_list)

        # Create source lookup map
        source_map = dict(zip(unified_loans['loan_id'], unified_loans.get('loan_source', 'Unknown')))

        # Convert to DataFrame
        ranked_data = []
        for opp in ranked[:top_n]:
            source = source_map.get(opp.loan_id, 'Unknown')
            ranked_data.append({
                'Rank': opp.rank,
                'Loan ID': opp.loan_id,
                'Address': opp.property_address,
                'Units': opp.units,
                'Class': opp.property_class,
                'Opportunity Score': f"{opp.opportunity_score:.1f}",
                'Risk Tier': f"Tier {opp.risk_tier}",
                'DSCR': f"{opp.dscr:.2f}",
                'LTV': f"{opp.ltv*100:.0f}%",
                'Months to Maturity': int(opp.months_to_maturity),
                'Source': source,
            })

        return pd.DataFrame(ranked_data)
    except Exception as e:
        logger.error(f"Error ranking opportunities: {e}")
        st.error(f"Error ranking opportunities: {str(e)}")
        return pd.DataFrame()


# ============================================================================
# UI COMPONENTS - PROPERTY CARDS
# ============================================================================

def render_property_card(prop_data: dict):
    """Render a modern professional property card with metrics and scores."""
    st.markdown(f"""
    <div style="
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    ">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem;">
            <div style="flex: 1;">
                <h3 style="margin: 0 0 0.35rem 0; color: #1f2937; font-size: 1.2rem; font-weight: 600;">
                    {prop_data['Property Name']}
                </h3>
                <p style="margin: 0; color: #6b7280; font-size: 0.9rem;">
                    {prop_data['City']}, {prop_data['State']} • {prop_data['Units']} units • Class {prop_data['Class']}
                </p>
            </div>
            <div style="
                background: #0066cc;
                color: white;
                padding: 1rem 1.25rem;
                border-radius: 8px;
                text-align: center;
                min-width: 110px;
                box-shadow: 0 1px 3px rgba(0,102,204,0.2);
            ">
                <div style="font-size: 1.75rem; font-weight: 700; line-height: 1;">
                    {prop_data['Final Fit Score']}
                </div>
                <div style="font-size: 0.75rem; font-weight: 600; opacity: 0.95; margin-top: 0.35rem; letter-spacing: 0.5px;">
                    FIT SCORE
                </div>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.25rem;">
            <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e5e7eb;">
                <div style="color: #6b7280; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">
                    Market Score
                </div>
                <div style="color: #1f2937; font-size: 1.5rem; font-weight: 700;">
                    {prop_data['Market Score']}
                </div>
            </div>
            <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e5e7eb;">
                <div style="color: #6b7280; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">
                    Model Score
                </div>
                <div style="color: #1f2937; font-size: 1.5rem; font-weight: 700;">
                    {prop_data['Model Score']}
                </div>
            </div>
            <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e5e7eb;">
                <div style="color: #6b7280; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">
                    Management Score
                </div>
                <div style="color: #1f2937; font-size: 1.5rem; font-weight: 700;">
                    {prop_data['Management Score']}
                </div>
            </div>
            <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e5e7eb;">
                <div style="color: #6b7280; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">
                    Grade
                </div>
                <div style="
                    display: inline-block;
                    background: {'#10b981' if prop_data['Grade'] == 'A' else '#f59e0b' if prop_data['Grade'] == 'B' else '#f97316' if prop_data['Grade'] == 'C' else '#ef4444'};
                    color: white;
                    padding: 0.5rem 0.75rem;
                    border-radius: 6px;
                    font-weight: 700;
                    font-size: 1.1rem;
                    box-shadow: 0 1px 2px rgba(0,0,0,0.1);
                ">
                    {prop_data['Grade']}
                </div>
            </div>
        </div>

        <div style="
            background: #eff6ff;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #3b82f6;
            color: #1f2937;
            font-size: 0.9rem;
            line-height: 1.6;
        ">
            <strong style="color: #1f2937;">Fit Rationale:</strong> {prop_data['Rationale']}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# UI COMPONENTS - PROPERTIES TAB
# ============================================================================

def render_properties_tab():
    """Render Properties tab - upload and score."""
    st.markdown("## Properties")
    st.markdown("Upload a CSV file with property data to score against the 3M thesis (Market, Model, Management).")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Upload Property CSV",
            type="csv",
            help="CSV should include: property_id, property_name, city, state, units, property_class, year_built, occupancy, avg_rent_per_unit, market_rent_per_unit, expense_ratio, market_expense_ratio"
        )

    with col2:
        st.markdown("**Sample CSV Template**")
        sample_csv = """property_id,property_name,city,state,units,property_class,year_built,occupancy,avg_rent_per_unit,market_rent_per_unit,expense_ratio,market_expense_ratio
001,San Marco Village,Jacksonville,FL,180,B,2005,0.85,1200,1300,0.32,0.27"""
        st.download_button(
            label="Download Template",
            data=sample_csv,
            file_name="property_template.csv",
            mime="text/csv"
        )

    # Show empty state if no file uploaded
    if uploaded_file is None:
        st.info("""
        **Upload a CSV to get started**

        1. Prepare your property data in CSV format
        2. Download the template above for reference
        3. Upload your file to score properties
        4. View detailed scoring, download results, and explore analytics
        """)
        return

    # File uploaded - process it
    df = load_uploaded_csv(uploaded_file)
    if df is not None:
        st.markdown(f"**Loaded {len(df)} properties**")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Score All Properties", key="score_all"):
                with st.spinner("Scoring properties..."):
                    results_df = score_batch_properties(df, st.session_state.thesis)
                    st.session_state.scored_results = results_df
                    st.session_state.last_update = datetime.now().isoformat()

        with col2:
            st.markdown("")  # Spacing

        if st.session_state.scored_results is not None and not st.session_state.scored_results.empty:
            st.markdown("### Scored Properties")

            # Download buttons
            col1, col2, col3 = st.columns(3)

            with col1:
                csv_buffer = StringIO()
                st.session_state.scored_results.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_buffer.getvalue(),
                    file_name="lexerd_scored_properties.csv",
                    mime="text/csv"
                )

            with col2:
                # Excel export (with fallback if openpyxl not available)
                try:
                    excel_buffer = BytesIO()
                    st.session_state.scored_results.to_excel(excel_buffer, index=False, engine='openpyxl')
                    excel_data = excel_buffer.getvalue()
                    st.download_button(
                        label="Download Excel",
                        data=excel_data,
                        file_name="lexerd_scored_properties.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception:
                    st.info("(Excel export requires openpyxl - use CSV instead)")

            with col3:
                # JSON export
                json_str = st.session_state.scored_results.to_json(orient='records', indent=2)
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name="lexerd_scored_properties.json",
                    mime="application/json"
                )

            # Data quality metrics
            st.markdown("### Data Quality")
            quality_col1, quality_col2, quality_col3 = st.columns(3)
            with quality_col1:
                st.metric("Properties Scored", len(st.session_state.scored_results))
            with quality_col2:
                grade_counts = st.session_state.scored_results['Grade'].value_counts()
                st.metric("A-Grade Properties", grade_counts.get('A', 0))
            with quality_col3:
                st.metric("Last Updated", datetime.fromisoformat(st.session_state.last_update).strftime('%H:%M:%S'))

            # Display property cards
            st.markdown("---")
            st.markdown("### Property Details")
            for idx, row in st.session_state.scored_results.iterrows():
                render_property_card(row.to_dict())
        else:
            st.info("Click 'Score All Properties' above to generate scores and view detailed property cards.")


# ============================================================================
# UI COMPONENTS - OPPORTUNITIES CARD
# ============================================================================

def render_opportunity_card(opp_data: dict):
    """Render a compact, professional opportunity card using Streamlit components."""

    tier = opp_data.get('risk_tier', 3)
    tier_colors = {1: '#ef4444', 2: '#f59e0b', 3: '#eab308'}
    tier_labels = {1: 'Critical', 2: 'High', 3: 'Monitor'}

    prop_name = opp_data.get('property_name', 'Property')
    city = opp_data.get('city', '')
    state = opp_data.get('state', '')
    dscr = opp_data.get('dscr', 0)
    ltv = opp_data.get('current_ltv', 0)
    maturity_date = opp_data.get('maturity_date', 'N/A')
    months = opp_data.get('months_to_maturity', 0)
    loan_id = opp_data.get('loan_id', 'N/A')
    source_url = opp_data.get('source_url', None)

    with st.container(border=True):
        st.write(f"**{prop_name}**")
        st.caption(f"📍 {city}, {state}")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("DSCR", f"{dscr:.2f}x" if pd.notna(dscr) else "N/A")
        with col2:
            st.metric("LTV", f"{ltv*100:.0f}%" if pd.notna(ltv) else "N/A")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Maturity", maturity_date)
        with col2:
            st.metric("Months", f"{int(months)}m" if pd.notna(months) else "N/A")

        st.caption(f"**ID:** {loan_id}")

        if source_url:
            st.link_button("📄 View Filing", source_url, use_container_width=True)


# ============================================================================
# UI COMPONENTS - OPPORTUNITIES TAB
# ============================================================================

def render_opportunities_tab():
    """Render Opportunities tab - auto-populated from Freddie Mac and SEC CMBS sources."""
    from calibration.opportunities import load_opportunities, get_data_freshness, get_tier_breakdown

    st.markdown("## Opportunities")
    st.markdown("Auto-populated top deals ranked by risk tier, combining Freddie Mac Multifamily and SEC CMBS data.")

    try:
        # Load opportunities
        with st.spinner("Loading opportunities..."):
            opportunities = load_opportunities(top_n=100)
            freshness = get_data_freshness()
            tier_breakdown = get_tier_breakdown()

        # Show data source status header
        st.markdown("### Data Source Status & Summary")

        # Status indicators
        status_col1, status_col2, status_col3, status_col4 = st.columns(4)

        fm_status = "🟢 Connected" if not opportunities.empty and 'loan_source' in opportunities.columns and any(opportunities['loan_source'] == 'Freddie Mac') else "🔴 Awaiting"
        sec_status = "🟢 Connected" if not opportunities.empty and 'loan_source' in opportunities.columns and any(opportunities['loan_source'] == 'SEC-CMBS') else "🔴 Awaiting"

        with status_col1:
            st.metric("Freddie Mac", fm_status, help="Multifamily Loan Database")

        with status_col2:
            st.metric("SEC CMBS", sec_status, help="CMBS 424B5 prospectuses")

        with status_col3:
            st.metric(
                "Total Opportunities",
                len(opportunities),
                help="Real deals loaded from data sources"
            )

        with status_col4:
            st.metric(
                "Last Updated",
                freshness.get('freddie_mac', 'Awaiting')[:10] if freshness.get('freddie_mac') != 'Awaiting' else 'Awaiting',
                help="Data freshness"
            )

        # Show awaiting message if no opportunities loaded yet
        if opportunities.empty:
            st.info("No opportunities available. Data connections will be configured to automatically populate this tab.")
        else:
            # Show tier breakdown
            st.markdown("### Tier Breakdown")
            tier_col1, tier_col2, tier_col3 = st.columns(3)

            with tier_col1:
                st.metric(
                    "Tier 1 (Critical)",
                    tier_breakdown.get(1, 0),
                    help="Immediate refinance pressure (< 6 months to maturity)"
                )

            with tier_col2:
                st.metric(
                    "Tier 2 (High)",
                    tier_breakdown.get(2, 0),
                    help="Near-term refinance risk (6-24 months to maturity)"
                )

            with tier_col3:
                st.metric(
                    "Tier 3 (Monitor)",
                    tier_breakdown.get(3, 0),
                    help="Future opportunities to monitor (24+ months to maturity)"
                )

        # Show opportunities cards with 4-column grid layout
        if not opportunities.empty:
            st.markdown("---")
            st.markdown("### Filters")

            # State filter dropdown
            available_states = ["Alabama", "Florida", "Georgia", "Kansas", "Kentucky", "Louisiana", "North Carolina", "Texas"]
            selected_states = st.multiselect(
                "State",
                options=available_states,
                default=available_states,
                key="state_filter"
            )

            # Filter opportunities by selected states
            filtered_opportunities = opportunities[opportunities['state'].isin(selected_states)]

            st.markdown("---")
            st.markdown("### Top Opportunities")

            # For each tier, show opportunities in a 4-column grid
            for tier in [1, 2, 3]:
                tier_opps = filtered_opportunities[filtered_opportunities['risk_tier'] == tier]

                if not tier_opps.empty:
                    tier_labels = {
                        1: 'Tier 1 - Critical (Immediate Refinance Pressure)',
                        2: 'Tier 2 - High (Near-term Refinance Risk)',
                        3: 'Tier 3 - Monitor (Future Opportunities)'
                    }

                    st.markdown(f"#### {tier_labels[tier]}")
                    st.caption(f"{len(tier_opps)} opportunity/opportunities")

                    # Display cards in 4-column grid
                    cols = st.columns(4)
                    for idx, (_, opp) in enumerate(tier_opps.iterrows()):
                        with cols[idx % 4]:
                            render_opportunity_card(opp.to_dict())

                    if tier < 3:
                        st.markdown("---")

        # Export buttons section
        st.markdown("---")
        st.markdown("### Export Opportunities")
        st.caption(f"Showing {len(filtered_opportunities)} of {len(opportunities)} opportunities")
        export_col1, export_col2, export_col3 = st.columns(3)

        with export_col1:
            csv = filtered_opportunities.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"lexerd_opportunities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with export_col2:
            # Excel export with formatting
            try:
                excel_buffer = BytesIO()
                filtered_opportunities.to_excel(excel_buffer, index=False, engine='openpyxl')
                st.download_button(
                    label="Download Excel",
                    data=excel_buffer.getvalue(),
                    file_name=f"lexerd_opportunities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception:
                st.info("(Excel export requires openpyxl - use CSV instead)")

        with export_col3:
            json_str = filtered_opportunities.to_json(orient='records', indent=2)
            st.download_button(
                label="Download JSON",
                data=json_str,
                file_name=f"lexerd_opportunities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )

    except Exception as e:
        logger.error(f"Error rendering opportunities: {e}")
        st.error(f"Error loading opportunities: {str(e)}")
        st.info("""
        **No data sources connected yet.**

        To use this tab, ensure:
        1. Freddie Mac Multifamily Loan Database connection is configured
        2. SEC CMBS (424B5) filing data source is available
        3. Live API connections or cached data is available

        Opportunities will be automatically:
        - Pulled daily for SEC CMBS filings
        - Pulled monthly for Freddie Mac tape
        - Scored and ranked by risk tier (Tier 1/2/3 by maturity)
        - Displayed in the Opportunities tab
        """)


# ============================================================================
# UI COMPONENTS - ANALYTICS TAB
# ============================================================================

def render_analytics_tab():
    """Render Analytics tab - visualizations and insights."""
    st.markdown("## Analytics")
    st.markdown("Score distribution and risk insights.")

    if st.session_state.scored_results is not None and not st.session_state.scored_results.empty:
        results = st.session_state.scored_results

        # Score distribution
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Final Fit Score Distribution")
            scores = pd.to_numeric(results['Final Fit Score'], errors='coerce')

            fig_data = {
                'A (90-100)': sum(scores >= 90),
                'B (75-89)': sum((scores >= 75) & (scores < 90)),
                'C (60-74)': sum((scores >= 60) & (scores < 75)),
                'D (<60)': sum(scores < 60),
            }

            st.bar_chart(pd.Series(fig_data))

        with col2:
            st.markdown("### Grade Breakdown")
            grade_dist = results['Grade'].value_counts()
            st.bar_chart(grade_dist)

        # Summary statistics
        st.markdown("### Summary Statistics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            avg_market = pd.to_numeric(results['Market Score'], errors='coerce').mean()
            st.metric("Avg Market Score", f"{avg_market:.0f}")

        with col2:
            avg_model = pd.to_numeric(results['Model Score'], errors='coerce').mean()
            st.metric("Avg Model Score", f"{avg_model:.0f}")

        with col3:
            avg_mgmt = pd.to_numeric(results['Management Score'], errors='coerce').mean()
            st.metric("Avg Management Score", f"{avg_mgmt:.0f}")

        with col4:
            avg_final = pd.to_numeric(results['Final Fit Score'], errors='coerce').mean()
            st.metric("Avg Final Fit", f"{avg_final:.0f}")
    else:
        st.info("Score some properties in the Properties tab to see analytics")


# ============================================================================
# UI COMPONENTS - SETTINGS TAB
# ============================================================================

def render_about_tab():
    """Render About tab - project explanation and methodology."""
    st.markdown("## About <span style='font-weight: 700; color: #0066cc; font-size: 1.1em;'>Lexerd Deal Engine</span>", unsafe_allow_html=True)

    st.markdown("""
    <span style='font-weight: 700; color: #0066cc; font-size: 1.1em;'>Lexerd Deal Engine</span> is a systematic platform for identifying, prioritizing, and scoring multifamily acquisition opportunities using evidence-based investment signals.

    I built Lexerd Deal Engine to address a core challenge in commercial real estate sourcing: identifying actionable opportunities before they become broadly marketed and determining which properties warrant immediate attention.

    ---

    ### The 3M Thesis

    Lexerd scores properties across three evaluation dimensions using fixed, disciplined weights:

    **Market — 30%**
    Geographic and economic fundamentals that influence long-term property performance, including employment growth, population trends, market rent growth, and cap-rate conditions. Market inputs are supported by data from the Bureau of Labor Statistics and U.S. Census Bureau.

    **Model — 40%**
    Property-level economics and potential for value creation, including property class, occupancy, rent positioning relative to market, operating efficiency, and potential for value enhancement. The highest-weighted component, reflecting the importance of the underlying asset economics and value-add opportunity.

    **Management — 30%**
    Ownership and execution characteristics, including management type, historical performance, sponsor track record, and capital structure discipline. This component evaluates the probability that the identified opportunity can be effectively executed.

    ---

    ### Deal Identification

    <span style='font-weight: 700; color: #0066cc; font-size: 1.1em;'>Lexerd Deal Engine</span> integrates two primary data channels:

    **Freddie Mac Multifamily Loan Data — GSE Channel**
    Loan-level financing, property, and historical performance data from Freddie Mac's multifamily portfolio.

    **SEC CMBS Filings — Private-Label Channel**
    Loan-level data from private-label commercial mortgage-backed securities, expanding coverage beyond the Freddie Mac universe.

    Loans are deduplicated across data sources and prioritized according to maturity:

    **Tier 1 — Critical | <6 Months**
    Immediate refinancing pressure and a potential window for acquisition outreach.

    **Tier 2 — High | 6–24 Months**
    Near-term refinancing risk creates an opportunity for proactive sourcing and owner engagement.

    **Tier 3 — Monitor | 24+ Months**
    Longer-term opportunities tracked for future acquisition activity.

    ---

    ### Features

    **Batch Property Scoring**
    Upload a CSV of potential acquisitions and systematically score properties against the 3M investment thesis.

    **Unified GSE + CMBS Coverage**
    Combine Freddie Mac multifamily loan data and private-label CMBS data within a single sourcing workflow.

    **Early-Warning Signals**
    Maturity profiles, DSCR, LTV, and other loan-level indicators help identify properties that may warrant additional review or proactive outreach.

    **Ranked Opportunity Pipeline**
    Prioritize opportunities based on investment score, maturity profile, and underlying property characteristics.

    **Exportable Reports**
    Download ranked opportunities and scored properties as CSV or Excel files for CRM integration, underwriting, and targeted outreach.

    **Analytics & Insights**
    Analyze score distributions, maturity tiers, geographic concentrations, and summary metrics to support acquisition strategy.

    ---

    **Built by Sajan for Lexerd Capital Management**
    """, unsafe_allow_html=True)


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Lexerd Deal Engine",
        page_icon="🏢",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom styling
    apply_custom_css()

    # Initialize session state
    init_session_state()

    # Clean, minimal header
    st.markdown("""
    <div style="border-bottom: 1px solid #e5e7eb; padding-bottom: 1.5rem; margin-bottom: 2rem;">
        <h1 style="color: #1f2937; margin: 0; font-size: 2rem; font-weight: 700;">Lexerd Deal Engine</h1>
        <p style="color: #6b7280; margin: 0.5rem 0 0 0; font-size: 0.95rem; font-weight: 400;">Unified multifamily acquisition scoring and opportunity identification</p>
    </div>
    """, unsafe_allow_html=True)

    # Main navigation tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Properties", "Opportunities", "Analytics", "About"])

    with tab1:
        render_properties_tab()

    with tab2:
        render_opportunities_tab()

    with tab3:
        render_analytics_tab()

    with tab4:
        render_about_tab()

    # Footer
    st.markdown("---")
    st.markdown("""
    <div class="footer" style="text-align: center; color: #6b7280; font-size: 0.875rem; padding-top: 1rem;">
        <p>ForwardAI © 2.0</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
