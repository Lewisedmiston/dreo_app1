"""Mobile-first landing page for Dreo Kitchen Ops."""

from __future__ import annotations

import streamlit as st

from common.db import get_metrics

st.set_page_config(page_title="Dreo Kitchen Ops", layout="wide")

st.markdown(
    """
    <style>
      .metric-card {background:#ffffff;border-radius:16px;padding:1.25rem;box-shadow:0 6px 14px rgba(0,0,0,0.08);text-align:center;}
      .metric-card h4 {margin:0;font-size:0.95rem;color:#6c757d;text-transform:uppercase;letter-spacing:0.06em;}
      .metric-card span {display:block;font-size:2rem;font-weight:700;color:#0f9b8e;margin-top:0.35rem;}
      .home-actions .stButton > button {height:110px;font-size:1.1rem;border-radius:16px;font-weight:600;background:linear-gradient(135deg,#0f9b8e,#56cfe1);color:white;border:none;box-shadow:0 8px 16px rgba(15,155,142,0.25);} 
      .home-actions .stButton > button:hover {filter:brightness(1.05);}
      .home-actions small {display:block;font-size:0.85rem;color:#0d3b37;margin-top:0.35rem;}
      @media (max-width:768px){
        .metric-card span {font-size:1.5rem;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🍳 Dreo Kitchen Ops")
st.caption("Inventory → Ordering → Catalog ETL — all tuned for the line cook's phone.")

metrics = get_metrics()
metric_cols = st.columns(3)
metric_labels = [
    ("Active SKUs", metrics["active_skus"]),
    ("Last Inventory Count", metrics["last_count_date"]),
    ("Open Order Lines", metrics["open_order_lines"]),
]
for col, (label, value) in zip(metric_cols, metric_labels):
    with col:
        st.markdown(
            f"<div class='metric-card'><h4>{label}</h4><span>{value}</span></div>",
            unsafe_allow_html=True,
        )

st.markdown("### Quick actions")

tiles = [
    ("📦", "Count Inventory", "Tap to capture walk-through counts", "pages/inventory.py"),
    ("🧾", "Build Order", "Par-driven vendor carts", "pages/ordering.py"),
    ("📄", "Upload Catalogs", "Import price lists & dedupe", "pages/upload_catalogs.py"),
    ("🧴", "Ingredient Master", "UOM + cost intelligence", "pages/ingredient_master.py"),
    ("⬇️", "Export", "Download latest counts & orders", "pages/export.py"),
]

st.markdown("<div class='home-actions'>", unsafe_allow_html=True)
for i in range(0, len(tiles), 2):
    cols = st.columns(2)
    for col, tile in zip(cols, tiles[i : i + 2]):
        emoji, title, subtitle, target = tile
        with col:
            if st.button(f"{emoji} {title}", key=f"tile_{title}", use_container_width=True):
                st.switch_page(target)
            st.markdown(f"<small>{subtitle}</small>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.divider()
st.markdown(
    "<p style='color:#6c757d;'>Pro tip: add this page to your phone's home screen for 1-tap launch during counts.</p>",
    unsafe_allow_html=True,
)
