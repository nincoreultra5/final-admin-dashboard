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

def get_warehouse_metrics(tx_df: pd.DataFrame, stock_df: pd.DataFrame) -> dict:
    """Warehouse specific metrics"""
    metrics = {}
    
    # Total IN to Warehouse
    if not tx_df.empty:
        warehouse_in = tx_df[(tx_df["type"] == "in") & (tx_df["organization"] == "Warehouse")]["quantity"].sum()
        warehouse_out = tx_df[(tx_df["type"] == "out") & (tx_df["organization"] == "Warehouse")]["quantity"].sum()
    else:
        warehouse_in = 0
        warehouse_out = 0
    
    # Current stock available in Warehouse
    if not stock_df.empty:
        warehouse_stock = stock_df[stock_df["organization"] == "Warehouse"]["quantity"].sum()
    else:
        warehouse_stock = 0
    
    metrics["total_in"] = int(warehouse_in)
    metrics["total_out"] = int(warehouse_out)
    metrics["stock_available"] = int(warehouse_stock)
    
    return metrics

# ---------------------------
# Header
# ---------------------------
st.markdown('<span class="brand-badge">Warehouse Analytics</span>', unsafe_allow_html=True)
st.title("🏭 Warehouse Inventory Dashboard")

# Load data
stock_df = get_stock_df()
tx_df = get_transactions_df(limit=5000)

# Calculate Warehouse metrics
warehouse_metrics = get_warehouse_metrics(tx_df, stock_df)

# ---------------------------
# Sidebar
# ---------------------------
with st.sidebar:
    st.header("Controls")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ---------------------------
# MAIN DASHBOARD - WAREHOUSE ONLY
# ---------------------------
st.subheader("📊 Warehouse Key Metrics (All Time)")

# 2x2 Metrics Grid
col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

with col1:
    st.metric("📦 Total IN", warehouse_metrics["total_in"])
with col2:
    st.metric("📤 Total OUT", warehouse_metrics["total_out"])
with col3:
    st.metric("📈 Stock Available", warehouse_metrics["stock_available"])
with col4:
    net_stock = warehouse_metrics["total_in"] - warehouse_metrics["total_out"]
    st.metric("🔄 Net (IN - OUT)", net_stock)

st.divider()

# Warehouse Stock Table
st.subheader("📋 Current Warehouse Stock by Size")
warehouse_stock = stock_df[stock_df["organization"] == "Warehouse"].copy()
if not warehouse_stock.empty:
    # Pivot by size
    stock_pivot = warehouse_stock.pivot_table(
        index="category", 
        columns="size", 
        values="quantity", 
        aggfunc="sum", 
        fill_value=0
    ).astype(int)
    st.dataframe(stock_pivot, use_container_width=True)
    
    # Summary totals
    st.markdown("**Totals by Category:**")
    kids_total = warehouse_stock[warehouse_stock["category"] == "kids"]["quantity"].sum()
    adults_total = warehouse_stock[warehouse_stock["category"] == "adults"]["quantity"].sum()
    col1, col2 = st.columns(2)
    col1.metric("👶 Kids Total", int(kids_total))
    col2.metric("👨 Adults Total", int(adults_total))
else:
    st.info("No warehouse stock data available.")

st.divider()

# Warehouse Transactions Table
st.subheader("📜 Recent Warehouse Transactions")
warehouse_tx = tx_df[tx_df["organization"] == "Warehouse"].copy()
if not warehouse_tx.empty:
    warehouse_tx = warehouse_tx.sort_values("created_at", ascending=False)
    warehouse_tx["created_at"] = warehouse_tx["created_at"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        warehouse_tx[["created_at", "type", "category", "size", "quantity", "reason", "user_name"]],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No warehouse transactions found.")
