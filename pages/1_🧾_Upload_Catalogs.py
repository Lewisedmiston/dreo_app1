import streamlit as st
import pandas as pd
from datetime import date
from common.utils import page_setup, load_file_to_dataframe, get_excel_sheet_names, detect_vendor_from_sheet_name
from common.settings import KNOWN_VENDORS
from common.db import execute_query, pd_read_sql, log_change, create_exception, get_db_connection, ensure_db_initialized
from common.etl import process_catalog_dataframe

# Ensure database is properly initialized before any operations
ensure_db_initialized()

page_setup("Upload Vendor Catalogs")

st.info("📊 Upload a vendor price sheet (CSV or Excel). Map the columns, preview the data, and import.")

# Cache vendor lookup for better performance
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_vendor_id(vendor_name):
    """Get vendor ID with caching to improve performance."""
    vendor = execute_query("SELECT id FROM vendors WHERE name = ?", (vendor_name,), fetch='one')
    if vendor:
        return vendor['id']
    return None

# --- 1. VENDOR SELECTION ---
st.subheader("1. Select Vendor")

# Auto-select vendor if detected from sheet
default_vendor_index = 0
if 'auto_detected_vendor' in st.session_state and st.session_state.auto_detected_vendor in KNOWN_VENDORS:
    default_vendor_index = KNOWN_VENDORS.index(st.session_state.auto_detected_vendor)
    st.info(f"🤖 Auto-selected **{st.session_state.auto_detected_vendor}** based on sheet detection")

vendor_name = st.selectbox("Choose a vendor for this catalog:", KNOWN_VENDORS, index=default_vendor_index)

# Get or create vendor_id with caching
if vendor_name:
    vendor_id = get_vendor_id(vendor_name)
    if not vendor_id:
        # Insert new vendor and get its ID
        vendor_id = execute_query("INSERT INTO vendors (name) VALUES (?)", (vendor_name,))
        st.success(f"✅ Added new vendor '{vendor_name}' to the database.")
        # Clear cache after adding new vendor
        get_vendor_id.clear()

# --- 2. FILE UPLOAD ---
st.subheader("2. Upload File")
uploaded_file = st.file_uploader("Drag and drop your file here or click to browse", type=["csv", "xlsx", "xls"])

