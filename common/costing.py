from __future__ import annotations
from typing import Optional

import pandas as pd

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


def prepare_ingredient_costs(ingredients: pd.DataFrame) -> pd.DataFrame:
    """Return ingredient data with normalized cost columns for recipe costing."""

    if ingredients is None or ingredients.empty:
        return pd.DataFrame(
            columns=[
                "ingredient_key",
                "description",
                "vendor",
                "item_number",
                "cost_per_oz",
                "cost_per_each",
                "default_uom",
            ]
        )

    df = ingredients.copy()
    if "description" not in df.columns:
        df["description"] = df.get("name", "")

    df["ingredient_key"] = df["description"].fillna("").astype(str).str.strip()
    df["vendor"] = df.get("vendor", "").fillna("")
    df["item_number"] = df.get("item_number", "").fillna("")

    numeric_cols = ["case_pack", "case_cost", "cost_per_count"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = 0.0

    df["case_uom"] = df.get("case_uom", "").fillna("")
    df["count_uom"] = df.get("count_uom", "").fillna("")

    cost_per_each = df.get("cost_per_count", pd.Series(dtype=float)).copy()

    mask_each = df["count_uom"].str.lower().isin({"each", "ea", "ct"})
    calc_each = pd.Series(index=df.index, dtype=float)
    calc_each.loc[mask_each] = (
        df.loc[mask_each, "case_cost"]
        / df.loc[mask_each, "case_pack"].replace({0: pd.NA})
    )
    cost_per_each = cost_per_each.fillna(calc_each)

    df["cost_per_each"] = cost_per_each

    total_oz = df.apply(
        lambda row: to_oz(row["case_pack"], row.get("case_uom")), axis=1
    )
    df["cost_per_oz"] = [
        (row_cost / total) if total not in (None, 0) else None
        for row_cost, total in zip(df["case_cost"], total_oz)
    ]

    default_uom = []
    for _, row in df.iterrows():
        for candidate in (row.get("count_uom"), row.get("case_uom"), "each"):
            if candidate:
                default_uom.append(str(candidate))
                break
        else:
            default_uom.append("each")
    df["default_uom"] = default_uom

    return df[
        [
            "ingredient_key",
            "description",
            "vendor",
            "item_number",
            "cost_per_oz",
            "cost_per_each",
            "default_uom",
        ]
    ]


def compute_recipe_costs(
    recipes: pd.DataFrame,
    recipe_lines: pd.DataFrame,
    ingredients: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute costed recipe lines and per-recipe profitability summaries."""

    ingredient_costs = prepare_ingredient_costs(ingredients)

    if recipe_lines is None or recipe_lines.empty:
        empty_lines = pd.DataFrame(
            columns=[
                "recipe_id",
                "line_id",
                "ingredient",
                "qty",
                "uom",
                "prep_note",
                "line_cost",
            ]
        )
        summary = pd.DataFrame(
            columns=[
                "recipe_id",
                "name",
                "menu_price",
                "recipe_cost",
                "margin",
                "margin_pct",
                "cost_per_serving",
                "yield_qty",
                "yield_uom",
            ]
        )
        return empty_lines, summary

    lines = recipe_lines.copy()
    for col in ("recipe_id", "ingredient"):
        if col not in lines.columns:
            lines[col] = ""

    if "line_id" not in lines.columns:
        lines["line_id"] = lines.groupby("recipe_id").cumcount() + 1

    numeric_cols = ["qty", "line_cost"]
    for col in numeric_cols:
        if col in lines.columns:
            lines[col] = pd.to_numeric(lines[col], errors="coerce")
        else:
            lines[col] = 0.0

    lines["uom"] = lines.get("uom", "").fillna("")
    lines["prep_note"] = lines.get("prep_note", "").fillna("")

    ingredient_lookup = (
        ingredient_costs.set_index("ingredient_key")
        if not ingredient_costs.empty
        else pd.DataFrame()
    )

    def compute_cost(row):
        key = str(row.get("ingredient", "")).strip()
        cost_per_oz = None
        cost_per_each = None
        default_uom = row.get("uom")
        if not ingredient_lookup.empty and key in ingredient_lookup.index:
            info = ingredient_lookup.loc[key]
            cost_per_oz = info.get("cost_per_oz")
            cost_per_each = info.get("cost_per_each")
            default_uom = row.get("uom") or info.get("default_uom")
        qty = row.get("qty")
        if pd.isna(qty):
            return None
        uom = default_uom or row.get("uom")
        if not uom:
            return None
        return line_cost(float(qty), str(uom), cost_per_oz, cost_per_each)

    lines["computed_cost"] = lines.apply(compute_cost, axis=1)
    existing_cost = lines.get("line_cost")
    if existing_cost is None:
        existing_cost = pd.Series(index=lines.index, dtype=float)
    else:
        existing_cost = pd.to_numeric(existing_cost, errors="coerce")
    lines["line_cost"] = lines["computed_cost"].fillna(existing_cost)
    lines["line_cost"] = lines["line_cost"].fillna(0.0).astype(float)

    if not ingredient_lookup.empty:
        lines["ingredient_key"] = lines["ingredient"].astype(str).str.strip()
        lines = lines.merge(
            ingredient_costs,
            on="ingredient_key",
            how="left",
            suffixes=("", "_ing"),
        )
        lines = lines.drop(columns=["key_0"], errors="ignore")

    recipe_cols = [
        "recipe_id",
        "name",
        "menu_price",
        "yield_qty",
        "yield_uom",
    ]
    recipes_slim = pd.DataFrame(columns=recipe_cols)
    if recipes is not None and not recipes.empty:
        recipes_slim = recipes.copy()
        for col in recipe_cols:
            if col not in recipes_slim.columns:
                recipes_slim[col] = 0 if "qty" in col else ""
        recipes_slim["menu_price"] = pd.to_numeric(
            recipes_slim["menu_price"], errors="coerce"
        )
        recipes_slim["yield_qty"] = pd.to_numeric(
            recipes_slim["yield_qty"], errors="coerce"
        )

    summary = (
        lines.groupby("recipe_id", dropna=False)["line_cost"].sum().reset_index()
    )
    summary = summary.merge(recipes_slim, on="recipe_id", how="left")
    summary = summary.rename(columns={"line_cost": "recipe_cost"})

    summary["menu_price"] = summary["menu_price"].fillna(0.0)
    summary["recipe_cost"] = summary["recipe_cost"].fillna(0.0)
    summary["yield_qty"] = summary["yield_qty"].fillna(0.0)

    summary["margin"] = summary["menu_price"] - summary["recipe_cost"]
    summary["margin_pct"] = summary.apply(
        lambda row: (row["margin"] / row["menu_price"])
        if row["menu_price"] not in (0, None)
        else None,
        axis=1,
    )
    summary["cost_per_serving"] = summary.apply(
        lambda row: (row["recipe_cost"] / row["yield_qty"])
        if row["yield_qty"] not in (0, None)
        else None,
        axis=1,
    )

    summary["margin_pct"] = pd.to_numeric(summary["margin_pct"], errors="coerce")
    summary["cost_per_serving"] = pd.to_numeric(
        summary["cost_per_serving"], errors="coerce"
    )

    return lines, summary
