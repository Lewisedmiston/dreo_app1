
import streamlit as st
import pandas as pd
from common.db import get_conn, init_db
from common.settings import FOOD_COST_TARGET_PCT

st.set_page_config(page_title="Summary", layout="wide")
st.title("📊 Summary")

init_db()
conn = get_conn()

menu = pd.read_sql_query("""
SELECT r.id, r.name, r.menu_price,
COALESCE(SUM(CASE WHEN rl.line_type='INGREDIENT' THEN
  (CASE
    WHEN i.last_cost_per_oz IS NOT NULL THEN rl.qty * 
      (CASE rl.uom
        WHEN 'oz' THEN 1.0
        WHEN 'lb' THEN 16.0
        WHEN 'g' THEN 0.03527396195
        WHEN 'kg' THEN 35.27396
        WHEN 'ml' THEN 0.033814
        WHEN 'L' THEN 33.814
        WHEN 'qt' THEN 32.0
        WHEN 'gal' THEN 128.0
        ELSE NULL
      END) * i.last_cost_per_oz
    WHEN i.last_cost_per_each IS NOT NULL AND LOWER(rl.uom) IN ('each','ea') THEN rl.qty * i.last_cost_per_each
    ELSE 0
  END)
END),0) AS plate_cost
FROM recipes r
LEFT JOIN recipe_lines rl ON rl.recipe_id = r.id
LEFT JOIN ingredients i ON i.id = rl.ref_id
GROUP BY r.id, r.name, r.menu_price
""", conn)

menu["food_cost_pct"] = (menu["plate_cost"] / menu["menu_price"]).where(menu["menu_price"]>0)
menu["status"] = menu["food_cost_pct"].apply(lambda x: "OK" if pd.notnull(x) and x*100 <= FOOD_COST_TARGET_PCT else ("HIGH" if pd.notnull(x) else "N/A"))
st.dataframe(menu[["name","menu_price","plate_cost","food_cost_pct","status"]], use_container_width=True)

st.caption("Badge anything > target.")
