
import streamlit as st
import pandas as pd
from common.db import get_conn, init_db

st.set_page_config(page_title="Exceptions_QA", layout="wide")
st.title("🚨 Exceptions / QA")

init_db()
conn = get_conn()

df = pd.read_sql_query("SELECT * FROM exceptions ORDER BY created_at DESC", conn)
st.dataframe(df, use_container_width=True)

if len(df) > 0:
    ids = st.multiselect("Mark resolved", options=df["id"].tolist())
    if st.button("Resolve Selected"):
        if ids:
            conn.executemany("UPDATE exceptions SET resolved=1, resolved_at=DATE('now') WHERE id=?", [(int(i),) for i in ids])
            conn.commit()
            st.success(f"Resolved {len(ids)} exceptions.")
