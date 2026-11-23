import pytest


@pytest.fixture
def web_db(tmp_path, settings):
    """Point the Django screens at an empty business database in a temp folder."""
    settings.BUSINESS_DB_PATH = tmp_path / "business.sqlite3"
    return settings.BUSINESS_DB_PATH


def test_dashboard_renders_in_hebrew_by_default(client, web_db):
    response = client.get("/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'dir="rtl"' in body
    assert "לוח בקרה" in body
    assert "הזמנות רכש פתוחות" in body


def test_dashboard_switches_to_english(client, web_db):
    response = client.get("/?lang=en")
    body = response.content.decode("utf-8")
    assert 'dir="ltr"' in body
    assert "Dashboard" in body
    assert response.cookies["lang"].value == "en"


def test_language_is_remembered_by_cookie(client, web_db):
    client.get("/?lang=en")
    body = client.get("/").content.decode("utf-8")
    assert 'dir="ltr"' in body


def test_dashboard_shows_demo_products_after_first_start(client, web_db):
    body = client.get("/?lang=en").content.decode("utf-8")
    # The demo finished products (5001, 5002) appear in the profit table.
    assert "5001" in body and "5002" in body
