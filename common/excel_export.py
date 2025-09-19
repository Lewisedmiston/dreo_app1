from __future__ import annotations

"""Helpers for composing a multi-sheet Excel workbook from the file-backed store."""

from datetime import datetime
from io import BytesIO
from typing import Dict, Optional, Tuple

import pandas as pd

from .costing import line_cost
from .db import INVENTORY_DIR, ORDERS_DIR, latest_file, load_catalogs, read_table

INGREDIENT_MASTER_TABLE = "ingredient_master"
RECIPES_TABLE = "recipes/recipes"
RECIPE_LINES_TABLE = "recipes/recipe_lines"
EXCEPTIONS_TABLE = "exceptions/log"


def _sheet(writer: pd.ExcelWriter, name: str, df: pd.DataFrame) -> None:
    """Write a DataFrame to the workbook with frozen headers and auto-filter."""
    safe_df = df if df is not None else pd.DataFrame()
    safe_df.to_excel(writer, sheet_name=name, index=False)
    worksheet = writer.sheets[name]
    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, max(0, len(safe_df)), max(0, len(safe_df.columns) - 1))


def _to_number(value) -> Optional[float]:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        stripped = str(value).strip()
        if not stripped:
            return None
        return float(stripped.replace("$", ""))
    except Exception:
        return None


def _normalise_key(value: str | float | int | None) -> str:
    return str(value or "").strip().lower()


def _prepare_ingredient_index(ingredients: pd.DataFrame) -> Dict[str, pd.Series]:
    """Return lookup dictionaries for ingredient by id or description."""
    by_key: Dict[str, pd.Series] = {}
    if ingredients.empty:
        return by_key

    if "id" in ingredients.columns:
        for _, row in ingredients.iterrows():
            key = f"id::{row['id']}"
            by_key[key] = row

    name_col = None
    for candidate in ("description", "name", "ingredient"):
        if candidate in ingredients.columns:
            name_col = candidate
            break

    if name_col:
        for _, row in ingredients.iterrows():
            key = _normalise_key(row.get(name_col))
            if key:
                by_key[f"name::{key}"] = row

    return by_key


def _lookup_ingredient(row: pd.Series, index: Dict[str, pd.Series]) -> Optional[pd.Series]:
    """Try to locate the ingredient referenced by a recipe line."""
    if not index:
        return None

    if "ref_id" in row and pd.notna(row.get("ref_id")):
        candidate = index.get(f"id::{row['ref_id']}")
        if candidate is not None:
            return candidate

    for col in ("ingredient", "ingredient_name", "name", "ref_name", "description"):
        if col in row:
            key = _normalise_key(row.get(col))
            if key:
                candidate = index.get(f"name::{key}")
                if candidate is not None:
                    return candidate
    return None


def _extract_costs(ingredient: Optional[pd.Series]) -> Tuple[Optional[float], Optional[float]]:
    if ingredient is None:
        return None, None

    cost_per_each: Optional[float] = None
    for col in ("unit_cost", "cost_per_each", "cost_per_count", "last_cost_per_each"):
        if col in ingredient:
            value = _to_number(ingredient[col])
            if value is not None:
                cost_per_each = value
                break

    cost_per_oz: Optional[float] = None
    for col in ("cost_per_oz", "last_cost_per_oz"):
        if col in ingredient:
            value = _to_number(ingredient[col])
            if value is not None:
                cost_per_oz = value
                break

    case_cost = _to_number(ingredient.get("case_cost"))
    case_pack = _to_number(ingredient.get("case_pack"))
    if cost_per_each is None and case_cost is not None and case_pack not in (None, 0):
        cost_per_each = case_cost / case_pack

    if cost_per_oz is None and case_cost is not None:
        # Derive a rough oz cost if we know the pack unit
        pack_qty = case_pack
        pack_uom = _normalise_key(ingredient.get("case_uom") or ingredient.get("count_uom"))
        if pack_qty not in (None, 0):
            if pack_uom in ("oz", "ounce", "ounces"):
                cost_per_oz = case_cost / pack_qty
            elif pack_uom in ("lb", "pound", "pounds", "lbs"):
                cost_per_oz = case_cost / (pack_qty * 16)

    return cost_per_oz, cost_per_each


def _line_cost(row: pd.Series, ingredient_lookup: Dict[str, pd.Series]) -> float:
    if str(row.get("line_type", "INGREDIENT")).upper() != "INGREDIENT":
        return 0.0

    ingredient = _lookup_ingredient(row, ingredient_lookup)
    qty = _to_number(row.get("qty"))
    if qty is None or ingredient is None:
        return 0.0

    cost_per_oz, cost_per_each = _extract_costs(ingredient)
    uom = str(row.get("uom", "each") or "each").strip()
    computed = line_cost(qty, uom, cost_per_oz, cost_per_each)
    return float(computed) if computed is not None else 0.0


def _ensure_recipe_structure(recipes: pd.DataFrame) -> pd.DataFrame:
    if recipes.empty:
        return pd.DataFrame(columns=["id", "name", "menu_price"])

    data = recipes.copy()
    if "name" not in data.columns:
        for candidate in ("recipe_name", "Recipe", "Name"):
            if candidate in data.columns:
                data["name"] = data[candidate]
                break
        else:
            data["name"] = ""

    if "menu_price" not in data.columns:
        data["menu_price"] = 0.0

    data["menu_price"] = pd.to_numeric(data["menu_price"], errors="coerce").fillna(0.0)

    if "id" not in data.columns:
        data = data.reset_index(drop=False).rename(columns={"index": "id"})

    data["id"] = pd.to_numeric(data["id"], errors="coerce")
    return data


