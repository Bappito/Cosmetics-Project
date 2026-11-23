import pytest

pytestmark = pytest.mark.django_db
from django.contrib.auth.models import Group, User


@pytest.fixture
def web_db(tmp_path, settings):
    settings.BUSINESS_DB_PATH = tmp_path / "business.sqlite3"
    return settings.BUSINESS_DB_PATH


def make_user(username, role):
    user = User.objects.create_user(username=username, password="test-pass-123")
    user.groups.add(Group.objects.get(name=role))
    return user


def test_dashboard_requires_login(client, web_db):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login/" in response["Location"]


def test_login_page_is_available_in_both_languages(client, web_db):
    assert "כניסה למערכת" in client.get("/login/").content.decode("utf-8")
    assert "Sign in" in client.get("/login/?lang=en").content.decode("utf-8")


def test_login_with_correct_password_opens_dashboard(client, web_db):
    make_user("tester", "Viewer")
    response = client.post("/login/", {"username": "tester", "password": "test-pass-123"}, follow=True)
    assert response.status_code == 200
    assert "לוח בקרה" in response.content.decode("utf-8")


def test_wrong_password_is_refused(client, web_db):
    make_user("tester", "Viewer")
    response = client.post("/login/", {"username": "tester", "password": "nope"})
    assert response.status_code == 200
    assert "שם המשתמש או הסיסמה שגויים" in response.content.decode("utf-8")


def test_viewer_does_not_see_profit(client, web_db):
    client.force_login(make_user("viewer", "Viewer"))
    body = client.get("/?lang=en").content.decode("utf-8")
    assert "Dashboard" in body
    assert "Estimated profit per finished product" not in body


def test_admin_sees_profit(client, web_db):
    client.force_login(make_user("boss", "Admin"))
    body = client.get("/?lang=en").content.decode("utf-8")
    assert "Estimated profit per finished product" in body


def test_roles_have_the_expected_screen_permissions(web_db):
    viewer = make_user("v2", "Viewer")
    admin = make_user("a2", "Admin")
    assert viewer.has_perm("dashboard.view_dashboard")
    assert not viewer.has_perm("dashboard.view_profit")
    assert admin.has_perm("dashboard.view_profit")
    assert admin.has_perm("dashboard.manage_users")
