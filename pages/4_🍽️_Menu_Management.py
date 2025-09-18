import streamlit as st
import pandas as pd
import io
from datetime import date
from common.utils import page_setup, load_file_to_dataframe, get_excel_sheet_names, clear_data_caches
from common.db import execute_query, pd_read_sql, log_change, get_db_connection, ensure_db_initialized

# Ensure database is properly initialized
ensure_db_initialized()

page_setup("Menu Management")

st.info("🍽️ Manage your menu items, pricing, allergens, and track modifications. Import from Excel or manage manually.")

# Create menu tables if they don't exist
with get_db_connection() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            menu_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            dish_name TEXT NOT NULL,
            current_price REAL,
            allergens TEXT,
            status TEXT DEFAULT 'Keep',
            notes TEXT,
            created_date TEXT DEFAULT CURRENT_DATE,
            modified_date TEXT DEFAULT CURRENT_DATE,
            UNIQUE(category, dish_name)
        )
    """)
    conn.commit()

# Tabs for different menu management functions
tab1, tab2, tab3, tab4 = st.tabs(["📋 Current Menu", "📤 Import Menu", "📊 Menu Analysis", "🏷️ Allergen Management"])

with tab1:
    st.subheader("Current Menu Items")
    
    # Load current menu items
    menu_df = pd_read_sql("SELECT * FROM menu_items ORDER BY category, dish_name")
    
    if menu_df.empty:
        st.info("📝 No menu items found. Import from Excel or add items manually below.")
        
        # Quick add form
        with st.expander("➕ Add New Menu Item", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_category = st.text_input("Category", placeholder="e.g., Starters, Mains, Desserts")
                new_dish = st.text_input("Dish Name", placeholder="e.g., Fried Calamari")
            with col2:
                new_price = st.number_input("Price ($)", min_value=0.0, step=0.50, format="%.2f")
                new_allergens = st.text_input("Allergens", placeholder="e.g., Shellfish, Dairy")
            with col3:
                new_status = st.selectbox("Status", ["Keep", "Modify", "Remove"])
                new_notes = st.text_area("Notes", placeholder="Any changes or notes...")
            
            if st.button("Add Menu Item") and new_category and new_dish:
                try:
                    execute_query("""
                        INSERT INTO menu_items (category, dish_name, current_price, allergens, status, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (new_category, new_dish, new_price, new_allergens, new_status, new_notes))
                    st.success(f"✅ Added {new_dish} to {new_category}")
                    log_change("MENU_ITEM_ADDED", f"Added {new_dish} in {new_category}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error adding menu item: {e}")
    
    else:
        # Display and edit existing menu
        st.write(f"📊 **{len(menu_df)} menu items** across **{menu_df['category'].nunique()} categories**")
        
        # Category filter
        categories = ['All'] + sorted(menu_df['category'].unique().tolist())
        selected_category = st.selectbox("Filter by Category:", categories)
        
        if selected_category != 'All':
            display_df = menu_df[menu_df['category'] == selected_category].copy()
        else:
            display_df = menu_df.copy()
        
        # Editable data editor with your real column structure
        edited_df = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "menu_item_id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "category": st.column_config.TextColumn("Category", required=True, width="medium"),
                "dish_name": st.column_config.TextColumn("Dish Name", required=True, width="large"),
                "current_price": st.column_config.NumberColumn("Price ($)", format="$%.2f", step=0.50, width="small"),
                "allergens": st.column_config.TextColumn("Allergens", width="medium"),
                "status": st.column_config.SelectboxColumn(
                    "Status", 
                    options=["Keep", "Modify", "Remove"],
                    required=True,
                    width="small"
                ),
                "notes": st.column_config.TextColumn("Notes / Proposed Changes", width="large"),
                "modified_date": st.column_config.DateColumn("Last Modified", disabled=True, width="small")
            },
            num_rows="dynamic"
        )
        
        # Save changes button
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button("💾 Save Changes", type="primary"):
                try:
                    with get_db_connection() as conn:
                        # Clear existing and insert updated data
                        if selected_category != 'All':
                            # Only update items in selected category
                            conn.execute("DELETE FROM menu_items WHERE category = ?", (selected_category,))
                        else:
                            # Update all items
                            conn.execute("DELETE FROM menu_items")
                        
                        # Insert edited data
                        for _, row in edited_df.iterrows():
                            conn.execute("""
                                INSERT INTO menu_items (category, dish_name, current_price, allergens, status, notes, modified_date)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (row['category'], row['dish_name'], row['current_price'], 
                                  row['allergens'], row['status'], row['notes'], str(date.today())))
                    
                    st.success("✅ Menu changes saved successfully!")
                    log_change("MENU_UPDATED", f"Updated {len(edited_df)} menu items")
                    clear_data_caches()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving changes: {e}")
        
        with col2:
            if st.button("🗑️ Delete Selected"):
                st.warning("Select items and confirm deletion")
        
        with col3:
            if st.button("📊 Export Menu"):
                # Export current menu to Excel
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    display_df.to_excel(writer, sheet_name='Current Menu', index=False)
                
                st.download_button(
                    label="📥 Download Excel",
                    data=excel_buffer.getvalue(),
                    file_name=f"menu_export_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

with tab2:
    st.subheader("Import Menu from Excel")
    st.write("📋 Upload an Excel file with your menu data. Format should match your existing structure:")
    
    # Show expected format
    with st.expander("📋 Expected Excel Format", expanded=False):
        example_data = {
            'Category': ['Starters', 'Starters', 'Mains'],
            'Dish Name': ['Fried Calamari', 'Ahi Tuna', 'Grilled Salmon'],
            'Current Price': [17.00, 17.00, 28.00],
            'Allergens': ['Shellfish, Dairy', 'Fish, Sesame, Soy', 'Fish'],
            'Keep, Remove or Modify?': ['Keep', 'Modify', 'Keep'],
            'Notes / Proposed Changes': ['', 'Switch back to steaks', '']
        }
        st.dataframe(pd.DataFrame(example_data))
    
    # File upload
    uploaded_menu_file = st.file_uploader(
        "Upload Menu Excel File", 
        type=["xlsx", "xls"],
        help="Excel file with menu items, pricing, and allergen information"
    )
    
    if uploaded_menu_file:
        # Sheet selection for menu files
        sheet_names = get_excel_sheet_names(uploaded_menu_file)
        if sheet_names and len(sheet_names) > 1:
            selected_menu_sheet = st.selectbox("Select Menu Sheet:", sheet_names)
        else:
            selected_menu_sheet = None
        
        menu_df_import = load_file_to_dataframe(uploaded_menu_file, selected_menu_sheet)
        
        if menu_df_import is not None:
            st.write("📋 Menu File Preview:")
            st.dataframe(menu_df_import.head())
            
            # Column mapping for menu import
            st.subheader("Map Menu Columns")
            menu_columns = [""] + menu_df_import.columns.tolist()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                category_col = st.selectbox("Category *", menu_columns)
                dish_col = st.selectbox("Dish Name *", menu_columns)
            with col2:
                price_col = st.selectbox("Price", menu_columns)
                allergen_col = st.selectbox("Allergens", menu_columns)
            with col3:
                status_col = st.selectbox("Status/Action", menu_columns)
                notes_col = st.selectbox("Notes", menu_columns)
            
            if st.button("Import Menu Items") and category_col and dish_col:
                try:
                    with get_db_connection() as conn:
                        imported_count = 0
                        
                        for _, row in menu_df_import.iterrows():
                            category = str(row[category_col]).strip() if category_col else "Uncategorized"
                            dish_name = str(row[dish_col]).strip() if dish_col else ""
                            price = float(row[price_col]) if price_col and pd.notna(row[price_col]) else 0.0
                            allergens = str(row[allergen_col]).strip() if allergen_col and pd.notna(row[allergen_col]) else ""
                            status = str(row[status_col]).strip() if status_col and pd.notna(row[status_col]) else "Keep"
                            notes = str(row[notes_col]).strip() if notes_col and pd.notna(row[notes_col]) else ""
                            
                            if dish_name:  # Only import if dish name exists
                                conn.execute("""
                                    INSERT OR REPLACE INTO menu_items 
                                    (category, dish_name, current_price, allergens, status, notes, modified_date)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (category, dish_name, price, allergens, status, notes, str(date.today())))
                                imported_count += 1
                        
                        conn.commit()
                    
                    st.success(f"🎉 Successfully imported {imported_count} menu items!")
                    log_change("MENU_IMPORTED", f"Imported {imported_count} menu items from {uploaded_menu_file.name}")
                    clear_data_caches()
                    
                except Exception as e:
                    st.error(f"Error importing menu: {e}")

