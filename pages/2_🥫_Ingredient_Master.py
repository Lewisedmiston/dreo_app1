import streamlit as st
import pandas as pd
from common.utils import page_setup
from common.db import pd_read_sql, execute_query, log_change
from common.data_layer import success_toast, error_toast, info_toast
from datetime import datetime

page_setup("Ingredient Master")

st.markdown("---")

# --- Functions to Refresh State ---
def refresh_ingredients():
    """Fetches the latest ingredient data from the DB and stores it in the session state."""
    st.session_state.ingredients_df = pd_read_sql("""
        SELECT 
            i.ingredient_id, 
            i.ingredient_name, 
            i.costing_method, 
            ci.item_description as locked_item, 
            v.vendor_name,
            i.current_cost_per_oz, 
            i.current_cost_per_each
        FROM ingredients i
        LEFT JOIN catalog_items ci ON i.locked_item_id = ci.item_id
        LEFT JOIN vendors v ON ci.vendor_id = v.vendor_id
        ORDER BY i.ingredient_name
    """)

# --- 1. View & Create Ingredients ---
st.header("Your Ingredient List")

# Load initial data into the session state if it's not already there
if 'ingredients_df' not in st.session_state:
    refresh_ingredients()

# --- Create New Ingredient Form ---
with st.expander("➕ Add New Ingredient"):
    with st.form("new_ingredient_form", clear_on_submit=True):
        new_name = st.text_input("New Ingredient Name")
        submitted = st.form_submit_button("Create Ingredient")
        if submitted and new_name:
            try:
                execute_query("INSERT INTO ingredients (ingredient_name) VALUES (?)", (new_name,))
                log_change("INGREDIENT_CREATE", f"Created new ingredient: {new_name}")
                st.success(f"Ingredient '{new_name}' created!")
                refresh_ingredients() # Refresh data to show the new ingredient immediately
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    st.error(f"An ingredient named '{new_name}' already exists.")
                else:
                    st.error(f"An error occurred: {e}")

# Display the main ingredients table
st.dataframe(
    st.session_state.ingredients_df, 
    use_container_width=True, 
    hide_index=True,
    column_config={
        "current_cost_per_oz": st.column_config.NumberColumn(format="$%.4f"),
        "current_cost_per_each": st.column_config.NumberColumn(format="$%.2f"),
    }
)


# --- 2. Map Ingredient to SKU ---
st.header("Map Ingredient to Vendor SKU")

ingredients = pd_read_sql("SELECT ingredient_id, ingredient_name FROM ingredients ORDER BY ingredient_name")
if not ingredients.empty:
    ingredient_options = {row['ingredient_name']: row['ingredient_id'] for _, row in ingredients.iterrows()}

    selected_ingredient_name = st.selectbox("Select an Ingredient to Map", options=ingredient_options.keys())

    if selected_ingredient_name:
        ingredient_id = ingredient_options[selected_ingredient_name]
        
        st.write(f"Searching for catalog items matching **{selected_ingredient_name}**...")
        
        # Split the ingredient name into terms for a better search (e.g., "Onion Yellow" -> "%Onion%" AND "%Yellow%")
        search_terms = [f"%{term.strip()}%" for term in selected_ingredient_name.split()]
        where_clause = " AND ".join(["ci.item_description LIKE ?" for _ in search_terms])
        
        query = f"""
            SELECT ci.item_id, v.vendor_name, ci.item_description, ci.pack_size_str, ci.case_price, ci.cost_per_oz, ci.cost_per_each
            FROM catalog_items ci
            JOIN vendors v ON ci.vendor_id = v.vendor_id
            WHERE {where_clause}
            ORDER BY ci.price_date DESC
            LIMIT 50
        """
        catalog_items = pd_read_sql(query, params=tuple(search_terms))

        if not catalog_items.empty:
            st.write("Select a vendor item to lock for this ingredient:")
            
            # Format the options for the radio button to be more readable
            item_options = []
            for _, row in catalog_items.iterrows():
                cost_oz_str = f"${row['cost_per_oz']:.4f}" if pd.notna(row['cost_per_oz']) else "N/A"
                cost_each_str = f"${row['cost_per_each']:.2f}" if pd.notna(row['cost_per_each']) else "N/A"
                label = (
                    f"{row['vendor_name']} - {row['item_description']} ({row['pack_size_str']}) "
                    f"| Cost/oz: {cost_oz_str} | Cost/ea: {cost_each_str}"
                )
                item_options.append((label, row['item_id']))
            
            selected_option = st.radio(
                "Matching SKUs (most recent prices shown)", 
                [opt[0] for opt in item_options],
                key=f"radio_{ingredient_id}"
            )

            if st.button("Lock SKU for Ingredient", key=f"lock_{ingredient_id}", type="primary"):
                if selected_option:
                    # Find the item_id corresponding to the selected radio button label
                    selected_item_id = next(opt[1] for opt in item_options if opt[0] == selected_option)
                    selected_item = catalog_items[catalog_items['item_id'] == selected_item_id].iloc[0]
                    
                    # Update the ingredient in the database with the locked item's info
                    execute_query("""
                        UPDATE ingredients
                        SET locked_item_id = ?, costing_method = 'locked_sku',
                            current_cost_per_oz = ?, current_cost_per_each = ?
                        WHERE ingredient_id = ?
                    """, (
                        int(selected_item_id),
                        selected_item['cost_per_oz'],
                        selected_item['cost_per_each'],
                        int(ingredient_id)
                    ))
                    
                    log_change(
                        "INGREDIENT_MAP", 
                        f"Mapped '{selected_ingredient_name}' to SKU '{selected_item['item_description']}' (ID: {selected_item_id})."
                    )
                    st.success(f"Locked '{selected_ingredient_name}' to '{selected_item['item_description']}'.")
                    refresh_ingredients()
                    st.rerun()

        else:
            st.warning("No matching items found in the catalog. Try a different name, check spelling, or upload more vendor catalogs.")
else:
    st.warning("No ingredients created yet. Add an ingredient above to begin mapping.")

