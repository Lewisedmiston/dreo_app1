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

st.info("Upload a vendor price sheet (CSV or Excel). Map the columns, preview the data, and import.")

# --- 1. VENDOR SELECTION ---
st.subheader("1. Select Vendor")
vendor_name = st.selectbox("Choose a vendor for this catalog:", KNOWN_VENDORS)

# Get or create vendor_id
if vendor_name:
    vendor = execute_query("SELECT id FROM vendors WHERE name = ?", (vendor_name,), fetch='one')
    if vendor:
        vendor_id = vendor['id']
    else:
        # Insert new vendor and get its ID
        vendor_id = execute_query("INSERT INTO vendors (name) VALUES (?)", (vendor_name,))
        st.success(f"Added new vendor '{vendor_name}' to the database.")

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

        # --- 4. PROCESS & IMPORT ---
        if st.button("Process and Import Data", disabled=(not all([code_col, desc_col, pack_col, price_col]))):
            with st.spinner("Processing..."):
                # Rename columns based on mapping
                df_mapped = df.rename(columns={
                    code_col: "vendor_item_code",
                    desc_col: "item_description",
                    pack_col: "pack_size_str",
                    price_col: "case_price",
                })
                
                # Handle date column
                if date_col:
                    df_mapped['price_date'] = pd.to_datetime(df[date_col]).dt.date
                else:
                    df_mapped['price_date'] = date.today()

                # Filter to only necessary columns
                required_cols = ["vendor_item_code", "item_description", "pack_size_str", "case_price", "price_date"]
                df_to_process = df_mapped[required_cols]

                # Process the dataframe using ETL logic
                df_processed = process_catalog_dataframe(df_to_process, vendor_id)
                
                # Populate vendor_name for all processed rows
                if not df_processed.empty:
                    df_processed['vendor_name'] = vendor_name
                
                if not df_processed.empty:
                    st.write("Processed Data Preview (ready for import):")
                    st.dataframe(df_processed.head())

                    # Insert into database
                    try:
                        with st.spinner("Importing to database..."), get_db_connection() as conn:
                            df_processed.to_sql('catalog_items', conn, if_exists='append', index=False)
                            
                            log_change(
                                event_type='CATALOG_IMPORT', 
                                details=f"Imported {len(df_processed)} items for vendor '{vendor_name}' from file '{uploaded_file.name}'."
                            )
                            st.success(f"Successfully imported {len(df_processed)} items!")
                            st.balloons()
                    except Exception as e:
                        st.error(f"An error occurred during database import: {e}")
                        # Check for constraint errors specifically
                        if "UNIQUE constraint failed" in str(e):
                            st.warning("It looks like some of this data (vendor, item code, date) already exists in the database. Duplicate rows were ignored.")
                        
                else:
                    st.warning("No rows were processed. Check the file for errors or see the Exceptions page for details on parsing failures.")

# --- Display latest imports ---
st.subheader("Recent Catalog Imports")
df_log = pd_read_sql("SELECT event_time, action, details FROM changelog WHERE action = 'CATALOG_IMPORT' ORDER BY event_time DESC LIMIT 10")
st.dataframe(df_log, use_container_width=True)

