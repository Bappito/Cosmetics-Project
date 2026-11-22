import sqlite3

import pytest

from cosmetics_erp.db.schema import init_db


@pytest.fixture
def conn():
    """A fresh in-memory database with the schema and demo data, isolated per test."""
    connection = sqlite3.connect(":memory:")
    init_db(connection)
    yield connection
    connection.close()
