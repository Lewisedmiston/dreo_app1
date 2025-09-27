"""Menu engineering insights blending recipes, inventory, and orders."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from common.costing import compute_recipe_costs
from common.db import (
    latest_inventory,
    latest_order,
    read_table,
    toast_info,
)

st.set_page_config(page_title="Menu Management", layout="wide")

st.title("🍽️ Menu Management")
st.caption(
    "Understand profitability, watch par gaps, and spot engineering opportunities at a glance."
)


def normalize_inventory(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    inventory = df.copy()
    columns_lower = {c.lower(): c for c in inventory.columns}

    name_col = columns_lower.get("description")
    if name_col is None:
        for candidate in ["item", "ingredient", "name"]:
            if candidate in columns_lower:
                name_col = columns_lower[candidate]
                break
    qty_col = None
    for candidate in ["on_hand", "on_hand_qty", "qty", "quantity", "count"]:
        if candidate in columns_lower:
            qty_col = columns_lower[candidate]
            break

    rename_map = {}
    if name_col:
        rename_map[name_col] = "description"
    if qty_col:
        rename_map[qty_col] = "inventory_qty"

    inventory = inventory.rename(columns=rename_map)
    if "description" not in inventory.columns:
        inventory["description"] = inventory.index.astype(str)
    if "inventory_qty" not in inventory.columns:
        inventory["inventory_qty"] = 0

    inventory["description"] = inventory["description"].astype(str).str.strip()
    inventory["inventory_qty"] = pd.to_numeric(
        inventory["inventory_qty"], errors="coerce"
    ).fillna(0.0)
    return inventory[["description", "inventory_qty"]]


recipes = read_table("recipes")
recipe_lines = read_table("recipe_lines")
ingredients = read_table("ingredient_master")

costed_lines, recipe_summary = compute_recipe_costs(recipes, recipe_lines, ingredients)

if recipe_summary.empty:
    toast_info("Add recipes to unlock menu engineering insights.")
    st.stop()

recipe_summary = recipe_summary.fillna(0)
recipe_summary["margin_pct"] = recipe_summary["margin_pct"] * 100
recipe_summary["cost_pct"] = recipe_summary.apply(
    lambda row: (row["recipe_cost"] / row["menu_price"] * 100)
    if row["menu_price"] > 0
    else None,
    axis=1,
)

total_sales_potential = recipe_summary["menu_price"].sum()
total_recipe_cost = recipe_summary["recipe_cost"].sum()
total_margin = recipe_summary["margin"].sum()
avg_margin_pct = recipe_summary["margin_pct"].replace({0: pd.NA}).mean()

metric_cols = st.columns(4)
metric_cols[0].metric("Potential sales", f"${total_sales_potential:,.0f}")
metric_cols[1].metric("Theoretical food cost", f"${total_recipe_cost:,.0f}")
metric_cols[2].metric("Margin dollars", f"${total_margin:,.0f}")
metric_cols[3].metric(
    "Average margin %",
    f"{avg_margin_pct:.1f}%" if pd.notna(avg_margin_pct) else "—",
)

price_median = recipe_summary["menu_price"].median()
margin_pct_median = recipe_summary["margin_pct"].replace({0: pd.NA}).median()


def classify_menu_item(row: pd.Series) -> str:
    margin_pct = row.get("margin_pct")
    price = row.get("menu_price")
    if pd.isna(margin_pct):
        return "Monitor"
    high_margin = margin_pct >= margin_pct_median if pd.notna(margin_pct_median) else margin_pct >= 50
    high_price = price >= price_median if pd.notna(price_median) else price >= 15
    if high_margin and high_price:
        return "⭐ Star"
    if high_margin and not high_price:
        return "🐎 Plowhorse"
    if not high_margin and high_price:
        return "💣 Puzzle"
    return "🛠️ Dog"


recipe_summary["classification"] = recipe_summary.apply(classify_menu_item, axis=1)
menu_table = recipe_summary[
    [
        "name",
        "menu_price",
        "recipe_cost",
        "margin",
        "margin_pct",
        "cost_per_serving",
        "classification",
    ]
].rename(
    columns={
        "name": "Recipe",
        "menu_price": "Menu $",
        "recipe_cost": "Cost $",
        "margin": "Margin $",
        "margin_pct": "Margin %",
        "cost_per_serving": "Cost / serving",
    }
)

st.subheader("Menu engineering matrix")
st.dataframe(
    menu_table.style.format(
        {
            "Menu $": "$%.2f",
            "Cost $": "$%.2f",
            "Margin $": "$%.2f",
            "Margin %": "%.1f%%",
            "Cost / serving": "$%.2f",
        }
    ),
    use_container_width=True,
    hide_index=True,
)


inventory_snapshot = latest_inventory()
inventory_normalized = normalize_inventory(inventory_snapshot) if inventory_snapshot is not None else pd.DataFrame()

ingredients = ingredients.copy()
ingredients["description"] = ingredients.get("description", "").fillna("").astype(str)
ingredients["par"] = pd.to_numeric(ingredients.get("par", 0), errors="coerce").fillna(0.0)
ingredients["on_hand"] = pd.to_numeric(ingredients.get("on_hand", 0), errors="coerce").fillna(0.0)

if not inventory_normalized.empty:
    ingredients = ingredients.merge(
        inventory_normalized,
        on="description",
        how="left",
    )
    ingredients["inventory_qty"] = ingredients["inventory_qty"].fillna(ingredients["on_hand"])
    ingredients["on_hand"] = ingredients["inventory_qty"]

ingredients["par_gap"] = (ingredients["par"] - ingredients["on_hand"]).clip(lower=0)
par_shortfall = ingredients[ingredients["par_gap"] > 0].copy()

st.subheader("Par shortfalls")
if par_shortfall.empty:
    st.success("All ingredients are at or above par levels.")
else:
    par_shortfall = par_shortfall.sort_values("par_gap", ascending=False)
    st.dataframe(
        par_shortfall[["description", "par", "on_hand", "par_gap"]]
        .rename(
            columns={
                "description": "Ingredient",
                "par": "Par",
                "on_hand": "On hand",
                "par_gap": "Par gap",
            }
        )
        .style.format({"Par": "%.0f", "On hand": "%.0f", "Par gap": "%.0f"}),
        use_container_width=True,
        hide_index=True,
    )


orders_df = latest_order()
st.subheader("Most recent order export")
if orders_df is None:
    st.info("Export an order from the Build Order page to unlock vendor insights.")
else:
    order = orders_df.copy()
    order["order_qty"] = pd.to_numeric(order.get("order_qty", 0), errors="coerce").fillna(0.0)
    order["case_cost"] = pd.to_numeric(order.get("case_cost", 0), errors="coerce").fillna(0.0)
    if "line_total" not in order.columns:
        order["line_total"] = order["order_qty"] * order["case_cost"]
    order_total = order["line_total"].sum()
    order["vendor"] = order.get("vendor", pd.Series(["Unknown"] * len(order)))
    order["vendor"] = order["vendor"].fillna("Unknown")
    vendor_summary = (
        order.groupby("vendor")["line_total"].sum().reset_index().rename(
            columns={"vendor": "Vendor", "line_total": "Spend"}
        )
    )
    st.metric("Order total", f"${order_total:,.0f}")
    st.dataframe(
        vendor_summary.style.format({"Spend": "$%.0f"}),
        use_container_width=True,
        hide_index=True,
    )
