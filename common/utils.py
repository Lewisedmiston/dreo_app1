from __future__ import annotations
import re
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional
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
    """Set up the Streamlit page with title and mobile-first configuration."""
    st.set_page_config(
        page_title=f"Dreo Kitchen Ops - {title}",
        page_icon="🍳",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Mobile-first CSS
    st.markdown("""
    <style>
    /* Touch-friendly buttons */
    .stButton > button {
        height: 50px;
        font-size: 1rem;
        border-radius: 8px;
        font-weight: bold;
        min-width: 120px;
    }
    
    .stNumberInput > div > div > input {
        height: 50px;
        font-size: 1.1rem;
    }
    
    .stSelectbox > div > div > div {
        height: 50px;
        font-size: 1rem;
    }
    
    .stTextInput > div > div > input {
        height: 50px;
        font-size: 1rem;
    }
    
    /* Mobile optimizations */
    @media (max-width: 768px) {
        .stButton > button {
            height: 60px;
            font-size: 1.1rem;
        }
        
        .stNumberInput > div > div > input {
            height: 60px;
            font-size: 1.2rem;
        }
    }
    
    /* Hide Streamlit branding for cleaner mobile experience */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
    
    st.title(title)

def smart_cache_key(*args, **kwargs):
    """Generate a cache key from arguments for complex caching."""
    key_str = str(args) + str(sorted(kwargs.items()))
    return hashlib.md5(key_str.encode()).hexdigest()

def load_file_to_dataframe(uploaded_file, sheet_name=None) -> Optional[pd.DataFrame]:
    """Load an uploaded file (CSV or Excel) into a pandas DataFrame with multi-sheet support."""
    if uploaded_file is None:
        return None
    
    try:
        # Use file content hash for stable caching instead of UploadedFile object
        file_hash = hash(uploaded_file.getvalue())
        cache_key = f"{uploaded_file.name}_{file_hash}_{sheet_name or 'default'}"
        
        # Simple session state caching to avoid UploadedFile hashing issues
        if hasattr(st, 'session_state') and cache_key in st.session_state:
            return st.session_state[cache_key]
        
        with st.spinner("📂 Loading file..."):
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                if sheet_name:
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                else:
                    df = pd.read_excel(uploaded_file)
            else:
                st.error("Unsupported file format. Please upload a CSV or Excel file.")
                return None
            
            # Cache in session state
            if hasattr(st, 'session_state'):
                st.session_state[cache_key] = df
            
            return df
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

def get_excel_sheet_names(uploaded_file) -> Optional[list]:
    """Get sheet names from an Excel file with session caching."""
    if uploaded_file is None or not uploaded_file.name.endswith(('.xlsx', '.xls')):
        return None
    
    try:
        # Use file hash for caching
        file_hash = hash(uploaded_file.getvalue()) 
        cache_key = f"sheets_{uploaded_file.name}_{file_hash}"
        
        if hasattr(st, 'session_state') and cache_key in st.session_state:
            return st.session_state[cache_key]
        
        with st.spinner("🔍 Analyzing file..."):
            xl = pd.ExcelFile(uploaded_file)
            sheet_names = xl.sheet_names
            
            # Cache result
            if hasattr(st, 'session_state'):
                st.session_state[cache_key] = sheet_names
            
            return sheet_names
    except Exception as e:
        st.error(f"Error reading Excel sheets: {e}")
        return None

def detect_vendor_from_sheet_name(sheet_name: str) -> str:
    """Smart vendor detection based on sheet names from your real data."""
    sheet_lower = sheet_name.lower()
    if 'sysco' in sheet_lower:
        return 'Sysco'
    elif 'pfg' in sheet_lower:
        return 'PFG Performance Food Group'
    elif 'produce' in sheet_lower:
        return 'Produce Vendor'
    elif 'order' in sheet_lower:
        return 'Order Guide'
    return sheet_name.title()

def clear_data_caches():
    """Clear all data caches when data is modified."""
    # Use Streamlit's cache clearing mechanism
    st.cache_data.clear()
    # Also clear session state cache if it exists
    if hasattr(st, 'session_state'):
        for key in list(st.session_state.keys()):
            key_str = str(key).lower()
            if 'cache' in key_str or 'df' in key_str:
                del st.session_state[key]

def safe_parse_date(date_str, default=None):
    """
    Safely parse dates with fallback to default
    Handles various date formats and edge cases
    """
    import pandas as pd
    
    if pd.isna(date_str) or date_str == "" or date_str is None:
        return default
    
    try:
        # Convert to string if not already
        date_str = str(date_str).strip()
        
        # Try pandas to_datetime first (handles many formats)
        parsed = pd.to_datetime(date_str, errors='raise')
        return parsed.date() if hasattr(parsed, 'date') else parsed
        
    except Exception:
        # Try some common formats manually
        common_formats = [
            '%Y-%m-%d',
            '%m/%d/%Y', 
            '%m-%d-%Y',
            '%d/%m/%Y',
            '%Y%m%d',
            '%m/%d/%y',
            '%Y-%m-%d %H:%M:%S'
        ]
        
        for fmt in common_formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed
            except:
                continue
        
        # If all else fails, return default
        return default

# Toast notification helpers (duplicates from data_layer for compatibility)
def success_toast(message: str):
    """Show success message"""
    st.success(f"✅ {message}")
    if hasattr(st, 'toast'):
        st.toast(f"✅ {message}", icon="✅")

def error_toast(message: str):
    """Show error message"""  
    st.error(f"❌ {message}")
    if hasattr(st, 'toast'):
        st.toast(f"❌ {message}", icon="❌")

def info_toast(message: str):
    """Show info message"""
    st.info(f"ℹ️ {message}")
    if hasattr(st, 'toast'):
        st.toast(f"ℹ️ {message}", icon="ℹ️")
