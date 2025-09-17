from __future__ import annotations
import sqlite3, pathlib
import pandas as pd
from typing import Any, Optional, Tuple
from .settings import DB_PATH
from .utils import iso_today

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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
        (iso_today(), actor, action, details),
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

def create_exception(ex_type: str, context: str):
    """Create an exception record."""
    with get_conn() as conn:
        add_exception(conn, ex_type, context)
