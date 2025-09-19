"""Vendor ordering workflow with sticky cart."""

from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st

from common.db import ORDERS_DIR, load_catalogs, read_table, toast_err, toast_info, toast_ok

st.set_page_config(page_title="Build Order", layout="wide")

if "order_cart" not in st.session_state:
    st.session_state.order_cart = {}
if "order_vendor" not in st.session_state:
    st.session_state.order_vendor = "PFG"

st.title("🧾 Build Order")

top_cols = st.columns([3, 1])
with top_cols[0]:
    st.caption("Tap to add cases, long press the ••• popover for manual entry.")
with top_cols[1]:
    st.write("")
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("Home.py")

vendors = ["PFG", "Sysco", "Produce"]
st.session_state.order_vendor = st.segmented_control(
    "Vendor", vendors, default=st.session_state.order_vendor
)

search_term = st.text_input("Search items", placeholder="Item, SKU, barcode")

catalogs = load_catalogs()
ingredients = read_table("ingredient_master")

if catalogs.empty and ingredients.empty:
    st.error("No data to build an order. Upload catalogs first.")
    st.stop()

vendor = st.session_state.order_vendor

if not catalogs.empty and "vendor" in catalogs.columns:
    vendor_catalog = catalogs[catalogs["vendor"].str.contains(vendor, case=False, na=False)]
else:
    vendor_catalog = pd.DataFrame()

if not ingredients.empty and "vendor" in ingredients.columns:
    vendor_items = ingredients[ingredients["vendor"].str.contains(vendor, case=False, na=False, regex=False)].copy()
else:
    vendor_items = pd.DataFrame()

if vendor_items.empty and vendor_catalog.empty:
    st.warning(f"No mapped items for {vendor}. Add them in the Ingredient Master.")
    st.stop()

if vendor_items.empty and not vendor_catalog.empty:
    vendor_items = vendor_catalog.copy()

if "description" not in vendor_items.columns and "item_description" in vendor_items.columns:
    vendor_items = vendor_items.rename(columns={"item_description": "description"})

if "uom" not in vendor_items.columns:
    for candidate in ("count_uom", "default_uom", "pack_uom"):
        if candidate in vendor_items.columns:
            vendor_items["uom"] = vendor_items[candidate]
            break
    else:
        vendor_items["uom"] = vendor_items.get("uom", "cs")

if "case_cost" not in vendor_items.columns and not vendor_catalog.empty:
    vendor_items = vendor_items.merge(
        vendor_catalog[["item_number", "case_cost", "pack_size", "uom"]],
        on="item_number",
        how="left",
        suffixes=("", "_cat"),
    )

vendor_items["par"] = vendor_items.get("par", 0).fillna(0)
vendor_items["on_hand"] = vendor_items.get("on_hand", 0).fillna(0)

vendor_items["suggested"] = (vendor_items["par"] - vendor_items["on_hand"]).clip(lower=0)

if search_term:
    term = search_term.lower().strip()
    vendor_items = vendor_items[
        vendor_items.apply(
            lambda row: term in str(row.get("description", "")).lower()
            or term in str(row.get("item_number", "")).lower()
            or term in str(row.get("barcode", "")).lower(),
            axis=1,
        )
    ]

if vendor_items.empty:
    st.info("No items match your filters.")
    st.stop()

st.subheader(f"{vendor} order guide")

order_records = []

