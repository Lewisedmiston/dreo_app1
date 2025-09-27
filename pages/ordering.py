"""Vendor ordering workspace with sticky cart and export helpers."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Dict

import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from common import utils
from common.constants import DEFAULT_VENDORS, INGREDIENT_MASTER_FILE, ORDERS_DIR, TZ_NAME, slugify
from common.db import available_vendors, latest_order, load_catalogs, read_table, snapshot
from common.team_state import (
    DEFAULT_WORKSPACE_NAME,
    ensure_workspace,
    list_workspaces,
    load_workspace,
    save_workspace,
)


TZ = ZoneInfo(TZ_NAME)
WORKSPACE_FEATURE = "ordering"
WORKSPACE_SESSION_KEY = "ordering_workspace"
NEW_WORKSPACE_OPTION = "➕ New workspace…"

SUMMARY_CSS = """
<style>
.ordering-summary {position: sticky; top: 64px; z-index: 20; background: rgba(255,255,255,0.94); border-radius: 14px; padding: 0.75rem 1rem; box-shadow: 0 8px 22px rgba(15,155,142,0.16); backdrop-filter: blur(6px);}
.ordering-summary h4 {margin: 0; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; color: #0f4c46;}
.ordering-summary span {display: block; font-weight: 700; font-size: 1.2rem; color: #0f9b8e;}
</style>
"""


def _timestamp() -> datetime:
    return datetime.now(tz=TZ)


def _persist_workspace(*, cart: Dict[str, int] | None = None, vendor: str | None = None) -> None:
    workspace_name = st.session_state.get(WORKSPACE_SESSION_KEY)
    if not workspace_name:
        return
    current = load_workspace(
        WORKSPACE_FEATURE,
        workspace_name,
        default={"cart": {}, "vendor": None},
    )
    payload: Dict[str, object] = {}
    payload["cart"] = cart if cart is not None else current.get("cart", {})
    payload["vendor"] = vendor if vendor is not None else current.get("vendor")
    save_workspace(WORKSPACE_FEATURE, workspace_name, payload)


def _init_workspace_state() -> None:
    workspaces = list_workspaces(WORKSPACE_FEATURE)
    if not workspaces:
        ensure_workspace(WORKSPACE_FEATURE, DEFAULT_WORKSPACE_NAME, default={"cart": {}, "vendor": None})
        workspaces = [DEFAULT_WORKSPACE_NAME]

    current = st.session_state.get(WORKSPACE_SESSION_KEY)
    if current not in workspaces:
        st.session_state[WORKSPACE_SESSION_KEY] = workspaces[0]

    payload = load_workspace(
        WORKSPACE_FEATURE,
        st.session_state[WORKSPACE_SESSION_KEY],
        default={"cart": {}, "vendor": None},
    )

    if "order_cart" not in st.session_state:
        st.session_state.order_cart = {str(k): int(v) for k, v in payload.get("cart", {}).items() if int(v) > 0}
    if "order_vendor" not in st.session_state:
        vendor_value = payload.get("vendor")
        st.session_state.order_vendor = str(vendor_value) if vendor_value else None


def _workspace_selector() -> None:
    workspaces = list_workspaces(WORKSPACE_FEATURE)
    current = st.session_state[WORKSPACE_SESSION_KEY]
    options = workspaces + [NEW_WORKSPACE_OPTION]
    current_index = options.index(current) if current in options else 0
    choice = st.selectbox("Active workspace", options, index=current_index)
    if choice == NEW_WORKSPACE_OPTION:
        new_name = st.text_input("Workspace name", key="ordering_new_workspace")
        create_cols = st.columns([1, 1])
        if create_cols[0].button("Create workspace", use_container_width=True):
            if not new_name.strip():
                st.warning("Enter a workspace name to create it.")
            else:
                normalized = ensure_workspace(
                    WORKSPACE_FEATURE,
                    new_name,
                    default={"cart": {}, "vendor": None},
                )
                st.session_state[WORKSPACE_SESSION_KEY] = normalized
                st.session_state.order_cart = {}
                st.session_state.order_vendor = None
                st.rerun()
        if create_cols[1].button("Cancel", use_container_width=True):
            st.session_state.pop("ordering_new_workspace", None)
            st.rerun()
        return

    if choice != current:
        payload = load_workspace(
            WORKSPACE_FEATURE,
            choice,
            default={"cart": {}, "vendor": None},
        )
        st.session_state[WORKSPACE_SESSION_KEY] = choice
        st.session_state.order_cart = {str(k): int(v) for k, v in payload.get("cart", {}).items() if int(v) > 0}
        vendor_value = payload.get("vendor")
        st.session_state.order_vendor = str(vendor_value) if vendor_value else None
        st.rerun()


def _update_cart(item_key: str) -> None:
    value = int(st.session_state.get(f"order_qty_{item_key}", 0))
    if value <= 0:
        st.session_state.order_cart.pop(item_key, None)
    else:
        st.session_state.order_cart[item_key] = value


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _export_workbook(order_df: pd.DataFrame) -> io.BytesIO:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        order_df.to_excel(writer, index=False, sheet_name="Order")
        workbook = writer.book
        worksheet = writer.sheets["Order"]
        currency_format = workbook.add_format({"num_format": "$#,##0.00"})
        qty_format = workbook.add_format({"num_format": "0"})
        worksheet.set_column("A:A", 18)
        worksheet.set_column("B:B", 36)
        worksheet.set_column("C:C", 10)
        worksheet.set_column("D:D", 10, qty_format)
        worksheet.set_column("E:F", 14, currency_format)
    buffer.seek(0)
    return buffer


def main() -> None:
    utils.page_setup("Build Order")
    st.markdown(SUMMARY_CSS, unsafe_allow_html=True)

    _init_workspace_state()
    _workspace_selector()

    catalogs = load_catalogs()
    ingredients = read_table(INGREDIENT_MASTER_FILE)
    base_df = ingredients if not ingredients.empty else catalogs
    if base_df.empty:
        utils.error_toast("Upload catalogs or build an ingredient master to start ordering.")
        return

    items = utils.normalize_items(base_df, catalogs)
    if items.empty:
        utils.error_toast("No items available after normalization. Check your data sources.")
        return

    vendor_options = available_vendors(items, defaults=DEFAULT_VENDORS)
    if vendor_options:
        if st.session_state.order_vendor not in vendor_options:
            st.session_state.order_vendor = vendor_options[0]
    else:
        st.session_state.order_vendor = None

    if not vendor_options:
        st.warning("No vendors available. Upload catalogs or set preferred vendors in the ingredient master.")
        return

    vendor = st.selectbox(
        "Vendor",
        vendor_options,
        index=vendor_options.index(st.session_state.order_vendor)
        if st.session_state.order_vendor in vendor_options
        else 0,
    )
    st.session_state.order_vendor = vendor
    _persist_workspace(vendor=vendor)

    search_term = st.text_input("Search items", placeholder="Item, SKU, or keyword")

    vendor_key = vendor.casefold() if vendor else ""
    vendor_items = items[items["vendor"].str.casefold() == vendor_key].copy()
    if vendor_items.empty:
        st.warning(f"No items mapped to {vendor}. Update the ingredient master to include vendor links.")
        return

    if search_term:
        lowered = search_term.casefold()
        vendor_items = vendor_items[vendor_items["search_key"].str.contains(lowered)]

    vendor_items["suggested_qty"] = (vendor_items["par"] - vendor_items["on_hand"]).clip(lower=0).round().astype(int)

    cart = st.session_state.order_cart
    extended = []
    for key, qty in cart.items():
        row = vendor_items[vendor_items["item_key"] == key]
        if row.empty:
            continue
        cost = float(row.iloc[0]["case_cost"])
        extended.append(cost * qty)
    total_cost = sum(extended)

    last_order_df = latest_order()
    if last_order_df is not None and "ordered_at" in last_order_df.columns:
        last_order_time = last_order_df["ordered_at"].max()
        last_export = str(last_order_time)
    else:
        last_export = "Never"

    with st.container():
        st.markdown("<div class='ordering-summary'>", unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        col1.markdown(f"<h4>Vendor</h4><span>{vendor}</span>", unsafe_allow_html=True)
        col2.markdown("<h4>Cart Lines</h4><span>{:,}</span>".format(len(cart)), unsafe_allow_html=True)
        col3.markdown(f"<h4>Est. Spend</h4><span>{_format_currency(total_cost)}</span>", unsafe_allow_html=True)
        col4.markdown(f"<h4>Last Export</h4><span>{last_export}</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if vendor_items.empty:
        st.info("Adjust filters to see items to order.")
        return

    for _, row in vendor_items.sort_values("display_name").iterrows():
        item_key = row["item_key"]
        default_value = cart.get(item_key, 0)
        state_key = f"order_qty_{item_key}"
        if state_key not in st.session_state:
            st.session_state[state_key] = default_value

        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.markdown(
                f"**{row['display_name']}**\n``{row['item_number']}`` • {row['uom']} • { _format_currency(float(row['case_cost'])) }"
            )
            st.caption(f"Par {row['par']:.0f} • On hand {row['on_hand']:.0f} • Suggested {row['suggested_qty']}")
        with cols[1]:
            st.number_input(
                "Cases",
                min_value=0,
                step=1,
                key=state_key,
                on_change=_update_cart,
                args=(item_key,),
            )
        with cols[2]:
            if st.button("Use suggested", key=f"suggest_{item_key}", use_container_width=True):
                st.session_state[state_key] = int(row["suggested_qty"])
                _update_cart(item_key)
                st.rerun()

    with st.form("order_actions"):
        note = st.text_input("Notes", placeholder="Delivery window, contact, etc.")
        col_save, col_clear, col_export = st.columns([1, 1, 1])
        save_draft = col_save.form_submit_button("💾 Save Cart")
        clear_cart = col_clear.form_submit_button("🗑️ Clear Cart")
        export_order = col_export.form_submit_button("⬇️ Export Order", type="primary")

    current_cart = {str(k): int(v) for k, v in st.session_state.order_cart.items() if int(v) > 0}

    if save_draft:
        _persist_workspace(cart=current_cart, vendor=vendor)
        utils.success_toast("Cart saved to shared workspace")

    if clear_cart:
        st.session_state.order_cart = {}
        _persist_workspace(cart={}, vendor=vendor)
        utils.info_toast("Cart cleared")
        st.rerun()

    if export_order:
        if not current_cart:
            utils.error_toast("Add items to the cart before exporting.")
        else:
            counts_series = pd.Series(current_cart, name="quantity")
            order_df = vendor_items.set_index("item_key").join(counts_series, how="inner").reset_index()
            order_df = order_df[order_df["quantity"] > 0]
            order_df["quantity"] = order_df["quantity"].astype(int)
            order_df["case_cost"] = order_df["case_cost"].astype(float)
            order_df["extended_cost"] = order_df["case_cost"] * order_df["quantity"]
            order_df["ordered_at"] = _timestamp().isoformat()
            if note:
                order_df["note"] = note

            file_name = snapshot(ORDERS_DIR, order_df, prefix=slugify(vendor)).name
            csv_data = order_df[
                ["vendor", "item_number", "description", "uom", "quantity", "case_cost", "extended_cost", "ordered_at"]
            ]
            st.download_button(
                "⬇️ Download CSV",
                data=csv_data.to_csv(index=False).encode("utf-8"),
                file_name=file_name,
                mime="text/csv",
            )
            workbook = _export_workbook(csv_data)
            st.download_button(
                "⬇️ Download XLSX",
                data=workbook.getvalue(),
                file_name=file_name.replace(".csv", ".xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            utils.success_toast(f"Order prepared • {file_name}")
            _persist_workspace(cart=current_cart, vendor=vendor)


if __name__ == "__main__":
    main()
