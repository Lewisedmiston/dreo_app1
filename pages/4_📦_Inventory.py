import streamlit as st
from common.db import init_db
st.set_page_config(page_title="Inventory", layout="wide")
st.title("📦 Inventory (Phase 2 placeholder)")
init_db()
st.info("Inventory counts, waste/transfer, and cycle counts will live here in Phase 2.")
