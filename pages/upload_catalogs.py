"""Vendor catalog upload with validation and deduplication."""

from __future__ import annotations

from typing import Dict

import pandas as pd
import streamlit as st

from zoneinfo import ZoneInfo

from common import utils
from common.constants import (
    CATALOGS_DIR,
    DEFAULT_VENDORS,
    REQUIRED_CATALOG_FIELDS,
    TZ_NAME,
    vendor_filename,
)
from common.db import (
    available_vendors,
    load_catalogs,
    log_exception,
    read_table,
    write_table,
)
from common.presets import load_presets


TZ = ZoneInfo(TZ_NAME)
REQUIRED_FIELDS = sorted(REQUIRED_CATALOG_FIELDS - {"vendor"})
OPTIONAL_FIELDS = ["brand", "pack_size", "category", "barcode"]
EXCEPTION_FEATURE = "catalog_upload"


def _format_price_date(series: pd.Series) -> pd.Series:
    formatted: list[str] = []
    for value in series:
        if isinstance(value, pd.Timestamp) and pd.notna(value):
            if value.tzinfo is None:
                value = value.tz_localize(TZ)
            else:
                value = value.tz_convert(TZ)
            formatted.append(value.date().isoformat())
        else:
            formatted.append("")
    return pd.Series(formatted, index=series.index)


def _log_issue(row: pd.Series, reason: str) -> None:
    payload = {
        "feature": EXCEPTION_FEATURE,
        "vendor": row.get("vendor"),
        "item_number": row.get("item_number"),
        "description": row.get("description"),
        "details": reason,
    }
    log_exception(payload)


def _apply_mapping(raw_df: pd.DataFrame, mapping: Dict[str, str], vendor: str) -> pd.DataFrame:
    mapped = pd.DataFrame(index=raw_df.index)
    for field, column in mapping.items():
        mapped[field] = raw_df[column]
    mapped["vendor"] = vendor
    return mapped


