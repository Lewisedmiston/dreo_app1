"""
Mobile-First Inventory Count Flow
Touch-optimized with +/- buttons and draft saving
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from common.data_layer import read_table, write_table, append_snapshot, success_toast, error_toast, info_toast
from common.utils import page_setup

page_setup("Inventory Count")

# Mobile-first CSS
st.markdown("""
<style>
.count-container {
    background: white;
    padding: 1rem;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-bottom: 1rem;
}

.item-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem;
    border-bottom: 1px solid #eee;
    min-height: 80px;
}

.item-info {
    flex: 1;
    margin-right: 1rem;
}

.item-name {
    font-weight: bold;
    font-size: 1.1rem;
    margin-bottom: 0.25rem;
}

.item-details {
    color: #666;
    font-size: 0.9rem;
}

.count-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.count-button {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    border: none;
    font-size: 1.5rem;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.2s;
}

.minus-btn {
    background: #ff4757;
    color: white;
}

.plus-btn {
    background: #2ed573;
    color: white;
}

.count-input {
    width: 80px;
    height: 50px;
    text-align: center;
    font-size: 1.2rem;
    font-weight: bold;
    border: 2px solid #ddd;
    border-radius: 8px;
}

.location-filter {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 0.75rem 1.5rem;
    border-radius: 25px;
    border: none;
    font-weight: bold;
    margin: 0.25rem;
    cursor: pointer;
    transition: all 0.2s;
}

