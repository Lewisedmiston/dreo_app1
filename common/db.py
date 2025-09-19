from __future__ import annotations

"""Lightweight file-based data helpers used across the Streamlit app."""

from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd
import streamlit as st

# Root data directory structure
DATA = Path("data")
CATALOGS_DIR = DATA / "catalogs"
INVENTORY_DIR = DATA / "inventory_counts"
ORDERS_DIR = DATA / "orders"

# Ensure directories exist on import so the UI can assume they are available
for directory in (DATA, CATALOGS_DIR, INVENTORY_DIR, ORDERS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def _resolve(path: str | Path) -> Path:
    """Resolve a logical path (within data/) to a concrete CSV path."""
    p = DATA / Path(path)
    if p.suffix == "":
        p = p.with_suffix(".csv")
    return p


def read_table(path: str | Path, **kwargs) -> pd.DataFrame:
    """Read a CSV file inside the data directory, returning an empty frame if missing."""
    csv_path = _resolve(path)
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path, **kwargs)


def write_table(path: str | Path, df: pd.DataFrame, **kwargs) -> Path:
    """Persist a DataFrame as CSV under the data directory."""
    csv_path = _resolve(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False, **kwargs)
    return csv_path


def snapshot(dir_name: str, df: pd.DataFrame, prefix: str) -> Path:
    """Save a timestamped snapshot CSV and return the file path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}.csv" if prefix else f"{ts}.csv"
    csv_path = DATA / dir_name / filename
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    return csv_path


# Streamlit toast helpers ---------------------------------------------------


def toast_ok(message: str) -> None:
    st.success(message, icon="✅")


def toast_err(message: str) -> None:
    st.error(message, icon="❌")


def toast_info(message: str) -> None:
    st.info(message, icon="ℹ️")


# Date helpers ---------------------------------------------------------------


def safe_parse_date(value, default: Optional[date] = None) -> pd.Timestamp:
    """Parse a date value, coercing invalid entries to the provided default/today."""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        fallback = default or date.today()
        return pd.to_datetime(fallback)
    return parsed


# Convenience accessors -----------------------------------------------------


def load_catalogs() -> pd.DataFrame:
    """Concatenate all catalog CSVs into a single normalized DataFrame."""
    frames: list[pd.DataFrame] = []
    for catalog_file in sorted(CATALOGS_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(catalog_file)
            if not df.empty:
                df["vendor"] = df.get("vendor", catalog_file.stem)
                frames.append(df)
        except Exception as exc:
            toast_err(f"Failed to read {catalog_file.name}: {exc}")
    if not frames:
        return pd.DataFrame(columns=["vendor", "item_number", "description", "uom", "case_cost"])
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["vendor", "item_number"], keep="last")
    return combined


def latest_file(directory: Path) -> Optional[Path]:
    files = [p for p in directory.glob("*.csv") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def latest_inventory() -> Optional[pd.DataFrame]:
    latest = latest_file(INVENTORY_DIR)
    if latest is None:
        return None
    try:
        return pd.read_csv(latest)
    except Exception as exc:
        toast_err(f"Unable to read inventory snapshot: {exc}")
        return None


def latest_order() -> Optional[pd.DataFrame]:
    latest = latest_file(ORDERS_DIR)
    if latest is None:
        return None
    try:
        return pd.read_csv(latest)
    except Exception as exc:
        toast_err(f"Unable to read order snapshot: {exc}")
        return None


def get_metrics() -> Dict[str, str]:
    """Return quick dashboard metrics derived from the file-backed data store."""
    catalogs = load_catalogs()
    ingredient_master = read_table("ingredient_master")
    active_skus = 0
    if not ingredient_master.empty:
        active_skus = ingredient_master["description"].nunique()
    elif not catalogs.empty:
        active_skus = catalogs["description"].nunique()

    last_count = "Never"
    latest_inventory_file = latest_file(INVENTORY_DIR)
    if latest_inventory_file is not None:
        try:
            parts = latest_inventory_file.stem.split("_")
            stamp = "_".join(parts[-2:]) if len(parts) >= 3 else parts[-1]
            dt = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
            last_count = dt.strftime("%b %d, %Y %I:%M %p")
        except Exception:
            last_count = latest_inventory_file.stem

    last_order_lines = 0
    latest_order_df = latest_order()
    if latest_order_df is not None:
        last_order_lines = int(latest_order_df.shape[0])

    return {
        "active_skus": f"{active_skus:,}",
        "last_count_date": last_count,
        "open_order_lines": f"{last_order_lines:,}",
    }


def detect_unsaved_changes(current: Dict[str, int], baseline: Optional[Dict[str, int]]) -> bool:
    """Return True if the current draft differs from a baseline snapshot."""
    baseline = baseline or {}
    return {k: v for k, v in current.items() if v} != {
        k: v for k, v in baseline.items() if v
    }


__all__ = [
    "CATALOGS_DIR",
    "DATA",
    "INVENTORY_DIR",
    "ORDERS_DIR",
    "detect_unsaved_changes",
    "get_metrics",
    "latest_file",
    "latest_inventory",
    "latest_order",
    "load_catalogs",
    "read_table",
    "safe_parse_date",
    "snapshot",
    "toast_err",
    "toast_info",
    "toast_ok",
    "write_table",
]
