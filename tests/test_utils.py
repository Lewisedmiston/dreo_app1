from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd

from common.constants import TZ_NAME, OPTIONAL_ITEM_FIELDS, REQUIRED_ITEM_FIELDS
from common import utils


def test_normalize_items_with_catalog_enrichment():
    raw = pd.DataFrame(
        {
            "Item Description": ["Tomatoes ", None],
            "SKU": [" 123", "456"],
            "Case Pack": ["6", ""],
            "Case Cost": ["$12.50", 20],
            "Par Level": ["10", None],
            "OnHand": ["", 5],
            "Unit": ["case", None],
            "Price Date": ["2024-07-01", "07/04/2024"],
        }
    )

    catalogs = pd.DataFrame(
        {
            "Vendor": ["FreshCo", "DairyWorld"],
            "Item_Number": ["123", "456"],
            "Description": ["Tomatoes", "Mozzarella"],
        }
    )

    normalized = utils.normalize_items(raw, catalogs)

    assert list(normalized.columns[:5]) == ["vendor", "item_number", "description", "uom", "pack_size"]
    assert normalized.loc[0, "vendor"] == "FreshCo"
    assert normalized.loc[1, "vendor"] == "DairyWorld"
    assert normalized.loc[0, "item_number"] == "123"
    assert normalized.loc[0, "description"] == "Tomatoes"
    assert normalized.loc[0, "uom"] == "case"
    assert normalized.loc[0, "pack_size"] == 6.0
    assert normalized.loc[0, "case_cost"] == 12.50
    assert round(normalized.loc[0, "unit_cost"], 4) == round(12.50 / 6, 4)
    assert normalized.loc[0, "par"] == 10.0
    assert normalized.loc[1, "pack_size"] == 1.0
    assert normalized.loc[1, "uom"] == "ea"
    assert normalized.loc[0, "item_key"].startswith("freshco::123")

    price_date = normalized.loc[0, "price_date"]
    assert pd.notna(price_date)
    assert price_date.tzinfo == ZoneInfo(TZ_NAME)


def test_normalize_items_empty_returns_schema():
    normalized = utils.normalize_items(pd.DataFrame())
    expected_columns = set(list(REQUIRED_ITEM_FIELDS) + list(OPTIONAL_ITEM_FIELDS) + ["display_name", "search_key", "item_key"])
    assert set(normalized.columns) == expected_columns


def test_safe_parse_date_behaviour():
    tz = ZoneInfo(TZ_NAME)
    parsed = utils.safe_parse_date("2024-07-04")
    assert parsed is not None
    assert parsed.tzinfo == tz

    assert utils.safe_parse_date("invalid-date") is None

    today = utils.safe_parse_date("", allow_today=True)
    assert today is not None and today.tzinfo == tz