.location-filter.active {
    background: linear-gradient(135deg, #2ed573 0%, #17a2b8 100%);
    transform: scale(1.05);
}

.sticky-footer {
    position: sticky;
    bottom: 0;
    background: white;
    padding: 1rem;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    border-radius: 15px 15px 0 0;
    margin-top: 2rem;
}

.draft-badge {
    background: #ffa726;
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 15px;
    font-size: 0.8rem;
    font-weight: bold;
}

/* Touch-friendly mobile styles */
@media (max-width: 768px) {
    .item-row {
        flex-direction: column;
        align-items: flex-start;
        padding: 1rem 0.5rem;
    }
    
    .count-controls {
        width: 100%;
        justify-content: center;
        margin-top: 1rem;
    }
    
    .count-button {
        width: 60px;
        height: 60px;
    }
    
    .count-input {
        width: 100px;
        height: 60px;
        font-size: 1.5rem;
    }
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "counts_draft" not in st.session_state:
    st.session_state.counts_draft = {}

if "current_location" not in st.session_state:
    st.session_state.current_location = "All"

# Header with draft indicator
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown("# 📦 Inventory Count")

with col2:
    if st.session_state.counts_draft:
        st.markdown('<span class="draft-badge">Unsaved Draft</span>', unsafe_allow_html=True)

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("Home.py")

# Location filters  
st.markdown("### 📍 Select Location")
locations = ["All", "Walk-in", "Dry Storage", "Freezer", "Prep Area"]

filter_cols = st.columns(len(locations))
for i, location in enumerate(locations):
    with filter_cols[i]:
        active_class = "active" if st.session_state.current_location == location else ""
        if st.button(location, key=f"loc_{location}", use_container_width=True):
            st.session_state.current_location = location
            st.rerun()

# Search bar
search_term = st.text_input("🔍 Search items...", placeholder="Type to filter items", key="search_box")

# Get ingredient data
ingredients_df = read_table("ingredient_master")

if ingredients_df.empty:
    st.warning("No ingredients found. Please add ingredients in the Ingredient Master page first.")
    if st.button("Go to Ingredient Master", use_container_width=True):
        st.switch_page("pages/2_🥫_Ingredient_Master.py")
    st.stop()

# Filter by location if not "All"
if st.session_state.current_location != "All":
    if "location" in ingredients_df.columns:
        ingredients_df = ingredients_df[ingredients_df["location"] == st.session_state.current_location]

# Filter by search term
if search_term:
    ingredients_df = ingredients_df[
        ingredients_df.apply(lambda row: search_term.lower() in str(row).lower(), axis=1)
    ]

# Item counting interface
st.markdown("### 📋 Count Items")

if ingredients_df.empty:
    st.info("No items match your current filters.")
else:
    # Display items with count controls
    for idx, item in ingredients_df.iterrows():
        item_id = str(item.get('id', idx))
        item_name = item.get('ingredient_name', 'Unknown Item')
        item_uom = item.get('default_uom', 'ea')
        current_count = st.session_state.counts_draft.get(item_id, 0)
        
        # Item container
        with st.container():
            col1, col2 = st.columns([3, 2])
            
            with col1:
                st.markdown(f"""
                <div class="item-info">
                    <div class="item-name">{item_name}</div>
                    <div class="item-details">UOM: {item_uom}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # Count controls
                control_col1, control_col2, control_col3 = st.columns([1, 2, 1])
                
                with control_col1:
                    if st.button("➖", key=f"minus_{item_id}", use_container_width=True):
                        st.session_state.counts_draft[item_id] = max(0, current_count - 1)
                        st.rerun()
                
                with control_col2:
                    # Allow direct input
                    new_count = st.number_input(
                        "",
                        min_value=0,
                        value=current_count,
                        key=f"count_{item_id}",
                        step=1,
                        help="Tap +/- or enter directly"
                    )
                    if new_count != current_count:
                        st.session_state.counts_draft[item_id] = new_count
                
                with control_col3:
                    if st.button("➕", key=f"plus_{item_id}", use_container_width=True):
                        st.session_state.counts_draft[item_id] = current_count + 1
                        st.rerun()
        
        st.markdown("---")

# Sticky footer with actions
st.markdown("### 💾 Save Actions")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("💾 Save Draft", use_container_width=True, help="Save to browser storage"):
        # Save draft to session state (already there) and show confirmation
        total_items = len([k for k, v in st.session_state.counts_draft.items() if v > 0])
        success_toast(f"Draft saved! {total_items} items counted")

with col2:
    if st.button("📤 Submit Count", use_container_width=True, help="Save final count"):
        if not st.session_state.counts_draft:
            error_toast("No counts to submit!")
        else:
            # Create count snapshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            count_data = []
            
            for item_id, count in st.session_state.counts_draft.items():
                if count > 0:  # Only save non-zero counts
                    item_info = ingredients_df[ingredients_df['id'] == int(item_id)] if item_id.isdigit() else ingredients_df.iloc[int(item_id)]
                    if not item_info.empty:
                        count_data.append({
                            'item_id': item_id,
                            'item_name': item_info.iloc[0].get('ingredient_name', 'Unknown'),
                            'count': count,
                            'uom': item_info.iloc[0].get('default_uom', 'ea'),
                            'location': st.session_state.current_location,
                            'counted_at': datetime.now().isoformat(),
                            'counted_by': 'User'
                        })
            
            if count_data:
                count_df = pd.DataFrame(count_data)
                if append_snapshot("inventory_count", count_df, timestamp):
                    success_toast(f"Count submitted! {len(count_data)} items saved")
                    st.session_state.counts_draft = {}  # Clear draft
                    st.balloons()
                else:
                    error_toast("Failed to submit count")
            else:
                error_toast("No non-zero counts to submit!")

with col3:
    if st.button("🗑️ Clear All", use_container_width=True, help="Clear all counts"):
        st.session_state.counts_draft = {}
        success_toast("All counts cleared")
        st.rerun()

# Summary info
if st.session_state.counts_draft:
    total_items = len([k for k, v in st.session_state.counts_draft.items() if v > 0])
    total_count = sum(v for v in st.session_state.counts_draft.values() if v > 0)
    
    st.markdown("---")
    st.markdown(f"**Draft Summary:** {total_items} items • {total_count} total count")