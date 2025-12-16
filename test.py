import streamlit as st
import pandas as pd
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

      /* Tables / DataFrames */
      [data-testid="stDataFrame"]{
        background: var(--white) !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        overflow: hidden !important;
      }
      [data-testid="stDataFrame"] *{
        color: var(--black) !important;
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
# Config
# ---------------------------
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
except KeyError:
    st.error("Missing secrets. Add SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit Cloud → Settings → Secrets.")
    st.stop()

ORGS = ["Warehouse", "Bosch", "TDK", "Mathma Nagar"]
CATEGORIES = ["kids", "adults"]

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
    return df

def stock_totals_by_org_size_with_totals(stock_df: pd.DataFrame) -> pd.DataFrame:
    """Stock totals per organization and size with ROW and COLUMN totals"""
    if stock_df.empty:
        return pd.DataFrame()
    
    # Get available organizations and sizes
    available_orgs = sorted(stock_df["organization"].unique())
    available_sizes = sorted(stock_df["size"].dropna().unique())
    
    if len(available_orgs) == 0 or len(available_sizes) == 0:
        return pd.DataFrame()
    
    # Create pivot table
    totals = stock_df.groupby(["organization", "size"], as_index=False)["quantity"].sum()
    pivot = totals.pivot(index="organization", columns="size", values="quantity").fillna(0)
    
    # Reset index to make organization a column
    result = pivot.reset_index()
    
    # Add row totals
    size_cols = available_sizes
    result["TOTAL"] = result[size_cols].sum(axis=1).astype(int)
    
    # Add column totals as new row
    total_row = pd.DataFrame({"organization": ["TOTAL"]})
    for size in size_cols:
        total_row[size] = pivot[size].sum().astype(int)
    total_row["TOTAL"] = total_row[size_cols].sum().astype(int)
    
    # Combine with total row
    result = pd.concat([result, total_row], ignore_index=True)
    
    # Reorder columns: organization first, then sizes, then TOTAL
    cols = ["organization"] + size_cols + ["TOTAL"]
    result = result[cols]
    
    return result

def get_warehouse_in_total(tx_df: pd.DataFrame) -> int:
    """Total IN to Warehouse only (TILL DATE)"""
    if tx_df.empty:
        return 0
    warehouse_in = tx_df[(tx_df["type"] == "in") & (tx_df["organization"] == "Warehouse")]["quantity"].sum()
    return int(warehouse_in)

def get_bosch_out_total(tx_df: pd.DataFrame) -> int:
    """Total OUT from Bosch only (TILL DATE)"""
    if tx_df.empty:
        return 0
    bosch_out = tx_df[(tx_df["type"] == "out") & (tx_df["organization"] == "Bosch")]["quantity"].sum()
    return int(bosch_out)

def get_tdk_out_total(tx_df: pd.DataFrame) -> int:
    """Total OUT from TDK only (TILL DATE)"""
    if tx_df.empty:
        return 0
    tdk_out = tx_df[(tx_df["type"] == "out") & (tx_df["organization"] == "TDK")]["quantity"].sum()
    return int(tdk_out)

def get_mathma_out_total(tx_df: pd.DataFrame) -> int:
    """Total OUT from Mathma Nagar only (TILL DATE)"""
    if tx_df.empty:
        return 0
    mathma_out = tx_df[(tx_df["type"] == "out") & (tx_df["organization"] == "Mathma Nagar")]["quantity"].sum()
    return int(mathma_out)

# ---------------------------
# Header
# ---------------------------
st.markdown('<span class="brand-badge">Inventory Analytics</span>', unsafe_allow_html=True)
st.title("T‑Shirt Inventory Dashboard")

# Load data
stock_df = get_stock_df()
tx_df = get_transactions_df(limit=5000)

# Calculate key metrics (ALL TILL DATE)
warehouse_in_total = get_warehouse_in_total(tx_df)
bosch_out_total = get_bosch_out_total(tx_df)
tdk_out_total = get_tdk_out_total(tx_df)
mathma_out_total = get_mathma_out_total(tx_df)

# ---------------------------
# Sidebar
# ---------------------------
with st.sidebar:
    st.header("Controls")
    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

tabs = st.tabs(["Overview (Analytics)", "Transactions (Table)"])

# ---------------------------
# Overview Tab - SEPARATE METRICS FIRST
# ---------------------------
with tabs[0]:
    # PRIORITY METRICS - FIRST ROW: Warehouse IN
    st.subheader("🏭 WAREHOUSE IN (TILL DATE)")
    col1 = st.columns(1)[0]
    col1.metric("📦 Total IN Warehouse", warehouse_in_total)
    
    st.divider()
    
    # SECOND ROW: OUT from each endpoint SEPARATELY
    st.subheader("📤 OUT FROM ENDPOINTS (TILL DATE)")
    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Bosch OUT", bosch_out_total)
    col2.metric("🔵 TDK OUT", tdk_out_total)
    col3.metric("🟢 Mathma Nagar OUT", mathma_out_total)
    
    st.divider()
    
    # Stock by Company Table with Totals
    st.subheader("📊 Current Stock by Company & Size (With Totals)")
    stock_table = stock_totals_by_org_size_with_totals(stock_df)
    if not stock_table.empty:
        st.dataframe(stock_table, use_container_width=True, hide_index=True)
    else:
        st.info("No stock data available.")

# ---------------------------
# Transactions Tab
# ---------------------------
with tabs[1]:
    st.subheader("Transactions Table (All Time)")

    if tx_df.empty:
        st.write("No transactions.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            org_f = st.selectbox("Org", ["all"] + ORGS, index=0)
        with c2:
            typ_f = st.selectbox("Type", ["all", "in", "out"], index=0)
        with c3:
            cat_f = st.selectbox("Category", ["all"] + CATEGORIES, index=0)

        df = tx_df.copy()
        if org_f != "all":
            df = df[df["organization"] == org_f]
        if typ_f != "all":
            df = df[df["type"] == typ_f]
        if cat_f != "all":
            df = df[df["category"] == cat_f]

        df = df.sort_values("created_at", ascending=False).copy()
        df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(
            df[["id", "created_at", "organization", "type", "category", "size", "quantity", "reason", "user_name"]],
            use_container_width=True,
            hide_index=True,
        )
