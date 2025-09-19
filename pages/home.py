# Home.py
import streamlit as st

from common.db import available_vendors, load_catalogs, read_table

DEFAULT_VENDORS = ["PFG", "Sysco", "Produce"]
st.set_page_config(page_title="Dreo Kitchen Ops", layout="wide")
st.title("Dreo Kitchen Ops")

st.caption("Quick access to your daily tools. Use the sidebar anytime.")

catalogs = load_catalogs()
ingredient_master = read_table("ingredient_master")
vendor_names = available_vendors(catalogs, ingredient_master, defaults=DEFAULT_VENDORS)
vendor_metric = " • ".join(vendor_names) if vendor_names else "—"

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Vendors", vendor_metric)
with c2: st.metric("Active SKUs", "—")
with c3: st.metric("Open Orders", "—")

st.subheader("Jump to a module")
st.page_link("pages/1_📄_Upload_Catalogs.py", label="Upload Vendor Catalogs")
st.page_link("pages/2_🧴_Ingredient_Master.py", label="Ingredient Master")
st.page_link("pages/3_👨‍🍳_Recipes.py", label="Recipes")
st.page_link("pages/4_📦_Inventory.py", label="Inventory")
st.page_link("pages/5_🧾_Ordering.py", label="Ordering")
st.page_link("pages/6_📊_Summary.py", label="Summary")
st.page_link("pages/7_🚨_Exceptions_QA.py", label="Exceptions / QA")
st.page_link("pages/8_⬇️_Export.py", label="Export")