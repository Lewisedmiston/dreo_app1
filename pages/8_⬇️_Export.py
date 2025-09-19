"""Centralised export surface for the file-backed data store."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from common.db import CATALOGS_DIR, INVENTORY_DIR, ORDERS_DIR, latest_file, read_table

st.set_page_config(page_title="Export", layout="wide")

st.title("⬇️ Export Data")
st.caption("Grab the latest ingredient master, counts, orders, or vendor catalogs.")

# Ingredient master -----------------------------------------------------------------
ingredients = read_table("ingredient_master")
if ingredients.empty:
    st.warning("Ingredient master is empty — add records first.")
else:
    st.subheader("Ingredient Master")
    csv_bytes = ingredients.to_csv(index=False).encode("utf-8")
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        ingredients.to_excel(writer, index=False, sheet_name="Ingredients")
    st.download_button("⬇️ Ingredient master CSV", data=csv_bytes, file_name="ingredient_master.csv", mime="text/csv")
    st.download_button(
        "⬇️ Ingredient master XLSX",
        data=excel_buffer.getvalue(),
        file_name="ingredient_master.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# Latest inventory ------------------------------------------------------------------
latest_inventory_path = latest_file(INVENTORY_DIR)
if latest_inventory_path:
    st.subheader("Latest Inventory Count")
    inv_df = pd.read_csv(latest_inventory_path)
    st.write(f"Snapshot: {latest_inventory_path.name} • {inv_df.shape[0]} lines")
    st.download_button(
        "⬇️ Download inventory CSV",
        data=inv_df.to_csv(index=False).encode("utf-8"),
        file_name=latest_inventory_path.name,
        mime="text/csv",
    )
else:
    st.info("No inventory snapshots yet.")

# Latest order ----------------------------------------------------------------------
latest_order_path = latest_file(ORDERS_DIR)
if latest_order_path:
    st.subheader("Latest Order")
    order_df = pd.read_csv(latest_order_path)
    st.write(f"Export: {latest_order_path.name} • {order_df.shape[0]} lines")
    st.download_button(
        "⬇️ Download order CSV",
        data=order_df.to_csv(index=False).encode("utf-8"),
        file_name=latest_order_path.name,
        mime="text/csv",
    )
else:
    st.info("No order exports yet.")

# Catalogs --------------------------------------------------------------------------
st.subheader("Vendor Catalogs")
catalog_files = sorted(CATALOGS_DIR.glob("*.csv"))
if not catalog_files:
    st.info("No catalogs saved yet.")
else:
    for catalog_file in catalog_files:
        st.write(f"{catalog_file.name}")
        catalog_df = pd.read_csv(catalog_file)
        st.download_button(
            f"⬇️ Download {catalog_file.stem} catalog",
            data=catalog_df.to_csv(index=False).encode("utf-8"),
            file_name=catalog_file.name,
            mime="text/csv",
            key=f"catalog_{catalog_file.stem}",
        )
