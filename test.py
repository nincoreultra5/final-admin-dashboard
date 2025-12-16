import streamlit as st
import pandas as pd
from supabase import create_client

# ---------------------------
# Page config
# ---------------------------
st.set_page_config(page_title="Complete Inventory Analytics Dashboard", layout="wide")

# ---------------------------
# HARD UI THEME: White + Black + Red ONLY
# ---------------------------
st.markdown("""
<style>
  :root{
    --red:#ef4444;
    --black:#111827;
    --white:#ffffff;
    --border:#e5e7eb;
    --muted:#6b7280;
    --soft-red: rgba(239,68,68,0.08);
  }

  html, body, [data-testid="stAppViewContainer"], .stApp {
    background: var(--white) !important;
    color: var(--black) !important;
  }

  [data-testid="stSidebar"]{
    background: var(--white) !important;
    border-right: 1px solid var(--border) !important;
  }
  [data-testid="stSidebar"] *{
    color: var(--black) !important;
  }

  [data-testid="stHeader"]{
    background: var(--white) !important;
  }

  h1,h2,h3,h4,h5,h6,p,span,div,label,small,li,strong,em,code {
    color: var(--black) !important;
  }

  a, a:visited { color: var(--red) !important; }

  button[data-baseweb="tab"]{
    color: var(--black) !important;
    font-weight: 800 !important;
  }
  button[data-baseweb="tab"][aria-selected="true"]{
    border-bottom: 2px solid var(--red) !important;
  }

  [data-testid="stMetric"]{
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    padding: 14px 14px !important;
  }

  [data-testid="stDataFrame"]{
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    overflow: hidden !important;
  }
  [data-testid="stDataFrame"] *{
    color: var(--black) !important;
  }

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
""", unsafe_allow_html=True)

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
def sb_to_df(resp):
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

def stock_totals_by_org_size_with_totals(stock_df):
    if stock_df.empty:
        return pd.DataFrame()
    
    available_orgs = sorted(stock_df["organization"].unique())
    available_sizes = sorted(stock_df["size"].dropna().unique())
    
    if len(available_orgs) == 0 or len(available_sizes) == 0:
        return pd.DataFrame()
    
    totals = stock_df.groupby(["organization", "size"], as_index=False)["quantity"].sum()
    pivot = totals.pivot(index="organization", columns="size", values="quantity").fillna(0)
    
    result = pivot.reset_index()
    size_cols = available_sizes
    result["TOTAL"] = result[size_cols].sum(axis=1).astype(int)
    
    total_row = pd.DataFrame({"organization": ["TOTAL"]})
    for size in size_cols:
        total_row[size] = pivot[size].sum().astype(int)
    total_row["TOTAL"] = total_row[size_cols].sum().astype(int)
    
    result = pd.concat([result, total_row], ignore_index=True)
    cols = ["organization"] + size_cols + ["TOTAL"]
    result = result[cols]
    
    return result

def get_all_metrics(tx_df, stock_df):
    metrics = {}
    
    # Warehouse metrics
    metrics["warehouse_in"] = int(tx_df[(tx_df["type"] == "in") & (tx_df["organization"] == "Warehouse")]["quantity"].sum())
    metrics["warehouse_out"] = int(tx_df[(tx_df["type"] == "out") & (tx_df["organization"] == "Warehouse")]["quantity"].sum())
    metrics["warehouse_stock"] = int(stock_df[stock_df["organization"] == "Warehouse"]["quantity"].sum())
    
    # Bosch metrics
    metrics["bosch_out"] = int(tx_df[(tx_df["type"] == "out") & (tx_df["organization"] == "Bosch")]["quantity"].sum())
    
    # TDK metrics
    metrics["tdk_out"] = int(tx_df[(tx_df["type"] == "out") & (tx_df["organization"] == "TDK")]["quantity"].sum())
    
    # Mathma Nagar metrics
    metrics["mathma_out"] = int(tx_df[(tx_df["type"] == "out") & (tx_df["organization"] == "Mathma Nagar")]["quantity"].sum())
    
    # Overall totals
    metrics["total_in"] = int(tx_df[tx_df["type"] == "in"]["quantity"].sum())
    metrics["total_out"] = int(tx_df[tx_df["type"] == "out"]["quantity"].sum())
    metrics["total_stock"] = int(stock_df["quantity"].sum())
    
    return metrics

