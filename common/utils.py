from __future__ import annotations
import re
from datetime import datetime

ISO = "%Y-%m-%d"

def iso_today() -> str:
    return datetime.now().strftime(ISO)

_money = re.compile(r"[^0-9.]+")
def to_float(x, default=0.0):
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return default
    s = _money.sub("", s)
    try:
        return float(s)
    except ValueError:
        return default
