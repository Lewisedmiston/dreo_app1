"""
File-based data layer for Dreo Kitchen Ops App
Provides simple CSV persistence with caching for performance
"""
from __future__ import annotations
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime
from typing import Optional
import os

# Data directories
DATA_DIR = Path("data")
CATALOGS_DIR = DATA_DIR / "catalogs"
INVENTORY_DIR = DATA_DIR / "inventory_counts" 
ORDERS_DIR = DATA_DIR / "orders"

def ensure_data_dirs():
    """Ensure all data directories exist"""
    for dir_path in [DATA_DIR, CATALOGS_DIR, INVENTORY_DIR, ORDERS_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def read_table(name: str) -> pd.DataFrame:
    """Read a table from CSV with caching"""
    ensure_data_dirs()
    file_path = DATA_DIR / f"{name}.csv"
    
    if not file_path.exists():
        return pd.DataFrame()
    
    try:
        return pd.read_csv(file_path)
    except Exception as e:
        st.error(f"Error reading {name}: {e}")
        return pd.DataFrame()

def write_table(name: str, df: pd.DataFrame) -> bool:
    """Write a table to CSV and clear cache"""
    ensure_data_dirs()
    file_path = DATA_DIR / f"{name}.csv"
    
    try:
        df.to_csv(file_path, index=False)
        # Clear cache to ensure fresh data
        read_table.clear()
        return True
    except Exception as e:
        st.error(f"Error writing {name}: {e}")
        return False

def append_snapshot(name: str, df: pd.DataFrame, timestamp: Optional[str] = None) -> bool:
    """Append timestamped snapshot to appropriate directory"""
    ensure_data_dirs()
    
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Determine directory based on name
    if "inventory" in name.lower():
        dir_path = INVENTORY_DIR
    elif "order" in name.lower():
        dir_path = ORDERS_DIR
    elif "catalog" in name.lower():
        dir_path = CATALOGS_DIR
    else:
        dir_path = DATA_DIR
    
    file_path = dir_path / f"{name}_{timestamp}.csv"
    
    try:
        df.to_csv(file_path, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving snapshot {name}: {e}")
        return False

def get_latest_snapshot(name: str) -> Optional[pd.DataFrame]:
    """Get the most recent snapshot of a table"""
    ensure_data_dirs()
    
    # Determine directory
    if "inventory" in name.lower():
        dir_path = INVENTORY_DIR
    elif "order" in name.lower():
        dir_path = ORDERS_DIR  
    elif "catalog" in name.lower():
        dir_path = CATALOGS_DIR
    else:
        dir_path = DATA_DIR
    
    # Find latest file matching pattern
    pattern = f"{name}_*.csv"
    files = list(dir_path.glob(pattern))
    
    if not files:
        return None
    
    # Sort by timestamp in filename and get latest
    latest_file = max(files, key=lambda x: x.stem)
    
    try:
        return pd.read_csv(latest_file)
    except Exception as e:
        st.error(f"Error reading latest {name}: {e}")
        return None

def safe_parse_date(s, default=None):
    """Safely parse dates with fallback to default"""
    import pandas as pd
    try:
        return pd.to_datetime(s, errors='raise').date()
    except Exception:
        return default

def get_metrics() -> dict:
    """Get quick metrics for dashboard"""
    try:
        # Get ingredient master
        ingredients = read_table("ingredient_master")
        active_skus = len(ingredients) if not ingredients.empty else 0
        
        # Get latest inventory count
        latest_inventory = get_latest_snapshot("inventory_count")
        last_count_date = "Never"
        if latest_inventory is not None and not latest_inventory.empty:
            # Try to get timestamp from filename or data
            inventory_files = list(INVENTORY_DIR.glob("inventory_count_*.csv"))
            if inventory_files:
                latest_file = max(inventory_files, key=lambda x: x.stem)
                timestamp_str = latest_file.stem.split("_")[-2:]  # Get date and time parts
                if len(timestamp_str) == 2:
                    try:
                        timestamp = datetime.strptime(f"{timestamp_str[0]}_{timestamp_str[1]}", "%Y%m%d_%H%M%S")
                        last_count_date = timestamp.strftime("%m/%d/%Y %I:%M %p")
                    except:
                        last_count_date = "Recent"
        
        # Get pending orders
        order_files = list(ORDERS_DIR.glob("order_*.csv"))
        open_orders = len(order_files)
        
        return {
            "active_skus": active_skus,
            "last_count_date": last_count_date,
            "open_orders": open_orders
        }
    except Exception as e:
        st.error(f"Error getting metrics: {e}")
        return {
            "active_skus": 0,
            "last_count_date": "Never", 
            "open_orders": 0
        }

# Toast notification helpers
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