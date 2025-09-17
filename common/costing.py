from __future__ import annotations
from typing import Optional

CONVERSIONS_TO_OZ = {
    "oz": 1.0,
    "lb": 16.0,
    "g": 1/28.349523125,  # 1 g = 0.03527396195 oz
    "kg": 35.27396,
    "ml": 1/29.5735295625,  # 1 ml = 0.033814 oz
    "L": 33.814,
    "qt": 32.0,
    "gal": 128.0,
}

def to_oz(qty: float, uom: str) -> Optional[float]:
    if qty is None or uom is None:
        return None
    u = uom.lower()
    # Normalize
    if u == "l":
        u = "L"
    if u not in CONVERSIONS_TO_OZ:
        return None
    return qty * CONVERSIONS_TO_OZ[u]

def line_cost(qty: float, uom: str, cost_per_oz: float | None, cost_per_each: float | None) -> Optional[float]:
    # prefer oz if available
    if cost_per_oz is not None:
        oz = to_oz(qty, uom)
        if oz is None:
            return None
        return oz * cost_per_oz
    if cost_per_each is not None and uom.lower() in ("each", "ea"):
        return qty * cost_per_each
    return None
