from __future__ import annotations
import re
import pandas as pd
import numpy as np
from .utils import to_float


def add_exception(*_args, **_kwargs):
    """Backward-compatible no-op placeholder for legacy DB exception logging."""
    return None

# Robust pack/size parser for patterns like '6/5 lb', '12/32 oz', '200 ct'
# Patterns for pack/size parsing - handles both "6/5 lb" and "200 ct" formats
PACK_RE = re.compile(
    r"""
    ^\s*
    (?P<pack_count>\d+)\s*[/x]\s*
    (?P<unit_qty>\d*\.?\d+)\s*
    (?P<unit_uom>lb|pound|oz|ounce|g|kg|ml|l|ct|each|ea)
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Single unit pattern for cases like "200 ct", "5 lb", etc.
SINGLE_UNIT_RE = re.compile(
    r"""
    ^\s*
    (?P<unit_qty>\d*\.?\d+)\s*
    (?P<unit_uom>lb|pound|oz|ounce|g|kg|ml|l|ct|each|ea)
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

UOM_MAP = {
    "lb": "lb", "pound": "lb",
    "oz": "oz", "ounce": "oz",
    "g": "g", "kg": "kg",
    "ml": "ml", "l": "L",
    "ct": "each", "each": "each", "ea": "each",
}

def parse_packsize(s: str) -> tuple[int|None, float|None, str|None]:
    if s is None:
        return None, None, None
    original = str(s).strip()
    s = original.lower().replace(" ", "")
    s = s.replace("pounds", "lb").replace("pound", "lb").replace("ounces", "oz").replace("ounce", "oz")
    s = s.replace("liter", "l").replace("liters", "l")
    
    # Try pack/unit pattern first (e.g., "6/5 lb")
    m = PACK_RE.match(s)
    if m:
        pack = int(m.group("pack_count"))
        unit_qty = float(m.group("unit_qty"))
        unit_uom = UOM_MAP.get(m.group("unit_uom"), m.group("unit_uom"))
        return pack, unit_qty, unit_uom
    
    # Try single unit pattern (e.g., "200 ct", "5 lb")
    m = SINGLE_UNIT_RE.match(s)
    if m:
        unit_qty = float(m.group("unit_qty"))
        unit_uom = UOM_MAP.get(m.group("unit_uom"), m.group("unit_uom"))
        # For single units, assume pack count of 1
        return 1, unit_qty, unit_uom
    
    return None, None, None

def compute_case_totals(pack, unit_qty, unit_uom) -> tuple[float|None, float|None]:
    from .costing import to_oz
    if pack is None or unit_qty is None or unit_uom is None:
        return None, None
    if unit_uom == "each":
        return None, float(pack * unit_qty)
    oz = to_oz(unit_qty, unit_uom)
    if oz is None:
        return None, None
    return float(pack * oz), None

REQUIRED_COLS = ["vendor", "item_number", "description", "pack_size", "price", "price_date"]

def normalize_catalog(df: pd.DataFrame, conn) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        vendor = str(r.get("vendor", "")).strip() or "UNKNOWN"
        item_number = str(r.get("item_number", "")).strip()
        description = str(r.get("description", "")).strip()
        pack_size_raw = str(r.get("pack_size", "")).strip()
        price = to_float(r.get("price"))
        price_date = str(r.get("price_date", "")).strip()

        if not item_number:
            add_exception(conn, "UNMAPPED_INGREDIENT", f"Missing item_number for {description}")
            continue

        pack, unit_qty, unit_uom = parse_packsize(pack_size_raw)
        case_total_oz, case_total_each = compute_case_totals(pack, unit_qty, unit_uom)
        cost_per_oz = (price / case_total_oz) if (case_total_oz and price) else None
        cost_per_each = (price / case_total_each) if (case_total_each and price) else None

        rows.append({
            "vendor": vendor,
            "item_number": item_number,
            "description": description,
            "pack_size_raw": pack_size_raw,
            "pack_count": pack,
            "unit_qty": unit_qty,
            "unit_uom": unit_uom,
            "case_total_oz": case_total_oz,
            "case_total_each": case_total_each,
            "price": price,
            "price_date": price_date,
            "cost_per_oz": cost_per_oz,
            "cost_per_each": cost_per_each,
        })
    return pd.DataFrame(rows)

def process_catalog_dataframe(df: pd.DataFrame, vendor_id: int) -> pd.DataFrame:
    """Process uploaded catalog dataframe into the format expected by the database."""
    from .db import get_db_connection
    
    processed_rows = []
    with get_db_connection() as conn:
        for _, row in df.iterrows():
            # Map the expected columns from the upload page
            vendor_item_code = str(row.get("vendor_item_code", "")).strip()
            item_description = str(row.get("item_description", "")).strip()
            pack_size_str = str(row.get("pack_size_str", "")).strip()
            case_price = to_float(row.get("case_price"))
            price_date = str(row.get("price_date", "")).strip()
            
            if not vendor_item_code:
                add_exception(conn, "MISSING_ITEM_CODE", f"Missing vendor item code for {item_description}")
                continue
                
            # Skip rows with missing or invalid prices - comprehensive validation
            if (
                case_price is None or 
                case_price <= 0 or 
                not isinstance(case_price, (int, float)) or 
                str(case_price).strip() == "" or
                str(case_price).lower() in ['nan', 'null', 'none', ''] or
                pd.isna(case_price) or
                pd.isnull(case_price)
            ):
                add_exception(conn, "MISSING_PRICE", f"Missing or invalid price for item {vendor_item_code}: {item_description} (price: {repr(case_price)})")
                continue
                
            # Skip rows with missing price_date (NOT NULL constraint)
            if not price_date or price_date.strip() == "":
                from datetime import date
                price_date = str(date.today())
                add_exception(conn, "MISSING_PRICE_DATE", f"Missing price date for item {vendor_item_code}, using today's date")
                
            # Parse pack size information
            pack_count, unit_qty, unit_uom = parse_packsize(pack_size_str)
            case_total_oz, case_total_each = compute_case_totals(pack_count, unit_qty, unit_uom)
            
            # Calculate cost per unit
            cost_per_oz = (case_price / case_total_oz) if (case_total_oz and case_price) else None
            cost_per_each = (case_price / case_total_each) if (case_total_each and case_price) else None
            
            # Build base row data
            row_data = {
                "vendor_id": vendor_id,
                "vendor_name": "",  # Will be populated in upload page
                "item_number": vendor_item_code,
                "description": item_description,
                "pack_size_raw": pack_size_str,
                "pack_count": pack_count,
                "unit_qty": unit_qty,
                "unit_uom": unit_uom,
                "case_total_oz": case_total_oz,
                "case_total_each": case_total_each,
                "price": case_price,
                "price_date": price_date,
                "cost_per_oz": cost_per_oz,
                "cost_per_each": cost_per_each,
            }
            
            # Add inventory fields if they exist in the input data (handle both naming conventions)
            if "brand" in row:
                row_data["brand"] = str(row.get("brand", "")).strip()
            if "category" in row:
                row_data["category"] = str(row.get("category", "")).strip()
            if "par_level" in row:
                par_val = row.get("par_level")
                row_data["par_level"] = to_float(par_val) if par_val is not None else None
            if "on_hand_qty" in row or "on_hand" in row:
                onhand_val = row.get("on_hand_qty") or row.get("on_hand")
                row_data["on_hand_qty"] = to_float(onhand_val) if onhand_val is not None else None
            if "order_qty" in row:
                order_val = row.get("order_qty")
                row_data["order_qty"] = to_float(order_val) if order_val is not None else None
                
            processed_rows.append(row_data)
    
    # Create DataFrame and perform final validation
    result_df = pd.DataFrame(processed_rows)
    
    if not result_df.empty:
        # Final cleanup: ensure no NaN/NULL values in required fields
        result_df = result_df.dropna(subset=['price', 'price_date', 'item_number', 'vendor_id']).copy()
        
        # Ensure price is numeric and positive
        result_df = result_df[result_df['price'] > 0].copy()
        
        # Ensure price_date is not empty (convert to string first, then filter)
        price_date_mask = result_df['price_date'].astype(str).str.strip() != ''
        result_df = result_df[price_date_mask].copy()
        
        # Replace any remaining NaN values with safe defaults
        result_df = result_df.fillna({
            'description': '',
            'pack_size_raw': '',
            'unit_uom': '',
            'cost_per_oz': 0.0,
            'cost_per_each': 0.0
        })
    
    return result_df
