"""Access to the business SQLite database.

The services in ``cosmetics_erp`` take a plain sqlite3 connection, so the web app opens one
per request and closes it when the request ends.
"""
import sqlite3
import threading

from django.conf import settings

from cosmetics_erp.db.schema import init_db

_init_lock = threading.Lock()
_initialized_paths: set[str] = set()


def open_erp_connection() -> sqlite3.Connection:
    path = str(settings.ERP_DB_PATH)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")

    # Create the schema and demo data once per database file.
    with _init_lock:
        if path not in _initialized_paths:
            init_db(conn)
            _initialized_paths.add(path)
    return conn
