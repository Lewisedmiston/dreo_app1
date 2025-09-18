"""
Mobile-First Ordering Flow
Vendor selection with touch-optimized cart functionality
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from common.data_layer import read_table, write_table, append_snapshot, success_toast, error_toast, info_toast

# Mobile-first page config
st.set_page_config(
    page_title="Build Order",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Mobile-first CSS
st.markdown("""
<style>
.order-item {
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 0.5rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.item-name {
    font-weight: bold;
    font-size: 1.1rem;
    flex: 1;
}

.cart-badge {
    background: #ff6b6b;
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 15px;
    font-size: 0.8rem;
    font-weight: bold;
    margin-left: 0.5rem;
}

.suggested-qty {
    background: #ffeaa7;
    color: #2d3436;
    padding: 0.25rem 0.5rem;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: bold;
}

/* Touch-friendly buttons */
.stButton > button {
    height: 50px;
    font-size: 1rem;
    border-radius: 8px;
    font-weight: bold;
}

/* Mobile optimizations */
@media (max-width: 768px) {
    .stButton > button {
        height: 60px;
        font-size: 1.1rem;
    }
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "order_cart" not in st.session_state:
    st.session_state.order_cart = {}

if "selected_vendor" not in st.session_state:
    st.session_state.selected_vendor = "PFG"

# Header with cart indicator
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown("# 🧾 Build Order")

with col2:
    cart_count = len([k for k, v in st.session_state.order_cart.items() if v > 0])
    if cart_count > 0:
        st.markdown(f'<span class="cart-badge">{cart_count} items</span>', unsafe_allow_html=True)

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("Home.py")

# Vendor Selection
st.markdown("### 🏪 Select Vendor")
vendors = ["PFG", "Sysco", "Produce", "Other"]

vendor_cols = st.columns(len(vendors))
for i, vendor in enumerate(vendors):
    with vendor_cols[i]:
        if st.button(vendor, key=f"vendor_{vendor}", use_container_width=True):
            st.session_state.selected_vendor = vendor
            st.rerun()

# Get catalog items for selected vendor
catalog_df = read_table("catalog_items")

if not catalog_df.empty and "vendor_name" in catalog_df.columns:
    # Filter by selected vendor
    vendor_items = catalog_df[catalog_df["vendor_name"].str.contains(st.session_state.selected_vendor, case=False, na=False)]
else:
    vendor_items = pd.DataFrame()

# Get ingredient master for par levels and on-hand quantities
ingredients_df = read_table("ingredient_master")

# Search functionality
search_term = st.text_input("🔍 Search items...", placeholder="Type to filter items", key="order_search")

if not vendor_items.empty and search_term:
    vendor_items = vendor_items[
        vendor_items.apply(lambda row: search_term.lower() in str(row).lower(), axis=1)
    ]

# Display ordering interface
st.markdown(f"### 📋 {st.session_state.selected_vendor} Items")

if vendor_items.empty:
    st.warning(f"No items found for {st.session_state.selected_vendor}. Please upload catalog data first.")
    if st.button("Upload Catalogs", use_container_width=True):
        st.switch_page("pages/1_🧾_Upload_Catalogs.py")
else:
    # Display simplified items with ordering controls
    for idx, item in vendor_items.head(20).iterrows():  # Limit for performance
        item_id = str(item.get('item_id', idx))
        item_name = item.get('item_description', 'Unknown Item')
        pack_size = item.get('pack_size_str', 'Unknown')
        price = item.get('case_price', 0)
        
        current_qty = st.session_state.order_cart.get(item_id, 0)
        
        # Simple item display with controls
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                st.write(f"**{item_name}**")
                st.caption(f"Pack: {pack_size} • ${price:.2f}")
            
            with col2:
                if st.button("➖", key=f"minus_{item_id}", use_container_width=True):
                    st.session_state.order_cart[item_id] = max(0, current_qty - 1)
                    st.rerun()
            
            with col3:
                st.write(f"**{current_qty}**", help="Current quantity")
            
            with col4:
                if st.button("➕", key=f"plus_{item_id}", use_container_width=True):
                    st.session_state.order_cart[item_id] = current_qty + 1
                    st.rerun()

# Order summary and actions
if any(qty > 0 for qty in st.session_state.order_cart.values()):
    st.markdown("---")
    st.markdown("### 📋 Order Summary")
    
    total_items = len([k for k, v in st.session_state.order_cart.items() if v > 0])
    total_cases = sum(v for v in st.session_state.order_cart.values() if v > 0)
    
    # Calculate total cost
    total_cost = 0
    order_details = []
    
    for item_id, qty in st.session_state.order_cart.items():
        if qty > 0:
            item_info = vendor_items[vendor_items['item_id'].astype(str) == item_id]
            if not item_info.empty:
                price = item_info.iloc[0].get('case_price', 0)
                total_cost += qty * price
                order_details.append({
                    'item_id': item_id,
                    'item_name': item_info.iloc[0].get('item_description', 'Unknown'),
                    'pack_size': item_info.iloc[0].get('pack_size_str', ''),
                    'quantity': qty,
                    'unit_price': price,
                    'line_total': qty * price,
                    'vendor': st.session_state.selected_vendor
                })
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Items", total_items)
    
    with col2:
        st.metric("Total Cases", total_cases)
    
    with col3:
        st.metric("Total Cost", f"${total_cost:.2f}")

# Action buttons
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("💾 Save Draft", use_container_width=True):
        success_toast(f"Order draft saved!")

with col2:
    if st.button("📤 Submit Order", use_container_width=True):
        if not any(qty > 0 for qty in st.session_state.order_cart.values()):
            error_toast("No items in cart!")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if order_details:
                order_df = pd.DataFrame(order_details)
                order_df['order_date'] = datetime.now().isoformat()
                order_df['order_by'] = 'User'
                order_df['status'] = 'Pending'
                
                if append_snapshot(f"order_{st.session_state.selected_vendor.lower()}", order_df, timestamp):
                    success_toast(f"Order submitted! {len(order_details)} items")
                    st.session_state.order_cart = {}  # Clear cart
                    st.balloons()
                else:
                    error_toast("Failed to submit order")

with col3:
    if st.button("🗑️ Clear Cart", use_container_width=True):
        st.session_state.order_cart = {}
        success_toast("Cart cleared")
        st.rerun()