def _ensure_recipe_ids(recipes: pd.DataFrame, recipe_lines: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    recipes_norm = _ensure_recipe_structure(recipes)
    if recipe_lines.empty:
        return recipes_norm, pd.DataFrame(columns=recipe_lines.columns)

    lines = recipe_lines.copy()
    if "line_type" not in lines.columns:
        lines["line_type"] = "INGREDIENT"
    lines["line_type"] = lines["line_type"].fillna("INGREDIENT")

    if "recipe_id" in lines.columns:
        return recipes_norm, lines

    recipe_name_col = None
    for candidate in ("recipe", "recipe_name", "name"):
        if candidate in lines.columns:
            recipe_name_col = candidate
            break

    if recipe_name_col is None or "name" not in recipes_norm.columns:
        return recipes_norm, pd.DataFrame(columns=lines.columns)

    recipes_norm["__recipe_key"] = recipes_norm["name"].map(_normalise_key)
    lines["__recipe_key"] = lines[recipe_name_col].map(_normalise_key)

    lines = lines.merge(
        recipes_norm[["id", "__recipe_key"]],
        on="__recipe_key",
        how="left",
        suffixes=("", "_recipe"),
    )
    lines = lines.rename(columns={"id": "recipe_id"})
    lines = lines.drop(columns=["__recipe_key", "recipe_id_recipe"], errors="ignore")

    recipes_norm = recipes_norm.drop(columns=["__recipe_key"], errors="ignore")
    return recipes_norm, lines


def _menu_cost_summary(recipes: pd.DataFrame, recipe_lines: pd.DataFrame, ingredients: pd.DataFrame) -> pd.DataFrame:
    recipes_norm, lines = _ensure_recipe_ids(recipes, recipe_lines)
    if recipes_norm.empty or lines.empty or "recipe_id" not in lines.columns:
        return pd.DataFrame(columns=["name", "menu_price", "plate_cost", "food_cost_pct"])

    ingredient_lookup = _prepare_ingredient_index(ingredients)
    line_costs = []
    for _, row in lines.iterrows():
        line_costs.append(_line_cost(row, ingredient_lookup))
    lines["line_cost"] = line_costs

    plate_costs = (
        lines.groupby("recipe_id", dropna=True)["line_cost"].sum().reset_index(name="plate_cost")
    )

    merged = recipes_norm.merge(plate_costs, left_on="id", right_on="recipe_id", how="left")
    merged["plate_cost"] = merged["plate_cost"].fillna(0.0)
    merged["menu_price"] = pd.to_numeric(merged["menu_price"], errors="coerce").fillna(0.0)
    merged["food_cost_pct"] = (
        (merged["plate_cost"] / merged["menu_price"]).where(merged["menu_price"] > 0).fillna(0.0)
    )

    summary = merged[["name", "menu_price", "plate_cost", "food_cost_pct"]].copy()
    return summary.sort_values("name")


def export_workbook() -> Tuple[str, bytes]:
    """Build the export workbook in-memory and return the filename + bytes."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Menu_Costing_DREO_{timestamp}.xlsx"

    ingredients = read_table(INGREDIENT_MASTER_TABLE)
    catalogs = load_catalogs()
    recipes = read_table(RECIPES_TABLE)
    recipe_lines = read_table(RECIPE_LINES_TABLE)
    exceptions = read_table(EXCEPTIONS_TABLE)

    latest_inventory_path = latest_file(INVENTORY_DIR)
    latest_order_path = latest_file(ORDERS_DIR)

    inventory = pd.read_csv(latest_inventory_path) if latest_inventory_path else pd.DataFrame()
    order = pd.read_csv(latest_order_path) if latest_order_path else pd.DataFrame()

    menu_summary = _menu_cost_summary(recipes, recipe_lines, ingredients)

    if not ingredients.empty:
        if "cost_per_count" not in ingredients.columns and {"case_cost", "case_pack"}.issubset(ingredients.columns):
            case_cost = pd.to_numeric(ingredients.get("case_cost"), errors="coerce")
            case_pack = pd.to_numeric(ingredients.get("case_pack"), errors="coerce")
            with pd.option_context("mode.use_inf_as_na", True):
                ingredients["cost_per_count"] = (case_cost / case_pack).fillna(0.0)

    buffer = BytesIO()
    with pd.ExcelWriter(
        buffer,
        engine="xlsxwriter",
        datetime_format="yyyy-mm-dd",
        date_format="yyyy-mm-dd",
    ) as writer:
        _sheet(writer, "Ingredient Master", ingredients)
        _sheet(writer, "Vendor Catalogs", catalogs)
        _sheet(writer, "Recipes", recipes)
        _sheet(writer, "Recipe Lines", recipe_lines)
        _sheet(writer, "Menu Cost Summary", menu_summary)
        _sheet(writer, "Exceptions_QA", exceptions)
        _sheet(writer, "Latest Inventory", inventory)
        _sheet(writer, "Latest Order", order)

        sources = []
        if latest_inventory_path:
            sources.append(
                {
                    "dataset": "Inventory",
                    "file": latest_inventory_path.name,
                    "updated": datetime.fromtimestamp(latest_inventory_path.stat().st_mtime).isoformat(),
                }
            )
        if latest_order_path:
            sources.append(
                {
                    "dataset": "Order",
                    "file": latest_order_path.name,
                    "updated": datetime.fromtimestamp(latest_order_path.stat().st_mtime).isoformat(),
                }
            )
        if sources:
            _sheet(writer, "Sources", pd.DataFrame(sources))
        else:
            _sheet(writer, "Sources", pd.DataFrame([{"dataset": "Inventory", "file": "", "updated": ""}]).head(0))

    buffer.seek(0)
    return filename, buffer.getvalue()


__all__ = [
    "export_workbook",
]
