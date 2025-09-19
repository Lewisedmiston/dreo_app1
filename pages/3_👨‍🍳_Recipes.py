"""Interactive recipe builder backed by the CSV data layer."""

from __future__ import annotations

from uuid import uuid4

import pandas as pd
import streamlit as st

from common.costing import compute_recipe_costs, prepare_ingredient_costs
from common.db import read_table, toast_err, toast_info, toast_ok, write_table

st.set_page_config(page_title="Recipes", layout="wide")

st.title("👨‍🍳 Recipes")
st.caption("Cost dishes, track profitability, and keep prep notes in one place.")


@st.cache_data(show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    recipes_df = read_table("recipes")
    lines_df = read_table("recipe_lines")
    ingredients_df = read_table("ingredient_master")
    return recipes_df, lines_df, ingredients_df


recipes, recipe_lines, ingredients = load_data()

recipe_defaults = {
    "recipe_id": "",
    "name": "",
    "category": "",
    "yield_qty": 1.0,
    "yield_uom": "each",
    "menu_price": 0.0,
    "notes": "",
}

if recipes.empty:
    recipes = pd.DataFrame(columns=list(recipe_defaults.keys()))

for column, default in recipe_defaults.items():
    if column not in recipes.columns:
        recipes[column] = default

if "recipe_id" not in recipes.columns:
    recipes["recipe_id"] = ""

missing_ids = recipes["recipe_id"].isin(["", None, pd.NA])
if missing_ids.any():
    recipes.loc[missing_ids, "recipe_id"] = [str(uuid4()) for _ in range(missing_ids.sum())]
    write_table("recipes", recipes)

numeric_recipe_cols = ["yield_qty", "menu_price"]
for col in numeric_recipe_cols:
    recipes[col] = pd.to_numeric(recipes[col], errors="coerce").fillna(
        recipe_defaults.get(col, 0.0)
    )

line_columns = ["recipe_id", "line_id", "ingredient", "qty", "uom", "prep_note", "line_cost"]
if recipe_lines.empty:
    recipe_lines = pd.DataFrame(columns=line_columns)

for col in line_columns:
    if col not in recipe_lines.columns:
        recipe_lines[col] = 0 if col in {"qty", "line_cost"} else ""

recipe_lines["qty"] = pd.to_numeric(recipe_lines["qty"], errors="coerce").fillna(0.0)
recipe_lines["line_cost"] = pd.to_numeric(
    recipe_lines["line_cost"], errors="coerce"
).fillna(0.0)

ingredient_costs = prepare_ingredient_costs(ingredients)
costed_lines, recipe_summary = compute_recipe_costs(recipes, recipe_lines, ingredients)

ingredient_options = ingredient_costs["ingredient_key"].dropna().tolist()
ingredient_options = sorted(dict.fromkeys(ingredient_options))

if not ingredient_options:
    toast_info("Populate the Ingredient Master to unlock the recipe builder.")

if "selected_recipe_id" not in st.session_state:
    st.session_state.selected_recipe_id = (
        recipes["recipe_id"].iloc[0] if not recipes.empty else None
    )


def create_recipe(name: str, category: str, yield_qty: float, yield_uom: str, price: float) -> None:
    new_id = str(uuid4())
    row = {
        "recipe_id": new_id,
        "name": name.strip(),
        "category": category.strip(),
        "yield_qty": yield_qty,
        "yield_uom": yield_uom.strip() or "each",
        "menu_price": price,
        "notes": "",
    }
    updated = pd.concat([recipes, pd.DataFrame([row])], ignore_index=True)
    write_table("recipes", updated)
    toast_ok(f"Created recipe '{row['name']}'")
    st.session_state.selected_recipe_id = new_id
    st.cache_data.clear()
    st.rerun()


library_col, builder_col = st.columns([1, 2])

with library_col:
    st.subheader("Recipe library")
    if recipe_summary.empty:
        st.info("Add your first recipe to begin costing.")
    else:
        display_cols = recipe_summary.copy()
        display_cols["margin_pct"] = display_cols["margin_pct"].fillna(0) * 100
        display_cols["cost_per_serving"] = display_cols["cost_per_serving"].fillna(0)
        st.dataframe(
            display_cols[["name", "menu_price", "recipe_cost", "margin", "margin_pct"]]
            .rename(
                columns={
                    "name": "Recipe",
                    "menu_price": "Menu $",
                    "recipe_cost": "Cost $",
                    "margin": "Margin $",
                    "margin_pct": "Margin %",
                }
            )
            .style.format({"Menu $": "$%.2f", "Cost $": "$%.2f", "Margin $": "$%.2f", "Margin %": "%.1f%%"}),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("➕ Add recipe"):
        with st.form("new_recipe_form", clear_on_submit=True):
            new_name = st.text_input("Name", placeholder="Fried Chicken Sandwich")
            new_category = st.text_input("Category", placeholder="Sandwiches")
            new_yield = st.number_input("Yield qty", min_value=0.0, value=1.0)
            new_uom = st.text_input("Yield unit", value="each")
            new_price = st.number_input("Menu price", min_value=0.0, value=0.0, step=0.5)
            create_clicked = st.form_submit_button("Create recipe", type="primary")

            if create_clicked:
                if not new_name.strip():
                    toast_err("Recipe name is required")
                else:
                    create_recipe(new_name, new_category, new_yield, new_uom, new_price)

    recipe_choices = {
        r.get("name", f"Recipe {i+1}") or f"Recipe {i+1}": r["recipe_id"]
        for i, r in recipes.sort_values("name", na_position="last").iterrows()
    }
    if recipe_choices:
        selected_name = st.selectbox(
            "Edit recipe",
            list(recipe_choices.keys()),
            index=list(recipe_choices.values()).index(st.session_state.selected_recipe_id)
            if st.session_state.selected_recipe_id in recipe_choices.values()
            else 0,
        )
        st.session_state.selected_recipe_id = recipe_choices[selected_name]


if not recipes.empty and st.session_state.selected_recipe_id:
    recipe_id = st.session_state.selected_recipe_id
    current_recipe = recipes[recipes["recipe_id"] == recipe_id].iloc[0].to_dict()

    with builder_col:
        st.subheader(f"Build: {current_recipe.get('name') or 'Untitled'}")
        header_cols = st.columns(4)
        name_val = header_cols[0].text_input(
            "Recipe name", value=current_recipe.get("name", ""), key=f"recipe_name_{recipe_id}"
        )
        category_val = header_cols[1].text_input(
            "Category", value=current_recipe.get("category", ""), key=f"recipe_cat_{recipe_id}"
        )
        yield_qty_val = header_cols[2].number_input(
            "Yield qty",
            min_value=0.0,
            value=float(current_recipe.get("yield_qty", 1.0) or 0.0),
            step=0.25,
            key=f"recipe_yield_{recipe_id}",
        )
        yield_uom_val = header_cols[3].text_input(
            "Yield unit",
            value=current_recipe.get("yield_uom", "each"),
            key=f"recipe_yielduom_{recipe_id}",
        )

        price_cols = st.columns(2)
        menu_price_val = price_cols[0].number_input(
            "Menu price",
            min_value=0.0,
            value=float(current_recipe.get("menu_price", 0.0) or 0.0),
            step=0.5,
            key=f"recipe_price_{recipe_id}",
        )
        notes_val = price_cols[1].text_input(
            "Notes",
            value=current_recipe.get("notes", ""),
            key=f"recipe_notes_{recipe_id}",
        )

        base_lines = costed_lines[costed_lines["recipe_id"] == recipe_id][
            ["ingredient", "qty", "uom", "prep_note"]
        ].copy()

        if base_lines.empty:
            base_lines = pd.DataFrame(
                [{"ingredient": "", "qty": 0.0, "uom": "", "prep_note": ""}]
            )

        base_lines["qty"] = pd.to_numeric(base_lines["qty"], errors="coerce").fillna(0.0)
        base_lines["uom"] = base_lines["uom"].fillna("")
        base_lines["prep_note"] = base_lines["prep_note"].fillna("")

        editor_config = {
            "ingredient": st.column_config.SelectboxColumn(
                "Ingredient",
                options=ingredient_options,
                help="Choose from the Ingredient Master",
            ),
            "qty": st.column_config.NumberColumn("Qty", min_value=0.0, step=0.1),
            "uom": st.column_config.SelectboxColumn(
                "UOM",
                options=["oz", "lb", "g", "kg", "ml", "L", "qt", "gal", "each", "ea"],
            ),
            "prep_note": st.column_config.TextColumn("Prep notes"),
        }

        edited_lines_raw = st.data_editor(
            base_lines,
            key=f"recipe_editor_{recipe_id}",
            column_config=editor_config,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
        )

        edited_lines = pd.DataFrame(edited_lines_raw)
        if not edited_lines.empty:
            edited_lines["ingredient"] = (
                edited_lines.get("ingredient", "").fillna("").astype(str).str.strip()
            )
            edited_lines["qty"] = pd.to_numeric(
                edited_lines.get("qty", 0), errors="coerce"
            ).fillna(0.0)
            edited_lines["uom"] = edited_lines.get("uom", "").fillna("")
            edited_lines["prep_note"] = edited_lines.get("prep_note", "").fillna("")
            edited_lines = edited_lines[
                edited_lines["ingredient"].str.len() > 0
            ]
        else:
            edited_lines = pd.DataFrame(columns=["ingredient", "qty", "uom", "prep_note"])

        edited_lines["recipe_id"] = recipe_id

        preview_recipes = recipes.copy()
        recipe_mask = preview_recipes["recipe_id"] == recipe_id
        preview_recipes.loc[recipe_mask, "name"] = name_val
        preview_recipes.loc[recipe_mask, "category"] = category_val
        preview_recipes.loc[recipe_mask, "yield_qty"] = yield_qty_val
        preview_recipes.loc[recipe_mask, "yield_uom"] = yield_uom_val
        preview_recipes.loc[recipe_mask, "menu_price"] = menu_price_val
        preview_recipes.loc[recipe_mask, "notes"] = notes_val

        other_lines = recipe_lines[recipe_lines["recipe_id"] != recipe_id]
        combined_lines = pd.concat([other_lines, edited_lines], ignore_index=True)

        preview_lines, preview_summary = compute_recipe_costs(
            preview_recipes, combined_lines, ingredients
        )

        selected_preview_lines = preview_lines[preview_lines["recipe_id"] == recipe_id].copy()
        selected_summary = preview_summary[preview_summary["recipe_id"] == recipe_id]

        if not selected_summary.empty:
            summary_row = selected_summary.iloc[0]
            metric_cols = st.columns(4)
            metric_cols[0].metric(
                "Recipe cost",
                f"${summary_row['recipe_cost']:.2f}",
            )
            metric_cols[1].metric(
                "Menu price",
                f"${summary_row['menu_price']:.2f}",
            )
            cost_per = summary_row.get("cost_per_serving")
            metric_cols[2].metric(
                "Cost / serving",
                f"${cost_per:.2f}" if pd.notna(cost_per) else "—",
            )
            margin_pct = summary_row.get("margin_pct")
            metric_cols[3].metric(
                "Margin %",
                f"{margin_pct*100:.1f}%" if pd.notna(margin_pct) else "—",
            )

        if not selected_preview_lines.empty:
            display_lines = selected_preview_lines[
                ["ingredient", "qty", "uom", "line_cost", "prep_note"]
            ].copy()
            display_lines = display_lines.rename(
                columns={
                    "ingredient": "Ingredient",
                    "qty": "Qty",
                    "uom": "UOM",
                    "line_cost": "Cost $",
                    "prep_note": "Prep notes",
                }
            )
            st.dataframe(
                display_lines.style.format({"Cost $": "$%.2f"}),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Add ingredients to cost the recipe.")

        save_clicked = st.button("💾 Save recipe", type="primary")

        if save_clicked:
            if not name_val.strip():
                toast_err("Recipe needs a name before saving.")
            else:
                persist_lines = selected_preview_lines.copy()
                persist_lines = persist_lines.sort_values("line_id")
                persist_lines["line_id"] = (
                    range(1, persist_lines.shape[0] + 1)
                    if persist_lines.shape[0] > 0
                    else []
                )
                columns_to_keep = [
                    "recipe_id",
                    "line_id",
                    "ingredient",
                    "qty",
                    "uom",
                    "prep_note",
                    "line_cost",
                    "vendor",
                    "item_number",
                    "cost_per_oz",
                    "cost_per_each",
                    "default_uom",
                ]
                for col in columns_to_keep:
                    if col not in persist_lines.columns:
                        persist_lines[col] = "" if col not in {"qty", "line_cost", "cost_per_oz", "cost_per_each"} else 0.0

                persist_lines["qty"] = pd.to_numeric(persist_lines["qty"], errors="coerce").fillna(0.0)
                persist_lines["line_cost"] = pd.to_numeric(
                    persist_lines["line_cost"], errors="coerce"
                ).fillna(0.0)

                updated_lines = pd.concat(
                    [
                        recipe_lines[recipe_lines["recipe_id"] != recipe_id],
                        persist_lines[columns_to_keep],
                    ],
                    ignore_index=True,
                )

                updated_recipes = recipes.copy()
                mask = updated_recipes["recipe_id"] == recipe_id
                updated_recipes.loc[mask, [
                    "name",
                    "category",
                    "yield_qty",
                    "yield_uom",
                    "menu_price",
                    "notes",
                ]] = [
                    name_val,
                    category_val,
                    yield_qty_val,
                    yield_uom_val,
                    menu_price_val,
                    notes_val,
                ]

                write_table("recipes", updated_recipes)
                write_table("recipe_lines", updated_lines)
                toast_ok("Recipe saved")
                st.cache_data.clear()
                st.rerun()

