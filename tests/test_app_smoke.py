from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGES = ["dash", "inv", "wh", "mrp", "batch", "sim_prod", "sim_pack", "sim_work", "ai"]


@pytest.fixture
def in_tmp_dir(tmp_path, monkeypatch):
    # The app creates its SQLite file in the working directory, so keep it out of the repo.
    monkeypatch.chdir(tmp_path)
    # Drop the shared connection so each test opens the database in its own folder.
    import streamlit as st
    st.cache_resource.clear()
    monkeypatch.delenv("COSMETICS_APP_PASSWORD", raising=False)
    return tmp_path


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_exceptions(in_tmp_dir, page):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.session_state["active_page"] = page
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_password_gate_blocks_until_correct_password(in_tmp_dir, monkeypatch):
    monkeypatch.setenv("COSMETICS_APP_PASSWORD", "secret-test")
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    assert any("סיסמה" in (el.label or "") for el in at.text_input)
    assert not at.metric  # the dashboard is hidden behind the login

    at.text_input[0].input("wrong")
    at.button[0].click().run()
    assert any("שגויה" in e.value for e in at.error)
    assert not at.metric


def test_mrp_creates_monthly_draft_orders(in_tmp_dir):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.session_state["active_page"] = "mrp"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.checkbox(key="mrp_confirm").check().run()
    at.button(key="mrp_create").click().run()
    assert not at.exception, [e.value for e in at.exception]
    import sqlite3
    conn = sqlite3.connect(in_tmp_dir / "cosmetics_3sim_erp.db")
    drafts = conn.execute("SELECT po_number, sku, eta_date FROM PurchaseOrders WHERE status = 'Draft'").fetchall()
    conn.close()
    assert drafts, "no draft orders were created"
    assert all(po.startswith("MRP-") for po, _, _ in drafts)
    # one draft per product per month, so no two drafts share a sku and month
    pairs = [(sku, eta[:7]) for _, sku, eta in drafts]
    assert len(pairs) == len(set(pairs))
