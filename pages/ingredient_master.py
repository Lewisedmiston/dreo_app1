"""Ingredient master maintenance with normalized costing."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from common import utils
from common.constants import INGREDIENT_MASTER_FILE
from common.db import load_catalogs, read_table, write_table


EDITOR_COLUMNS = [
    "description",
    "vendor",
    "item_number",
    "uom",
    "pack_size",
    "case_cost",
    "unit_cost",
    "par",
    "on_hand",
    "location",
    "barcode",
]

NUMERIC_COLUMNS = ["pack_size", "case_cost", "unit_cost", "par", "on_hand"]


def _prepare_editor_frame() -> pd.DataFrame:
    catalogs = load_catalogs()
    ingredients = read_table(INGREDIENT_MASTER_FILE)
    base = utils.normalize_items(ingredients if not ingredients.empty else catalogs, catalogs)
    editor = base.reindex(columns=EDITOR_COLUMNS).copy()
    if editor.empty:
        editor = pd.DataFrame(columns=EDITOR_COLUMNS)
    for column in NUMERIC_COLUMNS:
        editor[column] = pd.to_numeric(editor.get(column, 0), errors="coerce").fillna(0.0)
    return editor


def _save_editor_frame(df: pd.DataFrame) -> None:
    export_df = df.copy()
    for column in NUMERIC_COLUMNS:
        export_df[column] = pd.to_numeric(export_df[column], errors="coerce").fillna(0.0)
    export_df["unit_cost"] = export_df.apply(
        lambda row: row["case_cost"] / row["pack_size"] if row["pack_size"] else row["case_cost"],
        axis=1,
    )
    export_df = export_df.fillna("")
    export_df["case_pack"] = export_df["pack_size"]
    export_df["case_uom"] = export_df["uom"]
    export_df["count_uom"] = export_df["uom"]
    export_df["cost_per_count"] = export_df["unit_cost"]
    write_table(INGREDIENT_MASTER_FILE, export_df)
    utils.clear_data_caches()


def main() -> None:
    utils.page_setup("Ingredient Master")

    editor_df = _prepare_editor_frame()

    st.caption("Keep vendor SKUs, pack sizes, and pars aligned across vendors.")

    column_config = {
        "description": st.column_config.TextColumn("Description", help="What the team calls it"),
        "vendor": st.column_config.TextColumn("Vendor"),
        "item_number": st.column_config.TextColumn("Vendor SKU"),
        "uom": st.column_config.TextColumn("Count UOM"),
        "pack_size": st.column_config.NumberColumn("Pack Size", format="%d", step=1),
        "case_cost": st.column_config.NumberColumn("Case Cost", format="$%.2f"),
        "unit_cost": st.column_config.NumberColumn("Cost / Count", format="$%.4f", disabled=True),
        "par": st.column_config.NumberColumn("Par", step=1),
        "on_hand": st.column_config.NumberColumn("On Hand", step=1),
        "location": st.column_config.TextColumn("Storage"),
        "barcode": st.column_config.TextColumn("Barcode/UPC"),
    }

    edited = st.data_editor(
        editor_df,
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        key="ingredient_editor",
    )

    edited_df = pd.DataFrame(edited)
    for column in NUMERIC_COLUMNS:
        edited_df[column] = pd.to_numeric(edited_df[column], errors="coerce").fillna(0.0)
    edited_df["unit_cost"] = edited_df.apply(
        lambda row: row["case_cost"] / row["pack_size"] if row["pack_size"] else row["case_cost"],
        axis=1,
    )

    save_cols = st.columns([1, 1])
    if save_cols[0].button("💾 Save Ingredient Master", type="primary"):
        _save_editor_frame(edited_df)
        utils.success_toast("Ingredient master saved")

    csv_bytes = edited_df.to_csv(index=False).encode("utf-8")
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        edited_df.to_excel(writer, index=False, sheet_name="Ingredients")

    save_cols[1].download_button(
        "⬇️ Download CSV",
        data=csv_bytes,
        file_name="ingredient_master.csv",
        mime="text/csv",
    )
    st.download_button(
        "⬇️ Download XLSX",
        data=excel_buffer.getvalue(),
        file_name="ingredient_master.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    if load_catalogs().empty:
        utils.info_toast("Upload catalogs to enrich vendor suggestions.")


if __name__ == "__main__":
    main()
