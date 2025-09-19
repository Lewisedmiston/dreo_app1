"""Catalog upload pipeline with preset mappings and dedupe logic."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from common.db import read_table, toast_err, toast_info, toast_ok, write_table, safe_parse_date
from common.presets import load_presets

st.set_page_config(page_title="Upload Catalogs", layout="wide")

st.title("📄 Upload Vendor Catalogs")
st.caption("Map vendor files to the standard schema, dedupe, and save.")

presets = load_presets()
vendors = sorted(presets.keys()) or ["PFG", "Sysco", "Produce"]
selected_vendor = st.selectbox("Vendor", vendors, index=max(vendors.index("PFG") if "PFG" in vendors else 0, 0))
preset = presets.get(selected_vendor, {})

uploaded_file = st.file_uploader("Drop CSV/XLSX", type=["csv", "xlsx", "xls"])

if not uploaded_file:
    st.info("Upload a file to begin.")
    st.stop()

content = uploaded_file.getvalue()
file_ext = Path(uploaded_file.name).suffix.lower()
raw_df: pd.DataFrame

if file_ext in {".xlsx", ".xls"}:
    excel_buffer = io.BytesIO(content)
    xls = pd.ExcelFile(excel_buffer)
    sheet_name = xls.sheet_names[0]
    if len(xls.sheet_names) > 1:
        sheet_name = st.selectbox("Sheet", xls.sheet_names)
    raw_df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name)
else:
    raw_df = pd.read_csv(io.BytesIO(content))

if raw_df.empty:
    toast_err("Uploaded file is empty.")
    st.stop()

st.subheader("Step 1 • Map columns")
required_fields = ["item_number", "description", "uom", "case_cost", "price_date"]
optional_fields = ["brand", "pack_size", "category", "barcode"]

mapping_defaults = preset.get("map", {})

mapped_columns: dict[str, str] = {}
for field in required_fields + optional_fields:
    options = ["--"] + list(raw_df.columns)
    default_column = mapping_defaults.get(field, "--")
    if default_column not in options:
        default_column = "--"
    selection = st.selectbox(
        f"{field.replace('_', ' ').title()}",
        options,
        index=options.index(default_column),
        key=f"mapping_{field}",
    )
    if selection != "--":
        mapped_columns[field] = selection

missing_required = [field for field in required_fields if field not in mapped_columns]
if missing_required:
    st.warning(f"Map required fields: {', '.join(missing_required)}")
    st.stop()

st.subheader("Step 2 • Preview & clean")

normalized = pd.DataFrame()
normalized["vendor"] = selected_vendor
for field in required_fields + optional_fields:
    column = mapped_columns.get(field)
    if column:
        normalized[field] = raw_df[column]
    else:
        normalized[field] = ""

normalized["case_cost"] = pd.to_numeric(normalized["case_cost"], errors="coerce").fillna(0.0)
parsed_dates = normalized["price_date"].apply(lambda x: safe_parse_date(x, default=date.today()))
normalized["price_date"] = parsed_dates.dt.strftime("%Y-%m-%d")
missing_dates = (parsed_dates.dt.date == date.today()) & (~raw_df[mapped_columns["price_date"]].notna())
if missing_dates.any():
    toast_info(f"{missing_dates.sum()} rows missing price_date; defaulted to today.")

normalized = normalized.fillna("")
normalized["item_number"] = normalized["item_number"].astype(str).str.strip()
normalized = normalized[normalized["item_number"] != ""]

if normalized.empty:
    toast_err("No rows after mapping. Check your column selections.")
    st.stop()

normalized["price_date_parsed"] = pd.to_datetime(normalized["price_date"])
normalized = normalized.sort_values("price_date_parsed", ascending=False)
normalized = normalized.drop_duplicates(subset=["vendor", "item_number"], keep="first")

preview_cols = ["item_number", "description", "uom", "case_cost", "price_date", "brand", "pack_size", "category", "barcode"]
st.dataframe(normalized[preview_cols], use_container_width=True, hide_index=True)

existing = read_table(f"catalogs/{selected_vendor.lower()}")
existing_numbers = set(existing["item_number"].astype(str)) if not existing.empty and "item_number" in existing.columns else set()
created_count = len(set(normalized["item_number"]) - existing_numbers) if existing_numbers else normalized.shape[0]
updated_count = 0
if not existing.empty:
    merged = normalized.merge(
        existing,
        on="item_number",
        how="inner",
        suffixes=("_new", "_old"),
    )
    if not merged.empty:
        merged["price_date_new"] = pd.to_datetime(merged["price_date_new"])
        merged["price_date_old"] = pd.to_datetime(merged["price_date_old"])
        updated_mask = (
            (merged["case_cost_new"].round(4) != merged["case_cost_old"].round(4))
            | (merged["price_date_new"] > merged["price_date_old"])
        )
        updated_count = int(updated_mask.sum())

st.info(f"Preview: {normalized.shape[0]} rows • {created_count} new • {updated_count} updated")

csv_preview = normalized.drop(columns=["price_date_parsed"])
st.download_button(
    "⬇️ Download preview CSV",
    data=csv_preview.to_csv(index=False).encode("utf-8"),
    file_name=f"{selected_vendor.lower()}_preview.csv",
    mime="text/csv",
)

commit = st.button("✅ Commit to catalog", type="primary")
if commit:
    combined = pd.concat([existing, csv_preview], ignore_index=True)
    combined["price_date"] = pd.to_datetime(combined["price_date"])
    combined = combined.sort_values("price_date", ascending=False)
    combined = combined.drop_duplicates(subset=["vendor", "item_number"], keep="first")
    combined["price_date"] = combined["price_date"].dt.strftime("%Y-%m-%d")
    write_table(f"catalogs/{selected_vendor.lower()}", combined)
    toast_ok(f"Catalog saved • {created_count} new • {updated_count} updated")
    st.session_state.pop("catalog_upload", None)
    st.rerun()
