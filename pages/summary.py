"""Executive summary dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from common import utils
from common.costing import compute_recipe_costs
from common.constants import INGREDIENT_MASTER_FILE
from common.db import latest_inventory, latest_order, load_catalogs, read_table

utils.page_setup("Summary")

st.title("📊 Summary")
st.caption("One-stop view of profitability, inventory health, and purchasing activity.")


def normalize_inventory(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["item_key", "description", "quantity"])
    inventory = df.copy()
    if "item_key" not in inventory.columns:
        inventory["item_key"] = (
            inventory.get("description", inventory.index.astype(str))
            .astype(str)
            .str.lower()
        )
    columns_lower = {c.lower(): c for c in inventory.columns}
    name_col = columns_lower.get("description")
    qty_col = None
    for candidate in ["quantity", "qty", "count", "on_hand", "inventory_qty"]:
        if candidate in columns_lower:
            qty_col = columns_lower[candidate]
            break
    rename_map = {}
    if name_col:
        rename_map[name_col] = "description"
    if qty_col:
        rename_map[qty_col] = "quantity"
    inventory = inventory.rename(columns=rename_map)
    inventory["description"] = inventory.get("description", inventory["item_key"]).astype(str)
    inventory["quantity"] = pd.to_numeric(inventory.get("quantity", 0), errors="coerce").fillna(0.0)
    return inventory[["item_key", "description", "quantity"]]


recipes = read_table("recipes")
recipe_lines = read_table("recipe_lines")
raw_ingredients = read_table(INGREDIENT_MASTER_FILE)
catalogs = load_catalogs()
ingredients = utils.normalize_items(raw_ingredients, catalogs)
ingredients["case_pack"] = ingredients["pack_size"]
ingredients["case_uom"] = ingredients["uom"]
ingredients["count_uom"] = ingredients["uom"]
ingredients["cost_per_count"] = ingredients.get("unit_cost", 0)

costed_lines, recipe_summary = compute_recipe_costs(recipes, recipe_lines, ingredients)
recipe_summary = recipe_summary.fillna(0)
recipe_count = recipe_summary.shape[0]

avg_margin_pct = recipe_summary["margin_pct"].replace({0: pd.NA}).mean()
avg_margin_pct_display = f"{avg_margin_pct*100:.1f}%" if pd.notna(avg_margin_pct) else "—"

inventory_snapshot = latest_inventory()
inventory_df = normalize_inventory(inventory_snapshot)

par_df = ingredients.copy()
par_df["par"] = pd.to_numeric(par_df.get("par", 0), errors="coerce").fillna(0.0)
par_df["on_hand"] = pd.to_numeric(par_df.get("on_hand", 0), errors="coerce").fillna(0.0)

if not inventory_df.empty:
    inventory_counts = inventory_df[["item_key", "quantity"]].rename(columns={"quantity": "inventory_qty"})
    par_df = par_df.merge(inventory_counts, on="item_key", how="left")
    par_df["on_hand"] = par_df["inventory_qty"].fillna(par_df["on_hand"])

par_df["par_gap"] = (par_df["par"] - par_df["on_hand"]).clip(lower=0)
total_par_gap = par_df["par_gap"].sum()

orders_df = latest_order()
order_total = 0.0
vendor_breakdown = pd.DataFrame(columns=["Vendor", "Spend"])
if orders_df is not None and not orders_df.empty:
    order = orders_df.copy()
    order["quantity"] = pd.to_numeric(order.get("quantity", order.get("order_qty", 0)), errors="coerce").fillna(0.0)
    order["case_cost"] = pd.to_numeric(order.get("case_cost", 0), errors="coerce").fillna(0.0)
    if "extended_cost" not in order.columns:
        order["extended_cost"] = order["quantity"] * order["case_cost"]
    order_total = float(order["extended_cost"].sum())
    order["vendor"] = order.get("vendor", pd.Series(["Unknown"] * len(order)))
    order["vendor"] = order["vendor"].fillna("Unknown")
    vendor_breakdown = (
        order.groupby("vendor")["extended_cost"].sum().reset_index().rename(
            columns={"vendor": "Vendor", "extended_cost": "Spend"}
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
    par_df[par_df["par_gap"] > 0]
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
