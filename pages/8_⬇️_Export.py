
import streamlit as st
from common.db import init_db
from common.excel_export import export_workbook

st.set_page_config(page_title="Export", layout="wide")
st.title("⬇️ Export")

init_db()

if st.button("Generate Excel Workbook", type="primary"):
    path = export_workbook("Menu_Costing_DREO.xlsx")
    st.success("Workbook generated.")
    with open(path, "rb") as f:
        st.download_button("Download Menu_Costing_DREO.xlsx", f, file_name="Menu_Costing_DREO.xlsx")
