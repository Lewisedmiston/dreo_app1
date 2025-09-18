
"""
Export Page - Download master data and reports
Mobile-first interface for data exports
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from common.data_layer import read_table, get_latest_snapshot
from pathlib import Path

# Mobile-first page config
st.set_page_config(
    page_title="Export Data",
    page_icon="⬇️",
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# Mobile-first CSS
st.markdown("""
<style>
.export-tile {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
    margin-bottom: 1rem;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.export-description {
    color: #ddd;
    font-size: 0.9rem;
    margin-top: 0.5rem;
}

/* Touch-friendly buttons */
.stButton > button {
    height: 60px;
    font-size: 1.1rem;
    border-radius: 8px;
    font-weight: bold;
}

/* Mobile optimizations */
@media (max-width: 768px) {
    .export-tile {
        padding: 1rem;
    }
}
</style>
""", unsafe_allow_html=True)

# Header
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("# ⬇️ Export Data")
    st.markdown("Download your data as CSV or Excel files")

with col2:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("Home.py")

st.markdown("---")

# Export options
st.markdown("### 📊 Available Exports")

# Create export tiles
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="export-tile">
        <h3>📋 Ingredient Master</h3>
        <p class="export-description">Complete ingredient database with costs and vendor info</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get ingredient master data
    ingredients_df = read_table("ingredient_master")
    
    if not ingredients_df.empty:
        st.success(f"✅ {len(ingredients_df)} ingredients available")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            csv_data = ingredients_df.to_csv(index=False)
            st.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name=f"ingredient_master_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_b:
            # Create Excel with formatting
            excel_buffer = pd.io.common.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                ingredients_df.to_excel(writer, sheet_name='Ingredient Master', index=False)
            
            st.download_button(
                label="📊 Download Excel",
                data=excel_buffer.getvalue(),
                file_name=f"ingredient_master_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.warning("No ingredient data found")

with col2:
    st.markdown("""
    <div class="export-tile">
        <h3>📦 Latest Inventory Count</h3>
        <p class="export-description">Most recent inventory count snapshot</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get latest inventory count
    latest_count = get_latest_snapshot("inventory_count")
    
    if latest_count is not None and not latest_count.empty:
        st.success(f"✅ {len(latest_count)} items counted")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            csv_data = latest_count.to_csv(index=False)
            st.download_button(
                label="📄 Download CSV", 
                data=csv_data,
                file_name=f"inventory_count_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_b:
            excel_buffer = pd.io.common.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                latest_count.to_excel(writer, sheet_name='Inventory Count', index=False)
            
            st.download_button(
                label="📊 Download Excel",
                data=excel_buffer.getvalue(), 
                file_name=f"inventory_count_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.warning("No inventory counts found")

# Second row - Orders and Catalogs
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="export-tile">
        <h3>🧾 Recent Orders</h3>
        <p class="export-description">All submitted orders by vendor</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get order files from data directory
    orders_dir = Path("data/orders")
    if orders_dir.exists():
        order_files = list(orders_dir.glob("order_*.csv"))
        if order_files:
            st.success(f"✅ {len(order_files)} order files found")
            
            # Get the most recent order file
            if order_files:
                latest_order_file = max(order_files, key=lambda x: x.stat().st_mtime)
                latest_order_df = pd.read_csv(latest_order_file)
                
                col_a, col_b = st.columns(2)
                
                with col_a:
                    csv_data = latest_order_df.to_csv(index=False)
                    st.download_button(
                        label="📄 Download CSV",
                        data=csv_data,
                        file_name=f"latest_order_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv", 
                        use_container_width=True
                    )
                
                with col_b:
                    excel_buffer = pd.io.common.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                        latest_order_df.to_excel(writer, sheet_name='Latest Order', index=False)
                    
                    st.download_button(
                        label="📊 Download Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"latest_order_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        else:
            st.warning("No order files found")
    else:
        st.warning("Orders directory not found")

with col2:
    st.markdown("""
    <div class="export-tile">
        <h3>📂 Catalog Items</h3>
        <p class="export-description">Master catalog with all vendor items</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get catalog data
    catalog_df = read_table("catalog_items")
    
    if not catalog_df.empty:
        st.success(f"✅ {len(catalog_df)} catalog items")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            csv_data = catalog_df.to_csv(index=False)
            st.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name=f"catalog_items_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_b:
            excel_buffer = pd.io.common.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                catalog_df.to_excel(writer, sheet_name='Catalog Items', index=False)
            
            st.download_button(
                label="📊 Download Excel",
                data=excel_buffer.getvalue(),
                file_name=f"catalog_items_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.warning("No catalog data found")

# Summary section
st.markdown("---")
st.markdown("### 📁 Data Locations")

st.info("""
**File Storage Locations:**
- **Master Data**: `/data/*.csv` (ingredient_master.csv, catalog_items.csv)
- **Inventory Counts**: `/data/inventory_counts/inventory_count_YYYYMMDD_HHMMSS.csv`
- **Orders**: `/data/orders/order_vendor_YYYYMMDD_HHMMSS.csv`
- **Catalogs**: `/data/catalogs/*.csv` (vendor-specific files)

All downloads include timestamps for easy tracking.
""")