for _, row in vendor_items.iterrows():
    item_key = f"{vendor}::{row.get('item_number', row.name)}"
    current_qty = int(st.session_state.order_cart.get(item_key, 0))
    pack = row.get("pack_size") or row.get("pack_size_str") or row.get("pack") or ""
    uom = row.get("uom", "cs")
    price = float(row.get("case_cost", 0) or 0)
    par = float(row.get("par", 0) or 0)
    on_hand = float(row.get("on_hand", 0) or 0)
    suggested = max(par - on_hand, 0)

    info_col, actions_col, qty_col, popover_col = st.columns([4, 1, 1, 0.6])

    with info_col:
        st.markdown(
            f"**{row.get('description', 'Item')}**\n"
            f"<span style='color:#666;'>SKU {row.get('item_number', '')} • {pack or uom} • ${price:,.2f}</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"Par {par:g} / On hand {on_hand:g} ➜ Suggested {suggested:g}")

    with actions_col:
        if st.button("➖", key=f"minus_order_{item_key}", use_container_width=True):
            st.session_state.order_cart[item_key] = max(0, current_qty - 1)
            st.rerun()

    qty_state_key = f"order_qty_{item_key}"
    if qty_state_key not in st.session_state:
        st.session_state[qty_state_key] = current_qty

    with qty_col:
        st.metric("Qty", current_qty)

    with popover_col:
        with st.popover("•••", use_container_width=True):
            value = st.number_input(
                "Order qty",
                min_value=0,
                step=1,
                key=qty_state_key,
                value=current_qty,
            )
            if value != current_qty:
                st.session_state.order_cart[item_key] = int(value)
                st.session_state[qty_state_key] = int(value)
                st.rerun()
        if st.button("➕", key=f"plus_order_{item_key}", use_container_width=True):
            st.session_state.order_cart[item_key] = current_qty + 1
            st.rerun()

    order_records.append(
        {
            "vendor": vendor,
            "item_number": row.get("item_number"),
            "description": row.get("description", ""),
            "pack_uom": pack or uom,
            "par": par,
            "on_hand": on_hand,
            "suggested": suggested,
            "order_qty": st.session_state.order_cart.get(item_key, 0),
            "case_cost": price,
        }
    )

    st.divider()

order_df = pd.DataFrame(order_records)
order_df["line_total"] = order_df["order_qty"] * order_df["case_cost"]

active_lines = order_df[order_df["order_qty"] > 0]
line_count = int(active_lines.shape[0])
est_total = float(active_lines["line_total"].sum())

st.markdown(
    f"<div style='position:sticky;bottom:0;background:var(--background-color,#fff);padding:1rem;border-top:1px solid #eee;'>"
    f"<strong>Cart:</strong> {line_count} lines • ${est_total:,.2f}</div>",
    unsafe_allow_html=True,
)

with st.form("order_actions"):
    col1, col2, col3 = st.columns([1, 1, 1])
    save_clicked = col1.form_submit_button("💾 Save Draft", use_container_width=True)
    export_clicked = col2.form_submit_button("📤 Export Order", use_container_width=True)
    clear_clicked = col3.form_submit_button("🗑️ Clear Cart", use_container_width=True)

    if save_clicked:
        toast_info("Draft saved — quantities stay in session.")

    if export_clicked:
        if active_lines.empty:
            toast_err("Add at least one line to export.")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"{timestamp}_{vendor.lower()}"
            csv_path = ORDERS_DIR / f"{base_name}.csv"
            xlsx_path = ORDERS_DIR / f"{base_name}.xlsx"
            ORDERS_DIR.mkdir(parents=True, exist_ok=True)
            csv_bytes = active_lines.to_csv(index=False).encode("utf-8")
            with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
                active_lines.to_excel(writer, index=False, sheet_name="Order")
                workbook = writer.book
                worksheet = writer.sheets["Order"]
                header_fmt = workbook.add_format({"bold": True, "bg_color": "#0f9b8e", "font_color": "white"})
                money_fmt = workbook.add_format({"num_format": "$#,##0.00"})
                for col_num, _ in enumerate(active_lines.columns):
                    worksheet.set_column(col_num, col_num, 16)
                worksheet.set_row(0, 20, header_fmt)
                if "case_cost" in active_lines.columns:
                    idx = active_lines.columns.get_loc("case_cost")
                    worksheet.set_column(idx, idx, 16, money_fmt)
                if "line_total" in active_lines.columns:
                    idx = active_lines.columns.get_loc("line_total")
                    worksheet.set_column(idx, idx, 16, money_fmt)
            xlsx_bytes = xlsx_path.read_bytes()

            csv_path.write_bytes(csv_bytes)

            st.session_state.order_last_export = {
                "vendor": vendor,
                "timestamp": timestamp,
                "csv_name": csv_path.name,
                "xlsx_name": xlsx_path.name,
                "csv_bytes": csv_bytes,
                "xlsx_bytes": xlsx_bytes,
                "lines": line_count,
                "total": est_total,
            }
            st.session_state.order_cart = {}
            st.session_state.order_flash = f"Order exported to {csv_path.name}"
            st.rerun()

    if clear_clicked:
        st.session_state.order_cart = {}
        toast_info("Cart cleared")
        st.rerun()

flash = st.session_state.pop("order_flash", None)
if flash:
    toast_ok(flash)

last_export = st.session_state.get("order_last_export")
if last_export:
    st.success(
        f"Last export: {last_export['csv_name']} • {last_export['lines']} lines • ${last_export['total']:,.2f}"
    )
    st.download_button(
        "⬇️ Download CSV",
        data=last_export["csv_bytes"],
        file_name=last_export["csv_name"],
        mime="text/csv",
    )
    st.download_button(
        "⬇️ Download XLSX",
        data=last_export["xlsx_bytes"],
        file_name=last_export["xlsx_name"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
