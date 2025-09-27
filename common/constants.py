"""Centralized constants for Dreo Kitchen Ops data handling."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Final

__all__ = [
    "DATA_ROOT",
    "CATALOGS_DIR",
    "INVENTORY_DIR",
    "ORDERS_DIR",
    "RECIPES_DIR",
    "EXCEPTIONS_DIR",
    "DEFAULT_VENDORS",
    "REQUIRED_CATALOG_FIELDS",
    "slugify",
    "vendor_filename",
]

DATA_ROOT: Final[Path] = Path(os.getenv("DREO_DATA_DIR", "data"))
CATALOGS_DIR: Final[Path] = DATA_ROOT / "catalogs"
INVENTORY_DIR: Final[Path] = DATA_ROOT / "inventory_counts"
ORDERS_DIR: Final[Path] = DATA_ROOT / "orders"
RECIPES_DIR: Final[Path] = DATA_ROOT / "recipes"
EXCEPTIONS_DIR: Final[Path] = DATA_ROOT / "exceptions"

DEFAULT_VENDORS: Final[list[str]] = ["PFG", "Sysco", "Produce"]

REQUIRED_CATALOG_FIELDS: Final[set[str]] = {
    "vendor",
    "item_number",
    "description",
    "uom",
    "case_cost",
    "price_date",
}

_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Return a filesystem-safe slug for the provided vendor or filename."""
    value = value.strip().lower()
    slug = _slug_re.sub("-", value).strip("-")
    return slug or "vendor"


def vendor_filename(vendor: str, suffix: str = "csv") -> str:
    """Generate a canonical filename for a vendor asset."""
    suffix = suffix.lstrip(".")
    return f"{slugify(vendor)}.{suffix}"