def main() -> None:
    utils.page_setup("Upload Catalogs")

    presets = load_presets()
    catalogs = load_catalogs()
    vendor_options = available_vendors(catalogs, defaults=DEFAULT_VENDORS)

    preset_vendor = vendor_options[0] if vendor_options else ""
    vendor = st.selectbox("Vendor", vendor_options or [preset_vendor], index=0 if vendor_options else 0)
    custom_vendor = st.text_input("Custom vendor name", placeholder="Override vendor selection if needed")
    vendor = custom_vendor.strip() or vendor

    if not vendor:
        st.warning("Enter a vendor name to continue.")
        return

    uploaded_file = st.file_uploader("Upload vendor catalog", type=["csv", "xlsx", "xls"])
    if uploaded_file is None:
        st.info("Upload a catalog file to begin.")
        return

    sheet_names = utils.get_excel_sheet_names(uploaded_file)
    sheet_name = None
    if sheet_names:
        sheet_name = st.selectbox("Worksheet", sheet_names)

    raw_df = utils.load_file_to_dataframe(uploaded_file, sheet_name=sheet_name)
    if raw_df is None or raw_df.empty:
        utils.error_toast("Uploaded file has no rows to process.")
        return

    st.subheader("1. Map vendor columns")

    preset = presets.get(vendor, {})
    mapping_defaults: Dict[str, str] = preset.get("map", {})
    column_choices = ["--"] + list(raw_df.columns)

    selections: Dict[str, str] = {}
    for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        default_choice = mapping_defaults.get(field, "--")
        if default_choice not in column_choices:
            default_choice = "--"
        selection = st.selectbox(
            field.replace("_", " ").title(),
            column_choices,
            index=column_choices.index(default_choice),
            key=f"catalog_map_{field}",
        )
        if selection != "--":
            selections[field] = selection

    missing_required = [field for field in REQUIRED_FIELDS if field not in selections]
    if missing_required:
        utils.error_toast(f"Map required fields: {', '.join(missing_required)}")
        return

    mapped_df = _apply_mapping(raw_df, selections, vendor)

    parsed_dates = mapped_df["price_date"].apply(lambda value: utils.safe_parse_date(value))
    invalid_dates = parsed_dates.isna()
    if invalid_dates.any():
        for _, row in mapped_df.loc[invalid_dates].iterrows():
            _log_issue(row, "missing price_date")
        utils.error_toast(f"{int(invalid_dates.sum())} rows missing price dates were skipped and logged.")
        mapped_df = mapped_df.loc[~invalid_dates]
        parsed_dates = parsed_dates.loc[~invalid_dates]

    if mapped_df.empty:
        utils.error_toast("No valid rows after applying required fields. Fix the source file and retry.")
        return

    mapped_df["price_date"] = parsed_dates

    normalized = utils.normalize_items(mapped_df)

    missing_cost = normalized["case_cost"] <= 0
    if missing_cost.any():
        for _, row in normalized.loc[missing_cost].iterrows():
            _log_issue(row, "missing case_cost")
        utils.error_toast(f"{int(missing_cost.sum())} rows without prices were skipped and logged.")
        normalized = normalized.loc[~missing_cost]

    if normalized.empty:
        utils.error_toast("All rows were filtered due to missing dates or prices.")
        return

    normalized = normalized.sort_values(by=["item_number", "price_date"], ascending=[True, False], na_position="last")
    normalized = normalized.drop_duplicates(subset=["vendor", "item_number"], keep="first")

    catalog_path = CATALOGS_DIR / vendor_filename(vendor)
    existing = read_table(catalog_path)
    existing_normalized = utils.normalize_items(existing) if not existing.empty else pd.DataFrame(columns=normalized.columns)

    existing_keys = set(
        zip(existing_normalized["vendor"].str.casefold(), existing_normalized["item_number"])
    )
    incoming_keys = set(zip(normalized["vendor"].str.casefold(), normalized["item_number"]))
    new_count = len(incoming_keys - existing_keys)

    updated_count = 0
    if not existing_normalized.empty:
        merged = normalized.merge(
            existing_normalized,
            on=["vendor", "item_number"],
            suffixes=("_new", "_old"),
            how="inner",
        )
        if not merged.empty:
            updated_mask = (
                (merged["case_cost_new"].round(4) != merged["case_cost_old"].round(4))
                | (merged["price_date_new"] > merged["price_date_old"])
            )
            updated_count = int(updated_mask.sum())

    st.subheader("2. Review normalized rows")

    preview = normalized.copy()
    preview["price_date"] = _format_price_date(preview["price_date"])
    display_columns = [
        "item_number",
        "description",
        "uom",
        "case_cost",
        "price_date",
        "pack_size",
        "category",
        "barcode",
    ]
    preview = preview.reindex(columns=[col for col in display_columns if col in preview.columns])

    st.dataframe(preview, hide_index=True, use_container_width=True)
    st.info(f"{len(normalized)} rows ready • {new_count} new • {updated_count} updated")

    st.download_button(
        "⬇️ Download preview CSV",
        data=preview.to_csv(index=False).encode("utf-8"),
        file_name=f"{vendor_filename(vendor).replace('.csv', '')}_preview.csv",
        mime="text/csv",
    )

    if st.button("💾 Save catalog", type="primary"):
        combined = pd.concat([existing_normalized, normalized], ignore_index=True)
        combined = combined.sort_values(
            by=["vendor", "item_number", "price_date"],
            ascending=[True, True, False],
            na_position="last",
        )
        combined = combined.drop_duplicates(subset=["vendor", "item_number"], keep="first")
        to_save = combined.copy()
        if "price_date" in to_save.columns:
            to_save["price_date"] = _format_price_date(to_save["price_date"])
        write_table(catalog_path, to_save)
        utils.success_toast(f"Catalog saved — {new_count} new • {updated_count} updated")


if __name__ == "__main__":
    main()
