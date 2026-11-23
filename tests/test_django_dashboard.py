import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def web_db(tmp_path, settings):
    """Point the Django screens at an empty business database in a temp folder."""
    settings.BUSINESS_DB_PATH = tmp_path / "business.sqlite3"
    return settings.BUSINESS_DB_PATH


@pytest.fixture
def signed_in(client, web_db):
    from django.contrib.auth.models import Group, User

    user = User.objects.create_user(username="admin-test", password="test-pass-123")
    user.groups.add(Group.objects.get(name="Admin"))
    client.force_login(user)
    return client


def test_dashboard_renders_in_hebrew_by_default(signed_in, web_db):
    response = signed_in.get("/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'dir="rtl"' in body
    assert "לוח בקרה" in body
    assert "הזמנות רכש פתוחות" in body


def test_dashboard_switches_to_english(signed_in, web_db):
    response = signed_in.get("/?lang=en")
    body = response.content.decode("utf-8")
    assert 'dir="ltr"' in body
    assert "Dashboard" in body
    assert response.cookies["lang"].value == "en"


def test_language_is_remembered_by_cookie(signed_in, web_db):
    signed_in.get("/?lang=en")
    body = signed_in.get("/").content.decode("utf-8")
    assert 'dir="ltr"' in body


def test_dashboard_shows_demo_products_after_first_start(signed_in, web_db):
    body = signed_in.get("/?lang=en").content.decode("utf-8")
    # The demo finished products (5001, 5002) appear in the profit table.
    assert "5001" in body and "5002" in body
