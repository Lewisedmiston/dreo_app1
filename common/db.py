"""Unified file-backed data helpers used throughout the Streamlit app."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Sequence

import pandas as pd
import streamlit as st
from filelock import FileLock, Timeout
from zoneinfo import ZoneInfo

from .constants import (
    CATALOGS_DIR,
    DATA_ROOT,
    DEFAULT_VENDORS,
    EXCEPTIONS_DIR,
    EXPORT_DIR,
    INGREDIENT_MASTER_FILE,
    INVENTORY_DIR,
    ORDERS_DIR,
    RECIPES_DIR,
    REQUIRED_CATALOG_FIELDS,
    TZ_NAME,
)
from . import utils

__all__ = [
    "CATALOGS_DIR",
    "DATA_ROOT",
    "DEFAULT_VENDORS",
    "EXCEPTIONS_DIR",
    "EXPORT_DIR",
    "INGREDIENT_MASTER_FILE",
    "INVENTORY_DIR",
    "ORDERS_DIR",
    "RECIPES_DIR",
    "append_table",
    "available_vendors",
    "detect_unsaved_changes",
    "get_metrics",
    "latest_file",
    "latest_inventory",
    "latest_order",
    "load_catalogs",
    "log_exception",
    "read_table",
    "safe_parse_date",
    "snapshot",
    "toast_err",
    "toast_info",
    "toast_ok",
    "write_table",
]

LOCK_TIMEOUT = float(os.getenv("DREO_DATA_LOCK_TIMEOUT", "5"))
TZ = ZoneInfo(TZ_NAME)

_DATA_DIRECTORIES: tuple[Path, ...] = (
    DATA_ROOT,
    CATALOGS_DIR,
    INVENTORY_DIR,
    ORDERS_DIR,
    RECIPES_DIR,
    EXCEPTIONS_DIR,
    EXPORT_DIR,
)

for directory in _DATA_DIRECTORIES:
    directory.mkdir(parents=True, exist_ok=True)


def _resolve(path: str | Path) -> Path:
    """Resolve a logical table path (relative to ``DATA_ROOT``) to a CSV file."""

    if isinstance(path, Path):
        candidate = path
    else:
        slug = str(path).strip()
        if slug.endswith(".csv"):
            candidate = Path(slug)
        else:
            candidate = Path(f"{slug}.csv")

    if not candidate.is_absolute():
        candidate = DATA_ROOT / candidate

    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def _lock_for(csv_path: Path) -> FileLock:
    """Return a :class:`FileLock` guarding ``csv_path``."""

    return FileLock(str(csv_path.with_suffix(csv_path.suffix + ".lock")), timeout=LOCK_TIMEOUT)


@contextmanager
def _locked(csv_path: Path) -> Iterator[None]:
    lock = _lock_for(csv_path)
    try:
        with lock:
            yield
    except Timeout as exc:  # pragma: no cover - defensive guard
        raise Timeout(f"Timed out waiting to write {csv_path}") from exc


def _timestamp() -> datetime:
    """Return the current timezone-aware datetime."""

    return datetime.now(tz=TZ)


def _atomic_write(target: Path, df: pd.DataFrame, **kwargs) -> None:
    temp_path = target.with_suffix(target.suffix + ".tmp")
    df.to_csv(temp_path, index=False, **kwargs)
    temp_path.replace(target)


@st.cache_data(show_spinner=False)
def read_table(path: str | Path, **kwargs) -> pd.DataFrame:
    """Read a CSV file stored within the data directory."""

    csv_path = _resolve(path)
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(csv_path, **kwargs)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def write_table(path: str | Path, df: pd.DataFrame, **kwargs) -> Path:
    """Persist ``df`` to the given logical path and clear associated caches."""

    csv_path = _resolve(path)
    with _locked(csv_path):
        _atomic_write(csv_path, df, **kwargs)
    utils.clear_data_caches()
    return csv_path


def append_table(path: str | Path, rows: Iterable[Dict[str, object]]) -> Path:
    """Append ``rows`` to a CSV file, creating it if required."""

    csv_path = _resolve(path)
    frame = pd.DataFrame(rows)
    with _locked(csv_path):
        if csv_path.exists():
            existing = pd.read_csv(csv_path)
            if not existing.empty:
                frame = pd.concat([existing, frame], ignore_index=True, copy=False)
        _atomic_write(csv_path, frame)
    utils.clear_data_caches()
    return csv_path


def snapshot(directory: Path | str, df: pd.DataFrame, prefix: str) -> Path:
    """Persist ``df`` as a timestamped snapshot within ``directory``."""

    base_dir = Path(directory)
    if not base_dir.is_absolute():
        base_dir = DATA_ROOT / base_dir
    base_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}.csv" if prefix else f"{ts}.csv"
    csv_path = base_dir / filename
    with _locked(csv_path):
        _atomic_write(csv_path, df)
    utils.clear_data_caches()
    return csv_path


def toast_ok(message: str) -> None:
    st.success(message, icon="✅")


def toast_err(message: str) -> None:
    st.error(message, icon="❌")


def toast_info(message: str) -> None:
    st.info(message, icon="ℹ️")


def safe_parse_date(value, *, default: Optional[datetime] = None, allow_today: bool = False) -> Optional[pd.Timestamp]:
    """Parse ``value`` into a pandas ``Timestamp`` using timezone awareness."""

    if value is None or value == "":
        if allow_today:
            return pd.Timestamp(_timestamp().date())
        return default

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        if allow_today:
            return pd.Timestamp(_timestamp().date())
        return default
    if isinstance(parsed, datetime) and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return pd.Timestamp(parsed)


@st.cache_data(show_spinner=False)
def load_catalogs() -> pd.DataFrame:
    """Concatenate all vendor catalogs into a single normalised DataFrame."""

    frames: list[pd.DataFrame] = []
    for catalog_file in sorted(CATALOGS_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(catalog_file)
        except Exception as exc:  # pragma: no cover - defensive logging
            toast_err(f"Failed to read {catalog_file.name}: {exc}")
            continue

        if df.empty:
            continue
        df = df.copy()
        df["vendor"] = df.get("vendor", catalog_file.stem)
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=sorted(REQUIRED_CATALOG_FIELDS))

    combined = pd.concat(frames, ignore_index=True, copy=False)
    combined = combined.drop_duplicates(subset=["vendor", "item_number"], keep="last")
    return combined


def available_vendors(*frames: pd.DataFrame, defaults: Optional[Sequence[str]] = None) -> list[str]:
    """Return a sorted list of vendor names derived from the supplied frames."""

    vendor_map: dict[str, str] = {}
    for frame in frames:
        if frame.empty or "vendor" not in frame.columns:
            continue
        series = frame["vendor"].dropna().astype(str)
        series = series.map(lambda name: name.strip()).replace("", pd.NA).dropna()
        for vendor in series:
            key = vendor.casefold()
            vendor_map.setdefault(key, vendor)

    vendors = [vendor_map[key] for key in sorted(vendor_map)]
    if vendors:
        return vendors

    if defaults is None:
        defaults = DEFAULT_VENDORS
    return list(defaults)


def latest_file(directory: Path) -> Optional[Path]:
    files = [p for p in directory.glob("*.csv") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


@st.cache_data(show_spinner=False)
def latest_inventory() -> Optional[pd.DataFrame]:
    latest = latest_file(INVENTORY_DIR)
    if latest is None:
        return None
    try:
        return pd.read_csv(latest)
    except Exception as exc:  # pragma: no cover - defensive logging
        toast_err(f"Unable to read inventory snapshot: {exc}")
        return None


@st.cache_data(show_spinner=False)
def latest_order() -> Optional[pd.DataFrame]:
    latest = latest_file(ORDERS_DIR)
    if latest is None:
        return None
    try:
        return pd.read_csv(latest)
    except Exception as exc:  # pragma: no cover - defensive logging
        toast_err(f"Unable to read order snapshot: {exc}")
        return None


@st.cache_data(show_spinner=False)
def get_metrics() -> Dict[str, str]:
    """Return key dashboard metrics derived from the data store."""

    catalogs = load_catalogs()
    ingredient_master = read_table(INGREDIENT_MASTER_FILE)

    active_skus = 0
    if not ingredient_master.empty:
        active_skus = ingredient_master["description"].nunique(dropna=True)
    elif not catalogs.empty:
        active_skus = catalogs["description"].nunique(dropna=True)

    latest_inventory_file = latest_file(INVENTORY_DIR)
    if latest_inventory_file is None:
        last_count = "Never"
    else:
        stamp = latest_inventory_file.stem
        parts = stamp.split("_")
        ts_part = "_".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        try:
            dt = datetime.strptime(ts_part, "%Y%m%d_%H%M%S").replace(tzinfo=TZ)
            last_count = dt.strftime("%b %d, %Y %I:%M %p")
        except ValueError:
            last_count = stamp

    latest_order_df = latest_order()
    open_lines = latest_order_df.shape[0] if latest_order_df is not None else 0

    return {
        "active_skus": f"{active_skus:,}",
        "last_count_date": last_count,
        "open_order_lines": f"{open_lines:,}",
    }


def detect_unsaved_changes(current: Dict[str, int], baseline: Optional[Dict[str, int]]) -> bool:
    baseline = baseline or {}
    return {k: v for k, v in current.items() if v} != {
        k: v for k, v in baseline.items() if v
    }


def log_exception(record: Dict[str, object]) -> Path:
    """Append an exception record to ``exceptions.csv`` atomically."""

    csv_path = EXCEPTIONS_DIR / "exceptions.csv"
    payload = record.copy()
    payload.setdefault("logged_at", _timestamp().isoformat())
    return append_table(csv_path, [payload])

