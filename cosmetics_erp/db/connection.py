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


@st.cache_resource
def _shared_connection() -> sqlite3.Connection:
    # One connection per server process, reused across Streamlit reruns.
    return open_database(DB_NAME)


def get_connection() -> sqlite3.Connection:
    return _shared_connection()
