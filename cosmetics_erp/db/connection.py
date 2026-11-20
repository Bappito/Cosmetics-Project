import sqlite3


DB_NAME = "cosmetics_3sim_erp.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)