with tab3:
    st.subheader("Menu Analysis")
    
    menu_analysis_df = pd_read_sql("SELECT * FROM menu_items")
    
    if not menu_analysis_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_items = len(menu_analysis_df)
            st.metric("📋 Total Items", total_items)
        
        with col2:
            avg_price = menu_analysis_df['current_price'].mean()
            st.metric("💰 Avg Price", f"${avg_price:.2f}")
        
        with col3:
            categories = menu_analysis_df['category'].nunique()
            st.metric("🏷️ Categories", categories)
        
        with col4:
            to_modify = len(menu_analysis_df[menu_analysis_df['status'] == 'Modify'])
            st.metric("⚠️ To Modify", to_modify)
        
        # Category breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Items by Category")
            category_counts = menu_analysis_df['category'].value_counts()
            st.bar_chart(category_counts)
        
        with col2:
            st.subheader("Status Distribution")
            status_counts = menu_analysis_df['status'].value_counts()
            st.bar_chart(status_counts)
        
        # Price analysis
        st.subheader("Price Analysis by Category")
        price_by_category = menu_analysis_df.groupby('category')['current_price'].agg(['mean', 'min', 'max']).round(2)
        st.dataframe(price_by_category)
    
    else:
        st.info("📊 Import menu items to see analysis")

