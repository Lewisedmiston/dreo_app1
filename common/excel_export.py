from __future__ import annotations
import pandas as pd
from datetime import datetime
from .db import get_conn

def _sheet(writer, name, df):
    df.to_excel(writer, sheet_name=name, index=False)
    ws = writer.sheets[name]
    # Freeze header row
    ws.freeze_panes(1, 0)
    # Auto filter
    ws.autofilter(0, 0, max(0, len(df)), max(0, len(df.columns)-1))

def export_workbook(path: str = "Menu_Costing_DREO.xlsx") -> str:
    conn = get_conn()
    # Fetch dataframes
    vendors = pd.read_sql_query("SELECT * FROM vendors", conn)
    catalogs = pd.read_sql_query("SELECT * FROM catalog_items", conn)
    ingredients = pd.read_sql_query("SELECT * FROM ingredients", conn)
    recipes = pd.read_sql_query("SELECT * FROM recipes", conn)
    recipe_lines = pd.read_sql_query("SELECT * FROM recipe_lines", conn)
    exceptions = pd.read_sql_query("SELECT * FROM exceptions", conn)
    changelog = pd.read_sql_query("SELECT * FROM changelog", conn)

    # Simple Menu Cost Summary join
    # Compute plate cost by summing line costs using last_cost_per_oz/each from ingredients
    ing_cost = ingredients[["id","last_cost_per_oz","last_cost_per_each"]].copy()
    rl = recipe_lines.merge(ing_cost, left_on="ref_id", right_on="id", how="left", suffixes=("","_ing"))
    # Calculate line costs (restored working version)
    from .costing import line_cost
    costs = []
    for _, r in rl.iterrows():
        if r["line_type"] == "INGREDIENT":
            c = line_cost(r["qty"], r["uom"], r["last_cost_per_oz"], r["last_cost_per_each"])
        else:
            c = None  # simple MVP: sub-recipe cost not expanded here
        costs.append(c if c is not None else 0.0)
    rl["line_cost"] = costs
    plate_costs = rl.groupby("recipe_id")["line_cost"].sum().reset_index(name="plate_cost")
    menu = recipes.merge(plate_costs, left_on="id", right_on="recipe_id", how="left")
    menu["plate_cost"] = menu["plate_cost"].fillna(0.0)
    menu["food_cost_pct"] = (menu["plate_cost"] / menu["menu_price"]).where(menu["menu_price"]>0).round(4)

    with pd.ExcelWriter(path, engine="xlsxwriter", datetime_format="yyyy-mm-dd", date_format="yyyy-mm-dd") as writer:
        _sheet(writer, "Ingredient Master", ingredients)
        _sheet(writer, "Vendor Catalogs", catalogs)
        _sheet(writer, "Recipes", recipes)
        _sheet(writer, "Recipe Lines", recipe_lines)
        _sheet(writer, "Menu Cost Summary", menu[["name","menu_price","plate_cost","food_cost_pct"]])
        _sheet(writer, "Exceptions_QA", exceptions)
        _sheet(writer, "Change Log", changelog)
        # simple tabs for Phase2 placeholders
        _sheet(writer, "High Cost Items", menu.sort_values("plate_cost", ascending=False).head(50))
        _sheet(writer, "Cross-Checks", pd.DataFrame())

    return path
