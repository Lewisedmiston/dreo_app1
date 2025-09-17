import streamlit as st
import pandas as pd
from common.utils import page_setup
from common.db import pd_read_sql, execute_query, log_change
from common.costing import UOM_OPTIONS

page_setup("Recipes")

st.info("Build your menu items and sub-recipes. Add ingredients from your Ingredient Master and see live plate costs.")

# --- Functions to refresh data ---
def refresh_recipes():
    st.session_state.recipes_df = pd_read_sql("SELECT recipe_id, recipe_name, menu_price FROM recipes ORDER BY recipe_name")

def refresh_ingredients_list():
    st.session_state.ingredients_list_df = pd_read_sql("""
        SELECT ingredient_id, ingredient_name, current_cost_per_oz, current_cost_per_each 
        FROM ingredients 
        WHERE current_cost_per_oz IS NOT NULL OR current_cost_per_each IS NOT NULL
        ORDER BY ingredient_name
    """)

# --- Initialize session state ---
if 'recipes_df' not in st.session_state:
    refresh_recipes()
if 'ingredients_list_df' not in st.session_state:
    refresh_ingredients_list()
if 'recipe_lines' not in st.session_state:
    st.session_state.recipe_lines = pd.DataFrame()

# --- 1. Select or Create Recipe ---
st.header("Select or Create a Recipe")

# Form for creating a new recipe
with st.expander("➕ Create New Recipe"):
    with st.form("new_recipe_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        new_recipe_name = col1.text_input("New Recipe Name")
        new_menu_price = col2.number_input("Menu Price ($)", min_value=0.0, format="%.2f")
        
        if st.form_submit_button("Create Recipe", type="primary"):
            if new_recipe_name:
                try:
                    execute_query(
                        "INSERT INTO recipes (recipe_name, menu_price) VALUES (?, ?)",
                        (new_recipe_name, new_menu_price)
                    )
                    log_change("RECIPE_CREATE", f"Created recipe '{new_recipe_name}' with price ${new_menu_price:.2f}")
                    st.success(f"Recipe '{new_recipe_name}' created!")
                    refresh_recipes()
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e):
                        st.error(f"A recipe named '{new_recipe_name}' already exists.")
                    else:
                        st.error(f"An error occurred: {e}")

# Dropdown to select an existing recipe
recipe_options = {row['recipe_name']: row['recipe_id'] for _, row in st.session_state.recipes_df.iterrows()}
selected_recipe_name = st.selectbox("Select a Recipe to Edit", options=recipe_options.keys())

# --- 2. Edit Recipe Details and Lines ---
if selected_recipe_name:
    recipe_id = recipe_options[selected_recipe_name]
    
    # Load recipe details
    recipe_details = pd_read_sql("SELECT * FROM recipes WHERE recipe_id = ?", params=(recipe_id,)).iloc[0]
    
    st.header(f"Editing: {recipe_details['recipe_name']}")
    
    # --- Live Cost Summary ---
    plate_cost_query = pd_read_sql("""
        SELECT SUM(line_cost) as total
        FROM recipe_lines
        WHERE recipe_id = ?
    """, params=(recipe_id,))
    
    plate_cost = plate_cost_query['total'].iloc[0] if not plate_cost_query.empty and pd.notna(plate_cost_query['total'].iloc[0]) else 0.0
    menu_price = recipe_details['menu_price']
    food_cost_pct = (plate_cost / menu_price * 100) if menu_price > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Menu Price", f"${menu_price:.2f}")
    col2.metric("Plate Cost", f"${plate_cost:.2f}")
    fc_color = "inverse" if food_cost_pct > 35 else "normal"
    col3.metric("Food Cost %", f"{food_cost_pct:.1f}%", delta_color=fc_color)
    
    # --- Edit Recipe Lines ---
    st.subheader("Recipe Ingredients")
    
    # Load existing lines
    recipe_lines_df = pd_read_sql("""
        SELECT rl.line_id, i.ingredient_name, rl.quantity, rl.uom, rl.yield_pct, rl.line_cost
        FROM recipe_lines rl
        JOIN ingredients i ON rl.ingredient_id = i.ingredient_id
        WHERE rl.recipe_id = ?
        ORDER BY rl.line_id
    """, params=(recipe_id,))
    
    # Use data editor for modifications
    edited_df = st.data_editor(
        recipe_lines_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "ingredient_name": st.column_config.SelectboxColumn(
                "Ingredient",
                options=st.session_state.ingredients_list_df['ingredient_name'].tolist(),
                required=True,
            ),
            "quantity": st.column_config.NumberColumn("Qty", required=True),
            "uom": st.column_config.SelectboxColumn("Unit", options=UOM_OPTIONS, required=True),
            "yield_pct": st.column_config.NumberColumn("Yield %", default=100.0, min_value=1, max_value=100),
            "line_cost": st.column_config.NumberColumn("Line Cost", format="$%.4f", disabled=True),
        }
    )

    if st.button("Save Recipe Changes", type="primary"):
        with st.spinner("Saving..."):
            # This is a simplified save logic. A real app would handle diffs.
            # For now, we delete all lines and re-insert them.
            execute_query("DELETE FROM recipe_lines WHERE recipe_id = ?", (recipe_id,))
            
            for index, row in edited_df.iterrows():
                ingredient_name = row['ingredient_name']
                if not ingredient_name or pd.isna(ingredient_name): continue

                ing_details = st.session_state.ingredients_list_df[
                    st.session_state.ingredients_list_df['ingredient_name'] == ingredient_name
                ].iloc[0]
                
                # Recalculate line cost before saving
                cost_per_oz = ing_details['current_cost_per_oz']
                cost_per_each = ing_details['current_cost_per_each']
                quantity = row['quantity']
                uom = row['uom']
                yield_pct = row.get('yield_pct', 100) / 100.0
                
                # Basic line cost calculation (can be moved to costing.py)
                line_cost_val = 0
                if uom in ['oz', 'lb', 'g', 'kg'] and pd.notna(cost_per_oz):
                    base_oz = quantity * ({'oz': 1, 'lb': 16, 'g': 0.035274, 'kg': 35.274}[uom])
                    line_cost_val = (base_oz / yield_pct) * cost_per_oz
                elif uom == 'each' and pd.notna(cost_per_each):
                    line_cost_val = (quantity / yield_pct) * cost_per_each

                execute_query("""
                    INSERT INTO recipe_lines (recipe_id, ingredient_id, quantity, uom, yield_pct, line_cost)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    recipe_id, 
                    int(ing_details['ingredient_id']), 
                    row['quantity'], 
                    row['uom'], 
                    row.get('yield_pct', 100.0),
                    line_cost_val
                ))
            
            log_change("RECIPE_UPDATE", f"Updated recipe '{selected_recipe_name}'.")
            st.success("Recipe saved successfully!")
            st.rerun()

