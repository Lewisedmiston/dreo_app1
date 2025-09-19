"""Maintain ingredient metadata and vendor linkage."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from common.db import load_catalogs, read_table, toast_info, toast_ok, write_table

st.set_page_config(page_title="Ingredient Master", layout="wide")

st.title("🧴 Ingredient Master")
st.caption("Keep ingredient UOMs, vendor SKUs, and par levels in sync.")

catalogs = load_catalogs()
ingredients = read_table("ingredient_master")

columns = [
    "description",
    "vendor",
    "item_number",
    "count_uom",
    "case_pack",
    "case_uom",
    "case_cost",
    "cost_per_count",
    "location",
    "par",
    "on_hand",
    "barcode",
]

if ingredients.empty:
    ingredients = pd.DataFrame(columns=columns)

for col in columns:
    if col not in ingredients.columns:
        ingredients[col] = ""

numeric_cols = ["case_pack", "case_cost", "par", "on_hand"]
for col in numeric_cols:
    ingredients[col] = pd.to_numeric(ingredients[col], errors="coerce")

if "cost_per_count" not in ingredients.columns:
    ingredients["cost_per_count"] = 0.0

st.subheader("Edit ingredients")

column_config = {
    "description": st.column_config.TextColumn("Description", help="What the kitchen calls it"),
    "vendor": st.column_config.TextColumn("Vendor"),
    "item_number": st.column_config.TextColumn("Vendor SKU"),
    "count_uom": st.column_config.TextColumn("Count UOM"),
    "case_pack": st.column_config.NumberColumn("Case Pack", step=1),
    "case_uom": st.column_config.TextColumn("Case UOM"),
    "case_cost": st.column_config.NumberColumn("Case Cost", format="$%.2f"),
    "cost_per_count": st.column_config.NumberColumn("Cost / Count", format="$%.4f", disabled=True),
    "location": st.column_config.TextColumn("Location"),
    "par": st.column_config.NumberColumn("Par", step=1),
    "on_hand": st.column_config.NumberColumn("On Hand", step=1),
    "barcode": st.column_config.TextColumn("Barcode/UPC"),
}

edited = st.data_editor(
    ingredients,
    column_config=column_config,
    num_rows="dynamic",
    use_container_width=True,
    key="ingredient_editor",
)

edited_df = pd.DataFrame(edited)
for col in numeric_cols:
    edited_df[col] = pd.to_numeric(edited_df[col], errors="coerce").fillna(0.0)

edited_df["cost_per_count"] = edited_df.apply(
    lambda row: (row["case_cost"] / row["case_pack"]) if row.get("case_pack") not in (0, None) else row["case_cost"],
    axis=1,
)

if st.button("💾 Save Ingredient Master", type="primary"):
    write_table("ingredient_master", edited_df)
    toast_ok("Ingredient master saved")

csv_bytes = edited_df.to_csv(index=False).encode("utf-8")
excel_buffer = io.BytesIO()
with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
    edited_df.to_excel(writer, index=False, sheet_name="Ingredients")

st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="ingredient_master.csv", mime="text/csv")
st.download_button(
    "⬇️ Download XLSX",
    data=excel_buffer.getvalue(),
    file_name="ingredient_master.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

if catalogs.empty:
    toast_info("Upload catalogs to unlock vendor suggestions.")
