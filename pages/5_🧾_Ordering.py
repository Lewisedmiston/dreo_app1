import streamlit as st
from common.db import init_db
st.set_page_config(page_title="Ordering", layout="wide")
st.title("🧾 Ordering / POs (Phase 2 placeholder)")
init_db()
st.info("PAR-based PO generation and receiving updates will live here in Phase 2.")