with tab4:
    st.subheader("Allergen Management")
    
    allergen_df = pd_read_sql("SELECT * FROM menu_items WHERE allergens IS NOT NULL AND allergens != ''")
    
    if not allergen_df.empty:
        # Parse allergens and create summary
        all_allergens = []
        for allergens in allergen_df['allergens'].dropna():
            allergen_list = [a.strip() for a in str(allergens).split(',')]
            all_allergens.extend(allergen_list)
        
        allergen_counts = pd.Series(all_allergens).value_counts()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Most Common Allergens")
            st.bar_chart(allergen_counts.head(10))
        
        with col2:
            st.subheader("Items by Allergen")
            selected_allergen = st.selectbox("Select allergen to filter:", ["All"] + allergen_counts.index.tolist())
            
            if selected_allergen != "All":
                filtered_df = allergen_df[allergen_df['allergens'].str.contains(selected_allergen, na=False)]
                st.write(f"**{len(filtered_df)} items** contain {selected_allergen}:")
                st.dataframe(filtered_df[['category', 'dish_name', 'allergens']].reset_index(drop=True))
        
        # Allergen matrix
        st.subheader("Allergen Matrix")
        st.write("🔍 Items with multiple allergens:")
        multi_allergen_df = allergen_df[allergen_df['allergens'].str.contains(',')].copy()
        if not multi_allergen_df.empty:
            st.dataframe(multi_allergen_df[['category', 'dish_name', 'allergens']])
        else:
            st.info("No items with multiple allergens found")
            
    else:
        st.info("🏷️ Add allergen information to menu items to see analysis")

