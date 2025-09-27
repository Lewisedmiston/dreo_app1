"""Utility helpers shared across Streamlit pages."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Iterable, Optional

import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from pandas.api.types import DatetimeTZDtype, is_datetime64_dtype

from .constants import OPTIONAL_ITEM_FIELDS, REQUIRED_ITEM_FIELDS, TZ_NAME

TZ = ZoneInfo(TZ_NAME)
ISO_DATE = "%Y-%m-%d"
ISO_DATETIME = "%Y-%m-%d %H:%M:%S"

_MONEY_RE = re.compile(r"[^0-9.]+")
_CANONICAL_RE = re.compile(r"[^a-z0-9]+")


def _canonical_name(column: str) -> str:
    return _CANONICAL_RE.sub("", column.strip().lower())


_ALIAS_CANDIDATES = {
    "vendor": "vendor",
    "preferred_vendor": "vendor",
    "primary_vendor": "vendor",
    "supplier": "vendor",
    "item_number": "item_number",
    "item no": "item_number",
    "item#": "item_number",
    "sku": "item_number",
    "vendor_sku": "item_number",
    "vendor item": "item_number",
    "itemid": "item_number",
    "id": "item_number",
    "description": "description",
    "item_description": "description",
    "item description": "description",
    "product_description": "description",
    "name": "description",
    "itemname": "description",
    "uom": "uom",
    "unit": "uom",
    "count_uom": "uom",
    "case_uom": "uom",
    "pack_uom": "uom",
    "pack_size": "pack_size",
    "pack": "pack_size",
    "case_pack": "pack_size",
    "case qty": "pack_size",
    "caseqty": "pack_size",
    "case quantity": "pack_size",
    "pack_quantity": "pack_quantity",
    "packqty": "pack_quantity",
    "case_qty": "pack_quantity",
    "par": "par",
    "par_level": "par",
    "min_par": "par",
    "on_hand": "on_hand",
    "onhand": "on_hand",
    "qty": "on_hand",
    "quantity": "on_hand",
    "count": "on_hand",
    "location": "location",
    "area": "location",
    "station": "location",
    "section": "location",
    "barcode": "barcode",
    "upc": "barcode",
    "case_cost": "case_cost",
    "case_price": "case_cost",
    "price": "case_cost",
    "cost": "case_cost",
    "last_cost": "case_cost",
    "unit_cost": "unit_cost",
    "each_cost": "unit_cost",
    "price_date": "price_date",
    "cost_date": "price_date",
    "effective_date": "price_date",
    "last_updated": "price_date",
    "category": "category",
    "department": "category",
}

_COLUMN_ALIASES = {_canonical_name(alias): target for alias, target in _ALIAS_CANDIDATES.items()}

_NUMERIC_COLUMNS = ("pack_size", "pack_quantity", "par", "on_hand", "case_cost", "unit_cost")
_STRING_COLUMNS = ("vendor", "item_number", "description", "uom", "location", "barcode", "category")


def iso_today() -> str:
    return datetime.now(tz=TZ).strftime(ISO_DATE)


def iso_now() -> str:
    """Return an ISO timestamp for the current timezone-aware moment."""

    return datetime.now(tz=TZ).strftime(ISO_DATETIME)


def to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    string = str(value).strip()
    if not string:
        return default
    string = _MONEY_RE.sub("", string)
    try:
        return float(string)
    except ValueError:
        return default


def page_setup(title: str) -> None:
    """Configure Streamlit for a mobile-friendly experience."""

    st.set_page_config(
        page_title=f"Dreo Kitchen Ops - {title}",
        page_icon="🍳",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
        .stButton > button,
        .stNumberInput input,
        .stSelectbox div[data-baseweb="select"] > div,
        .stTextInput input {
            height: 52px;
            font-size: 1.05rem;
            border-radius: 10px;
        }

        @media (max-width: 768px) {
            .stButton > button,
            .stNumberInput input,
            .stSelectbox div[data-baseweb="select"] > div,
            .stTextInput input {
                height: 58px;
                font-size: 1.1rem;
            }
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(title)


def smart_cache_key(*args, **kwargs) -> str:
    key_str = str(args) + str(sorted(kwargs.items()))
    return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()


def load_file_to_dataframe(uploaded_file, sheet_name: str | None = None) -> Optional[pd.DataFrame]:
    if uploaded_file is None:
        return None

    try:
        content = uploaded_file.getvalue()
        cache_key = f"upload::{hash(content)}::{sheet_name or 'default'}"
        if cache_key in st.session_state:
            return st.session_state[cache_key]

        with st.spinner("📂 Loading file..."):
            if uploaded_file.name.endswith(".csv"):
                frame = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith((".xlsx", ".xls")):
                frame = pd.read_excel(uploaded_file, sheet_name=sheet_name)
            else:
                st.error("Unsupported file format. Please upload CSV or Excel files.")
                return None

        st.session_state[cache_key] = frame
        return frame
    except Exception as exc:  # pragma: no cover - UI feedback only
        st.error(f"Error reading file: {exc}")
        return None


def get_excel_sheet_names(uploaded_file) -> Optional[list[str]]:
    if uploaded_file is None or not uploaded_file.name.endswith((".xlsx", ".xls")):
        return None

    try:
        cache_key = f"sheets::{hash(uploaded_file.getvalue())}"
        if cache_key in st.session_state:
            return st.session_state[cache_key]

        workbook = pd.ExcelFile(uploaded_file)
        st.session_state[cache_key] = workbook.sheet_names
        return workbook.sheet_names
    except Exception as exc:  # pragma: no cover - UI feedback only
        st.error(f"Error reading Excel sheets: {exc}")
        return None


def detect_vendor_from_sheet_name(sheet_name: str) -> str:
    lower = sheet_name.lower()
    if "sysco" in lower:
        return "Sysco"
    if "pfg" in lower:
        return "PFG"
    if "produce" in lower:
        return "Produce"
    return sheet_name.title()


def clear_data_caches() -> None:
    st.cache_data.clear()
    if hasattr(st, "session_state"):
        for key in list(st.session_state.keys()):
            if "cache" in str(key).lower():
                st.session_state.pop(key, None)


def safe_parse_date(value, *, allow_today: bool = False) -> Optional[pd.Timestamp]:
    """Parse ``value`` into a timezone-aware ``Timestamp`` or return ``None``."""

    def _today() -> pd.Timestamp:
        return pd.Timestamp(datetime.now(tz=TZ).replace(hour=0, minute=0, second=0, microsecond=0))

    if value is None or value == "":
        return _today() if allow_today else None

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return _today() if allow_today else None

    timestamp = pd.Timestamp(parsed)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(TZ, nonexistent="NaT", ambiguous="NaT")
    else:
        timestamp = timestamp.tz_convert(TZ)
    return timestamp


def _prepare_catalog_lookup(catalogs: pd.DataFrame | None) -> tuple[dict[str, str], dict[str, str]]:
    if catalogs is None or catalogs.empty:
        return {}, {}

    normalized = catalogs.copy()
    rename_map = {}
    for column in normalized.columns:
        alias = _COLUMN_ALIASES.get(_canonical_name(column))
        if alias:
            rename_map[column] = alias
    normalized = normalized.rename(columns=rename_map)
    for column in ("vendor", "item_number", "description"):
        if column not in normalized.columns:
            normalized[column] = ""

    normalized["item_number"] = normalized["item_number"].fillna("").astype(str).str.strip()
    normalized["description"] = normalized["description"].fillna("").astype(str).str.strip()
    normalized["vendor"] = normalized["vendor"].fillna("").astype(str).str.strip()

    vendor_by_item = (
        normalized.replace("", pd.NA)
        .dropna(subset=["item_number", "vendor"])
        .drop_duplicates(subset=["item_number"], keep="last")
        .set_index("item_number")["vendor"]
        .to_dict()
    )

    vendor_by_description = (
        normalized.replace("", pd.NA)
        .dropna(subset=["description", "vendor"])
        .drop_duplicates(subset=["description"], keep="last")
        .set_index("description")["vendor"]
        .to_dict()
    )

    return vendor_by_item, vendor_by_description


def normalize_items(df: pd.DataFrame | None, catalogs: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a normalised item DataFrame safe for downstream pages."""

    base_columns = list(dict.fromkeys(
        list(REQUIRED_ITEM_FIELDS) + list(OPTIONAL_ITEM_FIELDS) + ["display_name", "search_key", "item_key"]
    ))

    if df is None or df.empty:
        return pd.DataFrame(columns=base_columns)

    frame = df.copy()
    rename_map: dict[str, str] = {}
    for column in frame.columns:
        alias = _COLUMN_ALIASES.get(_canonical_name(column))
        if alias and alias not in rename_map.values():
            rename_map[column] = alias
    frame = frame.rename(columns=rename_map)

    for column in REQUIRED_ITEM_FIELDS + OPTIONAL_ITEM_FIELDS:
        if column not in frame.columns:
            frame[column] = pd.NA

    vendor_by_item, vendor_by_description = _prepare_catalog_lookup(catalogs)

    for column in _STRING_COLUMNS:
        frame[column] = frame[column].fillna("").astype(str).str.strip()

    if vendor_by_item or vendor_by_description:
        missing_vendor = frame["vendor"] == ""
        if missing_vendor.any():
            frame.loc[missing_vendor, "vendor"] = frame.loc[missing_vendor, "item_number"].map(vendor_by_item).fillna("")
        missing_vendor = frame["vendor"] == ""
        if missing_vendor.any():
            frame.loc[missing_vendor, "vendor"] = frame.loc[missing_vendor, "description"].map(vendor_by_description).fillna("")

    frame["vendor"] = frame["vendor"].where(frame["vendor"] != "", "Vendor")

    if "item_number" in frame.columns:
        missing_number = frame["item_number"] == ""
        if missing_number.any():
            frame.loc[missing_number, "item_number"] = frame.loc[missing_number].index.astype(str)

    frame["description"] = frame["description"].where(frame["description"] != "", frame["item_number"])
    frame["uom"] = frame["uom"].where(frame["uom"] != "", "ea")

    for column in _NUMERIC_COLUMNS:
        frame[column] = frame[column].apply(to_float).fillna(0.0)

    frame.loc[frame["pack_size"] <= 0, "pack_size"] = 1.0
    frame.loc[frame["pack_quantity"] <= 0, "pack_quantity"] = 1.0

    if "price_date" in frame.columns:
        price_series = pd.to_datetime(frame["price_date"], errors="coerce")
        dtype = price_series.dtype
        if isinstance(dtype, DatetimeTZDtype):
            price_series = price_series.dt.tz_convert(TZ)
        elif is_datetime64_dtype(dtype):
            price_series = price_series.dt.tz_localize(TZ, nonexistent="NaT", ambiguous="NaT")
        frame["price_date"] = price_series

    needs_unit = (frame["unit_cost"] <= 0) & (frame["case_cost"] > 0) & (frame["pack_size"] > 0)
    frame.loc[needs_unit, "unit_cost"] = frame.loc[needs_unit, "case_cost"] / frame.loc[needs_unit, "pack_size"]

    display = frame["description"].where(frame["description"] != "", frame["item_number"])
    frame["display_name"] = display
    frame["search_key"] = display.str.casefold()

    vendor_key = frame["vendor"].str.casefold().str.replace(r"\s+", " ", regex=True).str.strip()
    number_key = frame["item_number"].str.casefold().str.strip()
    fallback_key = frame["description"].str.casefold().str.strip()
    frame["item_key"] = vendor_key + "::" + number_key.where(number_key != "", fallback_key)

    ordered = [col for col in base_columns if col in frame.columns]
    remaining = [col for col in frame.columns if col not in ordered]
    return frame.loc[:, ordered + remaining]


def success_toast(message: str) -> None:
    st.success(f"✅ {message}")
    if hasattr(st, "toast"):
        st.toast(f"✅ {message}", icon="✅")


def error_toast(message: str) -> None:
    st.error(f"❌ {message}")
    if hasattr(st, "toast"):
        st.toast(f"❌ {message}", icon="❌")


def info_toast(message: str) -> None:
    st.info(f"ℹ️ {message}")
    if hasattr(st, "toast"):
        st.toast(f"ℹ️ {message}", icon="ℹ️")
