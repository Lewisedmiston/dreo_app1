from __future__ import annotations
import sqlite3, pathlib
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
