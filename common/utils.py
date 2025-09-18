from __future__ import annotations
import re
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional
from functools import wraps
import hashlib

ISO = "%Y-%m-%d"

def iso_today() -> str:
    return datetime.now().strftime(ISO)

def iso_now() -> str:
    """Get current timestamp with date and time for better audit precision."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_cached_ingredients():
    """Get ingredients with smart caching to reduce database hits."""
    from .db import pd_read_sql
    return pd_read_sql("""
        SELECT 
            ingredient_id, 
            ingredient_name, 
            costing_method, 
            current_cost_per_oz, 
            current_cost_per_each
        FROM ingredients 
        ORDER BY ingredient_name
    """)

@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_cached_recipes():
    """Get recipes with smart caching to reduce database hits."""
    from .db import pd_read_sql
    return pd_read_sql("SELECT recipe_id, recipe_name, menu_price FROM recipes ORDER BY recipe_name")

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_vendors():
    """Get all vendors with caching."""
    from .db import pd_read_sql
    return pd_read_sql("SELECT vendor_id, vendor_name FROM vendors ORDER BY vendor_name")

def smart_cache_key(*args, **kwargs):
    """Generate a cache key from arguments for complex caching."""
    key_str = str(args) + str(sorted(kwargs.items()))
    return hashlib.md5(key_str.encode()).hexdigest()

@st.cache_data(show_spinner="📂 Loading file...")
def load_file_to_dataframe(uploaded_file) -> Optional[pd.DataFrame]:
    """Load an uploaded file (CSV or Excel) into a pandas DataFrame with caching."""
    if uploaded_file is None:
        return None
    
    try:
        # Cache based on file name and size for better performance
        file_key = f"{uploaded_file.name}_{uploaded_file.size}"
        
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

def clear_data_caches():
    """Clear all data caches when data is modified."""
    # Use Streamlit's cache clearing mechanism
    st.cache_data.clear()
    # Also clear session state cache if it exists
    if hasattr(st, 'session_state'):
        for key in list(st.session_state.keys()):
            if 'cache' in key.lower() or 'df' in key.lower():
                del st.session_state[key]
