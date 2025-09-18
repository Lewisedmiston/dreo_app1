"""
Home Dashboard - Mobile-First Kitchen Operations Hub
"""
import streamlit as st
from common.data_layer import get_metrics
import datetime

# Mobile-first page configuration
st.set_page_config(
    page_title="Dreo Kitchen Ops",
    page_icon="🍽️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile-first design
st.markdown("""
<style>
/* Mobile-first responsive design */
.main-header {
    font-size: 2rem;
    font-weight: bold;
    text-align: center;
    color: #2E8B57;
    margin-bottom: 1rem;
}

.metric-tile {
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin-bottom: 1rem;
    min-height: 120px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.action-tile {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin-bottom: 1rem;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    min-height: 120px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.action-tile:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
}

.tile-icon {
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
}

.tile-title {
    font-size: 1.2rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
}

.tile-subtitle {
    font-size: 0.9rem;
    opacity: 0.8;
}

.metric-value {
    font-size: 2rem;
    font-weight: bold;
    color: #2E8B57;
}

.metric-label {
    font-size: 0.9rem;
    color: #666;
    margin-top: 0.5rem;
}

/* Touch-friendly buttons */
.stButton > button {
    height: 60px;
    font-size: 1.1rem;
    border-radius: 12px;
    font-weight: bold;
}

/* Hide Streamlit menu and footer for cleaner mobile experience */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Responsive grid */
@media (max-width: 768px) {
    .metric-tile, .action-tile {
        min-height: 100px;
        padding: 1rem;
    }
    
    .tile-icon {
        font-size: 2rem;
    }
    
    .tile-title {
        font-size: 1rem;
    }
}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🍽️ Dreo Kitchen Ops</div>', unsafe_allow_html=True)

# Get metrics
metrics = get_metrics()

# Quick metrics row
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="metric-tile">
        <div class="tile-icon">📦</div>
        <div class="metric-value">{metrics['active_skus']}</div>
        <div class="metric-label">Active SKUs</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-tile">
        <div class="tile-icon">📋</div>
        <div class="metric-value">{metrics['open_orders']}</div>
        <div class="metric-label">Open Orders</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-tile">
        <div class="tile-icon">🕐</div>
        <div class="tile-title" style="font-size: 0.9rem;">{metrics['last_count_date']}</div>
        <div class="metric-label">Last Count</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Main action tiles
col1, col2 = st.columns(2)

with col1:
    if st.button("📦 Count Inventory", key="count_inventory", use_container_width=True):
        st.switch_page("pages/4_📦_Inventory_Count.py")
    
    if st.button("🧾 Build Order", key="build_order", use_container_width=True):
        st.switch_page("pages/5_🧾_Ordering.py")

with col2:
    if st.button("📄 Upload Catalogs", key="upload_catalogs", use_container_width=True):
        st.switch_page("pages/1_🧾_Upload_Catalogs.py")
        
    if st.button("🧴 Ingredient Master", key="ingredient_master", use_container_width=True):
        st.switch_page("pages/2_🥫_Ingredient_Master.py")

# Secondary actions
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🍽️ Menu Management", use_container_width=True):
        st.switch_page("pages/4_🍽️_Menu_Management.py")

with col2:
    if st.button("👨‍🍳 Recipes", use_container_width=True):
        st.switch_page("pages/3_👨‍🍳_Recipes.py")

with col3:
    if st.button("⬇️ Export Data", use_container_width=True):
        st.switch_page("pages/8_⬇️_Export.py")

# Quick actions section for mobile
st.markdown("---")
st.markdown("### 🚀 Quick Actions")

quick_col1, quick_col2 = st.columns(2)

with quick_col1:
    if st.button("🔍 Search Ingredients", use_container_width=True):
        st.switch_page("pages/2_🥫_Ingredient_Master.py")

with quick_col2:
    if st.button("📊 View Reports", use_container_width=True):
        st.switch_page("pages/6_📊_Reports.py")

# Footer with app info
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.8rem; margin-top: 2rem;">
    Dreo Kitchen Ops • Mobile-First Restaurant Management<br>
    Last updated: """ + datetime.datetime.now().strftime("%I:%M %p") + """
</div>
""", unsafe_allow_html=True)

# Initialize session state for mobile-first features
if "mobile_mode" not in st.session_state:
    st.session_state.mobile_mode = True

if "unsaved_changes" not in st.session_state:
    st.session_state.unsaved_changes = False
    
if "counts_draft" not in st.session_state:
    st.session_state.counts_draft = {}
    
if "order_cart" not in st.session_state:
    st.session_state.order_cart = {}