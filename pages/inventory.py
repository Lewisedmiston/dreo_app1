"""Touch-friendly inventory counting workflow with shared workspaces."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from common import utils
from common.constants import (
    DEFAULT_VENDORS,
    INGREDIENT_MASTER_FILE,
    INVENTORY_DIR,
    TZ_NAME,
    slugify,
)
from common.db import (
    available_vendors,
    latest_inventory,
    load_catalogs,
    read_table,
    snapshot,
)
from common.team_state import (
    DEFAULT_WORKSPACE_NAME,
    ensure_workspace,
    list_workspaces,
    load_workspace,
    save_workspace,
)


TZ = ZoneInfo(TZ_NAME)
WORKSPACE_FEATURE = "inventory"
WORKSPACE_SESSION_KEY = "inventory_workspace"
NEW_WORKSPACE_OPTION = "➕ New workspace…"

SUMMARY_CSS = """
<style>
.inventory-summary {position: sticky; top: 64px; z-index: 20; background: rgba(255,255,255,0.92); border-radius: 14px; padding: 0.75rem 1rem; box-shadow: 0 8px 22px rgba(15,155,142,0.16); backdrop-filter: blur(6px);}
.inventory-summary h4 {margin: 0; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; color: #0f4c46;}
.inventory-summary span {display: block; font-weight: 700; font-size: 1.25rem; color: #0f9b8e;}
</style>
"""


def _timestamp() -> datetime:
    return datetime.now(tz=TZ)


def _persist_workspace(*, draft: Dict[str, int] | None = None, submitted: Dict[str, int] | None = None) -> None:
    workspace_name = st.session_state.get(WORKSPACE_SESSION_KEY)
    if not workspace_name:
        return
    current = load_workspace(WORKSPACE_FEATURE, workspace_name, default={"draft": {}, "last_submitted": {}})
    payload: Dict[str, Dict[str, int]] = {}
    payload["draft"] = draft if draft is not None else current.get("draft", {})
    last = submitted if submitted is not None else current.get("last_submitted", {})
    if last:
        payload["last_submitted"] = last
    save_workspace(WORKSPACE_FEATURE, workspace_name, payload)


def _init_workspace_state() -> None:
    workspaces = list_workspaces(WORKSPACE_FEATURE)
    if not workspaces:
        ensure_workspace(WORKSPACE_FEATURE, DEFAULT_WORKSPACE_NAME, default={"draft": {}, "last_submitted": {}})
        workspaces = [DEFAULT_WORKSPACE_NAME]

    current = st.session_state.get(WORKSPACE_SESSION_KEY)
    if current not in workspaces:
        st.session_state[WORKSPACE_SESSION_KEY] = workspaces[0]

    payload = load_workspace(
        WORKSPACE_FEATURE,
        st.session_state[WORKSPACE_SESSION_KEY],
        default={"draft": {}, "last_submitted": {}},
    )

    draft = {str(k): int(v) for k, v in payload.get("draft", {}).items() if int(v) >= 0}
    baseline = {str(k): int(v) for k, v in payload.get("last_submitted", {}).items() if int(v) >= 0}

    if "inventory_counts" not in st.session_state:
        st.session_state.inventory_counts = draft
    if "inventory_last_saved" not in st.session_state:
        if baseline:
            st.session_state.inventory_last_saved = baseline
        else:
            last_snapshot = latest_inventory()
            if last_snapshot is not None and "item_key" in last_snapshot.columns:
                counts = {
                    str(row["item_key"]): int(row.get("quantity", 0))
                    for _, row in last_snapshot.iterrows()
                    if int(row.get("quantity", 0)) > 0
                }
                st.session_state.inventory_last_saved = counts
            else:
                st.session_state.inventory_last_saved = {}


def _workspace_selector() -> None:
    workspaces = list_workspaces(WORKSPACE_FEATURE)
    current = st.session_state[WORKSPACE_SESSION_KEY]
    options = workspaces + [NEW_WORKSPACE_OPTION]
    current_index = options.index(current) if current in options else 0
    choice = st.selectbox("Active workspace", options, index=current_index)
    if choice == NEW_WORKSPACE_OPTION:
        new_name = st.text_input("Workspace name", key="inventory_new_workspace")
        create_cols = st.columns([1, 1])
        if create_cols[0].button("Create workspace", use_container_width=True):
            if not new_name.strip():
                st.warning("Enter a workspace name to create it.")
            else:
                normalized = ensure_workspace(
                    WORKSPACE_FEATURE,
                    new_name,
                    default={"draft": {}, "last_submitted": {}},
                )
                st.session_state[WORKSPACE_SESSION_KEY] = normalized
                st.session_state.inventory_counts = {}
                st.session_state.inventory_last_saved = {}
                st.rerun()
        return

    if choice != current:
        st.session_state[WORKSPACE_SESSION_KEY] = choice
        payload = load_workspace(
            WORKSPACE_FEATURE,
            choice,
            default={"draft": {}, "last_submitted": {}},
        )
        st.session_state.inventory_counts = {
            str(k): int(v) for k, v in payload.get("draft", {}).items() if int(v) >= 0
        }
        st.session_state.inventory_last_saved = {
            str(k): int(v)
            for k, v in payload.get("last_submitted", {}).items()
            if int(v) >= 0
        }


def _update_count(item_key: str) -> None:
    value = st.session_state.get(f"inventory_count_{item_key}", 0)
    st.session_state.inventory_counts[item_key] = int(value)


def main() -> None:
    utils.page_setup("Inventory Count")
    st.markdown(SUMMARY_CSS, unsafe_allow_html=True)

    _init_workspace_state()
    _workspace_selector()

    catalogs = load_catalogs()
    ingredients = read_table(INGREDIENT_MASTER_FILE)

    if ingredients.empty and catalogs.empty:
        utils.error_toast("Upload catalogs or build an ingredient master to start counting.")
        return

    base_df = ingredients if not ingredients.empty else catalogs
    items = utils.normalize_items(base_df, catalogs if not catalogs.empty else None)
    if items.empty:
        utils.error_toast("No items available after normalization. Check your data sources.")
        return

    vendor_filter = st.multiselect(
        "Filter by vendor",
        options=available_vendors(items, defaults=DEFAULT_VENDORS),
        default=[],
    )
    search_term = st.text_input("Search by item or SKU", placeholder="e.g. tomato, 12345")

    filtered = items.copy()
    if vendor_filter:
        filtered = filtered[filtered["vendor"].isin(vendor_filter)]
    if search_term:
        lowered = search_term.casefold()
        mask = filtered["search_key"].str.contains(lowered)
        filtered = filtered[mask]

    filtered = filtered.sort_values(["vendor", "display_name"]).reset_index(drop=True)

    counts = {str(k): int(v) for k, v in st.session_state.inventory_counts.items() if int(v) >= 0}
    counted_lines = sum(1 for value in counts.values() if value)
    total_units = sum(counts.values())
    baseline = st.session_state.get("inventory_last_saved", {})
    unsaved = counts != {k: v for k, v in baseline.items() if v}

    with st.container():
        st.markdown("<div class='inventory-summary'>", unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        col1.markdown("<h4>Visible Items</h4><span>{:,}</span>".format(len(filtered)), unsafe_allow_html=True)
        col2.markdown("<h4>Lines Counted</h4><span>{:,}</span>".format(counted_lines), unsafe_allow_html=True)
        col3.markdown("<h4>Total Units</h4><span>{:,}</span>".format(total_units), unsafe_allow_html=True)
        status = "Unsaved draft" if unsaved else "Draft synced"
        col4.markdown(f"<h4>Status</h4><span>{status}</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if filtered.empty:
        st.info("Adjust filters to see items to count.")
        return

    for vendor, vendor_df in filtered.groupby("vendor"):
        st.subheader(vendor)
        for _, row in vendor_df.iterrows():
            item_key = row["item_key"]
            default_value = counts.get(item_key, 0)
            state_key = f"inventory_count_{item_key}"
            if state_key not in st.session_state:
                st.session_state[state_key] = default_value

            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown(
                    f"**{row['display_name']}**\n``{row['item_number']}`` • {row['uom']}"
                )
            with cols[1]:
                st.number_input(
                    "Qty",
                    min_value=0,
                    step=1,
                    key=state_key,
                    on_change=_update_count,
                    args=(item_key,),
                )

    with st.form("inventory_actions"):
        note = st.text_input("Notes", placeholder="Optional count context (crew, shift, etc.)")
        action_cols = st.columns([1, 1])
        save_draft = action_cols[0].form_submit_button("💾 Save Draft")
        submit_final = action_cols[1].form_submit_button("✅ Submit Count", type="primary")

    current_counts = {str(k): int(v) for k, v in st.session_state.inventory_counts.items() if int(v) >= 0}

    if save_draft:
        _persist_workspace(draft=current_counts)
        utils.success_toast("Draft saved to shared workspace")

    if submit_final:
        counts_series = pd.Series(current_counts, name="quantity")
        result = items.set_index("item_key").join(counts_series, how="left").fillna({"quantity": 0}).reset_index()
        result["quantity"] = result["quantity"].astype(int)
        result["counted_at"] = _timestamp().isoformat()
        if note:
            result["note"] = note
        prefix = slugify(st.session_state[WORKSPACE_SESSION_KEY])
        saved_path = snapshot(INVENTORY_DIR, result, prefix=prefix)
        _persist_workspace(draft=current_counts, submitted=current_counts)
        st.session_state.inventory_last_saved = current_counts
        utils.success_toast(f"Inventory submitted • saved to {saved_path.name}")


if __name__ == "__main__":
    main()