# ---------------------------
# Header
# ---------------------------
st.markdown('<span class="brand-badge">Complete Analytics</span>', unsafe_allow_html=True)
st.title("📊 T-Shirt Inventory Analytics Dashboard")

# Load data
stock_df = get_stock_df()
tx_df = get_transactions_df(limit=5000)

# Calculate all metrics
metrics = get_all_metrics(tx_df, stock_df)

# ---------------------------
# Sidebar
# ---------------------------
with st.sidebar:
    st.header("🔧 Controls")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.info(f"**Last Updated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")

# ---------------------------
# Tabs
# ---------------------------
tabs = st.tabs(["🏭 Warehouse Analytics", "📤 Endpoint Analytics", "📊 Stock Matrix", "📈 Transactions"])

# ---------------------------
# Tab 1: Warehouse Analytics
# ---------------------------
with tabs[0]:
    st.header("🏭 Warehouse Complete Analytics")
    
    # 2x2 Metrics
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    
    col1.metric("📦 Total IN", metrics["warehouse_in"])
    col2.metric("📤 Total OUT", metrics["warehouse_out"])
    col3.metric("📈 Current Stock", metrics["warehouse_stock"])
    col4.metric("🔄 Net Movement", metrics["warehouse_in"] - metrics["warehouse_out"])
    
    st.divider()
    
    # Warehouse stock table
    warehouse_stock = stock_df[stock_df["organization"] == "Warehouse"]
    if not warehouse_stock.empty:
        st.subheader("📋 Warehouse Stock by Category & Size")
        pivot = warehouse_stock.pivot_table(
            index="category", columns="size", values="quantity", aggfunc="sum", fill_value=0
        ).round().astype(int)
        st.dataframe(pivot, use_container_width=True)

# ---------------------------
# Tab 2: Endpoint Analytics
# ---------------------------
with tabs[1]:
    st.header("📤 Endpoint Dispatch Analytics")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Bosch OUT", metrics["bosch_out"])
    col2.metric("🔵 TDK OUT", metrics["tdk_out"])
    col3.metric("🟢 Mathma Nagar OUT", metrics["mathma_out"])
    
    st.divider()
    
    # Endpoint transactions summary
    endpoint_out = tx_df[(tx_df["type"] == "out") & 
                        (tx_df["organization"].isin(["Bosch", "TDK", "Mathma Nagar"]))]
    if not endpoint_out.empty:
        st.subheader("📊 OUT Summary by Endpoint")
        out_summary = endpoint_out.groupby("organization")["quantity"].sum().round().astype(int)
        st.dataframe(out_summary.reset_index(), use_container_width=True)

# ---------------------------
# Tab 3: Stock Matrix
# ---------------------------
with tabs[2]:
    st.header("📊 Complete Stock Matrix (All Organizations)")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("📊 Total Stock", metrics["total_stock"])
        st.metric("📦 Total IN (All)", metrics["total_in"])
        st.metric("📤 Total OUT (All)", metrics["total_out"])
    
    with col2:
        stock_table = stock_totals_by_org_size_with_totals(stock_df)
        if not stock_table.empty:
            st.dataframe(stock_table, use_container_width=True, height=400)
        else:
            st.info("No stock data available.")

# ---------------------------
# Tab 4: Transactions
# ---------------------------
with tabs[3]:
    st.header("📜 All Transactions (Recent 5000)")
    
    if tx_df.empty:
        st.info("No transactions available.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            org_filter = st.selectbox("Organization", ["all"] + ORGS)
        with col2:
            type_filter = st.selectbox("Type", ["all", "in", "out"])
        with col3:
            cat_filter = st.selectbox("Category", ["all"] + CATEGORIES)
        
        df = tx_df.copy()
        if org_filter != "all":
            df = df[df["organization"] == org_filter]
        if type_filter != "all":
            df = df[df["type"] == type_filter]
        if cat_filter != "all":
            df = df[df["category"] == cat_filter]
        
        df = df.sort_values("created_at", ascending=False).head(1000)
        df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        
        st.dataframe(
            df[["created_at", "organization", "type", "category", "size", "quantity", "reason"]],
            use_container_width=True,
            hide_index=True
        )

# ---------------------------
# Footer
# ---------------------------
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col2:
    st.markdown("*Complete T-Shirt Inventory Analytics Dashboard*")
