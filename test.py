import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client

# ---------------------------
# Page config
# ---------------------------
st.set_page_config(page_title="Inventory Analytics Dashboard", layout="wide")

# ---------------------------
# HARD UI THEME: White + Black + Red ONLY
# ---------------------------
st.markdown(
    """
    <style>
      :root{
        --red:#ef4444;
        --black:#111827;
        --white:#ffffff;
        --border:#e5e7eb;
        --muted:#6b7280;
        --soft-red: rgba(239,68,68,0.08);
      }

      /* Main background */
      html, body, [data-testid="stAppViewContainer"], .stApp {
        background: var(--white) !important;
        color: var(--black) !important;
      }

      /* Sidebar background */
      [data-testid="stSidebar"]{
        background: var(--white) !important;
        border-right: 1px solid var(--border) !important;
      }
      [data-testid="stSidebar"] *{
        color: var(--black) !important;
      }

      /* Header background */
      [data-testid="stHeader"]{
        background: var(--white) !important;
      }

      /* Force all text black */
      h1,h2,h3,h4,h5,h6,p,span,div,label,small,li,strong,em,code {
        color: var(--black) !important;
      }

      /* Links red */
      a, a:visited { color: var(--red) !important; }

      /* Tabs */
      button[data-baseweb="tab"]{
        color: var(--black) !important;
        font-weight: 800 !important;
      }
      button[data-baseweb="tab"][aria-selected="true"]{
        border-bottom: 2px solid var(--red) !important;
      }

      /* Metric cards */
      [data-testid="stMetric"]{
        background: var(--white) !important;
        border: 1px solid var(--border) !important;
        border-radius: 16px !important;
        padding: 14px 14px !important;
      }

      /* ---------------------------
         INPUTS: force WHITE
         --------------------------- */

      /* Text + password + number + date inputs */
      .stTextInput input,
      .stNumberInput input,
      .stDateInput input,
      .stTextArea textarea {
        background: var(--white) !important;
        color: var(--black) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
      }

      /* Some Streamlit versions wrap inputs inside extra divs */
      .stTextInput div[data-baseweb="input"] > div,
      .stNumberInput div[data-baseweb="input"] > div,
      .stDateInput div[data-baseweb="input"] > div {
        background: var(--white) !important;
      }

      /* Selectbox */
      .stSelectbox [data-baseweb="select"] > div{
        background: var(--white) !important;
        color: var(--black) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
      }

      /* Select dropdown menu */
      ul[role="listbox"]{
        background: var(--white) !important;
        color: var(--black) !important;
        border: 1px solid var(--border) !important;
      }
      li[role="option"]{
        background: var(--white) !important;
        color: var(--black) !important;
      }

      /* Buttons: white with red border */
      div.stButton > button{
        background: var(--white) !important;
        color: var(--black) !important;
        border: 1px solid rgba(239,68,68,0.55) !important;
        border-radius: 12px !important;
        font-weight: 900 !important;
      }
      div.stButton > button:hover{
        background: #f9fafb !important;
        border-color: var(--red) !important;
      }

      /* ---------------------------
         TABLES / DATAFRAMES: force WHITE
         --------------------------- */
      [data-testid="stDataFrame"]{
        background: var(--white) !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        overflow: hidden !important;
      }

      /* Some dataframe internal containers */
      [data-testid="stDataFrame"] *{
        color: var(--black) !important;
      }

      /* Expander */
      [data-testid="stExpander"]{
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        background: var(--white) !important;
      }

      /* Badge */
      .brand-badge{
        display:inline-block;
        padding:6px 10px;
        border-radius:999px;
        font-weight:900;
        font-size:12px;
        color:#b91c1c !important;
        background: var(--soft-red) !important;
        border: 1px solid rgba(239,68,68,0.25) !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# Config (Streamlit Secrets)
# ---------------------------
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
except KeyError:
    st.error("Missing secrets. Add SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit Cloud → Settings → Secrets.")
    st.stop()

ORGS = ["Warehouse", "Bosch", "TDK", "Mathma Nagar"]
CATEGORIES = ["kids", "adults"]
SIZES = ["S", "M", "L", "XL", "XXL"]  # Common sizes for all institutions

# ---------------------------
# Supabase client
# ---------------------------
@st.cache_resource
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

client = get_client()

# ---------------------------
# Helpers
# ---------------------------
def sb_to_df(resp) -> pd.DataFrame:
    data = getattr(resp, "data", None) or []
    return pd.DataFrame(data)

@st.cache_data(ttl=20)
def get_stock_df():
    resp = client.table("stock").select("organization,category,size,quantity,updated_at").execute()
    df = sb_to_df(resp)
    if not df.empty:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    return df

@st.cache_data(ttl=20)
def get_transactions_df(limit=5000):
    resp = (
        client.table("transactions")
        .select("id,organization,category,size,quantity,type,reason,user_name,created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    df = sb_to_df(resp)
    if not df.empty:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        df["date"] = df["created_at"].dt.date
    return df

def stock_totals(stock_df: pd.DataFrame) -> pd.DataFrame:
    if stock_df.empty:
        return pd.DataFrame(columns=["organization", "kids_total", "adults_total", "grand_total"])
    pivot = (
        stock_df.groupby(["organization", "category"], as_index=False)["quantity"]
        .sum()
        .pivot(index="organization", columns="category", values="quantity")
        .fillna(0)
        .reset_index()
    )
    if "kids" not in pivot.columns:
        pivot["kids"] = 0
    if "adults" not in pivot.columns:
        pivot["adults"] = 0
    pivot["grand_total"] = pivot["kids"] + pivot["adults"]
    pivot = pivot.rename(columns={"kids": "kids_total", "adults": "adults_total"})
    return pivot[["organization", "kids_total", "adults_total", "grand_total"]]

def current_stock_kpis(stock_df: pd.DataFrame) -> dict:
    totals = stock_totals(stock_df)
    out = {}
    for org in ORGS:
        row = totals[totals["organization"] == org]
        out[org] = int(row["grand_total"].iloc[0]) if not row.empty else 0
    return out

def get_total_in_out(tx_df: pd.DataFrame) -> dict:
    """Calculate total IN and total OUT across all organizations"""
    if tx_df.empty:
        return {"total_in": 0, "total_out": 0}
    
    in_total = tx_df[tx_df["type"] == "in"]["quantity"].sum()
    out_total = tx_df[tx_df["type"] == "out"]["quantity"].sum()
    return {"total_in": int(in_total), "total_out": int(out_total)}

def get_out_by_org(tx_df: pd.DataFrame) -> dict:
    """Calculate OUT totals for Bosch, TDK, Warehouse"""
    if tx_df.empty:
        return {"Bosch": 0, "TDK": 0, "Warehouse": 0}
    
    out_df = tx_df[tx_df["type"] == "out"]
    results = {}
    for org in ["Bosch", "TDK", "Warehouse"]:
        org_out = out_df[out_df["organization"] == org]["quantity"].sum()
        results[org] = int(org_out)
    return results

def tx_kpis(tx_df: pd.DataFrame) -> pd.DataFrame:
    """Updated without date filters - ALL TIME totals"""
    if tx_df.empty:
        return pd.DataFrame(columns=["organization", "in_qty", "out_qty", "net_in_minus_out"])
    
    grp = tx_df.groupby(["organization", "type"], as_index=False)["quantity"].sum()
    pivot = grp.pivot(index="organization", columns="type", values="quantity").fillna(0).reset_index()
    if "in" not in pivot.columns:
        pivot["in"] = 0
    if "out" not in pivot.columns:
        pivot["out"] = 0
    pivot["net_in_minus_out"] = pivot["in"] - pivot["out"]
    pivot = pivot.rename(columns={"in": "in_qty", "out": "out_qty"})
    return pivot.sort_values("organization")

def tx_daily_series(tx_df: pd.DataFrame) -> pd.DataFrame:
    """Updated without date filters - ALL TIME daily series"""
    if tx_df.empty:
        return pd.DataFrame(columns=["date", "in_qty", "out_qty"])
    
    daily = tx_df.groupby(["date", "type"], as_index=False)["quantity"].sum()
    pivot = daily.pivot(index="date", columns="type", values="quantity").fillna(0).reset_index()
    if "in" not in pivot.columns:
        pivot["in"] = 0
    if "out" not in pivot.columns:
        pivot["out"] = 0
    pivot = pivot.rename(columns={"in": "in_qty", "out": "out_qty"})
    pivot["date"] = pd.to_datetime(pivot["date"])
    return pivot.sort_values("date")

# ---------------------------
# Header
# ---------------------------
st.markdown('<span class="brand-badge">Inventory Analytics</span>', unsafe_allow_html=True)
st.title("T‑Shirt Inventory Dashboard")

# Load data
stock_df = get_stock_df()
tx_df = get_transactions_df(limit=5000)

# Calculate totals
total_metrics = get_total_in_out(tx_df)
out_by_org = get_out_by_org(tx_df)

# ---------------------------
# Sidebar - Filters only (NO DATE FILTER)
# ---------------------------
with st.sidebar:
    st.header("Filters")
    
    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

tabs = st.tabs(["Overview (Analytics)", "Transactions (Table)"])

# ---------------------------
# Overview
# ---------------------------
with tabs[0]:
    st.subheader("🏆 TOTAL INVENTORY METRICS (ALL TIME)")
    
    # Row 1: Current Stock + Grand Totals
    col1, col2, col3, col4 = st.columns(4)
    kpis = current_stock_kpis(stock_df)
    col1.metric("Warehouse Stock", kpis.get("Warehouse", 0))
    col2.metric("Bosch Stock", kpis.get("Bosch", 0))
    col3.metric("TDK Stock", kpis.get("TDK", 0))
    col4.metric("Mathma Nagar Stock", kpis.get("Mathma Nagar", 0))
    
    # Row 2: Total IN/OUT + OUT by endpoints
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("💰 TOTAL IN", total_metrics["total_in"])
    col6.metric("📤 TOTAL OUT", total_metrics["total_out"])
    col7.metric("🔴 Bosch OUT", out_by_org["Bosch"])
    col8.metric("🔵 TDK OUT", out_by_org["TDK"])

    st.divider()
    st.subheader("📊 Detailed Tables")

    st.markdown("**Current Stock by Organization**")
    st.dataframe(stock_totals(stock_df), use_container_width=True, hide_index=True)

    st.markdown("**ALL TIME IN/OUT by Organization**")
    tx_summary = tx_kpis(tx_df)
    st.dataframe(tx_summary, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📈 Charts (All Time Data)")

    totals_df = stock_totals(stock_df).set_index("organization")
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Current Stock (Grand Total)**")
        st.bar_chart(totals_df[["grand_total"]])
    
    with g2:
        st.markdown("**Kids vs Adults Stock**")
        st.bar_chart(totals_df[["kids_total", "adults_total"]])

    st.markdown("**Daily IN vs OUT Trend (All Time)**")
    daily = tx_daily_series(tx_df)
    if daily.empty:
        st.info("No transactions available.")
    else:
        st.line_chart(daily.set_index("date")[["in_qty", "out_qty"]])

    st.markdown("**Top Dispatch Reasons (OUT - All Time)**")
    if tx_df.empty:
        st.info("No transactions.")
    else:
        out_df = tx_df[tx_df["type"] == "out"].copy()
        if out_df.empty:
            st.info("No OUT transactions.")
        else:
            top_reasons = (
                out_df.assign(reason=out_df["reason"].fillna("No reason"))
                .groupby("reason", as_index=False)["quantity"]
                .sum()
                .sort_values("quantity", ascending=False)
                .head(12)
                .set_index("reason")
            )
            st.bar_chart(top_reasons)

# ---------------------------
# Transactions tab - Updated with Size filter
# ---------------------------
with tabs[1]:
    st.subheader("Transactions Table (All Time)")

    if tx_df.empty:
        st.write("No transactions.")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            org_f = st.selectbox("Org", ["all"] + ORGS, index=0)
        with c2:
            typ_f = st.selectbox("Type", ["all", "in", "out"], index=0)
        with c3:
            cat_f = st.selectbox("Category", ["all"] + CATEGORIES, index=0)
        with c4:
            size_f = st.selectbox("Size", ["all"] + SIZES, index=0)
        with c5:
            reason_f = st.text_input("Reason contains", value="")

        df = tx_df.copy()
        if org_f != "all":
            df = df[df["organization"] == org_f]
        if typ_f != "all":
            df = df[df["type"] == typ_f]
        if cat_f != "all":
            df = df[df["category"] == cat_f]
        if size_f != "all":
            df = df[df["size"] == size_f]
        if reason_f.strip():
            df = df[df["reason"].str.contains(reason_f.strip(), case=False, na=False)]

        df = df.sort_values("created_at", ascending=False).copy()
        df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(
            df[["id", "created_at", "organization", "type", "category", "size", "quantity", "reason", "user_name"]],
            use_container_width=True,
            hide_index=True,
        )
