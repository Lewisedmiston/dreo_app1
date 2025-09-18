import streamlit as st
import pandas as pd
from datetime import date
from common.utils import page_setup, load_file_to_dataframe
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
vendor_name = st.selectbox("Choose a vendor for this catalog:", KNOWN_VENDORS)

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
    df = load_file_to_dataframe(uploaded_file)
    
    if df is not None:
        st.write("File Preview (first 5 rows):")
        st.dataframe(df.head())

        # --- 3. COLUMN MAPPING ---
        st.subheader("3. Map Columns")
        st.write("Match the columns from your file to the required fields.")
        
        file_columns = [""] + df.columns.tolist()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            code_col = st.selectbox("Vendor Item Code *", file_columns, help="Unique code for the item from the vendor.")
            desc_col = st.selectbox("Item Description *", file_columns, help="The name or description of the item.")
        with col2:
            pack_col = st.selectbox("Pack/Size String *", file_columns, help="e.g., '6/5 lb' or '200 ct'.")
            price_col = st.selectbox("Case Price *", file_columns, help="The price for the entire case.")
        with col3:
            date_col = st.selectbox("Price Date", file_columns, help="Optional. If not provided, today's date will be used.")

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
                # Rename columns based on mapping
                df_mapped = df.rename(columns={
                    code_col: "vendor_item_code",
                    desc_col: "item_description",
                    pack_col: "pack_size_str",
                    price_col: "case_price",
                })
                
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

                # Filter to only necessary columns
                required_cols = ["vendor_item_code", "item_description", "pack_size_str", "case_price", "price_date"]
                df_to_process = df_mapped[required_cols]

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

