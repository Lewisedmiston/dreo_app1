"""Executive summary dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from common.costing import compute_recipe_costs
from common.db import latest_inventory, latest_order, read_table

st.set_page_config(page_title="Summary", layout="wide")

st.title("📊 Summary")
st.caption("One-stop view of profitability, inventory health, and purchasing activity.")


def normalize_inventory(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["description", "inventory_qty"])
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
recipe_summary = recipe_summary.fillna(0)
recipe_count = recipe_summary.shape[0]

avg_margin_pct = recipe_summary["margin_pct"].replace({0: pd.NA}).mean()
avg_margin_pct_display = f"{avg_margin_pct*100:.1f}%" if pd.notna(avg_margin_pct) else "—"

inventory_snapshot = latest_inventory()
inventory_df = normalize_inventory(inventory_snapshot)

ingredients = ingredients.copy()
ingredients["description"] = ingredients.get("description", "").fillna("").astype(str)
ingredients["par"] = pd.to_numeric(ingredients.get("par", 0), errors="coerce").fillna(0.0)
ingredients["on_hand"] = pd.to_numeric(ingredients.get("on_hand", 0), errors="coerce").fillna(0.0)

if not inventory_df.empty:
    ingredients = ingredients.merge(inventory_df, on="description", how="left")
    ingredients["on_hand"] = ingredients["inventory_qty"].fillna(ingredients["on_hand"])

ingredients["par_gap"] = (ingredients["par"] - ingredients["on_hand"]).clip(lower=0)
total_par_gap = ingredients["par_gap"].sum()

orders_df = latest_order()
order_total = 0.0
vendor_breakdown = pd.DataFrame(columns=["Vendor", "Spend"])
if orders_df is not None and not orders_df.empty:
    order = orders_df.copy()
    order["order_qty"] = pd.to_numeric(order.get("order_qty", 0), errors="coerce").fillna(0.0)
    order["case_cost"] = pd.to_numeric(order.get("case_cost", 0), errors="coerce").fillna(0.0)
    if "line_total" not in order.columns:
        order["line_total"] = order["order_qty"] * order["case_cost"]
    order_total = float(order["line_total"].sum())
    order["vendor"] = order.get("vendor", pd.Series(["Unknown"] * len(order)))
    order["vendor"] = order["vendor"].fillna("Unknown")
    vendor_breakdown = (
        order.groupby("vendor")["line_total"].sum().reset_index().rename(
            columns={"vendor": "Vendor", "line_total": "Spend"}
        )
    )

metric_cols = st.columns(4)
metric_cols[0].metric("Recipes costed", f"{recipe_count}")
metric_cols[1].metric("Average margin %", avg_margin_pct_display)
metric_cols[2].metric("Units below par", f"{total_par_gap:,.0f}")
metric_cols[3].metric("Latest order", f"${order_total:,.0f}")

top_margin = (
    recipe_summary.sort_values("margin", ascending=False)
    .head(5)
    .rename(
        columns={
            "name": "Recipe",
            "menu_price": "Menu $",
            "recipe_cost": "Cost $",
            "margin": "Margin $",
            "margin_pct": "Margin %",
        }
    )
)

par_watch = (
    ingredients[ingredients["par_gap"] > 0]
    .sort_values("par_gap", ascending=False)
    .head(5)
    .rename(
        columns={
            "description": "Ingredient",
            "par": "Par",
            "on_hand": "On hand",
            "par_gap": "Par gap",
        }
    )
)

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Top margin drivers")
    if top_margin.empty:
        st.info("Add menu items to surface profitability insights.")
    else:
        st.dataframe(
            top_margin[["Recipe", "Menu $", "Cost $", "Margin $", "Margin %"]]
            .style.format(
                {
                    "Menu $": "$%.2f",
                    "Cost $": "$%.2f",
                    "Margin $": "$%.2f",
                    "Margin %": "%.1f%%",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

with right_col:
    st.subheader("Par gap watchlist")
    if par_watch.empty:
        st.success("No ingredients are below par.")
    else:
        st.dataframe(
            par_watch.style.format({"Par": "%.0f", "On hand": "%.0f", "Par gap": "%.0f"}),
            use_container_width=True,
            hide_index=True,
        )

st.subheader("Vendor spend snapshot")
if vendor_breakdown.empty:
    st.info("Export an order to see spend by vendor.")
else:
    st.dataframe(
        vendor_breakdown.style.format({"Spend": "$%.0f"}),
        use_container_width=True,
        hide_index=True,
    )
