from __future__ import annotations
import re
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

ISO = "%Y-%m-%d"

def iso_today() -> str:
    return datetime.now().strftime(ISO)

_money = re.compile(r"[^0-9.]+")
def to_float(x, default=0.0):
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return default
    s = _money.sub("", s)
    try:
        return float(s)
    except ValueError:
        return default

def page_setup(title: str):
    """Set up the Streamlit page with title and configuration."""
    st.set_page_config(
        page_title=f"Dreo Kitchen Ops - {title}",
        page_icon="🍳",
        layout="wide"
    )
    st.title(title)

def load_file_to_dataframe(uploaded_file) -> Optional[pd.DataFrame]:
    """Load an uploaded file (CSV or Excel) into a pandas DataFrame."""
    if uploaded_file is None:
        return None
    
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Unsupported file format. Please upload a CSV or Excel file.")
            return None
        return df
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None