if uploaded_file:
    # --- 2.5. SHEET SELECTION (for Excel files) ---
    selected_sheet = None
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        sheet_names = get_excel_sheet_names(uploaded_file)
        if sheet_names and len(sheet_names) > 1:
            st.subheader("2.5. Select Sheet")
            st.info(f"📊 Found {len(sheet_names)} sheets in your Excel file. Choose which one to import:")
            
            # Smart suggestions based on your real data patterns
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_sheet = st.selectbox(
                    "Choose sheet to import:", 
                    sheet_names,
                    format_func=lambda x: f"{x} → {detect_vendor_from_sheet_name(x)}"
                )
            with col2:
                if st.button("🔄 Refresh Sheets"):
                    # Clear session state cache for this file
                    file_hash = hash(uploaded_file.getvalue())
                    cache_key = f"sheets_{uploaded_file.name}_{file_hash}"
                    if cache_key in st.session_state:
                        del st.session_state[cache_key]
                    st.rerun()
            
            # Auto-detect and suggest vendor based on sheet name
            suggested_vendor = detect_vendor_from_sheet_name(selected_sheet)
            # Try to match with known vendors (case insensitive)
            matched_vendor = None
            for known_vendor in KNOWN_VENDORS:
                if suggested_vendor.lower() in known_vendor.lower() or known_vendor.lower() in suggested_vendor.lower():
                    matched_vendor = known_vendor
                    break
            
            if matched_vendor:
                st.success(f"💡 Auto-detected vendor: **{matched_vendor}** - auto-selecting!")
                # Store auto-detected vendor in session state and trigger rerun for immediate update
                if 'auto_detected_vendor' not in st.session_state or st.session_state.auto_detected_vendor != matched_vendor:
                    st.session_state.auto_detected_vendor = matched_vendor
                    st.rerun()
            else:
                st.info(f"💡 Detected: **{suggested_vendor}** (not in known vendors - please select manually)")
    
    df = load_file_to_dataframe(uploaded_file, selected_sheet)
    
    if df is not None:
        # Enhanced preview with sheet info
        preview_title = f"File Preview: {uploaded_file.name}"
        if selected_sheet:
            preview_title += f" → {selected_sheet} sheet"
        st.write(preview_title + " (first 5 rows):")
        st.dataframe(df.head())
        
        # Show additional file info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Total Rows", f"{len(df):,}")
        with col2:
            st.metric("📈 Columns", len(df.columns))
        with col3:
            if selected_sheet:
                st.metric("📋 Sheet", selected_sheet)

        # --- 3. SMART COLUMN MAPPING ---
        st.subheader("3. Smart Column Mapping")
        st.write("🤖 Auto-detected mappings based on your data patterns. Adjust if needed:")
        
        file_columns = [""] + df.columns.tolist()
        
        # Smart auto-detection based on your real data patterns
        auto_mappings = {
            'vendor_item_code': "",
            'description': "",
            'pack_size': "",
            'case_price': "",
            'date': "",
            'brand': "",
            'category': "",
            'par_level': "",
            'on_hand': ""
        }
        
        for col in df.columns:
            col_lower = str(col).lower().replace(' ', '_').replace('#', '').replace('_', '')
            if any(x in col_lower for x in ['item', 'sku', 'productid', 'code']):
                auto_mappings['vendor_item_code'] = col
            elif any(x in col_lower for x in ['description', 'productname', 'name', 'dish']):
                auto_mappings['description'] = col
            elif any(x in col_lower for x in ['pack', 'size', 'unit']) and 'price' not in col_lower:
                auto_mappings['pack_size'] = col
            elif any(x in col_lower for x in ['caseprice', 'price', 'cost', 'defaultprice']):
                auto_mappings['case_price'] = col
            elif any(x in col_lower for x in ['date', 'updated', 'pricedate']):
                auto_mappings['date'] = col
            elif any(x in col_lower for x in ['brand', 'manufacturer']):
                auto_mappings['brand'] = col
            elif any(x in col_lower for x in ['category', 'type', 'group']):
                auto_mappings['category'] = col
            elif any(x in col_lower for x in ['par', 'parlevel', 'minimum']):
                auto_mappings['par_level'] = col
            elif any(x in col_lower for x in ['onhand', 'stock', 'inventory', 'available']):
                auto_mappings['on_hand'] = col
        
        # Show auto-detected mappings
        detected_count = sum(1 for v in auto_mappings.values() if v)
        if detected_count > 0:
            st.success(f"✨ Auto-detected {detected_count} column mappings from your data!")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**📋 Required Fields**")
            code_col = st.selectbox(
                "Vendor Item Code *", 
                file_columns, 
                index=file_columns.index(auto_mappings['vendor_item_code']) if auto_mappings['vendor_item_code'] in file_columns else 0,
                help="Unique code/SKU for the item"
            )
            desc_col = st.selectbox(
                "Item Description *", 
                file_columns,
                index=file_columns.index(auto_mappings['description']) if auto_mappings['description'] in file_columns else 0,
                help="Name or description of the item"
            )
            pack_col = st.selectbox(
                "Pack/Size String *", 
                file_columns,
                index=file_columns.index(auto_mappings['pack_size']) if auto_mappings['pack_size'] in file_columns else 0,
                help="e.g., '6/5 lb' or '200 ct'"
            )
            
        with col2:
            st.markdown("**💰 Pricing & Dates**")
            price_col = st.selectbox(
                "Case Price *", 
                file_columns,
                index=file_columns.index(auto_mappings['case_price']) if auto_mappings['case_price'] in file_columns else 0,
                help="Price for the entire case"
            )
            date_col = st.selectbox(
                "Price Date", 
                file_columns,
                index=file_columns.index(auto_mappings['date']) if auto_mappings['date'] in file_columns else 0,
                help="Optional. Uses today's date if not provided"
            )
            
            # Optional fields based on your data
            st.markdown("**🏷️ Optional Fields**")
            brand_col = st.selectbox(
                "Brand", 
                [""] + [c for c in df.columns if c],
                index=file_columns.index(auto_mappings['brand']) if auto_mappings['brand'] in file_columns else 0,
                help="Brand/manufacturer"
            )
            
        with col3:
            st.markdown("**📦 Inventory Management**")
            category_col = st.selectbox(
                "Category", 
                [""] + [c for c in df.columns if c],
                index=file_columns.index(auto_mappings['category']) if auto_mappings['category'] in file_columns else 0,
                help="Product category/type"
            )
            par_col = st.selectbox(
                "Par Level", 
                [""] + [c for c in df.columns if c],
                index=file_columns.index(auto_mappings['par_level']) if auto_mappings['par_level'] in file_columns else 0,
                help="Minimum stock level"
            )
            onhand_col = st.selectbox(
                "On Hand Qty", 
                [""] + [c for c in df.columns if c],
                index=file_columns.index(auto_mappings['on_hand']) if auto_mappings['on_hand'] in file_columns else 0,
                help="Current inventory quantity"
            )
            order_col = st.selectbox(
                "Order Qty", 
                [""] + [c for c in df.columns if c],
                help="Quantity to order"
            )

        # --- 4. DATA VALIDATION ---
        if all([code_col, desc_col, pack_col, price_col]):
            st.subheader("4. Data Validation")
            
            # Quick validation preview
            missing_codes = df[code_col].isna().sum() if code_col else 0
            missing_prices = df[price_col].isna().sum() if price_col else 0
            invalid_prices = (pd.to_numeric(df[price_col], errors='coerce') <= 0).sum() if price_col else 0
            
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Total Rows", len(df))
            with col_b:
                st.metric("Missing Codes", missing_codes, delta=None if missing_codes == 0 else "⚠️")
            with col_c:
                st.metric("Invalid Prices", missing_prices + invalid_prices, delta=None if (missing_prices + invalid_prices) == 0 else "⚠️")
            
            if missing_codes > 0 or (missing_prices + invalid_prices) > 0:
                st.warning(f"⚠️ {missing_codes + missing_prices + invalid_prices} rows will be skipped due to missing/invalid data. Check the Exceptions page after import for details.")

        # --- 5. PROCESS & IMPORT ---
        if st.button("Process and Import Data", disabled=(not all([code_col, desc_col, pack_col, price_col]))):
            with st.spinner("Processing and validating data..."):
                # Add inventory columns to database if they don't exist
                with get_db_connection() as conn:
                    # Add new columns safely (will skip if they already exist)
                    try:
                        conn.execute("ALTER TABLE catalog_items ADD COLUMN brand TEXT")
                        conn.execute("ALTER TABLE catalog_items ADD COLUMN category TEXT") 
                        conn.execute("ALTER TABLE catalog_items ADD COLUMN par_level REAL")
                        conn.execute("ALTER TABLE catalog_items ADD COLUMN on_hand_qty REAL")
                        conn.execute("ALTER TABLE catalog_items ADD COLUMN order_qty REAL")
                        conn.commit()
                    except Exception:
                        pass  # Columns already exist
                
                # Enhanced column mapping including inventory fields
                column_mapping = {
                    code_col: "vendor_item_code",
                    desc_col: "item_description", 
                    pack_col: "pack_size_str",
                    price_col: "case_price",
                }
                
                # Add optional inventory columns if mapped
                if brand_col:
                    column_mapping[brand_col] = "brand"
                if category_col:
                    column_mapping[category_col] = "category"
                if par_col:
                    column_mapping[par_col] = "par_level"
                if onhand_col:
                    column_mapping[onhand_col] = "on_hand_qty"
                if order_col:
                    column_mapping[order_col] = "order_qty"
                
                df_mapped = df.rename(columns=column_mapping)
                
                # Handle date column with robust error handling
                if date_col and date_col != "":
                    try:
                        # First check if the column contains valid date-like values
                        sample_values = df[date_col].dropna().head().tolist()
                        if sample_values:
                            # Try to parse a sample value to validate it's actually a date column
                            pd.to_datetime(sample_values[0], errors='raise')
                            df_mapped['price_date'] = pd.to_datetime(df[date_col], errors='coerce').dt.date
                            # Replace any failed parsing with today's date
                            df_mapped['price_date'] = df_mapped['price_date'].fillna(date.today())
                        else:
                            df_mapped['price_date'] = date.today()
                    except (pd.errors.ParserError, ValueError, TypeError):
                        st.warning(f"The selected date column '{date_col}' doesn't contain valid dates. Using today's date instead.")
                        df_mapped['price_date'] = date.today()
                else:
                    df_mapped['price_date'] = date.today()

                # Filter to required and optional columns that exist in mapped data
                required_cols = ["vendor_item_code", "item_description", "pack_size_str", "case_price", "price_date"]
                optional_cols = ["brand", "category", "par_level", "on_hand_qty", "order_qty"]
                
                # Include only columns that exist in the mapped dataframe
                cols_to_process = required_cols + [col for col in optional_cols if col in df_mapped.columns]
                df_to_process = df_mapped[cols_to_process]
                total_rows = len(df_to_process)  # Track total for status messages

                # Pre-clean the dataframe before processing
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                status_text.text("Pre-validating data...")
                progress_bar.progress(0.1)
                
                # Remove rows with completely empty required fields at DataFrame level
                df_clean = df_to_process.copy()
                df_clean = df_clean.dropna(subset=['vendor_item_code', 'case_price'], how='any')
                df_clean = df_clean[df_clean['vendor_item_code'].astype(str).str.strip() != '']
                df_clean = df_clean[pd.to_numeric(df_clean['case_price'], errors='coerce') > 0]
                
                status_text.text(f"Processing {len(df_clean)} validated rows...")
                progress_bar.progress(0.2)
                
                df_processed = process_catalog_dataframe(df_clean, vendor_id)
                progress_bar.progress(0.6)
                
                # Populate vendor_name for all processed rows
                if not df_processed.empty:
                    df_processed['vendor_name'] = vendor_name
                    status_text.text(f"Successfully processed {len(df_processed)} of {total_rows} rows")
                progress_bar.progress(0.8)
                
                if not df_processed.empty:
                    st.write("Processed Data Preview (ready for import):")
                    st.dataframe(df_processed.head())

                    # Final validation before database insertion
                    status_text.text("Final validation before database import...")
                    
                    # Ensure absolutely no invalid data reaches the database
                    df_final = df_processed.copy()
                    initial_count = len(df_final)
                    
                    # Remove any rows with null or invalid required fields
                    df_final = df_final.dropna(subset=['price', 'price_date', 'item_number', 'vendor_id'])
                    df_final = df_final[df_final['price'] > 0]
                    df_final = df_final[df_final['price_date'].astype(str).str.strip() != '']
                    df_final = df_final[df_final['item_number'].astype(str).str.strip() != '']
                    
                    final_count = len(df_final)
                    if initial_count > final_count:
                        st.warning(f"⚠️ Final validation removed {initial_count - final_count} additional problematic rows")
                    
                    # Insert into database with optimized batch processing
                    try:
                        status_text.text(f"Importing {len(df_final)} validated items to database...")
                        with get_db_connection() as conn:
                            # Use chunked insertion for better performance with large files
                            chunk_size = 100
                            total_chunks = (len(df_final) + chunk_size - 1) // chunk_size
                            imported_count = 0
                            
                            for i, chunk_start in enumerate(range(0, len(df_final), chunk_size)):
                                chunk_end = min(chunk_start + chunk_size, len(df_final))
                                chunk_df = df_final.iloc[chunk_start:chunk_end]
                                
                                try:
                                    chunk_df.to_sql('catalog_items', conn, if_exists='append', index=False)
                                    imported_count += len(chunk_df)
                                    progress = 0.8 + (0.2 * (i + 1) / total_chunks)
                                    progress_bar.progress(progress)
                                    status_text.text(f"Imported {imported_count}/{len(df_final)} items...")
                                except Exception as chunk_error:
                                    if "UNIQUE constraint failed" in str(chunk_error):
                                        st.warning(f"⚠️ Some duplicate items were skipped in batch {i+1}")
                                        continue
                                    else:
                                        raise chunk_error
                            
                            log_change(
                                event_type='CATALOG_IMPORT', 
                                details=f"Imported {imported_count} items for vendor '{vendor_name}' from file '{uploaded_file.name}'."
                            )
                            progress_bar.progress(1.0)
                            status_text.text("✅ Import completed successfully!")
                            
                            # Show final results with enhanced feedback
                            skipped_rows = total_rows - len(df_processed)
                            if skipped_rows > 0:
                                st.success(f"✅ Successfully imported {imported_count} items! ({skipped_rows} rows skipped - check Exceptions page for details)")
                            else:
                                st.success(f"✅ Successfully imported all {imported_count} items!")
                            st.balloons()
                    except Exception as e:
                        progress_bar.progress(0)
                        status_text.text("❌ Import failed")
                        st.error(f"An error occurred during database import: {e}")
                        # Enhanced error guidance
                        if "UNIQUE constraint failed" in str(e):
                            st.info("💡 Tip: This data may already exist. Try using a different price date to update existing items.")
                        elif "NOT NULL constraint failed" in str(e):
                            st.info("💡 Tip: Some rows have missing required data. The app should have filtered these out - please report this issue.")
                        
                else:
                    st.warning("No rows were processed. Check the file for errors or see the Exceptions page for details on parsing failures.")

# --- Display latest imports ---
st.subheader("Recent Catalog Imports")
df_log = pd_read_sql("SELECT event_time, action, details FROM changelog WHERE action = 'CATALOG_IMPORT' ORDER BY event_time DESC LIMIT 10")
st.dataframe(df_log, use_container_width=True)

