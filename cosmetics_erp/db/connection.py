from __future__ import annotations

import sqlite3

import streamlit as st


DB_NAME = "cosmetics_3sim_erp.db"


def open_database(path: str = DB_NAME) -> sqlite3.Connection:
    """Open the SQLite file with settings that tolerate a few concurrent users.

    WAL lets readers run while a write is in progress; busy_timeout makes a writer wait
    for a lock instead of failing immediately.
    """
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_connection() -> sqlite3.Connection:
    """One connection per browser session, reused across that session's reruns.

    Separate sessions no longer share a transaction. SQLite's busy timeout handles
    writes that happen at the same moment.
    """
    if "db_connection" not in st.session_state:
        st.session_state["db_connection"] = open_database(DB_NAME)
    return st.session_state["db_connection"]
