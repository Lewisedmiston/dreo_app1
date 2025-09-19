"""Load vendor column-mapping presets from JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

PRESETS_DIR = Path("presets")


def load_presets() -> Dict[str, Dict[str, Any]]:
    presets: Dict[str, Dict[str, Any]] = {}
    for preset_file in PRESETS_DIR.glob("*.json"):
        try:
            with preset_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        vendor = data.get("vendor") or preset_file.stem.title()
        presets[vendor] = data
    return presets


def get_preset(vendor: str) -> Dict[str, Any]:
    return load_presets().get(vendor, {})


__all__ = ["get_preset", "load_presets", "PRESETS_DIR"]
