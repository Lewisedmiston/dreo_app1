from __future__ import annotations
import sqlite3, pathlib
import pandas as pd
from typing import Any, Optional, Tuple
from contextlib import contextmanager
from .settings import DB_PATH
from .utils import iso_today, iso_now

import streamlit as st

# Global connection pool to avoid opening new connections constantly
_connection_pool = None

def get_conn():
    """Get database connection with smart pooling for performance."""
    global _connection_pool
    
    # Use Streamlit session state for connection pooling
    if hasattr(st, 'session_state'):
        if 'db_connection' not in st.session_state or st.session_state.db_connection is None:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key enforcement
            conn.execute("PRAGMA journal_mode = WAL")  # Performance optimization
            conn.execute("PRAGMA synchronous = NORMAL")  # Balance safety vs speed
            conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
            st.session_state.db_connection = conn
        return st.session_state.db_connection
    else:
        # Fallback for non-Streamlit contexts
        if _connection_pool is None:
            _connection_pool = sqlite3.connect(DB_PATH, check_same_thread=False)
            _connection_pool.row_factory = sqlite3.Row
            _connection_pool.execute("PRAGMA foreign_keys = ON")
            _connection_pool.execute("PRAGMA journal_mode = WAL")
            _connection_pool.execute("PRAGMA synchronous = NORMAL") 
            _connection_pool.execute("PRAGMA cache_size = -64000")
        return _connection_pool

def init_db():
    sql_path = pathlib.Path(__file__).with_name("models.sql")
    with get_conn() as conn, open(sql_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

def upsert_vendor(conn, name: str) -> int:
    cur = conn.execute("INSERT OR IGNORE INTO vendors(name) VALUES(?)", (name,))
    conn.commit()
    row = conn.execute("SELECT id FROM vendors WHERE name=?", (name,)).fetchone()
    return int(row["id"])

def add_exception(conn, ex_type: str, context: str):
    conn.execute(
        "INSERT INTO exceptions(ex_type, context, created_at) VALUES (?,?,?)",
        (ex_type, context, iso_today()),
    )
    conn.commit()

def add_changelog(conn, action: str, details: str, actor: str = "system"):
    conn.execute(
        "INSERT INTO changelog(event_time, actor, action, details) VALUES (?,?,?,?)",
        (iso_now(), actor, action, details),
    )
    conn.commit()

def get_db_connection():
    """Get a database connection context manager."""
    return get_conn()

def execute_query(sql: str, params: Optional[Tuple] = None, fetch: Optional[str] = None) -> Any:
    """Execute a SQL query with optional parameters and fetch mode."""
    with get_conn() as conn:
        if params:
            cursor = conn.execute(sql, params)
        else:
            cursor = conn.execute(sql)
        
        if fetch == 'one':
            return cursor.fetchone()
        elif fetch == 'all':
            return cursor.fetchall()
        else:
            # For INSERT statements, return the lastrowid
            conn.commit()
            return cursor.lastrowid

def pd_read_sql(sql: str, params: Optional[Tuple] = None) -> pd.DataFrame:
    """Read SQL query into a pandas DataFrame."""
    with get_conn() as conn:
        if params:
            return pd.read_sql_query(sql, conn, params=params)
        else:
            return pd.read_sql_query(sql, conn)

def log_change(event_type: str, details: str, actor: str = "system"):
    """Log a change event to the changelog table."""
    with get_conn() as conn:
        add_changelog(conn, event_type, details, actor)

def ensure_db_initialized():
    """Ensure database is initialized with proper schema before any operations."""
    # Check if the main tables exist
    with get_conn() as conn:
        result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vendors'").fetchone()
        if not result:
            # Database needs to be initialized
            init_db()

def create_exception(ex_type: str, context: str):
    """Create an exception record."""
    with get_conn() as conn:
        add_exception(conn, ex_type, context)
