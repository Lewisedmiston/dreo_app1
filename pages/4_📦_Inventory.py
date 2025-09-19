"""Touch-friendly inventory counting workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

import pandas as pd
import streamlit as st

from common.db import (
    INVENTORY_DIR,
    detect_unsaved_changes,
    latest_inventory,
    load_catalogs,
    read_table,
    toast_err,
    toast_info,
    toast_ok,
)

st.set_page_config(page_title="Inventory Count", layout="wide")

# ---------------------------------------------------------------------------
# Session state bootstrapping
# ---------------------------------------------------------------------------
if "inventory_draft" not in st.session_state:
    st.session_state.inventory_draft: Dict[str, int] = {}

if "inventory_last_saved" not in st.session_state:
    baseline: Dict[str, int] = {}
    last_snapshot = latest_inventory()
    if last_snapshot is not None and not last_snapshot.empty:
        if "item_key" in last_snapshot.columns and "quantity" in last_snapshot.columns:
            baseline = {
                str(row["item_key"]): int(row["quantity"])
                for _, row in last_snapshot.iterrows()
                if row.get("quantity", 0)
            }
    st.session_state.inventory_last_saved = baseline


# ---------------------------------------------------------------------------
# Load source data
# ---------------------------------------------------------------------------
catalogs = load_catalogs()
ingredients = read_table("ingredient_master")

if ingredients.empty and catalogs.empty:
    st.error("No catalog or ingredient data found. Upload catalogs to get started.")
    st.stop()

if ingredients.empty:
    base_df = catalogs.copy()
else:
    base_df = ingredients.copy()

# Normalise columns expected by the UI
if "description" not in base_df.columns and "item_description" in base_df.columns:
    base_df = base_df.rename(columns={"item_description": "description"})

if "uom" not in base_df.columns:
    for candidate in ("count_uom", "default_uom", "pack_uom"):
        if candidate in base_df.columns:
            base_df["uom"] = base_df[candidate]
            break
    else:
        base_df["uom"] = "ea"

if "vendor" not in base_df.columns:
    if not catalogs.empty and "vendor" in catalogs.columns:
        merged = catalogs[["vendor", "item_number", "description"]].drop_duplicates()
        base_df = base_df.merge(merged, on=["item_number", "description"], how="left")
    else:
        base_df["vendor"] = base_df.get("preferred_vendor", "Vendor")

if "item_number" not in base_df.columns:
    base_df["item_number"] = base_df.get("sku", base_df.get("id", base_df.index))

if "location" not in base_df.columns:
    base_df["location"] = "Walk-in"

if "barcode" not in base_df.columns:
    base_df["barcode"] = ""

base_df = base_df.fillna({"location": "Walk-in", "uom": "ea", "vendor": "Vendor", "barcode": ""})
base_df["item_key"] = base_df.apply(
    lambda row: f"{row.get('vendor', 'Vendor')}::{row.get('item_number', row.name)}", axis=1
)

# ---------------------------------------------------------------------------
# Filters and search
# ---------------------------------------------------------------------------
st.title("📦 Inventory Count")

cols = st.columns([3, 1])
with cols[0]:
    st.caption("Big tap targets for fast counts. Filters update instantly.")
with cols[1]:
    st.write("")
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("Home.py")

locations = sorted(base_df["location"].dropna().unique().tolist())
location_choice = st.segmented_control("Location", ["All"] + locations, default="All")
search_term = st.text_input("Search or scan (SKU, description, barcode)", placeholder="Type or scan barcode...")

filtered = base_df.copy()
if location_choice != "All":
    filtered = filtered[filtered["location"] == location_choice]

if search_term:
    term = search_term.lower().strip()
    filtered = filtered[
        filtered.apply(
            lambda row: term in str(row.get("description", "")).lower()
            or term in str(row.get("item_number", "")).lower()
            or term in str(row.get("barcode", "")).lower(),
            axis=1,
        )
    ]

if filtered.empty:
    st.info("No items match the current filters.")
    st.stop()

unsaved = detect_unsaved_changes(st.session_state.inventory_draft, st.session_state.inventory_last_saved)
if unsaved:
    st.markdown("<span style='color:#ffa000;font-weight:600;'>Unsaved changes</span>", unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# Item list
# ---------------------------------------------------------------------------
for _, item in filtered.iterrows():
    item_key = str(item["item_key"])
    current_qty = int(st.session_state.inventory_draft.get(item_key, 0))

    info_col, minus_col, qty_col, plus_col = st.columns([4, 1, 1.2, 1])

    with info_col:
        extra = f" • {item['barcode']}" if item.get("barcode") else ""
        st.markdown(
            f"**{item.get('description', 'Item')}**\n"
            f"<span style='color:#666;'>{item.get('vendor', 'Vendor')} • {item.get('uom', 'ea')} • {item.get('location', '')}{extra}</span>",
            unsafe_allow_html=True,
        )

    with minus_col:
        if st.button("➖", key=f"minus_{item_key}", use_container_width=True):
            st.session_state.inventory_draft[item_key] = max(0, current_qty - 1)
            st.rerun()

    state_key = f"qty_{item_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = current_qty

    with qty_col:
        qty_val = st.number_input(
            "Quantity",
            key=state_key,
            min_value=0,
            step=1,
            value=current_qty,
            label_visibility="collapsed",
        )
        if qty_val != current_qty:
            st.session_state.inventory_draft[item_key] = int(qty_val)

    with plus_col:
        if st.button("➕", key=f"plus_{item_key}", use_container_width=True):
            st.session_state.inventory_draft[item_key] = current_qty + 1
            st.rerun()

    st.divider()

# ---------------------------------------------------------------------------
# Sticky action bar
# ---------------------------------------------------------------------------
counts = {k: v for k, v in st.session_state.inventory_draft.items() if v}
item_count = len(counts)
unit_total = sum(counts.values())

st.markdown(
    """
    <div style="position:sticky;bottom:0;background:var(--background-color,#ffffff);padding:1rem;border-top:1px solid #eee;">
      <div style="display:flex;gap:1rem;flex-wrap:wrap;align-items:center;">
        <div><strong>Draft:</strong> {items} items • {units} units</div>
      </div>
    </div>
    """.format(items=item_count, units=unit_total),
    unsafe_allow_html=True,
)

with st.form("inventory_actions"):
    btn_cols = st.columns([1, 1, 1])
    save_clicked = btn_cols[0].form_submit_button("💾 Save Draft", use_container_width=True)
    submit_clicked = btn_cols[1].form_submit_button("✅ Submit Count", use_container_width=True)
    clear_clicked = btn_cols[2].form_submit_button("🗑️ Clear", use_container_width=True)

    if save_clicked:
        toast_ok("Draft saved in this session")

    if submit_clicked:
        if not counts:
            toast_err("No quantities entered yet.")
        else:
            indexed = base_df.set_index("item_key")
            records = []
            for key, qty in counts.items():
                if key in indexed.index:
                    meta = indexed.loc[key]
                else:
                    meta = {}
                records.append(
                    {
                        "item_key": key,
                        "quantity": qty,
                        "counted_at": datetime.now().isoformat(),
                        "location": meta.get("location", location_choice),
                        "description": meta.get("description", ""),
                        "uom": meta.get("uom", "ea"),
                        "vendor": meta.get("vendor", ""),
                        "barcode": meta.get("barcode", ""),
                    }
                )

            submitted_df = pd.DataFrame(records)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = INVENTORY_DIR / f"{timestamp}.csv"
            submitted_df.to_csv(file_path, index=False)
            st.session_state.inventory_last_saved = counts.copy()
            toast_ok(f"Snapshot saved ({item_count} items)")
            st.session_state.inventory_draft = {}
            st.experimental_set_query_params(last_snapshot=file_path.name)
            st.rerun()

    if clear_clicked:
        st.session_state.inventory_draft = {}
        toast_info("Counts cleared")
        st.rerun()

# ---------------------------------------------------------------------------
# Summary when a snapshot is present
# ---------------------------------------------------------------------------
params = st.experimental_get_query_params()
if "last_snapshot" in params:
    latest_file_name = params["last_snapshot"][0]
    file_path = INVENTORY_DIR / latest_file_name
    if file_path.exists():
        summary_df = pd.read_csv(file_path)
        total_units = int(summary_df["quantity"].sum()) if "quantity" in summary_df.columns else 0
        st.success(f"Last snapshot: {latest_file_name} • {len(summary_df)} lines • {total_units} units")
        st.download_button(
            "⬇️ Download snapshot CSV",
            data=summary_df.to_csv(index=False).encode("utf-8"),
            file_name=latest_file_name,
            mime="text/csv",
        )
